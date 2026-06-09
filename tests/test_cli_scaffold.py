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
