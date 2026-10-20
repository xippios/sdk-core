import pytest
from pydantic import Field, SecretStr

from xippios.core.config import SourceSettings, resolve_api_key
from xippios.core.errors import ConfigError

ENV = "EXAMPLE_TEST_API_KEY"
VALUE = "not-a-real-key"


class ExampleSettings(SourceSettings):
    api_key: SecretStr | None = Field(default=None, validation_alias=ENV)


def test_settings_read_the_documented_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV, VALUE)
    settings = ExampleSettings()
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == VALUE
    assert VALUE not in repr(settings)


def test_settings_constructor_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV, VALUE)
    settings = ExampleSettings(api_key=SecretStr("explicit"))
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == "explicit"


def test_settings_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV, raising=False)
    assert ExampleSettings().api_key is None


def test_resolve_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV, VALUE)
    key = resolve_api_key(ENV, "explicit")
    assert key is not None
    assert key.get_secret_value() == "explicit"
    assert resolve_api_key(ENV, SecretStr("s")) == SecretStr("s")


def test_resolve_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV, VALUE)
    key = resolve_api_key(ENV)
    assert key is not None
    assert key.get_secret_value() == VALUE


def test_resolve_missing_raises_with_variable_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV, raising=False)
    with pytest.raises(ConfigError, match=ENV):
        resolve_api_key(ENV, source="example")
    assert resolve_api_key(ENV, required=False) is None


def test_resolve_treats_empty_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV, "")
    with pytest.raises(ConfigError):
        resolve_api_key(ENV)
