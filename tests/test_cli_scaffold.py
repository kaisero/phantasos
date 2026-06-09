from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

SCAFFOLD = Path("src/phantasos/scaffold")


def _render(template: str, ctx: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(SCAFFOLD)),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),
        undefined=StrictUndefined,
    )
    return env.get_template(template).render(**ctx)


_BASE = {
    "distribution": "x", "description": "d", "license": "Apache-2.0", "author": "a",
    "author_email": "a@b.c", "repo_url": "https://x", "package": "x",
    "dependencies": ["typer>=0.12"],
}


def test_pyproject_emits_scripts_when_provided():
    out = _render("pyproject.toml.jinja", {**_BASE, "scripts": {"x-cli": "x.main:app"}})
    assert "[project.scripts]" in out
    assert 'x-cli = "x.main:app"' in out


def test_pyproject_no_scripts_block_for_sdk():
    out = _render("pyproject.toml.jinja", _BASE)
    assert "[project.scripts]" not in out


def test_pyproject_pins_sdk_to_sibling_path_when_provided():
    out = _render("pyproject.toml.jinja", {
        **_BASE,
        "dependencies": ["typer>=0.12", "prisma-browser-sdk"],
        "sdk_dist": "prisma-browser-sdk",
        "sdk_source_path": "../prisma-browser-sdk",
    })
    assert "[tool.uv.sources]" in out
    expected = (
        'prisma-browser-sdk = { path = "../prisma-browser-sdk", editable = true }'
    )
    assert expected in out


def test_pyproject_no_uv_sources_for_sdk():
    out = _render("pyproject.toml.jinja", _BASE)
    assert "[tool.uv.sources]" not in out


def test_sdk_pyproject_byte_identical_to_pre_task1():
    # Compare SDK (no scripts / no uv.sources) output against the pre-Task-1 template
    # to guard against whitespace regressions in the conditional blocks.
    import shutil
    import subprocess

    from jinja2 import BaseLoader, Environment, StrictUndefined, select_autoescape

    git = shutil.which("git") or "git"
    base_src = subprocess.run(  # noqa: S603
        [git, "show", "4de2aa4:src/phantasos/scaffold/pyproject.toml.jinja"],
        capture_output=True, text=True, check=True,
    ).stdout

    def _r(src: str) -> str:
        env = Environment(loader=BaseLoader(), keep_trailing_newline=True,
                          autoescape=select_autoescape(), undefined=StrictUndefined)
        return env.from_string(src).render(**_BASE)

    head_src = Path("src/phantasos/scaffold/pyproject.toml.jinja").read_text()
    assert _r(head_src) == _r(base_src)          # SDK output unchanged
    assert "\n\n\n" not in _r(head_src)           # no doubled blank line


def test_cli_pyproject_is_valid_toml():
    import tomllib
    out = _render("pyproject.toml.jinja", {
        **_BASE,
        "dependencies": ["typer>=0.12", "prisma-browser-sdk"],
        "scripts": {"my-cli": "my_cli.main:app"},
        "sdk_dist": "prisma-browser-sdk",
        "sdk_source_path": "../prisma-browser-sdk",
    })
    parsed = tomllib.loads(out)
    assert parsed["project"]["scripts"] == {"my-cli": "my_cli.main:app"}
    assert parsed["tool"]["uv"]["sources"]["prisma-browser-sdk"] == {
        "path": "../prisma-browser-sdk", "editable": True}
