import dataclasses

import pytest

from xippios.core import redaction
from xippios.core.testing import Scrub, scrub


def test_the_scrub_reads_the_one_rule() -> None:
    # The substring rule the recorder kept is gone (ADR-0019, decision 6).
    assert scrub.scrub_params is redaction.scrub_params
    assert scrub.scrub_url is redaction.scrub_url
    assert scrub.scrub_headers is redaction.scrub_headers


def test_scrub_defaults_name_no_secret_and_refuse_binary_bodies() -> None:
    scrub = Scrub()
    assert scrub.secrets == ()
    assert scrub.allow_binary is False


def test_scrub_is_frozen_and_keeps_secrets_as_a_tuple() -> None:
    scrub = Scrub(secrets=["tenant-1", "tenant-2"])
    assert scrub.secrets == ("tenant-1", "tenant-2")
    with pytest.raises(dataclasses.FrozenInstanceError):
        scrub.allow_binary = True  # type: ignore[misc]


def test_scrub_refuses_an_empty_secret() -> None:
    with pytest.raises(ValueError, match="empty string"):
        Scrub(secrets=["value", ""])


def test_scrub_refuses_one_string_as_secrets() -> None:
    one_string = "value"
    with pytest.raises(TypeError, match="not one string"):
        Scrub(secrets=one_string)


def test_scrub_keeps_secrets_out_of_its_repr() -> None:
    scrub = Scrub(secrets=["tenant-name"])
    assert "tenant-name" not in repr(scrub)
    assert repr(scrub) == "Scrub(allow_binary=False)"
