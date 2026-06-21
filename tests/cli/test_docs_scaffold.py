from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from phantasos.generator.cli.cliconfig import CliConfig, CliDocsConfig
from phantasos.generator.cli.render_cli import cli_overrides_dir
from phantasos.generator.cli.scaffold_context import build_cli_scaffold_context

SCAFFOLD = Path("src/phantasos/scaffold")


def _render(template_dir: Path, template: str, ctx: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),
        undefined=StrictUndefined,
    )
    return env.get_template(template).render(**ctx)


class _FakeLoaded:
    """Minimal stand-in for LoadedProduct (only what the builder reads)."""

    def __init__(self) -> None:
        self.context: dict[str, Any] = {
            "package": "prisma_browser",
            "spec_title": "Prisma Browser",
            "has_pagination": True,
            "distribution": "prisma-browser-sdk",
            "description": "Python SDK",
            "author": "Oliver",
            "author_email": "o@x.com",
            "repo_url": "https://github.com/x/prisma-browser-sdk",
            "license": "Apache-2.0",
            "python_versions": ["3.11", "3.12"],
            "dependencies": ["httpx"],
        }
        self.auth = None
        self.output_dir = Path("/home/x/git/prisma-browser-sdk")


def _cli_docs_ctx() -> dict[str, Any]:
    return build_cli_scaffold_context(
        _FakeLoaded(),
        ir=None,
        cli_cfg=CliConfig(docs=CliDocsConfig(showcase_object="w")),
    )


def test_cli_docs_flag_set_when_docs_present() -> None:
    on = _cli_docs_ctx()
    assert on["cli_docs"] is True
    assert on["has_docs"] is False  # SDK docs templates stay off for the CLI
    off = build_cli_scaffold_context(_FakeLoaded(), ir=None, cli_cfg=CliConfig())
    assert off["cli_docs"] is False


def test_emitted_pyproject_docs_group_is_mkdocs_material_only() -> None:
    pyproject = _render(SCAFFOLD, "pyproject.toml.jinja", _cli_docs_ctx())
    assert '"mkdocs-material>=9.5",' in pyproject
    assert "mkdocstrings" not in pyproject  # SDK-only dep absent for the CLI


def test_emitted_noxfile_has_docs_session_for_cli() -> None:
    noxfile = _render(SCAFFOLD, "noxfile.py.jinja", _cli_docs_ctx())
    assert "def docs(" in noxfile


def test_emitted_readme_has_documentation_section_for_cli() -> None:
    readme = _render(cli_overrides_dir(), "README.md.jinja", _cli_docs_ctx())
    assert "## Documentation" in readme


def test_sdk_pyproject_docs_group_unaffected() -> None:
    # the SDK has_docs branch must still emit its full dependency set
    sdk_ctx: dict[str, Any] = {
        "distribution": "x",
        "description": "d",
        "license": "Apache-2.0",
        "author": "a",
        "author_email": "a@b.c",
        "repo_url": "https://x",
        "package": "x",
        "dependencies": ["x"],
        "has_docs": True,
    }
    pyproject = _render(SCAFFOLD, "pyproject.toml.jinja", sdk_ctx)
    assert "mkdocstrings[python]>=0.26" in pyproject
    assert "griffe-pydantic>=1.0.0" in pyproject
