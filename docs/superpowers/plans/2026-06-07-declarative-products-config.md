# Declarative per-product config (Phase 1: A+B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Python `transformations/<product>.py` config modules with a declarative, pydantic-validated `products/<product>/sdk.yml` that drives the build, the vendored components, a `vars` substitution store, and an `include` template map.

**Architecture:** A new `productconfig.py` defines pydantic models for `sdk.yml` and a `load_product(name_or_path)` loader (validate + resolve paths + build the unified template context). `config.py`'s dataclasses become pydantic component models. `render.py` builds ONE unified context (auto-exposed build-config + spec-derived + `vars`) and renders components + the `include` map with it. `build()`/`cli.py` are refactored to consume the loaded config; the Python-module loader is removed. Both example products are migrated.

**Tech Stack:** Python 3.11+, pydantic v2 (new dep), ruamel.yaml, jinja2, pytest, nox, ruff, mypy. Builds on the `isolated-smoke-venv` branch. Design: `docs/superpowers/specs/2026-06-07-declarative-products-config-design.md`.

---

## Confirmed decisions (from grilling + review)

1. Scope = **A+B together** (config + components + `vars` + `include`); **C deferred** (infra scaffolding, `.openapi-generator-ignore`).
2. Layout `products/<product>/{openapi.yml, sdk.yml, templates/, hooks.py}`; `specs/` removed.
3. `sdk.yml` = build config + `transforms:` (declarative hoist/tag) + optional `hooks:` link + typed components + `vars` (supplemental) + `include` (→ `<package>/extras/` only).
4. Auto-exposed context (build-config + spec-derived) is single source of truth; **`vars` shadowing an auto-exposed name is a hard error**.
5. **pydantic v2** for validation (`extra="forbid"`).
6. Component templates adapted to the **unified context** with output **preserved** (prisma-browser-sdk behavioral suite is the guardrail).
7. `transforms:` run **before** `hooks.py`. CLI `phantasos build <product-name>`; module loader removed. Both examples migrated.

### Correction to the spec example

`base_url` (the API host) is a **top-level build-config field** (auto-exposed), *not* nested in `auth`. The `auth` block keeps `base_url_env` (the env-var *name*), which is different.

## Unified template context (the contract)

`render.py` builds one dict and renders every component + `include` template with `{**context, **component_fields, **per_call_extra}`:

```
package, library, base_url            # build config (auto-exposed)
spec_version, spec_title              # spec-derived (from openapi.yml info.*)
has_auth, has_pagination, has_errors, has_facade   # component presence
config_class_name                     # auth.config_class_name or "SdkConfiguration"
**vars                                # supplemental (validated: no collision with the above)
```

Existing templates reference component fields (`token_url`, `data_field`, …) + `base_url`/`resources`/`has_*`; those names are preserved, so output is unchanged. Templates may *additionally* reference `package`, `spec_version`, and `vars`.

## File structure

| File | Responsibility | Change |
|---|---|---|
| `src/phantasos/config.py` | pydantic component models (`OAuthClientCredentials`, `CursorPagination`, `NestedError`, `Facade`) + `BUILTIN_AUTH`/etc. registries | Rewrite |
| `src/phantasos/productconfig.py` | `ProductConfig` model + `load_product()` + context builder + validators | **Create** |
| `src/phantasos/render.py` | build unified context; render components + `include` | Modify |
| `src/phantasos/__init__.py` | `build(config: ProductConfig, ...)`; transforms→hooks order | Modify |
| `src/phantasos/cli.py` | `phantasos build <product-name>`; drop module loader | Rewrite |
| `tests/test_productconfig.py` | model + loader + validator tests | **Create** |
| `tests/test_render.py`, `tests/test_cli.py`, `tests/test_config.py` | update for the new model | Modify |
| `products/{adem,prisma-browser}/{openapi.yml,sdk.yml,hooks.py?}` | migrated examples | **Create** |
| `specs/`, `transformations/` | removed | Delete |
| `pyproject.toml` | add `pydantic>=2` dep; package-data for `components/**`; mypy/ruff | Modify |
| `noxfile.py`, `.github/workflows/ci.yml` | `phantasos build <name>` | Modify |
| `README.md`, `docs/AUTHORING_A_SPEC.md` | document `sdk.yml` | Modify |

---

### Task 1: Add pydantic; component models in `config.py`

**Files:**
- Modify: `pyproject.toml`, `src/phantasos/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml` `[project]`, change `dependencies` to:
```toml
dependencies = [
    "ruamel.yaml>=0.18",
    "jinja2>=3.1",
    "pydantic>=2",
]
```
Run `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv lock` to update the lock.

- [ ] **Step 2: Write the failing tests** (replace `tests/test_config.py`)

```python
# tests/test_config.py
"""Tests for the pydantic component models."""

import pytest
from pydantic import ValidationError

from phantasos.config import CursorPagination, Facade, NestedError, OAuthClientCredentials


def test_oauth_defaults_and_template() -> None:
    a = OAuthClientCredentials(type="oauth_client_credentials", token_url="https://t/")
    assert a.scope_env == "SCOPE"
    assert a.config_class_name == "SdkConfiguration"
    assert a.template == "auth/oauth_client_credentials.py.jinja"


def test_cursor_defaults() -> None:
    p = CursorPagination(type="cursor")
    assert p.data_field == "data" and p.cursor_field == "cursor"
    assert p.template == "pagination/cursor.py.jinja"


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        NestedError(type="nested", bogus_key="x")


def test_facade_template() -> None:
    assert Facade(type="default").template == "facade/client.py.jinja"
```

- [ ] **Step 3: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic pytest tests/test_config.py -q`
Expected: FAIL — `TypeError`/`ImportError` (current classes are dataclasses without `type`).

- [ ] **Step 4: Rewrite `config.py` as pydantic models**

```python
"""Pydantic component models for a generated SDK's vendored extras.

Each component carries a `type` (its built-in strategy name, validated by the
loader against a registry) and the config the matching Jinja template needs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Component(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str


class OAuthClientCredentials(_Component):
    """OAuth2 client-credentials auth (Basic creds, form body)."""

    token_url: str
    scope_env: str = "SCOPE"
    client_id_env: str = "CLIENT_ID"
    client_secret_env: str = "CLIENT_SECRET"  # noqa: S105  env-var name, not a secret
    base_url_env: str = "BASE_URL"
    config_class_name: str = "SdkConfiguration"
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    backoff_factor: float = 0.5
    template: str = "auth/oauth_client_credentials.py.jinja"


class CursorPagination(_Component):
    """Cursor pagination: items under `data_field`, cursor under page_info."""

    data_field: str = "data"
    page_info_field: str = "page_info"
    cursor_field: str = "cursor"
    has_next_field: str = "has_next_page"
    template: str = "pagination/cursor.py.jinja"


class NestedError(_Component):
    """Error message at ``body[error_field][message_field]`` (+ optional code)."""

    error_field: str = "error"
    message_field: str = "message"
    code_field: str = "code"
    template: str = "errors/nested_error.py.jinja"


class Facade(_Component):
    """Resource facade: binds generated *Api classes as client.<resource>."""

    template: str = "facade/client.py.jinja"


# Built-in strategy registries: category -> {type name: model}. The loader uses
# these to dispatch a YAML block's `type` to the right model (or a custom path).
BUILTIN_AUTH = {"oauth_client_credentials": OAuthClientCredentials}
BUILTIN_PAGINATION = {"cursor": CursorPagination}
BUILTIN_ERRORS = {"nested": NestedError}
BUILTIN_FACADE = {"default": Facade}
```

- [ ] **Step 5: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic pytest tests/test_config.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/phantasos/config.py tests/test_config.py
git commit -m "feat(config): pydantic component models + built-in registries; add pydantic dep"
```

---

### Task 2: `ProductConfig` model + `transforms`

**Files:**
- Create: `src/phantasos/productconfig.py`
- Test: `tests/test_productconfig.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_productconfig.py
"""Tests for sdk.yml parsing, validation, and the loader."""

import pytest
from pydantic import ValidationError

from phantasos.productconfig import Hoist, ProductConfig, TagOperation, Transforms


def test_productconfig_minimal() -> None:
    cfg = ProductConfig(package="acme", output="../acme-sdk", base_url="https://api/")
    assert cfg.library == "urllib3"
    assert cfg.apply_generic_patches is True
    assert cfg.transforms == Transforms()


def test_transforms_parse() -> None:
    cfg = ProductConfig(
        package="acme",
        output="../acme-sdk",
        base_url="https://api/",
        transforms={
            "hoist": [{"schema": "S", "field": "f", "item": "I"}],
            "tag_operations": [
                {"path": "/x", "method": "get", "operation_id": "GetX", "tag": "X"}
            ],
        },
    )
    assert cfg.transforms.hoist == [Hoist(schema="S", field="f", item="I")]
    assert cfg.transforms.tag_operations[0] == TagOperation(
        path="/x", method="get", operation_id="GetX", tag="X"
    )


def test_unknown_top_level_key_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductConfig(
            package="a", output="o", base_url="b", pagintion={}  # typo
        )
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic pytest tests/test_productconfig.py -q`
Expected: FAIL — `ModuleNotFoundError: phantasos.productconfig`.

- [ ] **Step 3: Create `productconfig.py` with the model skeleton**

```python
"""Load and validate a product's declarative sdk.yml into a ProductConfig."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .config import (
    BUILTIN_AUTH,
    BUILTIN_ERRORS,
    BUILTIN_FACADE,
    BUILTIN_PAGINATION,
)


class Hoist(BaseModel):
    # `schema` shadows a pydantic BaseModel attribute, so store it as schema_name
    # with a YAML alias of `schema`. populate_by_name lets tests pass either.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_name: str = Field(alias="schema")
    field: str
    item: str


class TagOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    method: str
    operation_id: str
    tag: str


class Transforms(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hoist: list[Hoist] = Field(default_factory=list)
    tag_operations: list[TagOperation] = Field(default_factory=list)


class ProductConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package: str
    output: str
    base_url: str
    library: str = "urllib3"
    spec: str = "./openapi.yml"
    apply_generic_patches: bool = True
    transforms: Transforms = Field(default_factory=Transforms)
    hooks: str | None = None
    # auth/pagination/errors are resolved to component models by the loader (Task 4);
    # at the raw-parse layer they are plain dicts.
    auth: dict[str, Any] | None = None
    pagination: dict[str, Any] | None = None
    errors: dict[str, Any] | None = None
    facade: bool | dict[str, Any] = True
    vars: dict[str, Any] = Field(default_factory=dict)
    include: dict[str, str] = Field(default_factory=dict)
```

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic pytest tests/test_productconfig.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/productconfig.py tests/test_productconfig.py
git commit -m "feat(productconfig): ProductConfig + Transforms models"
```

---

### Task 3: Resolve typed components (built-in `type` or custom path)

**Files:**
- Modify: `src/phantasos/productconfig.py`
- Test: `tests/test_productconfig.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
# append to tests/test_productconfig.py
from phantasos.config import OAuthClientCredentials  # noqa: E402
from phantasos.productconfig import resolve_component  # noqa: E402


def test_resolve_builtin_auth() -> None:
    from phantasos.config import BUILTIN_AUTH

    c = resolve_component(
        {"type": "oauth_client_credentials", "token_url": "https://t/"},
        BUILTIN_AUTH,
        base_dir=__import__("pathlib").Path("."),
    )
    assert isinstance(c, OAuthClientCredentials)
    assert c.token_url == "https://t/"


def test_resolve_custom_path(tmp_path) -> None:
    from phantasos.config import BUILTIN_AUTH

    tpl = tmp_path / "templates" / "api_key.py.jinja"
    tpl.parent.mkdir(parents=True)
    tpl.write_text("", encoding="utf-8")
    c = resolve_component(
        {"type": "./templates/api_key.py.jinja", "header_name": "X-API-Key"},
        BUILTIN_AUTH,
        base_dir=tmp_path,
    )
    assert c.template == str(tpl)
    assert c.extra["header_name"] == "X-API-Key"


def test_resolve_missing_custom_path(tmp_path) -> None:
    from phantasos.config import BUILTIN_AUTH

    with pytest.raises(ValueError, match="template not found"):
        resolve_component(
            {"type": "./templates/missing.jinja"}, BUILTIN_AUTH, base_dir=tmp_path
        )


def test_resolve_unknown_builtin() -> None:
    from phantasos.config import BUILTIN_AUTH

    with pytest.raises(ValueError, match="unknown.*type"):
        resolve_component(
            {"type": "magic"}, BUILTIN_AUTH, base_dir=__import__("pathlib").Path(".")
        )
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic pytest tests/test_productconfig.py -k resolve -q`
Expected: FAIL — `ImportError: cannot import name 'resolve_component'`.

- [ ] **Step 3: Implement `resolve_component` + a custom-component model** (append to `productconfig.py`)

```python
from pathlib import Path  # add to imports

from .config import _Component  # add to imports


class CustomComponent(BaseModel):
    """A component backed by a per-product template path (arbitrary config)."""

    model_config = ConfigDict(extra="allow")
    type: str
    template: str = ""

    @property
    def extra(self) -> dict[str, Any]:
        # pydantic v2 stores extra="allow" fields here, not in __dict__.
        return dict(self.__pydantic_extra__ or {})


def resolve_component(
    block: dict[str, Any], registry: dict[str, type], base_dir: Path
) -> Any:
    """Turn a raw sdk.yml component block into a validated component model."""
    type_ = block.get("type")
    if isinstance(type_, str) and (type_.startswith("./") or type_.endswith(".jinja")):
        path = (base_dir / type_).resolve()
        if not path.exists():
            raise ValueError(f"{type_}: template not found at {path}")
        data = {**block, "template": str(path)}
        return CustomComponent(**data)
    model = registry.get(type_) if isinstance(type_, str) else None
    if model is None:
        raise ValueError(f"unknown component type {type_!r}; expected one of {sorted(registry)}")
    return model(**block)
```

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic pytest tests/test_productconfig.py -k resolve -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/productconfig.py tests/test_productconfig.py
git commit -m "feat(productconfig): resolve components (built-in type or custom template path)"
```

---

### Task 4: The `load_product()` loader + spec-derived metadata + `vars` collision

**Files:**
- Modify: `src/phantasos/productconfig.py`
- Test: `tests/test_productconfig.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
# append to tests/test_productconfig.py
import textwrap  # noqa: E402
from pathlib import Path  # noqa: E402

from phantasos.productconfig import load_product  # noqa: E402

_SDK_YML = """\
package: acme
output: ../acme-sdk
base_url: https://api.example.com
auth: {type: oauth_client_credentials, token_url: "https://t/"}
pagination: {type: cursor}
errors: {type: nested}
facade: true
vars: {support_email: sdk@example.com}
"""

_OPENAPI = """\
openapi: 3.0.0
info: {title: Acme, version: 9.9.9}
paths: {}
"""


def _make_product(root: Path) -> Path:
    d = root / "products" / "acme"
    d.mkdir(parents=True)
    (d / "sdk.yml").write_text(_SDK_YML, encoding="utf-8")
    (d / "openapi.yml").write_text(_OPENAPI, encoding="utf-8")
    return d


def test_load_product_by_path(tmp_path: Path) -> None:
    d = _make_product(tmp_path)
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.config.package == "acme"
    assert loaded.auth.token_url == "https://t/"
    assert loaded.context["spec_version"] == "9.9.9"
    assert loaded.context["spec_title"] == "Acme"
    assert loaded.context["package"] == "acme"
    assert loaded.context["support_email"] == "sdk@example.com"
    assert loaded.context["has_auth"] is True


def test_load_product_by_name(tmp_path: Path, monkeypatch: "pytest.MonkeyPatch") -> None:
    _make_product(tmp_path)
    monkeypatch.chdir(tmp_path)
    loaded = load_product("acme")
    assert loaded.config.package == "acme"


def test_vars_collision_is_error(tmp_path: Path) -> None:
    d = _make_product(tmp_path)
    # A vars key that shadows an auto-exposed name (`package`) must error.
    (d / "sdk.yml").write_text(
        "package: acme\noutput: o\nbase_url: b\nvars: {package: oops}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="shadow|reserved"):
        load_product(str(d / "sdk.yml"))
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml pytest tests/test_productconfig.py -k load_product -q`
Expected: FAIL — `ImportError: cannot import name 'load_product'`.

- [ ] **Step 3: Implement `load_product` + `LoadedProduct`** (append to `productconfig.py`)

```python
from dataclasses import dataclass as _dataclass  # add to imports


@_dataclass
class LoadedProduct:
    config: ProductConfig
    base_dir: Path
    spec_path: Path
    output_dir: Path
    auth: Any | None
    pagination: Any | None
    errors: Any | None
    facade: Any | None
    context: dict[str, Any]


_AUTO_EXPOSED = {
    "package", "library", "base_url", "spec_version", "spec_title",
    "has_auth", "has_pagination", "has_errors", "has_facade", "config_class_name",
}


def _read_yaml(path: Path) -> dict[str, Any]:
    from ruamel.yaml import YAML

    with path.open(encoding="utf-8") as fh:
        return YAML(typ="safe").load(fh)


def load_product(name_or_path: str) -> LoadedProduct:
    p = Path(name_or_path)
    sdk_path = p if p.name == "sdk.yml" else Path("products") / name_or_path / "sdk.yml"
    sdk_path = sdk_path.resolve()
    if not sdk_path.exists():
        raise FileNotFoundError(f"no sdk.yml at {sdk_path}")
    base_dir = sdk_path.parent
    cfg = ProductConfig(**_read_yaml(sdk_path))

    auth = resolve_component(cfg.auth, BUILTIN_AUTH, base_dir) if cfg.auth else None
    pagination = (
        resolve_component(cfg.pagination, BUILTIN_PAGINATION, base_dir)
        if cfg.pagination
        else None
    )
    errors = resolve_component(cfg.errors, BUILTIN_ERRORS, base_dir) if cfg.errors else None
    facade = None
    if cfg.facade:
        block = {"type": "default"} if cfg.facade is True else dict(cfg.facade)
        block.setdefault("type", "default")
        facade = resolve_component(block, BUILTIN_FACADE, base_dir)

    spec_path = (base_dir / cfg.spec).resolve()
    info = (_read_yaml(spec_path) or {}).get("info", {}) if spec_path.exists() else {}

    context: dict[str, Any] = {
        "package": cfg.package,
        "library": cfg.library,
        "base_url": cfg.base_url,
        "spec_version": info.get("version"),
        "spec_title": info.get("title"),
        "has_auth": auth is not None,
        "has_pagination": pagination is not None,
        "has_errors": errors is not None,
        "has_facade": facade is not None,
        "config_class_name": getattr(auth, "config_class_name", "SdkConfiguration"),
    }
    collisions = set(cfg.vars) & _AUTO_EXPOSED
    if collisions:
        raise ValueError(
            f"vars keys {sorted(collisions)} shadow reserved auto-exposed names"
        )
    context.update(cfg.vars)

    return LoadedProduct(
        config=cfg,
        base_dir=base_dir,
        spec_path=spec_path,
        output_dir=(base_dir / cfg.output).resolve(),
        auth=auth,
        pagination=pagination,
        errors=errors,
        facade=facade,
        context=context,
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml pytest tests/test_productconfig.py -k load_product -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/productconfig.py tests/test_productconfig.py
git commit -m "feat(productconfig): load_product loader, spec-derived context, vars collision check"
```

---

### Task 5: Refactor `render.vendor` to the unified context + `include`

**Files:**
- Modify: `src/phantasos/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_render.py`)

```python
# append to tests/test_render.py
from pathlib import Path

from phantasos import render
from phantasos.productconfig import load_product


def test_vendor_uses_loaded_product_and_include(tmp_path: Path) -> None:
    # minimal generated package
    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text(
        "from acme.api.things_api import ThingsApi\n", encoding="utf-8"
    )
    # product dir with an extra include template
    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "templates" / "banner.py.jinja").write_text(
        "BANNER = '{{ package }} {{ spec_version }}'\n", encoding="utf-8"
    )
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {title: Acme, version: 1.0.0}\npaths: {}\n", encoding="utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: https://api/\n"
        "facade: true\ninclude: {banner.py: ./templates/banner.py.jinja}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded)
    assert "facade.py" in written
    assert (pkg / "extras" / "banner.py").read_text() == "BANNER = 'acme 1.0.0'\n"


def test_include_rejects_path_escape(tmp_path: Path) -> None:
    import pytest

    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")
    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "templates" / "x.jinja").write_text("x\n", encoding="utf-8")
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8")
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\n"
        "include: {'../escape.py': ./templates/x.jinja}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    with pytest.raises(ValueError, match="escapes"):
        render.vendor(pkg, loaded)
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_render.py -k "include or loaded_product" -q`
Expected: FAIL — `vendor()` signature/behavior mismatch (`load_product`/`LoadedProduct` unsupported).

- [ ] **Step 3: Refactor `render.py`** — replace `vendor()` and add a per-product Jinja loader. New `vendor(pkg_dir, loaded)`:

```python
def vendor(pkg_dir: Path, loaded: "LoadedProduct") -> list[str]:
    from jinja2 import Environment, FileSystemLoader

    extras = pkg_dir / "extras"
    extras.mkdir(exist_ok=True)
    written: list[str] = []
    ctx = dict(loaded.context)

    # Built-in component templates ship with phantasos; per-product templates
    # (custom types / include) resolve from the product dir.
    builtin_env = _env()  # FileSystemLoader(_COMPONENTS_DIR), autoescape off
    product_env = Environment(
        loader=FileSystemLoader(str(loaded.base_dir)),
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701  renders Python source, not HTML
    )

    def render_template(template: str, **extra: Any) -> str:
        merged = {**ctx, **extra}
        if Path(template).is_absolute():  # custom per-product template
            rel = Path(template).relative_to(loaded.base_dir)
            return product_env.get_template(str(rel)).render(**merged)
        return builtin_env.get_template(template).render(**merged)

    def write_component(name: str, component: Any, **extra: Any) -> None:
        fields = component.model_dump()
        template = fields.pop("template")
        fields.pop("type", None)
        (extras / name).write_text(
            render_template(template, **{**fields, **extra}), encoding="utf-8"
        )
        written.append(name)

    if loaded.auth:
        write_component("auth.py", loaded.auth)
    if loaded.pagination:
        write_component("pagination.py", loaded.pagination)
    if loaded.errors:
        write_component("errors.py", loaded.errors)
    if loaded.facade:
        write_component("facade.py", loaded.facade, resources=_discover_resources(pkg_dir))

    # include: dest (under extras/) -> source template (product-relative)
    for dest, source in loaded.config.include.items():
        target = (extras / dest).resolve()
        if not target.is_relative_to(extras.resolve()):
            raise ValueError(f"include destination {dest!r} escapes extras/")
        target.parent.mkdir(parents=True, exist_ok=True)
        rel = (loaded.base_dir / source).resolve().relative_to(loaded.base_dir)
        target.write_text(product_env.get_template(str(rel)).render(**ctx), encoding="utf-8")
        written.append(dest)

    (extras / "__init__.py").write_text(
        builtin_env.get_template("extras_init.py.jinja").render(**ctx), encoding="utf-8"
    )
    written.append("__init__.py")
    return written
```

Add `from typing import TYPE_CHECKING` import of `LoadedProduct` under `TYPE_CHECKING`, and remove the old `from dataclasses import asdict` usage / `SdkConfig` references.

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_render.py -q`
Expected: PASS — including the existing render tests (update any that constructed the old `SdkConfig`; see Task 8 for the example-driven ones).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/render.py tests/test_render.py
git commit -m "feat(render): unified context + include map; render from LoadedProduct"
```

---

### Task 6: Adapt the 4 component templates to the unified context

**Files:**
- Modify: `src/phantasos/components/{auth/oauth_client_credentials,pagination/cursor,errors/nested_error,facade/client,extras_init}.py.jinja`

- [ ] **Step 1: Read each template and confirm the variable contract**

Run: `grep -rnoE '\{\{ *[a-zA-Z_]+' src/phantasos/components/*.jinja src/phantasos/components/**/*.jinja | sort -u`
Expected: the variables each template references (e.g. `token_url`, `base_url`, `data_field`, `resources`, `has_auth`, …). Confirm every one is provided by the unified context + component fields (from Task 5's `render_template`). They are — component `model_dump()` supplies the component fields, `ctx` supplies `base_url`/`has_*`/`config_class_name`/`package`/etc.

- [ ] **Step 2: Update `facade/client.py.jinja`** so it reads presence flags from the context instead of the per-call `has_auth`/`has_pagination` (which `vendor` no longer passes individually — they're in `ctx`).

Open the file; wherever it uses `has_auth` / `has_pagination`, confirm they resolve from `ctx` (they do — `vendor` merges `ctx`). If the template referenced a variable *only* previously passed as a per-call extra and now absent, switch it to the context name. (For the bundled templates as written, `has_auth`/`has_pagination` are in `ctx`, so typically no change is needed — verify by the render test below.)

- [ ] **Step 3: Run the render tests + the example behavioral guardrail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_render.py tests/test_framework.py -q`
Expected: PASS. (Task 8's end-to-end build + the `prisma-browser-sdk` behavioral suite are the byte-level guardrail that output is preserved.)

- [ ] **Step 4: Commit**

```bash
git add src/phantasos/components
git commit -m "refactor(templates): read presence/config from the unified context"
```

*(If Step 1 shows every variable already resolves from the unified context with no edits needed, this task is a no-op commit documenting that verification — note it in the message.)*

---

### Task 7: Refactor `build()` to consume `LoadedProduct`; declarative transforms before hooks

**Files:**
- Modify: `src/phantasos/__init__.py`
- Test: `tests/test_cli.py` (build-level)

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli.py`)

```python
# append to tests/test_cli.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_cli.py -k transforms_then_hook -q`
Expected: FAIL — `build()` still expects the old `SdkConfig` + `preprocess_hook=` signature.

- [ ] **Step 3: Rewrite `build()` in `__init__.py`** to take a `LoadedProduct`. Update `__all__` (drop the dataclass component exports; export `build`). New body:

```python
def build(loaded: LoadedProduct, *, run_smoke: bool = True) -> dict[str, Any]:
    from . import generate, preprocess, render, smoke

    cfg = loaded.config
    project_dir = loaded.output_dir
    stats: defaultdict[str, int] = defaultdict(int)

    # 1. preprocess: generic clean -> declarative transforms -> linked hook
    spec, yaml = preprocess.load(str(loaded.spec_path))
    preprocess.clean(spec, stats)
    if cfg.transforms.hoist:
        preprocess.hoist_items(
            spec,
            [(h.schema_name, h.field, h.item) for h in cfg.transforms.hoist],
            stats,
        )
    if cfg.transforms.tag_operations:
        preprocess.tag_operations(
            spec,
            [(t.path, t.method, t.operation_id, t.tag) for t in cfg.transforms.tag_operations],
            stats,
        )
    hook_mod = _load_hooks(loaded)
    if hook_mod and hasattr(hook_mod, "preprocess"):
        hook_mod.preprocess(spec)

    pp_dir = project_dir / ".phantasos"
    pp_dir.mkdir(parents=True, exist_ok=True)
    pp_path = pp_dir / "preprocessed.yaml"
    preprocess.dump(spec, yaml, str(pp_path))
    spec_version = spec.get("info", {}).get("version")

    # 2. generate
    generate.generate(str(pp_path), str(project_dir), cfg.package, library=cfg.library)
    pkg_dir = project_dir / cfg.package

    # 3. patches: generic -> linked hook
    patch_stats: dict[str, int] = {}
    if cfg.apply_generic_patches:
        from . import patches

        patch_stats = patches.apply_generic_patches(pkg_dir)
    if hook_mod and hasattr(hook_mod, "patch"):
        hook_mod.patch(pkg_dir)

    # 4. vendor
    vendored = render.vendor(pkg_dir, loaded)

    # 5. provenance
    (pkg_dir / "_about.py").write_text(
        _ABOUT.format(
            spec_version=spec_version,
            phantasos_version="0.1.0",
            oag_version=generate.OAG_VERSION,
        ),
        encoding="utf-8",
    )

    # 6. smoke
    result = smoke.smoke(str(project_dir), cfg.package, run=run_smoke)
    return {"preprocess": dict(stats), "patches": patch_stats, "vendored": vendored, "smoke": result}


def _load_hooks(loaded: LoadedProduct) -> Any | None:
    if not loaded.config.hooks:
        return None
    import importlib.util

    path = (loaded.base_dir / loaded.config.hooks).resolve()
    spec = importlib.util.spec_from_file_location("_phantasos_hooks", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load hooks from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

Add the imports at the top of `__init__.py`: `from .productconfig import LoadedProduct`.

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_cli.py -k transforms_then_hook -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/__init__.py tests/test_cli.py
git commit -m "feat(build): consume LoadedProduct; declarative transforms before linked hooks"
```

---

### Task 8: CLI — `phantasos build <product-name>`; drop the module loader

**Files:**
- Modify: `src/phantasos/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Rewrite the success test** — replace `test_cli_build_returns_zero_on_success` so it writes a `products/acme/{sdk.yml,openapi.yml}`, monkeypatches `generate.generate` to emit a fake package, and calls `cli.main(["build", "acme", "--no-smoke"])`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_cli.py -q`
Expected: FAIL — CLI still does module loading.

- [ ] **Step 3: Rewrite `cli.py`**

```python
"""`phantasos build <product>` — load products/<product>/sdk.yml and build its SDK."""

from __future__ import annotations

import argparse
import sys

from .productconfig import load_product


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phantasos")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build an SDK from a product's sdk.yml")
    b.add_argument("product", help="product name (products/<name>/sdk.yml) or a path to sdk.yml")
    b.add_argument(
        "--no-smoke",
        action="store_true",
        help="skip the isolated import-check (offline/locked-down builds)",
    )
    args = parser.parse_args(argv)

    if args.cmd == "build":
        from . import build

        try:
            loaded = load_product(args.product)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        result = build(loaded, run_smoke=not args.no_smoke)
        s = result["smoke"]
        pkg = loaded.config.package
        if s.get("skipped"):
            print(f"built {pkg}: smoke skipped; operations: {s['operations']}")
            return 0
        print(
            f"built {pkg}: imported {s['imported']} modules, "
            f"{s['failed']} failures; operations: {s['operations']}"
        )
        for name, err in s["failures"][:10]:
            print("  FAIL", name, err)
        return 1 if s["failed"] else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/cli.py tests/test_cli.py
git commit -m "feat(cli): phantasos build <product-name>; drop the Python-module loader"
```

---

### Task 9: Migrate the two example products

**Files:**
- Create: `products/prisma-browser/{openapi.yml,sdk.yml}`, `products/adem/{openapi.yml,sdk.yml,hooks.py?}`
- Delete: `specs/`, `transformations/`

- [ ] **Step 1: Move the specs**

```bash
mkdir -p products/prisma-browser products/adem
git mv specs/prisma-browser.yml products/prisma-browser/openapi.yml
git mv specs/adem.yml products/adem/openapi.yml
```

- [ ] **Step 2: Author `products/prisma-browser/sdk.yml`** (translate the current `transformations/prisma-browser.py`; its `preprocess` is pure hoist/tag data → `transforms:`, so **no hooks.py**)

```yaml
package: prisma_browser
output: ../../../prisma-browser-sdk        # sibling of the phantasos repo
base_url: https://api.sase.paloaltonetworks.com
auth:
  type: oauth_client_credentials
  token_url: https://auth.apps.paloaltonetworks.com/oauth2/access_token
  scope_env: SCOPE
  base_url_env: PRISMA_SASE_BASE_URL
  config_class_name: PrismaSaseConfiguration
pagination: {type: cursor}
errors: {type: nested}
facade: true
transforms:
  hoist:
    - {schema: AllowedOrBlockedExtensionsControl, field: extensions, item: AllowedOrBlockedExtensionEntry}
    - {schema: LaunchingExternalApplicationsControl, field: exceptions, item: ExternalApplicationLaunchException}
    - {schema: TrustedCertificateAuthoritiesControl, field: additionalCertificates, item: TrustedCertificateEntry}
    - {schema: InternetExplorerCompatibilityModeControl, field: sites, item: InternetExplorerCompatibilitySite}
  tag_operations:
    - {path: /seb-api/v1/user-requests, method: get, operation_id: ListUserRequests, tag: User Requests}
    - {path: /seb-api/v1/user-requests/{id}, method: get, operation_id: GetUserRequestByID, tag: User Requests}
    - {path: /seb-api/v1/user-requests/{id}/action, method: post, operation_id: ActionUserRequest, tag: User Requests}
    - {path: /seb-api/v1/user-requests/{id}/revoke, method: post, operation_id: RevokeUserRequest, tag: User Requests}
```

Confirm the `output` path resolves to the existing sibling `prisma-browser-sdk` (from `products/prisma-browser/` it's `../../../prisma-browser-sdk` — verify with `realpath`).

- [ ] **Step 3: Author `products/adem/sdk.yml` + `hooks.py`**

adem has no pagination/errors components, and its `preprocess` is *imperative* (`spec.pop("ExternalTags")` — not a hoist/tag), so it needs a linked hook.

`products/adem/sdk.yml`:
```yaml
package: adem
output: ../../../adem-sdk
base_url: https://api.sase.paloaltonetworks.com
auth:
  type: oauth_client_credentials
  token_url: https://auth.apps.paloaltonetworks.com/oauth2/access_token
  scope_env: SCOPE
  base_url_env: ADEM_BASE_URL
  config_class_name: AdemConfiguration
facade: true
hooks: ./hooks.py
# pagination/errors intentionally omitted (the API has neither)
```

`products/adem/hooks.py`:
```python
"""adem spec-specific surgery (imperative; not expressible as hoist/tag)."""


def preprocess(spec):
    # The spec carries a stray top-level `ExternalTags: {}` key (not a valid OpenAPI
    # root field), which fails OAG spec validation. Drop it.
    spec.pop("ExternalTags", None)
```

- [ ] **Step 4: Delete the old format**

```bash
git rm -r transformations
rmdir specs 2>/dev/null || true
```

- [ ] **Step 5: Verify both products load**

Run:
```bash
PYTHONPATH=src uv run --no-project --python 3.12 --with pydantic --with ruamel.yaml \
  python -c "from phantasos.productconfig import load_product; [print(load_product(p).config.package) for p in ('products/prisma-browser/sdk.yml','products/adem/sdk.yml')]"
```
Expected: prints `prisma_browser` and the adem package name; no validation errors.

- [ ] **Step 6: Commit**

```bash
git add -A products specs transformations
git commit -m "refactor: migrate adem + prisma-browser to products/<name>/{openapi.yml,sdk.yml}"
```

---

### Task 10: Update nox, CI, packaging, and docs

**Files:**
- Modify: `noxfile.py`, `.github/workflows/ci.yml`, `pyproject.toml`, `README.md`, `docs/AUTHORING_A_SPEC.md`

- [ ] **Step 1: nox smoke session** — `noxfile.py`:

```python
    _sync(session)
    session.run("phantasos", "build", "prisma-browser")
    session.run("phantasos", "build", "adem")
```

- [ ] **Step 2: CI smoke job** — `.github/workflows/ci.yml` step `Build example SDKs (Java auto-provisioned)` already runs `uv run nox -s smoke`; no change needed. Verify the `products/` dir ships in the checkout (it does — it's committed).

- [ ] **Step 3: Packaging** — confirm `pyproject.toml` still ships the component templates as package data (`[tool.hatch.build.targets.wheel] artifacts = ["src/phantasos/components/**/*.jinja"]`). No `products/` packaging (those are repo examples, not shipped). Leave as-is.

- [ ] **Step 4: Docs** — update `README.md` (Quickstart `phantasos build prisma-browser`; the Layout table: `products/<product>/{openapi.yml,sdk.yml,templates/,hooks.py}` replaces `specs/` + `transformations/`) and rewrite `docs/AUTHORING_A_SPEC.md` to document the `sdk.yml` schema (build config, components, `vars`, `include`, `transforms`, `hooks`). Show a full annotated `sdk.yml`.

- [ ] **Step 5: Lint, type-check, unit suite**

Run:
```bash
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox --envdir $HOME/.nox-phantasos -s lint type_check tests-3.12
```
Expected: ruff + mypy clean; all unit tests pass (coverage ≥ 70%). Fix any leftover references to the removed `SdkConfig`/module loader in `tests/test_framework.py` (update them to the `ProductConfig`/`load_product` API).

- [ ] **Step 6: Commit**

```bash
git add noxfile.py .github/workflows/ci.yml pyproject.toml README.md docs/AUTHORING_A_SPEC.md
git commit -m "docs/ci: phantasos build <product-name>; document sdk.yml"
```

---

### Task 11: Full end-to-end verification (the real proof)

**Files:** none (verification only).

- [ ] **Step 1: Build both example SDKs from YAML**

Run (uses Java auto-provision + isolated smoke):
```bash
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox --envdir $HOME/.nox-phantasos -s smoke
```
Expected: `built prisma_browser: imported … 0 failures` and `built adem: …`, each from its `sdk.yml`.

- [ ] **Step 2: Behavioral guardrail — the regenerated SDK still passes its suite**

Run:
```bash
cd /home/ubuntu/git/prisma-browser-sdk
uv run --no-project --python 3.12 --with pytest --with-requirements requirements.txt pytest tests/ -q
cd -
```
Expected: all prisma-browser-sdk tests pass — proving the component-template adaptation preserved output (no behavioral drift from the config-layer rewrite).

- [ ] **Step 3: Validation UX check — a bad sdk.yml gives a clear error**

Run:
```bash
PYTHONPATH=src uv run --no-project --python 3.12 --with pydantic --with ruamel.yaml \
  python -c "import io,sys; from phantasos.productconfig import ProductConfig; ProductConfig(package='a', output='o', base_url='b', pagintion={})" 2>&1 | tail -3
```
Expected: a pydantic `ValidationError` naming the unknown key `pagintion` (extra-forbidden).

- [ ] **Step 4: Confirm the old format is gone**

Run: `ls transformations specs 2>/dev/null && echo "STILL PRESENT" || echo "removed"; grep -rn "_load_spec_module\|SdkConfig" src/ || echo "no module-loader / SdkConfig refs"`
Expected: `removed` and `no module-loader / SdkConfig refs`.

- [ ] **Step 5: Final review against the design**

Re-read `docs/superpowers/specs/2026-06-07-declarative-products-config-design.md` and confirm each section maps to merged work. If all green, Phase 1 (A+B) is complete.

---

## Notes for the executor

- **Output preservation is the guardrail.** Task 6's template adaptation must not change generated code; Task 11 Step 2 (the prisma-browser-sdk suite) is the byte-level proof. If it goes red, a template variable was renamed incorrectly — fix the reference, don't change the emitted code.
- **`facade` shorthand:** `facade: true` → `{type: default}`; `facade: false`/absent → no facade.
- **Custom component templates** live under `products/<product>/templates/` and are referenced as `type: ./templates/x.py.jinja`; they render with the same unified context plus their own block's extra keys.
- **Filesystem note (this sandbox):** repo is on a symlink-less FUSE mount — use `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos` for `uv run` and the home-fs `--envdir` for nox; the smoke venvs live under `~/.cache/phantasos` (home fs).
- **Rebase base:** this plan sits on `isolated-smoke-venv`. `build()`/`cli.py` here already have `run_smoke`/`--no-smoke`; the plan preserves them.
