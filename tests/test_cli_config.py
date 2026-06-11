from phantasos.generator.cli.cliconfig import CliConfig, load_cli_config


def test_empty_config_when_file_missing(tmp_path):
    cfg = load_cli_config(tmp_path / "nope.yml")
    assert cfg == CliConfig()
    assert cfg.hide == []
    assert cfg.request == {}
    assert cfg.variants == {}


def test_loads_all_sections(tmp_path):
    p = tmp_path / "cli.yml"
    p.write_text(
        "request:\n"
        "  devices.force_reauth_devices: {object: devices, action: force-reauth}\n"
        "override:\n"
        "  applications.create_application: {object: application}\n"
        "hide:\n"
        "  - applications.list_application_categories\n"
        "variants:\n"
        "  applications.create_application:\n"
        "    path_param: type\n"
        "    map: {custom: CustomApplicationInput, private: PrivateApplicationInput}\n"
        "custom:\n"
        "  commands: [pkg.custom.doctor]\n"
    )
    cfg = load_cli_config(p)
    assert cfg.request["devices.force_reauth_devices"].action == "force-reauth"
    assert cfg.override["applications.create_application"].object == "application"
    assert "applications.list_application_categories" in cfg.hide
    v = cfg.variants["applications.create_application"]
    assert v.path_param == "type"
    assert v.map["custom"] == "CustomApplicationInput"
    assert cfg.custom.commands == ["pkg.custom.doctor"]


def test_cli_config_optional_project_block(tmp_path):
    p = tmp_path / "cli.yml"
    p.write_text(
        "project:\n"
        "  distribution: prisma-browser-cli\n"
        "  author: Oliver Kaiser\n"
        "  author_email: o@example.com\n"
        "  repo_url: https://github.com/x/prisma-browser-cli\n"
        "  description: CLI for the Prisma Browser SDK\n"
    )
    cfg = load_cli_config(p)
    assert cfg.project is not None
    assert cfg.project.distribution == "prisma-browser-cli"


def test_cli_config_project_absent_is_none(tmp_path):
    p = tmp_path / "cli.yml"
    p.write_text("hide: []\n")
    assert load_cli_config(p).project is None


def test_columns_section_loads(tmp_path):
    from phantasos.generator.cli.cliconfig import ColumnEntry, load_cli_config

    p = tmp_path / "cli.yml"
    p.write_text(
        "columns:\n"
        "  device-group:\n"
        "    - id\n"
        "    - name\n"
        "    - header: MEMBERS\n"
        "      path: \"members[].name\"\n",
        encoding="utf-8",
    )
    cfg = load_cli_config(p)
    entries = cfg.columns["device-group"]
    assert entries[0] == "id"
    assert isinstance(entries[2], ColumnEntry)
    assert entries[2].header == "MEMBERS"
    assert entries[2].path == "members[].name"


def test_defaults_section_loads(tmp_path):
    from phantasos.generator.cli.cliconfig import load_cli_config

    p = tmp_path / "cli.yml"
    p.write_text(
        "defaults:\n"
        "  applications.list_applications:\n"
        "    sort: application.id\n"
        "    order: asc\n"
        "  widgets.list_widgets:\n"
        "    limit: 50\n",
        encoding="utf-8",
    )
    cfg = load_cli_config(p)
    assert cfg.defaults["applications.list_applications"] == {
        "sort": "application.id", "order": "asc",
    }
    assert cfg.defaults["widgets.list_widgets"] == {"limit": 50}  # int preserved
