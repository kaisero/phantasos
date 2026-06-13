# phantasos

Generate Python SDKs and command-line tools from OpenAPI specs. `phantasos` wraps
[OpenAPI Generator](https://openapi-generator.tech/) and adds generic spec
preprocessing, codegen-bug patches, vendored components (auth, pagination,
errors, a resource facade) selected per spec, and a complete project scaffold.

## Install

```bash
pip install -e .
```

## Build an SDK and CLI

```bash
phantasos sdk build prisma-browser    # SDK from products/prisma-browser/
phantasos cli build prisma-browser    # CLI from the built SDK
```

See the [Authoring guide](AUTHORING_A_SPEC.md) to onboard a new spec, the
[Architecture](ARCHITECTURE.md) for the design, and the
[API Reference](reference.md) for the `phantasos` package.
