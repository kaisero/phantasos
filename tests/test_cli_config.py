from pathlib import Path

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
