# CLI reference

The `phantasos` host CLI drives both build stages. Every command takes a
**product** — either a name (resolved to `products/<name>/sdk.yml` from the
current directory) or a direct path to an `sdk.yml` file.

## `phantasos sdk build <product>`

Build a Python SDK from the product's `sdk.yml`.

| Flag | Description |
|------|-------------|
| `--no-smoke` | Skip the post-build import/smoke check (useful for offline or locked-down builds). |

```bash
phantasos sdk build prisma-browser
phantasos sdk build products/prisma-browser/sdk.yml --no-smoke
```

## `phantasos cli discover <product>`

Introspect the built SDK and print the operation → command classification table.
Requires the SDK to have been built first.

| Flag | Description |
|------|-------------|
| `--write-stub` | Also write a `cli.yml.stub` next to `sdk.yml` to seed CLI customization. |

```bash
phantasos cli discover prisma-browser --write-stub
```

## `phantasos cli build <product>`

Emit a full Typer + Rich CLI project from the built SDK. Prints the file count
and command count on success. Requires a `project:` block in `sdk.yml` or `cli.yml`.

```bash
phantasos cli build prisma-browser
```

Run `phantasos --help` (or `phantasos <command> --help`) for the authoritative,
always-current flag list.
