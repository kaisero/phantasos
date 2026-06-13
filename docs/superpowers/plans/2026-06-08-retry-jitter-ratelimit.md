# Modern retry (jitter) + RateLimitException Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every generated SDK on-by-default retry with jitter (`JitteredRetry`, Tier 1) and a typed `RateLimitException` dispatched in generated `exceptions.py` via an OAG template override (Tier 2), removing `is_rate_limited()`.

**Architecture:** Per `CLAUDE.md`'s 3-tier model — retry is Tier 1 (`extras/retry.py` over urllib3's `configuration.retries` seam); 429→`RateLimitException` is Tier 2 (a `exceptions.mustache` override passed to OAG via `-t`, so it's on every path). This also introduces phantasos's reusable **OAG custom-template** capability.

**Tech Stack:** Python 3.11+, pydantic v2, jinja2, urllib3, OpenAPI Generator 7.22.0 (`-t` templates), pytest, nox. Design: `docs/superpowers/specs/2026-06-08-retry-jitter-ratelimit-design.md`.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `src/phantasos/config.py` | `RetryConfig` component model + `BUILTIN_RETRY` | Modify |
| `src/phantasos/productconfig.py` | `ProductConfig.retry`; resolve (default-on); `has_retry` context | Modify |
| `src/phantasos/components/retry/jittered_retry.py.jinja` | `extras/retry.py`: `JitteredRetry` + `default_retry()` | **Create** |
| `src/phantasos/render.py` | vendor `retry.py` when enabled | Modify |
| `src/phantasos/oag_templates/python/exceptions.mustache` | OAG override: `RateLimitException` + 429 dispatch | **Create** |
| `src/phantasos/generate.py` | pass `-t <oag_templates>` to OAG | Modify |
| `src/phantasos/components/errors/nested_error.py.jinja` | re-export `RateLimitException`; drop `is_rate_limited` | Modify |
| `src/phantasos/components/extras_init.py.jinja` | re-export retry + `RateLimitException`; drop `is_rate_limited` | Modify |
| `src/phantasos/components/auth/oauth_client_credentials.py.jinja` | use shared `default_retry()` | Modify |
| `src/phantasos/components/facade/client.py.jinja` | wire `default_retry()` into the client config | Modify |
| `src/phantasos/scaffold/tests/test_errors.py.jinja` | assert `RateLimitException` (not `is_rate_limited`) | Modify |
| `src/phantasos/scaffold/tests/test_retry.py.jinja` | gated retry tests | **Create** |
| `pyproject.toml` | ship `oag_templates/**` as package data | Modify |
| `tests/test_config.py`, `tests/test_productconfig.py`, `tests/test_render.py`, `tests/test_generate.py` | unit tests | Modify |

---

### Task 1: `retry` component model (Tier-1 config) + default-on resolution

**Files:** Modify `src/phantasos/config.py`, `src/phantasos/productconfig.py`; Test `tests/test_config.py`, `tests/test_productconfig.py`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_config.py`:
```python
def test_retry_defaults() -> None:
    from phantasos.config import RetryConfig

    r = RetryConfig(type="default")
    assert r.max_retries == 3
    assert r.backoff_base == 0.5
    assert r.backoff_max == 8.0
    assert r.jitter_frac == 0.25
    assert r.statuses == [408, 429, 500, 502, 503, 504]
    assert r.respect_retry_after is True
    assert r.template == "retry/jittered_retry.py.jinja"
```

Append to `tests/test_productconfig.py`:
```python
def test_retry_default_on(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8")
    (d / "sdk.yml").write_text("package: acme\noutput: ../acme-sdk\nbase_url: https://api/\n", "utf-8")
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.retry is not None          # on by default
    assert loaded.context["has_retry"] is True
    assert loaded.retry.max_retries == 3


def test_retry_disabled(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8")
    (d / "sdk.yml").write_text(
        "package: acme\noutput: ../acme-sdk\nbase_url: https://api/\nretry: false\n", "utf-8"
    )
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.retry is None
    assert loaded.context["has_retry"] is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml pytest tests/test_config.py tests/test_productconfig.py -k retry -q`
Expected: FAIL — `ImportError: cannot import name 'RetryConfig'`.

- [ ] **Step 3a: Add `RetryConfig` + registry to `config.py`**

```python
class RetryConfig(_Component):
    """Retry policy with jitter (urllib3.Retry subclass) — on by default."""

    max_retries: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 8.0
    jitter_frac: float = 0.25
    statuses: list[int] = [408, 429, 500, 502, 503, 504]
    respect_retry_after: bool = True
    template: str = "retry/jittered_retry.py.jinja"
```
Add the registry near the others: `BUILTIN_RETRY = {"default": RetryConfig}`.

- [ ] **Step 3b: Wire `retry` into `productconfig.py`**

(a) Import `BUILTIN_RETRY` in the `from .config import (...)` block.
(b) On `ProductConfig`, add: `retry: bool | dict[str, Any] = True` (default-on; place with `facade`).
(c) On `LoadedProduct`, add a field: `retry: Any | None`.
(d) In `load_product`, resolve it like `facade` (default-on). After the `facade` resolution block, add:
```python
    retry = None
    if cfg.retry:
        block = {"type": "default"} if cfg.retry is True else dict(cfg.retry)
        block.setdefault("type", "default")
        retry = resolve_component(block, BUILTIN_RETRY, base_dir)
```
(e) Add `"has_retry": retry is not None,` to the `context` dict; and pass `retry=retry` to the `LoadedProduct(...)` constructor.

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml pytest tests/test_config.py tests/test_productconfig.py -q`
Expected: PASS (all, including the existing tests).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/config.py src/phantasos/productconfig.py tests/test_config.py tests/test_productconfig.py
git commit -m "feat(retry): RetryConfig component, default-on, has_retry context"
```

---

### Task 2: `JitteredRetry` template + vendor it

**Files:** Create `src/phantasos/components/retry/jittered_retry.py.jinja`; Modify `src/phantasos/render.py`; Test `tests/test_render.py`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_render.py`)

```python
def test_vendor_writes_retry(tmp_path: Path) -> None:
    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8")
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\nfacade: false\n", "utf-8"
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded)
    assert "retry.py" in written
    src = (pkg / "extras" / "retry.py").read_text()
    assert "class JitteredRetry" in src and "def default_retry" in src
    assert "status_forcelist=[408, 429, 500, 502, 503, 504]" in src
    import ast
    ast.parse(src)  # valid Python
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_render.py -k retry -q`
Expected: FAIL — `retry.py` not written.

- [ ] **Step 3a: Create `src/phantasos/components/retry/jittered_retry.py.jinja`**

```jinja
"""Retry with jitter (vendored by phantasos). Subclasses urllib3's Retry; jitter is
applied in get_backoff_time(); Retry-After handling stays urllib3's."""

from __future__ import annotations

import random

from urllib3.util.retry import Retry

__all__ = ["JitteredRetry", "default_retry"]


class JitteredRetry(Retry):
    """urllib3 Retry with cloudflare-style multiplicative jitter on the backoff."""

    backoff_base = {{ backoff_base }}
    backoff_max = {{ backoff_max }}
    jitter_frac = {{ jitter_frac }}

    def get_backoff_time(self) -> float:
        consecutive = len([h for h in self.history if h.redirect_location is None])
        if consecutive <= 1:
            return 0.0
        exp = min(self.backoff_base * (2 ** (consecutive - 1)), self.backoff_max)
        return exp * (1 - self.jitter_frac * random.random())


def default_retry() -> JitteredRetry:
    """The SDK's default retry policy (on by default, wired by the facade/auth)."""
    return JitteredRetry(
        total={{ max_retries }},
        status_forcelist={{ statuses }},
        allowed_methods=None,
        respect_retry_after_header={{ respect_retry_after }},
        raise_on_status=False,
    )
```
(`{{ statuses }}` renders a Python list literal; `{{ respect_retry_after }}` renders `True`/`False`. The jitter params are class attributes so urllib3's `new()`/clone preserves them.)

- [ ] **Step 3b: Vendor it in `render.vendor`** — in `src/phantasos/render.py`, after the `if loaded.facade:` block (and before the `include` loop), add:
```python
    if loaded.retry:
        write_component("retry.py", loaded.retry)
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_render.py -k retry -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/components/retry src/phantasos/render.py tests/test_render.py
git commit -m "feat(retry): JitteredRetry template vendored to extras/retry.py"
```

---

### Task 3: OAG `exceptions.mustache` override (Tier 2) + `-t` plumbing

**Files:** Create `src/phantasos/oag_templates/python/exceptions.mustache`; Modify `src/phantasos/generate.py`, `pyproject.toml`; Test `tests/test_generate.py`.

- [ ] **Step 1: Extract OAG's base `exceptions.mustache`**

Run (uses the auto-provisioned Java + the pinned jar):
```bash
JAR=$(ls ~/.cache/phantasos/openapi-generator-cli-*.jar | head -1)
JAVA=$(ls ~/.cache/phantasos/temurin-*/bin/java | head -1)
rm -rf /tmp/oagtpl && "$JAVA" -jar "$JAR" author template -g python -o /tmp/oagtpl
mkdir -p src/phantasos/oag_templates/python
cp /tmp/oagtpl/exceptions.mustache src/phantasos/oag_templates/python/exceptions.mustache
```

- [ ] **Step 2: Edit the override — add `RateLimitException` + helpers + 429 dispatch**

In `src/phantasos/oag_templates/python/exceptions.mustache`:

(a) **Add the 429 branch** in `ApiException.from_response`, immediately after the `422` block and before the `if 500 <= http_resp.status <= 599:` line:
```python
        if http_resp.status == 429:
            raise RateLimitException(http_resp=http_resp, body=body, data=data)

```

(b) **Add `RateLimitException` + parse helpers** — place them right after the `ApiException` class's `__str__` method ends (i.e. just before the `class BadRequestException(ApiException):` line):
```python
def _phantasos_retry_after(headers) -> "Optional[float]":
    import email.utils
    import time

    if not headers:
        return None
    try:
        val = headers.get("Retry-After")
    except AttributeError:
        return None
    if val is None:
        return None
    val = str(val).strip()
    if val.isdigit():
        return float(val)
    dt = email.utils.parsedate_to_datetime(val)
    if dt is None:
        return None
    return max(0.0, dt.timestamp() - time.time())


def _phantasos_reset(headers) -> "Optional[float]":
    import time

    if not headers:
        return None
    try:
        val = headers.get("X-RateLimit-Reset")
    except AttributeError:
        return None
    if val is None:
        return None
    try:
        return max(0.0, float(val) - time.time())
    except (TypeError, ValueError):
        return None


class RateLimitException(ApiException):
    """Raised on HTTP 429. `retry_after`/`reset` (seconds) parsed from response headers."""

    def __init__(self, http_resp=None, body=None, data=None) -> None:
        super().__init__(http_resp=http_resp, body=body, data=data)
        self.retry_after = _phantasos_retry_after(self.headers)
        self.reset = _phantasos_reset(self.headers)


```
(`Optional` is already imported in the OAG exceptions template; the `import email.utils/time` are local to the helpers to avoid touching the template's import block.)

- [ ] **Step 3: Plumb `-t` into `generate.py`** — write the failing test first (append to `tests/test_generate.py`):
```python
def test_generate_cmd_uses_template_dir() -> None:
    from phantasos import generate

    cmd = generate._oag_cmd("spec.yaml", "/out", "pkg", "urllib3")
    assert "-t" in cmd
    i = cmd.index("-t")
    assert cmd[i + 1].endswith("oag_templates/python")
```
Run it (FAIL — no `_oag_cmd`). Then refactor `generate.generate` to build the command via a `_oag_cmd(spec_path, out_dir, package, library) -> list[str]` helper that returns the list, and have `generate()` call `subprocess.run(_oag_cmd(...), ...)`. Add to `_oag_cmd` the `-t` flag:
```python
_OAG_TEMPLATES = Path(__file__).parent / "oag_templates" / "python"


def _oag_cmd(spec_path: str, out_dir: str, package: str, library: str) -> list[str]:
    return [
        str(provision.resolve_java()),
        "-jar",
        str(ensure_jar()),
        "generate",
        "-g",
        "python",
        "-t",
        str(_OAG_TEMPLATES),
        "-i",
        spec_path,
        "-o",
        out_dir,
        "--package-name",
        package,
        "--additional-properties",
        f"library={library},disallowAdditionalPropertiesIfNotPresent=false",
        "--global-property",
        "modelDocs=false,apiDocs=false,modelTests=false,apiTests=false",
        "--inline-schema-options",
        "RESOLVE_INLINE_ENUMS=true",
    ]
```
And `generate()` becomes:
```python
def generate(spec_path: str, out_dir: str, package: str, library: str = "urllib3") -> None:
    subprocess.run(_oag_cmd(spec_path, out_dir, package, library), check=True, stdout=subprocess.DEVNULL)  # noqa: S603
```

- [ ] **Step 4: Ship templates as package data** — in `pyproject.toml` `[tool.hatch.build.targets.wheel]`, add `"src/phantasos/oag_templates/**"` to the `artifacts` list.

- [ ] **Step 5: Run to verify**

Run:
```bash
PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_generate.py -k "template_dir or ignore" -q
grep -c "class RateLimitException" src/phantasos/oag_templates/python/exceptions.mustache
grep -c "status == 429" src/phantasos/oag_templates/python/exceptions.mustache
```
Expected: tests PASS; both greps print `1`.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/oag_templates src/phantasos/generate.py pyproject.toml tests/test_generate.py
git commit -m "feat(exceptions): OAG exceptions.mustache override — RateLimitException + 429 dispatch; -t plumbing"
```

---

### Task 4: `errors` component re-exports `RateLimitException`; drop `is_rate_limited`

**Files:** Modify `src/phantasos/components/errors/nested_error.py.jinja`, `src/phantasos/components/extras_init.py.jinja`; Test `tests/test_render.py`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_render.py`)

```python
def test_errors_exports_ratelimit_not_helper(tmp_path: Path) -> None:
    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8")
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\nerrors: {type: nested}\nfacade: false\n",
        "utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    render.vendor(pkg, loaded)
    src = (pkg / "extras" / "errors.py").read_text()
    assert "RateLimitException" in src
    assert "is_rate_limited" not in src
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_render.py -k ratelimit_not_helper -q`
Expected: FAIL.

- [ ] **Step 3a: Edit `errors/nested_error.py.jinja`** — add `RateLimitException` to the import from `..exceptions` and to `__all__`; **remove** the `is_rate_limited` function and its `__all__` entry. The import block becomes:
```python
from ..exceptions import (  # noqa: F401  (re-exported)
    ApiException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    RateLimitException,
    ServiceException,
    UnauthorizedException,
)
```
`__all__` becomes (drop `is_rate_limited`, add `RateLimitException`):
```python
__all__ = [
    "ApiException",
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "RateLimitException",
    "ServiceException",
    "error_message",
]
```
Delete the entire `def is_rate_limited(exc): ...` function. Keep `error_message`.

- [ ] **Step 3b: Edit `extras_init.py.jinja`** — in the `{% if has_errors %}` import block, add `RateLimitException` and remove `is_rate_limited`; do the same in `__all__`. Also add a `{% if has_retry %}` block re-exporting retry:
```jinja
{% if has_retry %}
from .retry import JitteredRetry, default_retry
{% endif %}
```
and in `__all__`:
```jinja
{% if has_retry %}    "JitteredRetry", "default_retry",
{% endif %}
```
In the errors block of `__all__`, replace `"is_rate_limited", "error_message",` with `"RateLimitException", "error_message",`.

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_render.py -q`
Expected: PASS (all render tests).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/components/errors src/phantasos/components/extras_init.py.jinja tests/test_render.py
git commit -m "feat(errors): re-export RateLimitException; drop is_rate_limited; retry re-exports"
```

---

### Task 5: `auth` + `facade` consume the shared `default_retry()`

**Files:** Modify `src/phantasos/components/auth/oauth_client_credentials.py.jinja`, `src/phantasos/components/facade/client.py.jinja`; Test `tests/test_render.py`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_render.py`)

```python
def test_auth_and_facade_use_default_retry(tmp_path: Path) -> None:
    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text(
        "from acme.api.things_api import ThingsApi\n", encoding="utf-8"
    )
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8")
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\n"
        "auth: {type: oauth_client_credentials, token_url: 'https://t/'}\nfacade: true\n",
        "utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    render.vendor(pkg, loaded)
    auth_src = (pkg / "extras" / "auth.py").read_text()
    facade_src = (pkg / "extras" / "facade.py").read_text()
    assert "from .retry import default_retry" in auth_src
    assert "default_retry()" in auth_src
    assert "from .retry import default_retry" in facade_src
    assert "default_retry()" in facade_src
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_render.py -k default_retry -q`
Expected: FAIL.

- [ ] **Step 3a: Edit `auth/oauth_client_credentials.py.jinja`** — replace the private `_retry()` with the shared one. Remove the `_RETRY_STATUSES = {{ retry_statuses }}` line and the entire `def _retry(retries): ...` function. Add near the top imports a guarded import:
```jinja
{% if has_retry %}from .retry import default_retry
{% endif %}
```
In both `api_client_from_credentials` and `api_client_from_env`, replace `cfg.retries = _retry(retries)` with:
```jinja
{% if has_retry %}    cfg.retries = default_retry()
{% endif %}
```
(Drop the now-unused `retries: int = 3` parameter from both signatures, and any `import urllib3` only used by `_retry` — keep `urllib3` if still referenced elsewhere; verify by rendering.)

- [ ] **Step 3b: Edit `facade/client.py.jinja`** — wire retry into the client config. Add the guarded import near the top:
```jinja
{% if has_retry %}from .retry import default_retry
{% endif %}
```
In `Client.__init__`, after `self._api_client = api_client`, default the retry on the client's configuration when not already set:
```jinja
{% if has_retry %}        if getattr(api_client.configuration, "retries", None) is None:
            api_client.configuration.retries = default_retry()
{% endif %}
```
(The OAG `ApiClient` exposes `.configuration`; setting `.retries` before requests are made applies on the next pool build. The auth path already set it, so the `is None` guard avoids overriding it.)

- [ ] **Step 4: Run to verify it passes (and the full render suite)**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_render.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/components/auth src/phantasos/components/facade tests/test_render.py
git commit -m "feat(retry): auth + facade consume the shared default_retry()"
```

---

### Task 6: Scaffold tests — update `test_errors`, add `test_retry`

**Files:** Modify `src/phantasos/scaffold/tests/test_errors.py.jinja`; Create `src/phantasos/scaffold/tests/test_retry.py.jinja`; Test `tests/test_scaffold.py`.

- [ ] **Step 1: Update `scaffold/tests/test_errors.py.jinja`** — replace the `is_rate_limited` assertion with a `RateLimitException` one. The body (still gated `{% if has_errors %}`) asserts:
```jinja
{% if has_errors %}"""Errors component smoke tests (generated)."""

from {{ package }}.exceptions import ApiException
from {{ package }}.extras import errors


def test_errors_helpers() -> None:
    assert callable(errors.error_message)
    assert issubclass(errors.RateLimitException, ApiException)
{% endif %}```
(Keep the `{% if %}` as the first/last chars with no surrounding newline — the empty-render-skip gating.)

- [ ] **Step 2: Create `scaffold/tests/test_retry.py.jinja`** (gated on `has_retry`). It asserts the runtime shape of the rendered SDK's retry, **without** referencing the retry config numbers (those live on `loaded.retry`/`model_dump`, not in the scaffold's `loaded.context`, so don't template them here — keep the scaffold test self-contained):
```jinja
{% if has_retry %}"""Retry component smoke tests (generated)."""

from {{ package }}.extras.retry import JitteredRetry, default_retry


def test_default_retry_config() -> None:
    r = default_retry()
    assert isinstance(r, JitteredRetry)
    assert r.total >= 1
    assert 429 in r.status_forcelist


def test_jitter_attrs() -> None:
    assert JitteredRetry.backoff_max > 0
    assert 0.0 <= JitteredRetry.jitter_frac < 1.0
{% endif %}```
(NOTE: the **component** template `jittered_retry.py.jinja` *does* get `max_retries`/`statuses`/etc. — `render.vendor`'s `write_component` passes the retry component's `model_dump()` fields into the render. Only the **scaffold** renderer uses `loaded.context`, which doesn't carry them; hence the scaffold test avoids templating those numbers. No context-flattening is needed.)

- [ ] **Step 3: Add a gating assertion to `tests/test_scaffold.py`** (append):
```python
def test_scaffold_retry_test_gated(tmp_path: Path) -> None:
    base = {"distribution": "acme-sdk", "description": "d", "license": "Apache-2.0",
            "author": "A", "author_email": "a@b.c", "repo_url": "https://x/y",
            "package": "acme", "dependencies": ["pydantic"], "python_versions": ["3.12"],
            "config_class_name": "AcmeConfiguration",
            "max_retries": 3, "backoff_base": 0.5, "backoff_max": 8.0,
            "jitter_frac": 0.25, "statuses": [429], "respect_retry_after": True,
            "has_auth": True, "has_pagination": True, "has_errors": True, "has_facade": True}
    out_on = tmp_path / "on"; out_on.mkdir()
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out_on, {**base, "has_retry": True})
    assert (out_on / "tests" / "test_retry.py").exists()
    out_off = tmp_path / "off"; out_off.mkdir()
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out_off, {**base, "has_retry": False})
    assert not (out_off / "tests" / "test_retry.py").exists()
```

- [ ] **Step 4: Run to verify**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_scaffold.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/scaffold/tests tests/test_scaffold.py
git commit -m "feat(scaffold): RateLimitException + JitteredRetry component tests"
```

---

### Task 7: Full verification (lint/mypy + e2e + the real proof)

**Files:** none (verification + any fixes).

- [ ] **Step 1: Lint + mypy + unit suite**

Run:
```bash
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox --envdir $HOME/.nox-phantasos -s lint type_check
PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 --with urllib3 --with python-dateutil --with typing_extensions pytest tests/ -q -p no:cacheprovider
```
Expected: lint + mypy clean; all unit tests pass. Fix any issues in the new code.

- [ ] **Step 2: Build both example SDKs (default-on retry; no sdk.yml change needed)**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox --envdir $HOME/.nox-phantasos -s smoke`
Expected: both build, 0 smoke failures.

- [ ] **Step 3: Confirm the generated SDK has the new capabilities**

Run:
```bash
SDK=/home/ubuntu/git/prisma-browser-sdk/prisma_browser
grep -c "class RateLimitException" $SDK/exceptions.py        # expect 1 (Tier-2 template)
grep -c "status == 429" $SDK/exceptions.py                   # expect 1 (dispatch)
grep -c "class JitteredRetry" $SDK/extras/retry.py           # expect 1 (Tier-1)
grep -c "default_retry" $SDK/extras/auth.py $SDK/extras/facade.py  # expect 1 each
grep -c "is_rate_limited" $SDK/extras/errors.py || echo "is_rate_limited gone (good)"
```
Expected: the `RateLimitException`/`JitteredRetry`/`default_retry` greps are `1`; `is_rate_limited` is gone.

- [ ] **Step 4: Behavioral proof — import-check the generated SDK + the regenerated suite**

Run:
```bash
cd /home/ubuntu/git/prisma-browser-sdk
uv run --no-project --python 3.12 --with pytest --with urllib3 --with python-dateutil --with pydantic --with typing-extensions \
  python -c "from prisma_browser.exceptions import RateLimitException, ApiException; assert issubclass(RateLimitException, ApiException); from prisma_browser.extras.retry import default_retry; r=default_retry(); assert r.total==3 and 429 in r.status_forcelist; print('OK: RateLimitException + JitteredRetry wired')"
uv run --no-project --python 3.12 --with pytest --with urllib3 --with python-dateutil --with pydantic --with typing-extensions pytest tests/ -q -p no:cacheprovider
cd -
```
Expected: prints `OK: …`; the regenerated SDK's own suite (now testing `RateLimitException` + retry) passes.

- [ ] **Step 5: Final review vs. spec + CLAUDE.md**

Confirm: retry is Tier 1 (`extras/retry.py`), 429 is Tier 2 (`exceptions.py` via template — generated code only via OAG `-t`), no `patches.py`/runtime-proxy hacks were added, `is_rate_limited` is gone. If green, the feature is complete and consistent with `CLAUDE.md`.

---

## Notes for the executor

- **No facade proxy, no patches.py.** 429 dispatch is the OAG template (`exceptions.mustache`) — generated code is touched *only* through OAG's own `-t` mechanism, per `CLAUDE.md` Tier 2. Do not add a runtime proxy.
- **Context must carry the retry fields** (`max_retries`, `backoff_base`, `backoff_max`, `jitter_frac`, `statuses`, `respect_retry_after`) — `jittered_retry.py.jinja` and the scaffold `test_retry` reference them. Flatten them in `load_product` (Task 1/Task 6 note) and add to `_AUTO_EXPOSED`.
- **`-t` with one file is safe:** OAG falls back to its built-in templates for every file not in the dir (verified). The build's other generated files are unchanged.
- **Filesystem note (sandbox):** use `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos` for `uv run`/nox; the JRE+jar live under `~/.cache/phantasos`.
