"""Tenants declared in the environment, and one client per tenant (conventions §7).

Some upstreams serve each tenant from a host of its own or under a key of its own:
CashCtrl serves every organisation from its own subdomain, and an API user belongs to one
organisation. A source for such an upstream declares its tenants in the environment,
the contract of conventions §7, and every task takes the tenant's name::

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

Isolation is by configuration: a deployment reaches exactly the tenants its environment
declares. Nothing here spans tenants or returns a value; messages name tenants and
variables, never what a variable holds (ADR-0005).
"""

import hashlib
import os
import re
import threading
from collections.abc import Callable, Mapping, Sequence

from xippios.core.client import AsyncClient
from xippios.core.errors import ConfigError, InvalidRequestError
from xippios.core.models import Result, ResultMeta

__all__ = ["Tenants", "list_task"]

_NAME = re.compile(r"[a-z0-9_]+")
_LISTS_TENANTS = "__xippios_lists_tenants__"
"""Marks a ``list_task``: the MCP adapter narrows its result to a locked server's tenant."""
_FIELD = re.compile(r"[A-Z0-9_]+")


def _is_set(variable: str) -> bool:
    return bool(os.environ.get(variable, "").strip())


class Tenants:
    """The tenants a multi-tenant source declares in the environment, and their clients.

    One variable, ``list_var``, lists the tenant names, comma-separated, each matching
    ``^[a-z0-9_]+$`` (``EXAMPLE_TENANTS=acme,acme_test``). Every tenant has one variable
    per field, ``<SOURCE>_<NAME>_<FIELD>`` with the source and the name upper-cased and
    ``-`` made ``_`` (``EXAMPLE_ACME_SUBDOMAIN``). A reserved tenant, such as the demo
    tenant fixtures and live tests use, is never listed: it exists when every one of its
    field variables is set, and not otherwise. The environment is read on every call;
    only the clients are cached.

    Args:
        source: Source slug, e.g. ``"cashctrl"``; prefixes every variable and names the
            source in errors.
        list_var: The variable listing the tenant names, e.g. ``"CASHCTRL_ORGS"``.
        fields: The per-tenant variables' suffixes, upper-case as they appear in the
            variable name, e.g. ``("SUBDOMAIN", "API_KEY")``.
        reserved: Tenant names declared by their own field variables alone and never
            listed, e.g. ``("demo",)``; they follow the listed names, in this order.
        validate: Per field, a check applied to the value ``field`` returns, e.g.
            ``{"SUBDOMAIN": check_subdomain}``. It returns the value to use, possibly
            normalised, and raises ``ValueError`` for a value it refuses.

    Attributes:
        source: The source slug.
        list_var: The variable listing the tenant names.
        fields: The field suffixes, as a tuple.
        reserved: The reserved tenant names, as a tuple.

    Raises:
        TypeError: ``fields`` or ``reserved`` is one string rather than a sequence.
        ValueError: An empty ``source`` or ``list_var``; no field, a field that is not
            upper-case letters, digits and underscores, or a field given twice; a
            reserved name that is not a valid tenant name or is given twice; a
            ``validate`` entry for a field not in ``fields``.
    """

    def __init__(
        self,
        source: str,
        *,
        list_var: str,
        fields: Sequence[str],
        reserved: Sequence[str] = (),
        validate: Mapping[str, Callable[[str], str]] | None = None,
    ) -> None:
        if not source:
            raise ValueError("source must not be empty")
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
            if not _FIELD.fullmatch(field):
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
        self.source = source
        self.list_var = list_var
        self.fields = fields
        self.reserved = reserved
        self._prefix = source.upper().replace("-", "_")
        self._validate = checks
        self._clients: dict[str, tuple[str, AsyncClient]] = {}
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return (
            f"Tenants({self.source!r}, list_var={self.list_var!r}, fields={self.fields!r}, "
            f"reserved={self.reserved!r})"
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
        return f"{self._prefix}_{name.upper().replace('-', '_')}_{field}"

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
                none, the variables to set, and never a value.
            ConfigError: ``list_var`` is malformed (see ``names``).
        """
        declared = self.names()
        if name in declared:
            return name
        if declared:
            hint = "declared tenants: " + ", ".join(declared)
        else:
            per_name = " and ".join(f"{self._prefix}_<NAME>_{field}" for field in self.fields)
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
                the variable, never the value.
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
        except ValueError:
            pass
        # Raised outside the handler: the check's error may quote the value, so it is
        # neither the cause nor the context of this one.
        raise ConfigError(
            f"{variable} does not hold a valid {field} for tenant {name!r}", source=self.source
        )

    def client_for(self, name: str, build: Callable[[str], AsyncClient]) -> AsyncClient:
        """Tenant ``name``'s client: ``build(name)`` on first use, the same client after.

        The client is cached under the current values of the tenant's field variables
        (as a digest, never the values), so a changed value builds a new client on the
        next call; the one it replaces is dropped, not closed. Every tenant has a client
        of its own, and its own rate limiter and cache when ``build`` creates them, as it
        should. ``build`` runs under the registry's lock: it must not call
        ``client_for``. Thread-safe.

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
            return client

    def reset(self) -> None:
        """Drop every cached client, without closing it; the next ``client_for`` builds anew."""
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
    tenants: Tenants, *, name: str, doc: str | None = None
) -> Callable[[], Result[list[str]]]:
    """A task returning the declared tenants' names, for a ``<source>_list_<tenants>`` tool.

    The task is synchronous and takes no argument; it reads ``tenants.names()`` on every
    call and returns names only (ADR-0005), with ``meta.endpoint`` set to ``name`` and no
    ``meta.tenant``. Register it with the source's other tasks. On an MCP server locked
    to one tenant (``xippios.core.mcp.TenantLock``) its tool lists that tenant only.

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
