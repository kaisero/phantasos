# sdkgen

Generate native, self-contained Python SDKs from OpenAPI specs. `sdkgen` wraps
[OpenAPI Generator](https://openapi-generator.tech/) and adds generic spec
preprocessing, codegen-bug patches, and vendored, templated components (auth,
pagination, errors, a resource facade) selected per spec.

## Install

```bash
pip install -e ".[generated]"
```

## Build an SDK

```bash
sdkgen build transformations/prisma-browser.py
```

See the [Authoring guide](AUTHORING_A_SPEC.md) to onboard a new spec, the
[Architecture](ARCHITECTURE.md) for the design, and the
[API Reference](reference.md) for the `sdkgen` package.
