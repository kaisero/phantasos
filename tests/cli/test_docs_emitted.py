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
    # Token-cache section: overview + configure + verify, with the REAL env prefix
    # rendered (FAKESDK for this fixture — not a `<PREFIX>` placeholder).
    assert "## Token cache" in auth_md
    assert "show cli cache" in auth_md and "config cache-clear" in auth_md
    assert "FAKESDK_CACHE_ENABLED" in auth_md
    assert "cache.enabled" in auth_md and "cache.dir" in auth_md


def test_errors_guide_documents_exit_codes(emit_cli: Callable[..., Path]) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    errors = (out / "docs" / "guides" / "errors.md").read_text()
    for code in ("| `0` |", "| `1` |", "| `2` |"):  # structural, not prose
        assert code in errors
    # fakesdk has no error component -> the IR-driven API-error subsection is absent
    assert "## API error messages" not in errors
    # the Logs section documents the `show cli log` viewer
    assert "show cli log" in errors


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


def test_reference_links_nested_model_type_to_schema_anchor(
    emit_cli: Callable[..., Path],
) -> None:
    import re

    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    # --profile is the WidgetProfile body flag; its command key is create:widget,
    # so the anchor slug is create-widget-profile-schema.
    anchor = "create-widget-profile-schema"
    # The Type cell is a markdown link to the anchor (code span inside the link text).
    assert f"[`WidgetProfile`](#{anchor})" in text
    # A matching anchor target sits immediately above the ??? note schema block.
    assert f'<a id="{anchor}"></a>' in text
    # mkdocs --strict does NOT validate intra-page fragments by default, so guard the
    # link<->anchor wiring directly: every WidgetProfile Type-cell link must point at an
    # <a id> that is actually emitted on the page (catches a future slug drift).
    link_slugs = set(re.findall(r"\[`WidgetProfile`\]\(#([a-z0-9-]+)\)", text))
    id_slugs = set(re.findall(r'<a id="([a-z0-9-]+-profile-schema)">', text))
    assert anchor in link_slugs and anchor in id_slugs
    assert link_slugs <= id_slugs, f"link slugs with no anchor: {link_slugs - id_slugs}"
    # The blank line between the <a id> and the ??? note is LOAD-BEARING: without it
    # python-markdown folds the admonition into the raw-HTML block. Assert it exactly.
    lines = text.splitlines()
    a = next(k for k, ln in enumerate(lines) if f'id="{anchor}"' in ln)
    assert lines[a + 1] == "", "missing load-bearing blank line after <a id>"
    assert lines[a + 2].startswith('??? note "`--profile` schema"')


def test_reference_nested_field_shows_model_description(
    emit_cli: Callable[..., Path],
) -> None:
    # WidgetProfile.contact has no field-level description; the Contact model's own
    # class docstring must surface in the nested --profile schema table (Task 2).
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    assert "How to reach the widget owner." in text


def test_reference_schema_anchors_unique_per_page(
    emit_cli: Callable[..., Path],
) -> None:
    import re

    # --profile (WidgetProfile) renders under several widget commands on one page; the
    # command-keyed slug must keep every <a id> distinct (no duplicate HTML ids), and
    # a non-create command must produce a DIFFERENT anchor (proves `key` threading).
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    ids = re.findall(r'<a id="([a-z0-9-]+)"></a>', text)
    assert len(ids) == len(set(ids)), f"duplicate anchor ids on page: {ids}"
    profile_ids = {i for i in ids if i.endswith("-profile-schema")}
    # WidgetProfile renders under >1 widget command, each with a distinct slug.
    assert "create-widget-profile-schema" in profile_ids
    assert len(profile_ids) >= 2, f"expected per-command anchors, got {profile_ids}"


def test_environments_guide_lists_vars_and_precedence(
    emit_cli: Callable[..., Path],
) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"), auth=True)
    env_md = (out / "docs" / "guides" / "environments.md").read_text()
    # precedence / order is documented (both chains)
    assert "FAKESDK_ENVIRONMENT" in env_md and "default_environment" in env_md
    assert "--environment" in env_md  # -e is the top of the selection chain
    # every credential env var the CLI reads is listed
    cfg = (out / "fakesdk_cli" / "_generated" / "config.py").read_text()
    env_map_vars = set(__import__("re").findall(r'"(FAKESDK_[A-Z0-9_]+)"', cfg))
    for var in env_map_vars:  # config vars (logging/cache/output/...)
        assert var in env_md, f"{var} missing from environments.md"
    assert "CLIENT_ID" in env_md  # credential var (from the IR)
    assert "FAKESDK_ENVIRONMENT" in env_map_vars or "FAKESDK_ENVIRONMENT" in env_md


def test_environments_guide_absent_without_env(emit_cli: Callable[..., Path]) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))  # no auth -> no env
    assert not (out / "docs" / "guides" / "environments.md").exists()


def test_environments_guide_in_nav(emit_cli: Callable[..., Path]) -> None:
    import yaml

    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"), auth=True)
    cfg = yaml.safe_load((out / "mkdocs.yml").read_text())
    guides = next(s["Guides"] for s in cfg["nav"] if "Guides" in s)
    assert any(
        "environments.md" in (next(iter(g.values())) if isinstance(g, dict) else g)
        for g in guides
    )
