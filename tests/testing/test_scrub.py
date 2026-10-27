import dataclasses

import pytest

from xippios.core import redaction
from xippios.core.testing import Scrub, scrub


def test_the_scrub_reads_the_one_rule() -> None:
    # The substring rule the recorder kept is gone (ADR-0019, decision 6).
    assert scrub.scrub_params is redaction.scrub_params
    assert scrub.scrub_url is redaction.scrub_url
    assert scrub.scrub_headers is redaction.scrub_headers


def test_scrub_defaults_keep_the_host_and_refuse_binary_bodies() -> None:
    scrub = Scrub()
    assert scrub.host is None
    assert scrub.secrets == ()
    assert scrub.rewrite is None
    assert scrub.allow_binary is False


def test_scrub_is_frozen_and_keeps_secrets_as_a_tuple() -> None:
    scrub = Scrub(host="demo.example.test", secrets=["tenant-1", "tenant-2"])
    assert scrub.secrets == ("tenant-1", "tenant-2")
    with pytest.raises(dataclasses.FrozenInstanceError):
        scrub.host = "other.example.test"  # type: ignore[misc]


def test_scrub_refuses_an_empty_secret() -> None:
    with pytest.raises(ValueError, match="empty string"):
        Scrub(secrets=["value", ""])


def test_scrub_refuses_one_string_as_secrets() -> None:
    one_string = "value"
    with pytest.raises(TypeError, match="not one string"):
        Scrub(secrets=one_string)


@pytest.mark.parametrize(
    "host", ["", "demo.example.test:8443", "https://demo.example.test", "demo/x", "a b", "-a"]
)
def test_scrub_refuses_a_host_that_is_not_a_plain_name(host: str) -> None:
    with pytest.raises(ValueError, match="plain host name"):
        Scrub(host=host)


@pytest.mark.parametrize("secret", ["acme", "ACME", "Acme-Demo"])
def test_scrub_refuses_a_host_that_contains_a_secret(secret: str) -> None:
    # The placeholder is written into every URL; a secret inside it would be too.
    with pytest.raises(ValueError, match=r"^host contains one of the secrets") as info:
        Scrub(host="acme-demo.example.test", secrets=["unrelated", secret])
    assert secret.lower() not in str(info.value).lower()
    assert "acme-demo.example.test" not in str(info.value)


def test_scrub_keeps_secrets_out_of_its_repr() -> None:
    scrub = Scrub(host="demo.example.test", secrets=["tenant-name"])
    assert "tenant-name" not in repr(scrub)
    assert "demo.example.test" in repr(scrub)
