"""Behavioral tests for the emitted CLI docs site (IR-driven markdown)."""

from collections.abc import Callable
from pathlib import Path

import yaml

from phantasos.generator.cli.cliconfig import CliDocsConfig


def test_no_docs_when_config_absent(emit_cli: Callable[..., Path]) -> None:
    out = emit_cli(docs=None)
    assert not (out / "docs").exists()
    assert not (out / "mkdocs.yml").exists()


def test_home_and_quickstart_emitted(emit_cli: Callable[..., Path]) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    index = (out / "docs" / "index.md").read_text()
    assert "Fakesdk CLI" in index
    assert "| `create` |" in index and "| `show` |" in index  # verbs table
    quickstart = (out / "docs" / "quickstart.md").read_text()
    assert "fakesdk create widget" in quickstart  # showcase create example


def test_reference_page_per_object(emit_cli: Callable[..., Path]) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    assert "## `create widget`" in text  # lean heading (no dist prefix, no [OPTIONS])
    assert "[OPTIONS]" not in text  # the verbose usage suffix is gone
    assert ":param" not in text  # no raw Sphinx docstring block leaks in
    # the flag-table header is FLUSH (no leading spaces) so Markdown renders a table
    assert "\n| Flag | Type | Required | Description |\n" in text
    assert "`--name`" in text
    assert "fakesdk create widget --name" in text  # synthesized example
    # a page is emitted per object, not just the showcase
    assert (out / "docs" / "reference" / "gizmo.md").exists()
    # the universal Common options are documented once per object page (D9)
    assert "## Common options" in text
    assert "`--output`" in text
    assert "`--environment`" not in text  # no auth in this build


def test_guides_always_present_and_auth_gating(emit_cli: Callable[..., Path]) -> None:
    no_auth = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    g = no_auth / "docs" / "guides"
    assert (g / "output.md").exists()
    assert (g / "errors.md").exists()
    assert not (g / "authentication.md").exists()  # gated OFF without credentials
    # --columns documents the CLI's real HEADER=expr syntax, not a JSON object
    output_md = (g / "output.md").read_text()
    assert "--columns 'ID=id,Name=name'" in output_md
    assert '{"ID"' not in output_md

    with_auth = emit_cli(docs=CliDocsConfig(showcase_object="widget"), auth=True)
    auth_md = (with_auth / "docs" / "guides" / "authentication.md").read_text()
    # `environment` is a root command group with a `show` lister — NOT `config
    # environment ... list` (which would be a "No such command" error).
    assert "environment create" in auth_md
    assert "environment show" in auth_md
    assert "config environment" not in auth_md
    assert "config init" in auth_md  # config init is documented


def test_errors_guide_documents_exit_codes(emit_cli: Callable[..., Path]) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    errors = (out / "docs" / "guides" / "errors.md").read_text()
    for code in ("| `0` |", "| `1` |", "| `2` |"):  # structural, not prose
        assert code in errors
    # fakesdk has no error component -> the IR-driven API-error subsection is absent
    assert "## API error messages" not in errors


def test_quickstart_honors_showcase_variant(emit_cli: Callable[..., Path]) -> None:
    # D6: a oneOf-create showcase picks the configured variant for the Quickstart.
    out = emit_cli(
        docs=CliDocsConfig(showcase_object="gizmo", showcase_variant="complex")
    )
    quickstart = (out / "docs" / "quickstart.md").read_text()
    assert "fakesdk create gizmo complex" in quickstart
    assert "fakesdk create gizmo simple" not in quickstart


def test_mkdocs_yml_nav(emit_cli: Callable[..., Path]) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    cfg = yaml.safe_load((out / "mkdocs.yml").read_text())
    assert cfg["site_name"] == "Fakesdk CLI"
    assert cfg["theme"]["name"] == "material"
    # plain static markdown site — none of the SDK-docs plugins (D2/D13)
    plugin_names = [p if isinstance(p, str) else next(iter(p)) for p in cfg["plugins"]]
    for forbidden in ("mkdocstrings", "gen-files", "literate-nav", "griffe"):
        assert forbidden not in plugin_names
    # explicit IR-generated nav has a Command Reference entry per object
    ref = next(s["Command Reference"] for s in cfg["nav"] if "Command Reference" in s)
    assert {"widget": "reference/widget.md"} in ref


def test_mkdocs_yml_nav_with_auth(emit_cli: Callable[..., Path]) -> None:
    # the has_auth=True nav branch must also be valid YAML and list the auth guide
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"), auth=True)
    cfg = yaml.safe_load((out / "mkdocs.yml").read_text())
    guides = next(s["Guides"] for s in cfg["nav"] if "Guides" in s)
    assert {"Authentication & environments": "guides/authentication.md"} in guides


def test_reference_page_renders_nested_schema_disclosure(
    emit_cli: Callable[..., Path],
) -> None:
    # emit_cli + CliDocsConfig are the existing conftest fixture + import (already in
    # tests/cli/test_docs_emitted.py); _emit:58 must thread models= (Task 6).
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    assert '??? note "`--profile` schema"' in text  # collapsed details block
    assert "Full body" in text  # copy & fill skeleton block
    # The nested table MUST be indented (4 spaces) so it stays INSIDE the ??? block.
    # Catches the indent(first=True) bug structurally — runs even when mkdocs is absent.
    lines = text.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("??? note"))
    # first non-blank line after the header
    body = next(ln for ln in lines[i + 1 :] if ln.strip())
    assert body.startswith("    "), f"schema body escaped the ??? block: {body!r}"


def test_mkdocs_enables_details_and_tabbed(emit_cli: Callable[..., Path]) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    cfg = yaml.safe_load((out / "mkdocs.yml").read_text())
    exts = cfg["markdown_extensions"]
    flat = [e if isinstance(e, str) else next(iter(e)) for e in exts]
    assert "pymdownx.details" in flat
    assert "attr_list" in flat
    assert any("tabbed" in (e if isinstance(e, str) else next(iter(e))) for e in exts)


def test_emitted_docs_build_strict(emit_cli: Callable[..., Path]) -> None:
    import shutil
    import subprocess

    mkdocs = shutil.which("mkdocs")
    if mkdocs is None:
        import pytest

        pytest.skip("mkdocs not installed; strict build is enforced in Task 11")
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    res = subprocess.run(  # noqa: S603 — trusted `mkdocs` binary (shutil.which)
        [mkdocs, "build", "--strict"],
        cwd=str(out),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
