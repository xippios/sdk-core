"""Authentication helpers that read the key from the environment on first use.

Every upstream sends its key differently: USDA NASS as a query parameter, UN Comtrade
in a header, CashCtrl as the HTTP basic user name. These ``httpx.Auth`` classes cover
those shapes and resolve the key lazily through ``resolve_api_key``, so a package
imports without credentials and fails with ``ConfigError`` on the first request
instead of at import time.
"""

import base64
import threading
from collections.abc import Generator

import httpx
from pydantic import SecretStr

from xippios.core.config import resolve_api_key

__all__ = ["BasicKeyAuth", "BearerAuth", "EnvKeyAuth", "HeaderKeyAuth", "QueryKeyAuth"]


class EnvKeyAuth(httpx.Auth):
    """Base class: resolve the key once, then let a subclass attach it to each request.

    Subclass and implement ``apply`` for a shape not covered below. ``apply`` reads the
    key through ``self.key()`` where it attaches it, and keeps it in no local variable,
    so no traceback frame holds the key as an argument or a local.

    Args:
        env_var: Variable that holds the key, named as the upstream documents it.
        key: Explicit key; wins over the environment (conventions §7).
        source: Source slug for the ``ConfigError`` message.
    """

    requires_request_body = False

    def __init__(
        self, env_var: str, *, key: str | SecretStr | None = None, source: str | None = None
    ) -> None:
        self.env_var = env_var
        self.source = source
        self._override = key
        self._key: str | None = None
        self._lock = threading.Lock()

    def key(self) -> str:
        """The key, resolved on first use and cached for the life of the object."""
        if self._key is None:
            with self._lock:
                if self._key is None:
                    secret = resolve_api_key(self.env_var, self._override, source=self.source)
                    self._key = secret.get_secret_value()
        return self._key

    def apply(self, request: httpx.Request) -> None:
        """Attach the key, read with ``self.key()``, to ``request``; implemented by subclasses."""
        raise NotImplementedError

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """The httpx hook: one request, the key attached."""
        self.apply(request)
        yield request


class QueryKeyAuth(EnvKeyAuth):
    """Send the key as a query parameter, e.g. ``?key=...`` for USDA NASS.

    Args:
        param: Query parameter name.
        env_var: Variable that holds the key.
        key: Explicit key; wins over the environment.
        source: Source slug for error messages.
    """

    def __init__(
        self,
        param: str,
        env_var: str,
        *,
        key: str | SecretStr | None = None,
        source: str | None = None,
    ) -> None:
        super().__init__(env_var, key=key, source=source)
        self.param = param

    def apply(self, request: httpx.Request) -> None:
        """Merge the key into the query string."""
        request.url = request.url.copy_merge_params({self.param: self.key()})


class HeaderKeyAuth(EnvKeyAuth):
    """Send the key in a header, e.g. ``Ocp-Apim-Subscription-Key`` for UN Comtrade.

    Args:
        header: Header name.
        env_var: Variable that holds the key.
        key: Explicit key; wins over the environment.
        source: Source slug for error messages.
    """

    def __init__(
        self,
        header: str,
        env_var: str,
        *,
        key: str | SecretStr | None = None,
        source: str | None = None,
    ) -> None:
        super().__init__(env_var, key=key, source=source)
        self.header = header

    def apply(self, request: httpx.Request) -> None:
        """Set the header."""
        request.headers[self.header] = self.key()


class BearerAuth(EnvKeyAuth):
    """Send the key as ``Authorization: Bearer <key>``."""

    def apply(self, request: httpx.Request) -> None:
        """Set the Authorization header."""
        request.headers["Authorization"] = f"Bearer {self.key()}"


class BasicKeyAuth(EnvKeyAuth):
    """Send the key as the HTTP basic user name, as CashCtrl expects.

    Args:
        env_var: Variable that holds the key.
        password: Basic-auth password; empty for key-as-user-name schemes.
        key: Explicit key; wins over the environment.
        source: Source slug for error messages.
    """

    def __init__(
        self,
        env_var: str,
        *,
        password: str = "",
        key: str | SecretStr | None = None,
        source: str | None = None,
    ) -> None:
        super().__init__(env_var, key=key, source=source)
        self.password = password

    def apply(self, request: httpx.Request) -> None:
        """Set the Authorization header."""
        request.headers["Authorization"] = "Basic " + base64.b64encode(
            f"{self.key()}:{self.password}".encode()
        ).decode("ascii")
