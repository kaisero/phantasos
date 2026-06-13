# Onboarding a new SDK

This guide walks through adding a brand-new product to phantasos from scratch.

---

## 1. Create the product directory

```
products/<name>/
├── openapi.yml                    # OpenAPI source document
├── sdk.yml                        # build config (see below)
├── overrides/
│   ├── README.md.jinja            # required — README for the generated SDK
│   └── tests/                     # optional — per-product integration/contract tests
│       └── test_<something>.py.jinja
└── hooks.py                       # optional — Python preprocessing / patch hooks
```

Only `openapi.yml`, `sdk.yml`, and `overrides/README.md.jinja` are required.

---

## 2. Write `sdk.yml`

### Required core fields

```yaml
package: my_sdk          # Python package name (snake_case)
output: ../../../my-sdk  # where to write the SDK (relative to sdk.yml)
base_url: https://api.example.com
```

### `project:` block (required for a scaffold)

The `project:` block drives `pyproject.toml`, GitHub workflows, docs config, and
other scaffold files written into the generated SDK:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `distribution` | yes | — | PyPI distribution name, e.g. `my-sdk` |
| `author` | yes | — | Author full name |
| `author_email` | yes | — | Author email |
| `repo_url` | yes | — | GitHub repo URL, e.g. `https://github.com/org/my-sdk` |
| `description` | no | `""` | One-line package description |
| `license` | no | `"Apache-2.0"` | SPDX licence identifier |
| `python_versions` | no | `["3.11","3.12","3.13","3.14"]` | Tested Python versions |
| `dependencies` | no | see below | Runtime deps for `pyproject.toml` |

Minimal example:

```yaml
project:
  distribution: my-sdk
  description: Python SDK for the My API
  author: Jane Smith
  author_email: jane@example.com
  repo_url: https://github.com/org/my-sdk
```

### Runtime dependencies (`project.dependencies`)

The scaffold's built-in default is correct for virtually every `library: urllib3` SDK:

```
urllib3 >= 2.1.0, < 3.0.0
python-dateutil >= 2.8.2
pydantic >= 2.11
typing-extensions >= 4.7.1
```

**You almost never need to set this field.** Only override it if the SDK genuinely
needs extra or different deps. If you're unsure what deps OAG would emit, you can
temporarily remove the `.openapi-generator-ignore` suppression, run OAG once to
read the `requirements.txt` it produces, then restore the ignore file and set
`project.dependencies` accordingly. A smoke failure citing a missing import is also
an acceptable signal to add a dep — it does not block you from proceeding.

### Other common fields

```yaml
auth:
  type: oauth_client_credentials
  token_url: https://auth.example.com/oauth2/token
pagination: {type: cursor}
errors: {type: nested}
facade: true
```

Full field reference: [`docs/AUTHORING_A_SPEC.md`](AUTHORING_A_SPEC.md).

---

## 3. Write `overrides/README.md.jinja`

This is the only mandatory override. It becomes the `README.md` of the generated SDK.
The Jinja context includes all `sdk.yml` fields plus the standard phantasos variables
(`package`, `base_url`, `spec_title`, `has_auth`, etc.).

```jinja
# {{ project.distribution }}

{{ project.description }}

## Installation

```bash
pip install {{ project.distribution }}
```
...
```

---

## 4. Build

```bash
phantasos sdk build <name>
```

phantasos will:
1. Pre-process the spec (generic transforms + `transforms:` block + `hooks.py::preprocess`).
2. Run OpenAPI Generator (OAG's own `setup.py`, `requirements.txt`, `tox.ini`, and CI
   are suppressed via `.openapi-generator-ignore`).
3. Apply generic patches (apostrophe-enum, lenient-enum, oneOf first-match).
4. Vendor component templates into `<package>/extras/`.
5. Render the full project scaffold (see next section).
6. Smoke-install and import-check the SDK in an isolated venv.

---

## 5. What the scaffold produces

phantasos renders a complete, phantasos-grade project around the generated package:

| Source | Description |
|--------|-------------|
| `src/phantasos/scaffold/` | Built-in templates: `pyproject.toml`, `noxfile.py`, `.pre-commit-config.yaml`, 6 GitHub workflows (ci / release / audit / secrets / codeql / docs), `mkdocs.yml`, `.gitignore`, `.editorconfig`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, gated component tests |
| `products/<name>/overrides/` | Per-product overrides — any file at the same relative path replaces the built-in scaffold file; `README.md.jinja` is required |

Files in `overrides/` win over the built-in scaffold (same-path-wins). Per-product tests
placed under `overrides/tests/` are rendered alongside the gated scaffold tests.

---

## 6. Never hand-edit the generated SDK

**The generated SDK is a pure build artifact.** Every file in it — including tests,
`pyproject.toml`, workflows, and `README.md` — is regenerated on every `phantasos sdk build`.
All customisation must live in one of two places that are version-controlled:

- `products/<name>/` — spec, build config, README template, per-product tests, hooks
- `src/phantasos/scaffold/` — built-in scaffold templates shared across all products

Nothing can be lost across regenerations because nothing lives in the SDK itself.
