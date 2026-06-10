"""The emitted live-CRUD suite template must render to valid Python."""

from pathlib import Path

from jinja2 import Environment, select_autoescape

TEMPLATE = Path("products/prisma-browser/overrides/tests/test_sdk_crud_live.py.jinja")


def test_template_renders_and_compiles() -> None:
    # select_autoescape: renders Python source, not HTML (same as scaffold.py)
    env = Environment(autoescape=select_autoescape())
    rendered = env.from_string(TEMPLATE.read_text()).render(package="prisma_browser")
    compile(rendered, "test_sdk_crud_live.py", "exec")  # SyntaxError = fail
    assert "from prisma_browser.extras.facade import Client" in rendered
    assert "device_group" in rendered
    assert "skipif" in rendered  # must skip, not fail, without credentials
