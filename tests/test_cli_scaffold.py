from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from phantasos.generator.cli.render_cli import cli_overrides_dir
from phantasos.generator.cli.scaffold_context import build_cli_scaffold_context

SCAFFOLD = Path("src/phantasos/scaffold")


def _render(template: str, ctx: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(SCAFFOLD)),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),
        undefined=StrictUndefined,
    )
    return env.get_template(template).render(**ctx)


_BASE: dict[str, Any] = {
    "distribution": "x",
    "description": "d",
    "license": "Apache-2.0",
    "author": "a",
    "author_email": "a@b.c",
    "repo_url": "https://x",
    "package": "x",
    "dependencies": ["typer>=0.12"],
}


def test_pyproject_emits_scripts_when_provided() -> None:
    out = _render("pyproject.toml.jinja", {**_BASE, "scripts": {"x-cli": "x.main:app"}})
    assert "[project.scripts]" in out
    assert 'x-cli = "x.main:app"' in out


def test_pyproject_no_scripts_block_for_sdk() -> None:
    out = _render("pyproject.toml.jinja", _BASE)
    assert "[project.scripts]" not in out


def test_pyproject_pins_sdk_to_sibling_path_when_provided() -> None:
    out = _render(
        "pyproject.toml.jinja",
        {
            **_BASE,
            "dependencies": ["typer>=0.12", "prisma-browser-sdk"],
            "sdk_dist": "prisma-browser-sdk",
            "sdk_source_path": "../prisma-browser-sdk",
        },
    )
    assert "[tool.uv.sources]" in out
    expected = 'prisma-browser-sdk = { path = "../prisma-browser-sdk", editable = true }'
    assert expected in out


def test_pyproject_no_uv_sources_for_sdk() -> None:
    out = _render("pyproject.toml.jinja", _BASE)
    assert "[tool.uv.sources]" not in out


def test_sdk_pyproject_no_whitespace_regressions() -> None:
    # The SDK case toggles the scripts / uv.sources conditional blocks OFF; guard
    # that they leave no stray blank lines and are cleanly omitted (a whitespace
    # regression in the `{% if %}` blocks would strand a doubled newline here).
    out = _render("pyproject.toml.jinja", _BASE)
    assert "\n\n\n" not in out  # no doubled blank line
    assert "[project.scripts]" not in out  # scripts block cleanly omitted
    assert "[tool.uv.sources]" not in out  # uv.sources block cleanly omitted


def test_cli_pyproject_is_valid_toml() -> None:
    import tomllib

    out = _render(
        "pyproject.toml.jinja",
        {
            **_BASE,
            "dependencies": ["typer>=0.12", "prisma-browser-sdk"],
            "scripts": {"my-cli": "my_cli.main:app"},
            "sdk_dist": "prisma-browser-sdk",
            "sdk_source_path": "../prisma-browser-sdk",
        },
    )
    parsed = tomllib.loads(out)
    assert parsed["project"]["scripts"] == {"my-cli": "my_cli.main:app"}
    assert parsed["tool"]["uv"]["sources"]["prisma-browser-sdk"] == {
        "path": "../prisma-browser-sdk",
        "editable": True,
    }


def test_env_example_renders_vars_when_provided() -> None:
    out = _render(
        ".env.example.jinja",
        {
            "auth_env_vars": [
                {"name": "PRISMA_CLIENT_ID", "example": "<client-id>"},
                {"name": "SCOPE", "example": "tsg_id:123"},
            ]
        },
    )
    assert "PRISMA_CLIENT_ID=<client-id>" in out
    assert "SCOPE=tsg_id:123" in out


def test_env_example_empty_without_vars() -> None:
    # SDK context has no auth_env_vars -> renders only-whitespace
    # -> render_scaffold skips it
    out = _render(".env.example.jinja", {})
    assert out.strip() == ""


class _FakeLoaded:
    """Minimal stand-in for LoadedProduct (only what the builder reads)."""

    def __init__(self) -> None:
        self.context: dict[str, Any] = {
            "package": "prisma_browser",
            "library": "urllib3",
            "base_url": "https://api",
            "spec_version": "1.0.0",
            "spec_title": "Prisma Browser",
            "has_auth": True,
            "has_pagination": True,
            "has_errors": True,
            "has_facade": True,
            "config_class_name": "PrismaSaseConfiguration",
            "distribution": "prisma-browser-sdk",
            "description": "Python SDK",
            "author": "Oliver",
            "author_email": "o@x.com",
            "repo_url": "https://github.com/x/prisma-browser-sdk",
            "license": "Apache-2.0",
            "python_versions": ["3.11", "3.12"],
            "dependencies": ["httpx", "urllib3", "pydantic"],
        }
        self.auth = type("A", (), {"scope_env": "SCOPE", "base_url_env": "PRISMA_SASE_BASE_URL"})()
        self.output_dir = Path("/home/x/git/prisma-browser-sdk")


def test_build_context_overrides_for_cli() -> None:
    ctx = build_cli_scaffold_context(_FakeLoaded(), ir=None, cli_cfg=None)
    assert ctx["sdk_dist"] == "prisma-browser-sdk"
    assert ctx["sdk_source_path"] == "../prisma-browser-sdk"
    assert ctx["package"] == "prisma_browser_cli"
    assert ctx["distribution"] == "prisma-browser-cli"
    assert "prisma-browser-sdk" in ctx["dependencies"]
    assert "typer>=0.26.7" in ctx["dependencies"] and "rich>=13" in ctx["dependencies"]
    assert "prisma_browser" not in ctx["dependencies"]  # never the import name
    assert ctx["scripts"] == {"prisma-browser-cli": "prisma_browser_cli.main:app"}
    assert ctx["has_auth"] is False and ctx["has_facade"] is False
    assert "CLI" in ctx["description"]
    names = {v["name"] for v in ctx["auth_env_vars"]}
    assert "SCOPE" in names and "PRISMA_SASE_BASE_URL" in names


def test_build_context_respects_cli_project_block() -> None:
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.productconfig import ProjectConfig

    cli_cfg = CliConfig(
        project=ProjectConfig(
            distribution="custom-cli",
            author="A",
            author_email="a@x",
            repo_url="https://x",
            description="My CLI",
        )
    )
    ctx = build_cli_scaffold_context(_FakeLoaded(), ir=None, cli_cfg=cli_cfg)
    assert ctx["distribution"] == "custom-cli"
    assert ctx["description"] == "My CLI"
    assert ctx["scripts"] == {"custom-cli": "prisma_browser_cli.main:app"}


def test_cli_overrides_dir_has_readme_and_tests() -> None:
    d = cli_overrides_dir()
    assert (d / "README.md.jinja").is_file()
    assert "{{ distribution }}" in (d / "README.md.jinja").read_text()
    assert (d / "tests" / "conftest.py.jinja").is_file()
    assert (d / "tests" / "test_cli_smoke.py.jinja").is_file()
    assert (d / "tests" / "test_config.py.jinja").is_file()
