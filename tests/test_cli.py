"""Unit tests for the phantasos CLI (offline: generate is monkeypatched out)."""

from pathlib import Path
from typing import Any

import pytest

from phantasos import cli


def test_cli_build_returns_zero_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {title: Acme, version: 1.2.3}\npaths: {}\n",
        encoding="utf-8",
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out\nbase_url: https://api/\nfacade: true\n"
        "project: {distribution: acme-sdk, author: A, author_email: a@b.c, repo_url: https://x/y}\n",
        encoding="utf-8",
    )
    (prod / "overrides").mkdir()
    readme = prod / "overrides" / "README.md.jinja"
    readme.write_text("# Acme SDK\n", encoding="utf-8")

    def fake_generate(
        spec_path: str,
        out_dir: str,
        package: str,
        library: str = "urllib3",
        oneof_discriminator_lookup: bool = True,
    ) -> None:
        pkg = Path(out_dir) / package
        (pkg / "api").mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "api" / "__init__.py").write_text(
            "from acme.api.things_api import ThingsApi\n", encoding="utf-8"
        )
        (pkg / "api" / "things_api.py").write_text(
            "class ThingsApi:\n    def list_things(self):\n        return []\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("phantasos.generator.sdk.generate.generate", fake_generate)
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["build", "acme", "--no-smoke"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "built acme" in out
    about = (tmp_path / "out" / "acme" / "_about.py").read_text(encoding="utf-8")
    assert "1.2.3" in about
    assert (tmp_path / "out" / "acme" / "extras" / "facade.py").exists()


def test_cli_build_missing_product_returns_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["build", "nope"]) == 2


def test_cli_build_invalid_sdk_yml_returns_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: o\nbase_url: b\npagintion: {type: cursor}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["build", "acme"])
    assert rc == 2
    assert "ERROR" in capsys.readouterr().err


def test_build_runs_transforms_then_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    import phantasos
    from phantasos.productconfig import load_product

    order: list[str] = []
    monkeypatch.setattr(
        "phantasos.generator.sdk.generate.generate", lambda *a, **k: None
    )
    monkeypatch.setattr("phantasos.generator.sdk.render.vendor", lambda *a: [])
    monkeypatch.setattr(
        "phantasos.generator.sdk.patches.apply_generic_patches", lambda d: {}
    )
    monkeypatch.setattr(
        "phantasos.generator.sdk.smoke.smoke",
        lambda *a, **k: {"skipped": True, "operations": 0},
    )
    monkeypatch.setattr(
        "phantasos.generator.sdk.preprocess.tag_operations",
        lambda spec, ops, stats=None: order.append("transforms"),
    )

    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n",
        encoding="utf-8",
    )
    (prod / "hooks.py").write_text(
        "def preprocess(spec):\n    import builtins; builtins._ORDER.append('hook')\n",
        encoding="utf-8",
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out\nbase_url: b\n"
        "transforms:\n"
        "  tag_operations:\n"
        "    - {path: /x, method: get, operation_id: G, tag: T}\n"
        "hooks: ./hooks.py\n"
        "project: {distribution: acme-sdk, author: A, author_email: a@b.c, repo_url: https://x/y}\n",
        encoding="utf-8",
    )
    (prod / "overrides").mkdir()
    readme = prod / "overrides" / "README.md.jinja"
    readme.write_text("# Acme SDK\n", encoding="utf-8")
    _order_sentinel: Any = order
    builtins._ORDER = _order_sentinel  # type: ignore[attr-defined]
    loaded = load_product(str(prod / "sdk.yml"))
    phantasos.build(loaded)
    del builtins._ORDER  # type: ignore[attr-defined]
    assert order == ["transforms", "hook"]


def test_build_writes_ignore_and_scaffolds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import phantasos
    from phantasos.productconfig import load_product

    calls: list[str] = []

    def fake_generate(
        spec_path: str,
        out_dir: str,
        package: str,
        library: str = "urllib3",
        oneof_discriminator_lookup: bool = True,
    ) -> None:
        assert (Path(out_dir) / ".openapi-generator-ignore").exists()
        calls.append("generate")
        pkg = Path(out_dir) / package
        (pkg / "api").mkdir(parents=True)
        (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")

    def fake_scaffold(*a: object, **k: object) -> list[str]:
        calls.append("scaffold")
        return []

    monkeypatch.setattr(
        "phantasos.generator.sdk.generate.generate", fake_generate
    )
    monkeypatch.setattr(
        "phantasos.generator.sdk.smoke.smoke",
        lambda *a, **k: {"skipped": True, "operations": 0},
    )
    monkeypatch.setattr("phantasos.scaffold.render_scaffold", fake_scaffold)

    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n",
        encoding="utf-8",
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out\nbase_url: b\nfacade: false\n"
        "project: {distribution: acme-sdk, author: A, author_email: a@b.c, repo_url: https://x/y}\n",
        encoding="utf-8",
    )
    (prod / "overrides").mkdir()
    readme = prod / "overrides" / "README.md.jinja"
    readme.write_text("# Acme SDK\n", encoding="utf-8")
    loaded = load_product(str(prod / "sdk.yml"))
    phantasos.build(loaded, run_smoke=False)
    assert calls == ["generate", "scaffold"]


def test_build_requires_project_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "phantasos.generator.sdk.generate.generate", lambda *a, **k: None
    )
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out\nbase_url: b\nfacade: false\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["build", "acme", "--no-smoke"])
    assert rc == 2


def test_build_requires_readme_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "phantasos.generator.sdk.generate.generate", lambda *a, **k: None
    )
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out\nbase_url: b\nfacade: false\n"
        "project: {distribution: acme-sdk, author: A, author_email: a@b.c,"
        " repo_url: https://x/y}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["build", "acme", "--no-smoke"])  # no overrides/README.md.jinja
    assert rc == 2
