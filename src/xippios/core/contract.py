"""The variables of the package contract, which a source declares without the ``mcp`` extra.

The package contract is how a host serves a source (ADR-0026, decision 8, and its
amendment of 2026-11-18, (c)): the variables the package needs, here, and the tool set
its ``build(**options)`` returns, ``xippios.core.mcp.ToolSet``. A source's ``_client.py``
declares its variables, so ``EnvVar`` imports without the ``mcp`` extra::

    from xippios.core import EnvVar

    ENV_VARS = (
        EnvVar("EXAMPLE_ORGS", secret=False, required=False),
        EnvVar("EXAMPLE_<NAME>_SUBDOMAIN", secret=False, required=True),
        EnvVar("EXAMPLE_<NAME>_API_KEY", secret=True, required=True),
    )

An ``EnvVar`` names a variable and never reads one.
"""

import re
from dataclasses import KW_ONLY, dataclass

__all__ = ["EnvVar"]

_NAME_OR_PATTERN = re.compile(r"(?:[A-Z_]|<[A-Z]+>)(?:[A-Z0-9_]|<[A-Z]+>)*")
"""A variable's name, upper-case, or a pattern with a placeholder such as ``<NAME>``."""


@dataclass(frozen=True, slots=True)
class EnvVar:
    """A variable a package needs: its name or pattern, whether it is secret and required.

    A pattern names one variable per tenant of a multi-tenant source by a placeholder in
    angle brackets, as conventions §1 writes them: ``CASHCTRL_<NAME>_API_KEY``,
    ``GOOGLE_<NAME>_REFRESH_TOKEN``. ``secret`` and ``required`` are keyword-only and
    take no default, so each entry says both.

    Attributes:
        name_or_pattern: The variable's name, e.g. ``"NASS_API_KEY"``, or a pattern, e.g.
            ``"CASHCTRL_<NAME>_API_KEY"``.
        secret: Whether the variable holds a credential, a key or a token say, e.g.
            ``True`` for an API key and ``False`` for a tenant list.
        required: Whether the package needs the variable to serve, e.g. ``False`` for a
            tenant list that the reserved tenant does without.

    Raises:
        ValueError: ``name_or_pattern`` is not upper-case letters, digits and underscores,
            a digit not first, with placeholders such as ``<NAME>``.
    """

    name_or_pattern: str
    _: KW_ONLY
    secret: bool
    required: bool

    def __post_init__(self) -> None:
        if not _NAME_OR_PATTERN.fullmatch(self.name_or_pattern):
            raise ValueError(
                f"{self.name_or_pattern!r} is no variable name: upper-case letters, digits "
                "and underscores, a digit not first, with placeholders such as <NAME>"
            )
