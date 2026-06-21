"""Behavioral tests for the emitted CLI docs site (IR-driven markdown)."""

from collections.abc import Callable
from pathlib import Path

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
    assert "fakesdk create widget [OPTIONS]" in text  # usage line
    # the flag-table header is FLUSH (no leading spaces) so Markdown renders a table
    assert "\n| Flag | Type | Required | Description |\n" in text
    assert "`--name`" in text
    assert "fakesdk create widget --name" in text  # synthesized example
    # a page is emitted per object, not just the showcase
    assert (out / "docs" / "reference" / "gizmo.md").exists()


def test_guides_always_present_and_auth_gating(emit_cli: Callable[..., Path]) -> None:
    no_auth = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    g = no_auth / "docs" / "guides"
    assert (g / "output.md").exists()
    assert (g / "errors.md").exists()
    assert not (g / "authentication.md").exists()  # gated OFF without credentials

    with_auth = emit_cli(docs=CliDocsConfig(showcase_object="widget"), auth=True)
    assert (with_auth / "docs" / "guides" / "authentication.md").exists()


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
