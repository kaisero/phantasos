"""Unit tests for the phantasos CLI (offline: generate is monkeypatched out)."""

from pathlib import Path

import pytest

from phantasos import cli


def test_cli_build_returns_zero_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {title: Acme, version: 1.2.3}\npaths: {}\n", encoding="utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out\nbase_url: https://api/\nfacade: true\n",
        encoding="utf-8",
    )

    def fake_generate(spec_path, out_dir, package, library="urllib3"):
        pkg = Path(out_dir) / package
        (pkg / "api").mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "api" / "__init__.py").write_text(
            "from acme.api.things_api import ThingsApi\n", encoding="utf-8"
        )
        (pkg / "api" / "things_api.py").write_text(
            "class ThingsApi:\n    def list_things(self):\n        return []\n", encoding="utf-8"
        )

    monkeypatch.setattr("phantasos.generate.generate", fake_generate)
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["build", "acme", "--no-smoke"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "built acme" in out
    about = (tmp_path / "out" / "acme" / "_about.py").read_text(encoding="utf-8")
    assert "1.2.3" in about
    assert (tmp_path / "out" / "acme" / "extras" / "facade.py").exists()


def test_cli_build_missing_product_returns_2(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["build", "nope"]) == 2


def test_build_runs_transforms_then_hook(tmp_path, monkeypatch) -> None:
    import phantasos
    from phantasos.productconfig import load_product

    order: list[str] = []
    monkeypatch.setattr("phantasos.generate.generate", lambda *a, **k: None)
    monkeypatch.setattr("phantasos.render.vendor", lambda *a, **k: [])
    monkeypatch.setattr("phantasos.patches.apply_generic_patches", lambda d: {})
    monkeypatch.setattr("phantasos.smoke.smoke", lambda *a, **k: {"skipped": True, "operations": 0})
    monkeypatch.setattr(
        "phantasos.preprocess.tag_operations",
        lambda spec, ops, stats=None: order.append("transforms"),
    )

    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8")
    (prod / "hooks.py").write_text(
        "def preprocess(spec):\n    import builtins; builtins._ORDER.append('hook')\n",
        encoding="utf-8",
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out\nbase_url: b\n"
        "transforms: {tag_operations: [{path: /x, method: get, operation_id: G, tag: T}]}\n"
        "hooks: ./hooks.py\n",
        encoding="utf-8",
    )
    import builtins
    builtins._ORDER = order  # let the hook record into the same list
    loaded = load_product(str(prod / "sdk.yml"))
    phantasos.build(loaded)
    del builtins._ORDER
    assert order == ["transforms", "hook"]
