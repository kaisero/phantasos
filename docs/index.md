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
phantasos sdk build prisma-browser    # SDK from products/prisma-browser/
phantasos cli build prisma-browser    # matching CLI from the built SDK
```

## Where to next

- **[Architecture](architecture.md)** — what phantasos is, its scope, and how the
  two-stage build works (with diagrams).
- **[Authoring a product](authoring.md)** — create a `products/<name>/` directory
  and configure a build, end to end.
- **[CLI reference](cli-reference.md)** — the host commands and their flags.
