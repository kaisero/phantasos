from pathlib import Path

import pytest
from pydantic import ValidationError

from phantasos.generator.cli.cliconfig import CliDocsConfig, load_cli_config


def test_cli_config_parses_docs_block(tmp_path: Path) -> None:
    p = tmp_path / "cli.yml"
    p.write_text(
        "docs:\n"
        "  showcase_object: widget\n"
        "  showcase_variant: simple\n"
        "  site_name: Acme CLI\n"
        "  examples:\n"
        '    "create:widget": acmecli create widget --name foo\n',
        encoding="utf-8",
    )
    cfg = load_cli_config(p)
    assert cfg.docs == CliDocsConfig(
        showcase_object="widget",
        showcase_variant="simple",
        site_name="Acme CLI",
        examples={"create:widget": "acmecli create widget --name foo"},
    )


def test_cli_docs_absent_is_none(tmp_path: Path) -> None:
    p = tmp_path / "cli.yml"
    p.write_text("hide: []\n", encoding="utf-8")
    assert load_cli_config(p).docs is None


def test_cli_docs_requires_showcase_object() -> None:
    with pytest.raises(ValidationError):
        CliDocsConfig()  # type: ignore[call-arg]


def test_cli_docs_forbids_unknown_key() -> None:
    with pytest.raises(ValidationError):
        CliDocsConfig(showcase_object="widget", bogus=1)  # type: ignore[call-arg]
