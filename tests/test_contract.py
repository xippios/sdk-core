"""EnvVar: a variable a package needs, by name or pattern (ADR-0026, decision 8).

Each name here is a fictitious source's: an ``EnvVar`` names a variable and never reads
one, so no test sets or reads the environment.
"""

import dataclasses
import subprocess
import sys

import pytest

from xippios.core import EnvVar


def test_an_env_var_names_a_variable_with_whether_it_is_secret_and_required() -> None:
    key = EnvVar("FICTIVE_API_KEY", secret=True, required=True)
    assert (key.name_or_pattern, key.secret, key.required) == ("FICTIVE_API_KEY", True, True)
    listed = EnvVar("FICTIVE_ORGS", secret=False, required=False)
    assert (listed.secret, listed.required) == (False, False)


def test_a_pattern_names_one_variable_per_tenant() -> None:
    # Conventions §1's scheme: sdk-cashctrl's CASHCTRL_<NAME>_API_KEY, sdk-google-mail's
    # GOOGLE_<NAME>_REFRESH_TOKEN, a prefix apart from its slug, as
    # https://github.com/xippios/sdk-core/issues/279 has it.
    for pattern in ("FICTIVE_<NAME>_API_KEY", "GOOGLE_<NAME>_REFRESH_TOKEN", "<SOURCE>_API_KEY"):
        assert EnvVar(pattern, secret=True, required=True).name_or_pattern == pattern


def test_secret_and_required_are_named_at_every_entry() -> None:
    # Swapped positions would mark a key as no secret: both are keyword-only, neither defaults.
    with pytest.raises(TypeError):
        EnvVar("FICTIVE_API_KEY", True, True)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        EnvVar("FICTIVE_API_KEY", secret=True)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        EnvVar("FICTIVE_API_KEY", required=True)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "name",
    ["", "fictive_api_key", "FICTIVE-API-KEY", "1FICTIVE", "FICTIVE_<name>_KEY", "FICTIVE_<>_KEY"],
)
def test_a_name_that_is_no_variable_name_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="upper-case letters, digits and underscores"):
        EnvVar(name, secret=True, required=True)


def test_an_env_var_is_frozen() -> None:
    key = EnvVar("FICTIVE_API_KEY", secret=True, required=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        key.secret = False  # type: ignore[misc]
    assert key == EnvVar("FICTIVE_API_KEY", secret=True, required=True)
    assert len({key, EnvVar("FICTIVE_API_KEY", secret=True, required=True)}) == 1


def test_env_var_imports_without_the_mcp_extra() -> None:
    # A source's _client.py declares its variables, and it never imports the mcp extra.
    code = (
        "import sys; from xippios.core import EnvVar; "
        "print(sorted(m for m in sys.modules if m.startswith(('xippios.core.mcp', 'mcp'))))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    ).stdout
    assert out.strip() == "[]"
