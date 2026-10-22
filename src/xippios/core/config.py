"""Settings loading (conventions §7): keys come from the environment, overridable by argument.

No config files and no dotenv loading happen here. The environment is the contract:
direnv in development, secrets in CI.
"""

import os
from typing import Literal, overload

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from xippios.core.errors import ConfigError

__all__ = ["SourceSettings", "resolve_api_key"]


class SourceSettings(BaseSettings):
    """Base settings for one source package.

    Subclass it and bind ``api_key`` to the variable name the upstream documents::

        class NassSettings(SourceSettings):
            api_key: SecretStr | None = Field(default=None, validation_alias="NASS_API_KEY")

    Constructor arguments win over the environment, so ``NassSettings(api_key="...")``
    is the documented override.
    """

    model_config = SettingsConfigDict(
        frozen=True, extra="ignore", validate_by_name=True, validate_by_alias=True
    )

    api_key: SecretStr | None = None


@overload
def resolve_api_key(
    env_var: str,
    override: str | SecretStr | None = None,
    *,
    required: Literal[True] = True,
    source: str | None = None,
) -> SecretStr: ...


@overload
def resolve_api_key(
    env_var: str,
    override: str | SecretStr | None = None,
    *,
    required: bool,
    source: str | None = None,
) -> SecretStr | None: ...


def resolve_api_key(
    env_var: str,
    override: str | SecretStr | None = None,
    *,
    required: bool = True,
    source: str | None = None,
) -> SecretStr | None:
    """Return the API key from ``override`` or from the environment.

    Args:
        env_var: Variable name as the upstream documents it, e.g. ``"NASS_API_KEY"``.
        override: Key passed explicitly by the caller; wins over the environment.
        required: Raise ``ConfigError`` when no key is found. ``False`` returns ``None``.
        source: Source slug for the error message.

    Returns:
        The key wrapped as ``SecretStr`` so it never prints by accident.
    """
    if override is not None:
        return override if isinstance(override, SecretStr) else SecretStr(override)
    value = os.environ.get(env_var)
    if value:
        return SecretStr(value)
    if required:
        raise ConfigError(
            f"{env_var} is not set; export it or pass the key explicitly", source=source
        )
    return None
