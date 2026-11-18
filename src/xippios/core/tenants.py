"""Tenants declared in the environment, and one client per tenant (conventions §7).

Some upstreams serve each tenant from a host of its own or under a key of its own:
CashCtrl serves every organisation from its own subdomain, and a Gmail refresh token
reaches one mailbox. A source for such an upstream declares its tenants in the
environment, the contract of conventions §7, and every task takes the tenant's name::

    tenants = Tenants(
        "example",
        list_var="EXAMPLE_TENANTS",  # EXAMPLE_TENANTS=acme,acme_test
        fields=("SUBDOMAIN", "API_KEY"),  # EXAMPLE_ACME_SUBDOMAIN, EXAMPLE_ACME_API_KEY
        reserved=("demo",),  # declared by EXAMPLE_DEMO_SUBDOMAIN and _API_KEY alone
        validate={"SUBDOMAIN": check_subdomain},
    )


    def build(name: str) -> AsyncClient:
        subdomain = tenants.field(name, "SUBDOMAIN")
        config = ClientConfig(..., base_url=f"https://{subdomain}.example.org/api")
        return AsyncClient(config, auth=BasicKeyAuth(tenants.var(name, "API_KEY")))


    client = tenants.client_for("acme", build)
    list_tenants = list_task(tenants, name="list_tenants")  # the tool example_list_tenants

A source whose variables carry a prefix other than its slug names it apart,
``Tenants("google-mail", var_prefix="GOOGLE", ...)`` for ``GOOGLE_<NAME>_REFRESH_TOKEN``,
and its errors still name the source.

A server bound to one tenant takes a ``TenantLock``: ``bind_tasks`` gives the source's
tool set (``xippios.core.mcp.ToolSet``) the tasks with the tenant's argument bound, so no
tool takes it, and ``tenant_instructions`` ends the server's instructions with a sentence
naming the tenant::

    def build(lock: TenantLock | None = None) -> ToolSet:
        return ToolSet(
            "example",
            bind_tasks(tool_functions(tasks), lock),
            instructions=tenant_instructions(INSTRUCTIONS, lock, bound=BOUND_INSTRUCTIONS),
        )


    server = build_server(build())  # every declared tenant; build(TenantLock("org", "acme"))

``xippios.core.mcp.serve_tenants`` builds the bound server from ``--org acme`` and runs it.

Isolation is by configuration: a deployment reaches exactly the tenants its environment
declares. Nothing here spans tenants or returns a value; messages name tenants and
variables, never what a variable holds (ADR-0005). The module left core in 0.3.0 for
sdk-cashctrl alone and came back in 0.4.0 from its copy and sdk-google-mail's (ADR-0024,
amendment 2026-11-18, (b) and (d)).
"""

import asyncio
import functools
import hashlib
import inspect
import os
import re
import threading
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from xippios.core._loop import as_async, sync
from xippios.core.client import AsyncClient
from xippios.core.errors import ConfigError, InvalidRequestError
from xippios.core.models import Result, ResultMeta

__all__ = ["TenantLock", "Tenants", "bind_tasks", "list_task", "tenant_instructions"]

_NAME = re.compile(r"[a-z0-9_]+")
_LISTS_TENANTS = "__xippios_lists_tenants__"
"""Marks a ``list_task``: a lock that binds one tenant narrows its result to that tenant."""
_UPPER = re.compile(r"[A-Z0-9_]+")
"""A field, or the variable prefix: the upper-case parts of a variable's name."""


def _is_set(variable: str) -> bool:
    return bool(os.environ.get(variable, "").strip())


class Tenants:
    """The tenants a multi-tenant source declares in the environment, and their clients.

    One variable, ``list_var``, lists the tenant names, comma-separated, each matching
    ``^[a-z0-9_]+$`` (``EXAMPLE_TENANTS=acme,acme_test``). Every tenant has one variable
    per field, ``<PREFIX>_<NAME>_<FIELD>``, the prefix ``var_prefix`` and the name
    upper-cased with ``-`` made ``_`` (``EXAMPLE_ACME_SUBDOMAIN``). A reserved tenant, such
    as the demo tenant fixtures and live tests use, is never listed: it exists when every
    one of its field variables is set, and not otherwise. The environment is read on every
    call; only the clients are cached.

    Args:
        source: Source slug, e.g. ``"cashctrl"``; names the source in errors and in the
            tenant list's ``meta.source``.
        var_prefix: The prefix of every per-tenant variable, upper-case as it appears in
            the variable name, e.g. ``"GOOGLE"`` for sdk-google-mail's
            ``GOOGLE_WORK_REFRESH_TOKEN``, a prefix every Google source shares. ``None``,
            the default, derives it from ``source``, upper-cased with ``-`` made ``_``:
            ``"CASHCTRL"``.
        list_var: The variable listing the tenant names, e.g. ``"CASHCTRL_ORGS"``.
        fields: The per-tenant variables' suffixes, upper-case as they appear in the
            variable name, e.g. ``("SUBDOMAIN", "API_KEY")``.
        reserved: Tenant names declared by their own field variables alone and never
            listed, e.g. ``("demo",)``; they follow the listed names, in this order.
        validate: Per field, a check applied to the value ``field`` returns, e.g.
            ``{"SUBDOMAIN": check_subdomain}``. It returns the value to use, possibly
            normalised, and raises ``ValueError`` for a value it refuses; any exception
            it raises refuses the value the same way.
        hints: Per field, static text appended to the ``ConfigError`` when ``validate``
            refuses a value, e.g. ``{"SUBDOMAIN": "set the subdomain alone, e.g. acme
            for acme.example.org"}``, read as "...; <hint>". It tells the operator what
            the variable should hold; the check's own message, which may quote the
            value, is never used. A field with a hint has a ``validate`` check.

    Attributes:
        source: The source slug.
        var_prefix: The variable prefix, given or derived from ``source``.
        list_var: The variable listing the tenant names.
        fields: The field suffixes, as a tuple.
        reserved: The reserved tenant names, as a tuple.

    Raises:
        TypeError: ``fields`` or ``reserved`` is one string rather than a sequence.
        ValueError: An empty ``source`` or ``list_var``; a ``var_prefix`` that is not
            upper-case letters, digits and underscores; no field, a field that is not
            upper-case letters, digits and underscores, or a field given twice; a
            reserved name that is not a valid tenant name or is given twice; a
            ``validate`` or ``hints`` entry for a field not in ``fields``; a ``hints``
            entry for a field without a ``validate`` check, which could never be shown.
    """

    def __init__(
        self,
        source: str,
        *,
        var_prefix: str | None = None,
        list_var: str,
        fields: Sequence[str],
        reserved: Sequence[str] = (),
        validate: Mapping[str, Callable[[str], str]] | None = None,
        hints: Mapping[str, str] | None = None,
    ) -> None:
        if not source:
            raise ValueError("source must not be empty")
        if var_prefix is not None and not _UPPER.fullmatch(var_prefix):
            raise ValueError(
                f"var_prefix {var_prefix!r} is not upper-case letters, digits and underscores"
            )
        if not list_var:
            raise ValueError("list_var must not be empty")
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
        checks = dict(validate or {})
        unknown = sorted(set(checks) - set(fields))
        if unknown:
            raise ValueError(f"validate names fields not in fields: {', '.join(unknown)}")
        texts = dict(hints or {})
        unknown = sorted(set(texts) - set(fields))
        if unknown:
            raise ValueError(f"hints names fields not in fields: {', '.join(unknown)}")
        unchecked = sorted(set(texts) - set(checks))
        if unchecked:
            # Shown only when the check refuses a value: without a check it never would be.
            raise ValueError(f"hints names fields without a validate check: {', '.join(unchecked)}")
        self.source = source
        self.var_prefix = source.upper().replace("-", "_") if var_prefix is None else var_prefix
        self.list_var = list_var
        self.fields = fields
        self.reserved = reserved
        self._validate = checks
        self._hints = texts
        self._clients: dict[str, tuple[str, AsyncClient]] = {}
        self._closing: set[asyncio.Task[None]] = set()
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return (
            f"Tenants({self.source!r}, var_prefix={self.var_prefix!r}, "
            f"list_var={self.list_var!r}, fields={self.fields!r}, reserved={self.reserved!r})"
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

        Raises:
            InvalidRequestError: ``name`` is not declared, the caller's bad argument
                (ADR-0007); the message lists the declared tenants or, when there are
                none, the variables to set, and for an absent reserved tenant the
                variables that declare it; never a value.
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
        raise InvalidRequestError(f"unknown tenant {name!r}; {hint}", source=self.source)

    def field(self, name: str, field: str) -> str:
        """The value of tenant ``name``'s ``field`` variable, stripped and checked.

        Args:
            name: A declared tenant, e.g. ``"acme"``.
            field: One of ``fields``, e.g. ``"SUBDOMAIN"``.

        Returns:
            The value without surrounding whitespace, passed through ``validate[field]``
            when the source gave one.

        Raises:
            InvalidRequestError: ``name`` is not declared (see ``require``).
            ConfigError: The variable of a declared tenant is unset or blank, or the
                check refused its value: the operator's environment. The message names
                the variable, never the value; for a refused value it ends with the
                field's hint, when the source gave one.
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
        check = self._validate.get(field)
        if check is None:
            return os.environ[variable].strip()
        try:
            return check(os.environ[variable].strip())
        except Exception:  # any failure refuses the value; none passes it on
            pass
        # Raised outside the handler: the check's error may quote the value, so it is
        # neither the cause nor the context of this one.
        message = f"{variable} does not hold a valid {field} for tenant {name!r}"
        hint = self._hints.get(field)
        if hint:
            message += f"; {hint}"
        raise ConfigError(message, source=self.source)

    def client_for(self, name: str, build: Callable[[str], AsyncClient]) -> AsyncClient:
        """Tenant ``name``'s client: ``build(name)`` on first use, the same client after.

        The client is cached under the current values of the tenant's field variables
        (as a digest, never the values), so a changed value builds a new client on the
        next call, and the one it replaces is closed through its ``aclose()``, which
        closes the connection pool it holds on the event loop that awaits it (queue row
        24 b). Called inside a running event loop, as every endpoint wrapper calls it,
        the close is scheduled as a task on that loop and runs once the caller next
        yields; called outside any loop, it runs on core's background loop through
        ``sync``, the loop every sync facade uses, before this returns. A pool the
        replaced client holds on yet another loop is not reached and goes with the
        client. A request still in flight on the replaced client on the same loop is cut
        off by the close; only tests and notebooks that change the environment inside a
        running process meet it. Every tenant has a client of its own, and its own rate
        limiter and cache when ``build`` creates them, as it should. ``build`` runs under
        the registry's lock: it must not call ``client_for``. Thread-safe.

        Args:
            name: A declared tenant, e.g. ``"acme"``.
            build: Builds the tenant's client from its name, usually reading
                ``field(name, ...)`` for the host and passing an auth on
                ``var(name, ...)`` that reads the key on the first request.

        Raises:
            InvalidRequestError: ``name`` is not declared; ``build`` is not called.
            ConfigError: ``build`` raised it, e.g. from ``field`` for a missing or
                invalid value.
        """
        self.require(name)
        with self._lock:
            digest = self._digest(name)
            cached = self._clients.get(name)
            if cached is not None and cached[0] == digest:
                return cached[1]
            client = build(name)
            self._clients[name] = (digest, client)
        if cached is not None:
            self._close(cached[1])
        return client

    def _close(self, replaced: AsyncClient) -> None:
        """Close ``replaced`` on the running loop, or on core's background loop without one."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            sync(replaced.aclose)()
            return
        task = loop.create_task(replaced.aclose())
        self._closing.add(task)  # held until done: the loop keeps a weak reference only
        task.add_done_callback(self._closing.discard)

    def reset(self) -> None:
        """Drop every cached client, without closing it; the next ``client_for`` builds anew.

        A source's ``tests/conftest.py`` calls it around each test; a dropped client's
        pools go with it, unlike the client ``client_for`` replaces.
        """
        with self._lock:
            self._clients.clear()

    def _known_field(self, field: str) -> None:
        if field not in self.fields:
            raise ValueError(f"unknown field {field!r}; fields: {', '.join(self.fields)}")

    def _digest(self, name: str) -> str:
        """A digest of tenant ``name``'s field values, unset ones included; no value in a local."""
        digest = hashlib.sha256()
        for field in self.fields:
            # repr tells an unset variable (None) from an empty one and escapes NUL.
            digest.update(repr(os.environ.get(self.var(name, field))).encode("utf-8") + b"\x00")
        return digest.hexdigest()


_LIST_DOC = """List the tenants this server can reach, by name.

Every other tool takes one of these names to choose the tenant it works on. Only names
come back, never a credential, a host or another value. An empty list means that no
tenant is declared where the server runs.
"""


def list_task(
    tenants: Tenants, *, name: str, doc: str | None = None, source: str | None = None
) -> Callable[[], Result[list[str]]]:
    """A task returning the declared tenants' names, for a ``<source>_list_<tenants>`` tool.

    The task is synchronous and takes no argument; it reads ``tenants.names()`` on every
    call and returns names only (ADR-0005), with ``meta.endpoint`` set to ``name`` and no
    ``meta.tenant``. Register it with the source's other tasks, on the read server: a
    write server exposes write tools only (conventions §8). The task carries a mark by
    which ``bind_tasks`` lists the tenant a ``TenantLock`` binds alone.

    Args:
        tenants: The source's registry.
        name: The task's ``__name__``, e.g. ``"list_organisations"``; the MCP tool is
            named from it (``cashctrl_list_organisations``).
        doc: The docstring, which is the tool description; ``None`` gives a default
            written for agents that says "tenants".
        source: The source slug ``meta.source`` names, e.g. ``"google-mail"``, for a
            registry that several sources share; ``None`` names ``tenants.source``.

    Raises:
        ValueError: ``name`` is not a Python identifier.
    """
    if not name.isidentifier():
        raise ValueError(f"name {name!r} is not a Python identifier")
    slug = tenants.source if source is None else source

    def task() -> Result[list[str]]:
        return Result[list[str]](
            data=list(tenants.names()), meta=ResultMeta(source=slug, endpoint=name)
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
    ``OrgLock`` and sdk-google-mail's ``AccountLock`` until core 0.4.0 (ADR-0014, amendment
    2026-11-18, (d)). ``bind_tasks`` binds a server's tasks to it, ``tenant_instructions``
    names it in the server's instructions, and ``xippios.core.mcp.serve_tenants`` builds it
    from the command line.

    Attributes:
        param: The task parameter that names the tenant, e.g. ``"org"``.
        value: The tenant the server serves, e.g. ``"demo"``, which the serve command checks
            at startup; a lock on an undeclared name lists no tenant.
        noun: The word for one tenant in the sentence of the instructions, e.g.
            ``"organisation"``; ``None``, the default, uses ``param``, e.g. ``"account"``.

    Raises:
        ValueError: ``param`` is not a parameter name, ``value`` is empty, or ``noun`` is
            given but blank.
    """

    param: str
    value: str
    noun: str | None = None

    def __post_init__(self) -> None:
        if not self.param.isidentifier():
            raise ValueError("param must be a parameter name such as 'org'")
        if not self.value:
            raise ValueError("value must name the tenant the server serves")
        if self.noun is not None and not self.noun.strip():
            raise ValueError("noun must be a word such as 'organisation', or None for param")


def _sentence(lock: TenantLock) -> str:
    """The sentence a bound server's instructions end with."""
    noun = lock.param if lock.noun is None else lock.noun
    return (
        f"This server is bound to {lock.param} {lock.value}; every tool acts on that {noun} "
        f"and takes no {lock.param}."
    )


def tenant_instructions(
    text: str | None, lock: TenantLock | None, *, bound: str | None = None
) -> str | None:
    """A server's instructions: ``text`` unbound; bound, ``bound`` and the lock's sentence.

    The sentence names the tenant, "This server is bound to org acme; every tool acts on
    that organisation and takes no org.", the noun the lock's. A source whose ``text``
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
    if getattr(fn, _LISTS_TENANTS, False) is True:

        @functools.wraps(fn)
        def only_the_locked_tenant() -> Any:
            return _only_the_locked_tenant(lock, fn())

        return only_the_locked_tenant
    signature = inspect.signature(fn)
    if lock.param not in signature.parameters:
        return fn
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
    ``meta.tenant`` ``None``. Any other task is returned as it is. The HTTP router takes
    no lock: a deployment that needs one declares only that tenant.

    Args:
        tasks: A server's tasks, e.g. ``tool_functions(tasks)``.
        lock: The tenant the server is bound to, e.g. ``TenantLock("org", "acme")``, or
            ``None`` for a server of every declared tenant.

    Returns:
        A list of the tools to be, in the order of ``tasks``.
    """
    if lock is None:
        return list(tasks)
    return [_bind(fn, lock) for fn in tasks]
