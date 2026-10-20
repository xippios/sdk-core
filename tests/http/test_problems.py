import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from xippios.core.errors import (
    AuthError,
    ConfigError,
    NotFoundError,
    RateLimitError,
    TransportError,
    UpstreamError,
    ValidationError,
    XippiosError,
)
from xippios.core.http import (
    PROBLEM_MEDIA_TYPE,
    install_error_handlers,
    problem_response,
    status_for,
)


class SpecialNotFound(NotFoundError):
    pass


@pytest.mark.parametrize(
    ("exc", "status"),
    [
        (ConfigError("x"), 500),
        (AuthError("x", status=401), 502),
        (RateLimitError("x"), 429),
        (NotFoundError("x"), 404),
        (ValidationError("x", raw=None), 502),
        (UpstreamError("x", status=500, body=""), 502),
        (TransportError("x"), 504),
        (XippiosError("x"), 500),
        (SpecialNotFound("x"), 404),
    ],
)
def test_status_table(exc: XippiosError, status: int) -> None:
    assert status_for(exc) == status
    assert problem_response(exc).status_code == status


def test_problem_body_and_media_type() -> None:
    response = problem_response(NotFoundError("no series X", source="example"))
    assert response.media_type == PROBLEM_MEDIA_TYPE
    assert json.loads(bytes(response.body)) == {
        "type": "urn:xippios:error:NotFoundError",
        "title": "NotFoundError",
        "status": 404,
        "detail": "no series X",
        "source": "example",
    }


def test_rate_limit_and_upstream_extras() -> None:
    limited = problem_response(RateLimitError("slow", retry_after=12.6))
    assert limited.headers["retry-after"] == "12"
    assert json.loads(bytes(limited.body))["retry_after"] == 12.6
    upstream = problem_response(UpstreamError("bad", status=503, body="x"))
    assert json.loads(bytes(upstream.body))["upstream_status"] == 503
    auth = problem_response(AuthError("nope", status=403))
    assert json.loads(bytes(auth.body))["upstream_status"] == 403


def test_install_error_handlers_covers_plain_routes() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise TransportError("gateway gone", source="example")

    client = TestClient(app)
    response = client.get("/boom")
    assert response.status_code == 504
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    assert response.json()["title"] == "TransportError"
