"""Tenants declared in the environment, and one client per tenant (conventions §7).

Some upstreams serve each tenant from a host of its own or under a key of its own:
CashCtrl serves every organisation from its own subdomain, and a Gmail refresh token
reaches one mailbox. A source for such an upstream declares its tenants in the
environment, the contract of conventions §7, and every task takes the tenant's name::

    tenants = Tenants(
        "example",
        list_var="EXAMPLE_TENANTS",  # EXAMPLE_TENANTS=acme,acme_test
        param="org",  # every task takes org, the tenant's name
        fields=("SUBDOMAIN", "API_KEY"),  # EXAMPLE_ACME_SUBDOMAIN, EXAMPLE_ACME_API_KEY
        reserved=("demo",),  # declared by EXAMPLE_DEMO_SUBDOMAIN and _API_KEY alone
        noun="organisation",  # the word for one tenant
    )


    def build(name: str) -> AsyncClient:
        subdomain = tenants.field(name, "SUBDOMAIN")
        config = ClientConfig(..., base_url=f"https://{subdomain}.example.org/api")
        return AsyncClient(config, auth=KeyAuth(tenants.var(name, "API_KEY"), location="basic"))


    client = tenants.client_for("acme", build)
    list_tenants = list_task(tenants, name="list_tenants")  # the tool example_list_tenants

A source whose variables carry a prefix other than its slug names it apart,
``Tenants("google-mail", var_prefix="GOOGLE", param="account", ...)`` for
``GOOGLE_<NAME>_REFRESH_TOKEN``, and its errors still name the source. ``field`` returns a
value stripped, and a source that knows the value's shape checks it itself, its
``ConfigError`` naming the variable and never the value.

A server bound to one tenant takes a ``TenantLock``: ``bind_tasks`` gives the source's
tool set (``xippios.core.mcp.ToolSet``) the tasks with the tenant's argument bound, so no
tool takes it, and ``tenant_instructions`` ends the server's instructions with a sentence
naming the tenant. ``ToolSet.from_tasks`` does both for a lock it is given::

    def build(lock: TenantLock | None = None) -> ToolSet:
        return ToolSet.from_tasks("example", tasks, version=__version__, lock=lock)


    server = build_server(build())  # every declared tenant; build(TenantLock(tenants, "acme"))


    def run() -> None:
        main(build, tenants=tenants)  # --org acme serves build(TenantLock(tenants, "acme"))

``xippios.core.mcp.main`` builds the bound server from ``--org acme`` and runs it.

One tenant per call (conventions §7; ADR-0036, decisions 11 and 13): no task, tool or
helper in core works across tenants, and the tenant list returns names only. A source's
own tasks follow the same line, each taking exactly one tenant, required, with nothing
shared between tenants. ``bind_tasks`` refuses a task that takes no tenant unless it is
the tenant list, so a bound server serves the tenant's tasks and the tenant list, and the
family check of ``xippios.core.testing`` holds every task of a source whose ``_client``,
``tasks`` or ``tasks_write`` module holds a ``Tenants`` to it, the tenant's parameter the
one the registry declares, ``param``, which the serve command's option and every
``TenantLock`` take too. A signature shows neither what a task reaches nor what it
shares, so a task that takes one tenant and opens another's client passes both
(https://github.com/xippios/sdk-core/issues/302).

Isolation is by configuration: a deployment reaches exactly the tenants its environment
declares. Nothing here returns a tenant's value: results and messages name tenants and
variables, never what a variable holds (ADR-0030). The module left core in 0.3.0 for
sdk-cashctrl alone and came back in 0.4.0 from its copy and sdk-google-mail's (ADR-0042,
decision 1).
"""

import functools
import inspect
import os
import re
import threading
import typing
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from xippios.core._loop import as_async
from xippios.core.client import AsyncClient
from xippios.core.errors import _UNSENT, ConfigError, InvalidRequestError
from xippios.core.models import Result, ResultMeta

__all__ = ["TenantLock", "Tenants", "bind_tasks", "list_task", "tenant_instructions"]

_NAME = re.compile(r"[a-z0-9_]+")
_LISTS_TENANTS = "__xippios_lists_tenants__"
"""Marks a ``list_task``: a lock that binds one tenant narrows its result to that tenant."""
_UPPER = re.compile(r"[A-Z0-9_]+")
"""A field, or the variable prefix: the upper-case parts of a variable's name."""
_declared = False
"""Set once a ``Tenants`` is built in this process, and never cleared (``_tenants_declared``)."""


def _tenants_declared() -> bool:
    """Whether this process built a ``Tenants``, so that it may have sent to a tenant's host.

    The testing plugin's count of a live run's requests names no host then, since a
    multi-tenant source's host can name its tenant (ADR-0030, decision 4) and nothing tells
    a tenant's host from another at the connection pool.
    """
    return _declared


def _is_set(variable: str) -> bool:
    return bool(os.environ.get(variable, "").strip())


def _lists_tenants(fn: Callable[..., Any]) -> bool:
    """Whether ``fn`` is a tenant list of ``list_task``, or a wrapper that keeps its mark."""
    return getattr(fn, _LISTS_TENANTS, False) is True


class Tenants:
    """The tenants a multi-tenant source declares in the environment, and their clients.

    One variable, ``list_var``, lists the tenant names, comma-separated, each matching
    ``^[a-z0-9_]+$`` (``EXAMPLE_TENANTS=acme,acme_test``). Every tenant has one variable
    per field, ``<PREFIX>_<NAME>_<FIELD>``, the prefix ``var_prefix`` and the name
    upper-cased with ``-`` made ``_`` (``EXAMPLE_ACME_SUBDOMAIN``). A reserved tenant, such
    as the demo tenant fixtures and live tests use, is never listed: it exists when every
    one of its field variables is set, and not otherwise. The environment is read on every
    call; only the clients are cached, one per tenant until ``reset()``.

    Args:
        source: Source slug, e.g. ``"cashctrl"``; names the source in errors and in the
            tenant list's ``meta.source``.
        var_prefix: The prefix of every per-tenant variable, upper-case as it appears in
            the variable name, e.g. ``"GOOGLE"`` for sdk-google-mail's
            ``GOOGLE_WORK_REFRESH_TOKEN``, a prefix every Google source shares; that
            source is its one consumer (ADR-0036, amendment 2026-11-24). ``None``, the
            default, derives it from ``source``, upper-cased with ``-`` made ``_``:
            ``"CASHCTRL"``.
        list_var: The variable listing the tenant names, e.g. ``"CASHCTRL_ORGS"``.
        param: The task parameter that names the tenant, e.g. ``"org"``: the one
            declaration of it, which the family check holds every task to, the serve
            command's ``--org`` names and every ``TenantLock`` on this registry binds
            (ADR-0036, decision 13).
        fields: The per-tenant variables' suffixes, upper-case as they appear in the
            variable name, e.g. ``("SUBDOMAIN", "API_KEY")``.
        reserved: Tenant names declared by their own field variables alone and never
            listed, e.g. ``("demo",)``; they follow the listed names, in this order.
        noun: The word for one tenant, e.g. ``"organisation"``, in the help of the serve
            command's option and the sentence of a bound server's instructions; ``None``,
            the default, uses ``param``, e.g. ``"account"``. The registry's, so the serve
            command and every lock read one word (ADR-0063, decision 7).

    Attributes:
        source: The source slug.
        var_prefix: The variable prefix, given or derived from ``source``.
        list_var: The variable listing the tenant names.
        param: The task parameter that names the tenant.
        fields: The field suffixes, as a tuple.
        reserved: The reserved tenant names, as a tuple.
        noun: The word for one tenant, or ``None``.

    Raises:
        TypeError: ``fields`` or ``reserved`` is one string rather than a sequence.
        ValueError: An empty ``source`` or ``list_var``; a ``var_prefix`` that is not
            upper-case letters, digits and underscores; a ``param`` that is not a
            parameter name; no field, a field that is not upper-case letters, digits and
            underscores, or a field given twice; a reserved name that is not a valid
            tenant name or is given twice; a ``noun`` that is given but blank.
    """

    def __init__(
        self,
        source: str,
        *,
        var_prefix: str | None = None,
        list_var: str,
        param: str,
        fields: Sequence[str],
        reserved: Sequence[str] = (),
        noun: str | None = None,
    ) -> None:
        if not source:
            raise ValueError("source must not be empty")
        if var_prefix is not None and not _UPPER.fullmatch(var_prefix):
            raise ValueError(
                f"var_prefix {var_prefix!r} is not upper-case letters, digits and underscores"
            )
        if not list_var:
            raise ValueError("list_var must not be empty")
        if not param.isidentifier():
            raise ValueError(f"param {param!r} is not a parameter name such as 'org'")
        for label, values in (("fields", fields), ("reserved", reserved)):
            if isinstance(values, str):
                raise TypeError(f"{label} is a sequence of names, e.g. [name], not one string")
        fields = tuple(fields)
        reserved = tuple(reserved)
        if not fields:
            raise ValueError("fields must name at least one per-tenant variable")
        for field in fields:
            if not _UPPER.fullmatch(field):
                raise ValueError(
                    f"field {field!r} is not upper-case letters, digits and underscores"
                )
        for label, values in (("field", fields), ("reserved name", reserved)):
            duplicates = sorted({value for value in values if values.count(value) > 1})
            if duplicates:
                raise ValueError(f"{label} given twice: {', '.join(duplicates)}")
        for name in reserved:
            if not _NAME.fullmatch(name):
                raise ValueError(
                    f"reserved name {name!r} is not lower-case letters, digits and underscores"
                )
        if noun is not None and not noun.strip():
            raise ValueError("noun must be a word such as 'organisation', or None for param")
        self.source = source
        self.var_prefix = source.upper().replace("-", "_") if var_prefix is None else var_prefix
        self.list_var = list_var
        self.param = param
        self.fields = fields
        self.reserved = reserved
        self.noun = noun
        self._clients: dict[str, AsyncClient] = {}
        self._lock = threading.Lock()
        global _declared
        _declared = True

    def __repr__(self) -> str:
        return (
            f"Tenants({self.source!r}, var_prefix={self.var_prefix!r}, "
            f"list_var={self.list_var!r}, param={self.param!r}, fields={self.fields!r}, "
            f"reserved={self.reserved!r}, noun={self.noun!r})"
        )

    def var(self, name: str, field: str) -> str:
        """The variable holding ``field`` for tenant ``name``, e.g. ``CASHCTRL_ACME_SUBDOMAIN``.

        A name only: nothing is read from the environment, and ``name`` need not be
        declared.

        Args:
            name: A tenant name, e.g. ``"acme"``.
            field: One of ``fields``, e.g. ``"SUBDOMAIN"``.

        Raises:
            ValueError: ``field`` is not one of ``fields``.
        """
        self._known_field(field)
        return f"{self.var_prefix}_{name.upper().replace('-', '_')}_{field}"

    def names(self) -> tuple[str, ...]:
        """The declared tenants: ``list_var`` in its order, then each reserved one present.

        A reserved name is present when every one of its field variables is set to
        something other than whitespace. Read from the environment on every call.

        Raises:
            ConfigError: ``list_var`` lists a reserved name, a name twice, or an entry that
                is not lower-case letters, digits and underscores; that entry is named by
                its position, never quoted, since it may be a value pasted by mistake.
        """
        listed = [part.strip() for part in os.environ.get(self.list_var, "").split(",")]
        names: list[str] = []
        for position, name in enumerate(listed, start=1):
            if not name:
                continue
            if name in self.reserved:
                variables = " and ".join(self.var(name, field) for field in self.fields)
                raise ConfigError(
                    f"{self.list_var} lists {name!r}, which is reserved: it is declared by "
                    f"{variables} alone",
                    source=self.source,
                )
            if not _NAME.fullmatch(name):
                # By position, never quoted: a pasted subdomain or key would be a value.
                raise ConfigError(
                    f"entry {position} of {self.list_var} is not a tenant name; names use "
                    "only lower-case letters, digits and underscores",
                    source=self.source,
                )
            if name in names:
                raise ConfigError(f"{self.list_var} lists {name!r} twice", source=self.source)
            names.append(name)
        for name in self.reserved:
            if all(_is_set(self.var(name, field)) for field in self.fields):
                names.append(name)
        return tuple(names)

    def require(self, name: str) -> str:
        """Return ``name`` when it is a declared tenant, a reserved one that is present included.

        A task resolves its tenant before any request of the call, through ``client_for``,
        which makes the refusal's ``Nothing was sent.`` true (conventions §5; ADR-0045,
        amendment 2026-11-24).

        Raises:
            InvalidRequestError: ``name`` is not declared, the caller's bad argument
                (ADR-0007); the message lists the declared tenants or, when there are
                none, the variables to set, and for an absent reserved tenant the
                variables that declare it, never a value, and says that nothing was sent:
                ``unknown tenant 'nope'; declared tenants: acme. Nothing was sent.``
            ConfigError: ``list_var`` is malformed (see ``names``).
        """
        declared = self.names()
        if name in declared:
            return name
        if declared:
            hint = "declared tenants: " + ", ".join(declared)
            if name in self.reserved:
                variables = " and ".join(self.var(name, field) for field in self.fields)
                hint += f"; {name!r} is declared by {variables} alone"
        else:
            per_name = " and ".join(f"{self.var_prefix}_<NAME>_{field}" for field in self.fields)
            hint = f"no tenant is declared; set {self.list_var} and, per name, {per_name}"
            for reserved in self.reserved:
                variables = " and ".join(self.var(reserved, field) for field in self.fields)
                hint += f"; {reserved!r} is declared by {variables} alone"
        raise InvalidRequestError(f"unknown tenant {name!r}; {hint}. {_UNSENT}", source=self.source)

    def field(self, name: str, field: str) -> str:
        """The value of tenant ``name``'s ``field`` variable, stripped.

        A source that knows the value's shape, a subdomain say, checks the value this
        returns itself and refuses it with a ``ConfigError`` that names the variable,
        ``var(name, field)``, and never the value.

        Args:
            name: A declared tenant, e.g. ``"acme"``.
            field: One of ``fields``, e.g. ``"SUBDOMAIN"``.

        Returns:
            The value without surrounding whitespace.

        Raises:
            InvalidRequestError: ``name`` is not declared (see ``require``).
            ConfigError: The variable of a declared tenant is unset or blank: the
                operator's environment. The message names the variable, never a value.
            ValueError: ``field`` is not one of ``fields``.
        """
        self._known_field(field)
        self.require(name)
        variable = self.var(name, field)
        if not _is_set(variable):
            raise ConfigError(
                f"{variable} is not set; export the {field} of tenant {name!r}",
                source=self.source,
            )
        return os.environ[variable].strip()

    def client_for(self, name: str, build: Callable[[str], AsyncClient]) -> AsyncClient:
        """Tenant ``name``'s client: ``build(name)`` on first use, the same client after.

        The registry keeps one client per tenant until ``reset()``, whatever the tenant's
        variables hold later: ``build`` reads them when it builds, and nothing compares
        them again, since no code of the family changes them after start. Every tenant
        has a client of its own, and its own rate limiter and cache when ``build`` creates
        them, as it should. ``build`` runs under the registry's lock: it must not call
        ``client_for``. Thread-safe.

        Args:
            name: A declared tenant, e.g. ``"acme"``.
            build: Builds the tenant's client from its name, usually reading
                ``field(name, ...)`` for the host and passing an auth on
                ``var(name, ...)`` that reads the key on the first request.

        Raises:
            InvalidRequestError: ``name`` is not declared; ``build`` is not called.
            ConfigError: ``build`` raised it, e.g. from ``field`` for a missing value or
                from the source's own check of it.
        """
        self.require(name)
        with self._lock:
            client = self._clients.get(name)
            if client is None:
                client = self._clients[name] = build(name)
            return client

    def reset(self) -> None:
        """Drop every cached client, without closing it; the next ``client_for`` builds anew.

        The one way to a new client: a source's ``tests/conftest.py`` calls it around each
        test, and a process that changes a tenant's variables calls it to take them up. A
        dropped client's pools go with it.
        """
        with self._lock:
            self._clients.clear()

    def _known_field(self, field: str) -> None:
        if field not in self.fields:
            raise ValueError(f"unknown field {field!r}; fields: {', '.join(self.fields)}")


_LIST_DOC = """List the tenants this server can reach, by name.

Every other tool takes one of these names to choose the tenant it works on. Only names
come back, never a credential, a host or another value. An empty list means that no
tenant is declared where the server runs.
"""


def list_task(
    tenants: Tenants, *, name: str, doc: str | None = None
) -> Callable[[], Result[list[str]]]:
    """A task returning the declared tenants' names, for a ``<source>_list_<tenants>`` tool.

    The task is synchronous and takes no argument; it reads ``tenants.names()`` on every
    call and returns names only (ADR-0030), with ``meta.source`` the registry's source,
    ``meta.endpoint`` set to ``name`` and no ``meta.tenant``. Register it with the source's
    other tasks, on the read server: a write server exposes write tools only (conventions
    §8). The task carries a mark by which ``bind_tasks`` lists the tenant a ``TenantLock``
    binds alone.

    Args:
        tenants: The source's registry.
        name: The task's ``__name__``, e.g. ``"list_organisations"``; the MCP tool is
            named from it (``cashctrl_list_organisations``).
        doc: The docstring, which is the tool description; ``None`` gives a default
            written for agents that says "tenants".

    Raises:
        ValueError: ``name`` is not a Python identifier.
    """
    if not name.isidentifier():
        raise ValueError(f"name {name!r} is not a Python identifier")

    def task() -> Result[list[str]]:
        return Result[list[str]](
            data=list(tenants.names()), meta=ResultMeta(source=tenants.source, endpoint=name)
        )

    task.__name__ = name
    task.__qualname__ = name
    task.__doc__ = _LIST_DOC if doc is None else doc
    setattr(task, _LISTS_TENANTS, True)
    return task


@dataclass(frozen=True, slots=True)
class TenantLock:
    """Bind a server to one tenant: every tool acts on it and none takes ``param``.

    The lock of a server that a source's ``--org`` or ``--account`` binds, sdk-cashctrl's
    ``OrgLock`` and sdk-google-mail's ``AccountLock`` until core 0.4.0 (ADR-0036,
    decision 7). ``bind_tasks`` binds a server's tasks to it, ``tenant_instructions``
    names it in the server's instructions, and ``xippios.core.mcp.main`` builds it from the
    command line. The parameter it binds is the one its registry declares,
    ``tenants.param``, so no lock binds another (ADR-0036, decision 13), and the word for
    one tenant is the registry's ``noun`` too.

    Attributes:
        tenants: The source's registry, e.g. ``TENANTS``.
        value: The tenant the server serves, e.g. ``"acme"``, which the serve command checks
            at startup; a lock on an undeclared name lists no tenant.

    Raises:
        TypeError: ``tenants`` is not a ``Tenants`` registry, a parameter's name say.
        ValueError: ``value`` is empty.
    """

    tenants: Tenants
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.tenants, Tenants):
            raise TypeError(
                "a lock takes the source's Tenants registry, whose param is the parameter it "
                "binds, e.g. TenantLock(TENANTS, 'acme')"
            )
        if not self.value:
            raise ValueError("value must name the tenant the server serves")

    @property
    def param(self) -> str:
        """The task parameter that names the tenant, the registry's, e.g. ``"org"``."""
        return self.tenants.param


def _sentence(lock: TenantLock) -> str:
    """The sentence a bound server's instructions end with."""
    noun = lock.param if lock.tenants.noun is None else lock.tenants.noun
    return (
        f"This server is bound to {lock.param} {lock.value}; every tool acts on that {noun} "
        f"and takes no {lock.param}."
    )


def tenant_instructions(
    text: str | None, lock: TenantLock | None, *, bound: str | None = None
) -> str | None:
    """A server's instructions: ``text`` unbound; bound, ``bound`` and the lock's sentence.

    The sentence names the tenant, "This server is bound to org acme; every tool acts on
    that organisation and takes no org.", the noun the registry's. A source whose ``text``
    tells an agent that every tool takes the tenant's argument passes ``bound``, its text
    without that clause, for the bound server, as sdk-google-mail does; without it the
    bound server's instructions are ``text`` and the sentence, as sdk-cashctrl's are.

    Args:
        text: The unbound server's instructions, e.g. ``"Every tool takes org."``.
        lock: The tenant the server is bound to, or ``None``.
        bound: The bound server's own text, which must not say that a tool takes the
            tenant's argument; ``None`` uses ``text``, and an empty one leaves the
            sentence alone.
    """
    if lock is None:
        return text
    return " ".join(filter(None, [text if bound is None else bound, _sentence(lock)]))


def _only_the_locked_tenant(lock: TenantLock, result: Any) -> Any:
    """A tenant list narrowed to the tenant ``lock`` binds; anything else unchanged."""
    if not isinstance(result, Result) or not isinstance(result.data, list):
        return result
    return result.model_copy(update={"data": [name for name in result.data if name == lock.value]})


def _without_arg(doc: str, param: str) -> str:
    """``doc`` without ``param``'s entry under ``Args:``, and without an ``Args:`` left empty.

    ``doc`` is cleaned as ``inspect.getdoc`` cleans it. The entry is its first line,
    ``    <param>: ...``, and every line after it indented deeper, its continuation.
    """
    entry = re.compile(rf"\s+{re.escape(param)}:")
    kept: list[str] = []
    in_args = False
    skipping: int | None = None
    for line in doc.splitlines():
        indent = len(line) - len(line.lstrip())
        if skipping is not None and line.strip() and indent > skipping:
            continue
        skipping = None
        if line.strip() == "Args:":
            in_args = True
        elif line.strip() and indent == 0:
            in_args = False
        if in_args and entry.match(line):
            skipping = indent
            continue
        kept.append(line)
    lines: list[str] = []
    for index, line in enumerate(kept):
        following = kept[index + 1] if index + 1 < len(kept) else ""
        if line == "Args:" and not following.startswith(" "):
            continue  # the parameter was its only entry
        lines.append(line)
    return "\n".join(lines).rstrip()


def _bind(fn: Callable[..., Any], lock: TenantLock) -> Callable[..., Any]:
    """``fn`` as the tool of a server bound to ``lock.value``; see ``bind_tasks``."""
    if _lists_tenants(fn):

        @functools.wraps(fn)
        def only_the_locked_tenant() -> Any:
            return _only_the_locked_tenant(lock, fn())

        return only_the_locked_tenant
    signature = inspect.signature(fn)  # it takes lock.param: bind_tasks refused any other
    # Annotated metadata kept: a bound tool's schema and check hold its constraints too.
    hints = typing.get_type_hints(fn, include_extras=True)
    parameters = [
        p.replace(annotation=hints.get(p.name, p.annotation))
        for p in signature.parameters.values()
        if p.name != lock.param
    ]
    returns = hints.get("return", signature.return_annotation)
    target = as_async(fn)  # the async twin of a sync facade, or fn in a worker thread
    bound_to = {lock.param: lock.value}

    async def bound(**kwargs: Any) -> Any:
        return await target(**bound_to, **kwargs)

    bound.__name__ = fn.__name__
    bound.__qualname__ = fn.__qualname__
    bound.__module__ = fn.__module__
    bound.__doc__ = _without_arg(inspect.getdoc(fn) or "", lock.param)
    bound.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=parameters, return_annotation=returns
    )
    bound.__annotations__ = {p.name: p.annotation for p in parameters} | {"return": returns}
    return bound


def bind_tasks(
    tasks: Iterable[Callable[..., Any]], lock: TenantLock | None
) -> list[Callable[..., Any]]:
    """``tasks`` as the tools of a server bound to ``lock``, or as they are without one.

    A task that takes ``lock.param`` becomes an async function of its other parameters
    that awaits the task with ``param=value``, its async twin for a ``sync`` facade and a
    worker thread for a plain function, as the MCP adapter awaits a task. It keeps the
    task's ``__name__`` and ``__module__``, so tool names, ``MCP_CAPS`` keys and
    ``BULK_TASKS`` stay as they are; its docstring loses the parameter's entry under
    ``Args:``, and its signature and annotations lose the parameter, so no tool's input
    schema declares it and the argument check refuses a call that names it (conventions
    §8). The other parameters keep their ``Annotated`` metadata, so a constraint, a
    description or a validator holds in the bound tool's schema and check, and in a
    route's. The tenant list of ``list_task`` lists the bound tenant alone, still with
    ``meta.tenant`` ``None``. Any other task that takes no ``lock.param`` is refused, since
    the bound server would serve it unbound: a bound server serves the tenant's tasks and
    the tenant list (conventions §7; ADR-0036, decision 13). The HTTP router takes no lock:
    a deployment that needs one declares only that tenant.

    Args:
        tasks: A server's tasks, e.g. ``tool_functions(tasks)``.
        lock: The tenant the server is bound to, e.g. ``TenantLock(TENANTS, "acme")``, or
            ``None`` for a server of every declared tenant, whose tasks come back as they
            are.

    Returns:
        A list of the tools to be, in the order of ``tasks``.

    Raises:
        ValueError: A task takes no ``lock.param`` and is not the tenant list; the
            message names every such task and the parameter, and nothing is bound.
    """
    if lock is None:
        return list(tasks)
    given = list(tasks)
    unbound = [
        getattr(fn, "__name__", repr(fn))
        for fn in given
        if not _lists_tenants(fn) and lock.param not in inspect.signature(fn).parameters
    ]
    if unbound:
        verb = "takes" if len(unbound) == 1 else "take"
        raise ValueError(
            f"{', '.join(unbound)} {verb} no {lock.param}, the tenant's parameter that the lock "
            f"binds; a bound server serves the tenant list and the tasks that take "
            f"{lock.param}, and no other (conventions §7)"
        )
    return [_bind(fn, lock) for fn in given]
