# phantasos

Generate native, self-contained Python SDKs and command-line tools from OpenAPI
specs. `phantasos` wraps [OpenAPI Generator](https://openapi-generator.tech/) and
adds generic spec preprocessing, codegen-bug patches, vendored components (auth,
pagination, errors, a resource facade), and a complete project scaffold — so the
output is a real, shippable package, not just `models/` and `api/`.

## Install

```bash
pip install -e .
```

## Build an SDK and CLI

```bash
phantasos sdk build <product>    # SDK from products/<product>
```

```bash
phantasos cli build <product>    # matching CLI from the built SDK
```

## Generate SDK documentation

Generated SDKs can ship their own documentation site — guides for authentication,
pagination, and CRUD, plus an API reference auto-generated from the emitted
docstrings. Opt in by adding a `docs:` block to the product's `sdk.yml`:

```yaml
docs:
  showcase_resource: applications   # the resource whose CRUD drives the examples
```

`phantasos sdk build <product>` then scaffolds the site inside the generated SDK.
Build it from the SDK directory:

```bash
cd ../my-product-sdk
uv run nox -s docs        # strict mkdocs build
```

See **[Authoring a product → `docs:`](authoring.md#docs)** for the full field
reference.

## Where to next

- **[Architecture](architecture.md)** — what phantasos is, its scope, and how the
  two-stage build works (with diagrams).
- **[Authoring a product](authoring.md)** — create a `products/<name>/` directory
  and configure a build, end to end.
- **[CLI reference](cli-reference.md)** — the host commands and their flags.
- **[Development](development.md)** — contribute to phantasos: branching, tests,
  CI/CD, and running the nox task runner.
