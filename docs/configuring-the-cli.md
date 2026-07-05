# Configuring the generated CLI

A `cli build`-generated CLI reads its settings from a layered config: packaged
defaults ← `~/.<distribution>/config.yml` ← `.env`/shell env ← per-invocation
flags. This page documents one knob in that file: the **auth token cache**,
available on any generated CLI whose product has credentials (an auth
component in `sdk.yml`). For the full config-file schema see the emitted
`config.yml`'s comments (written by `<dist> config init`); for the host
`phantasos` build commands see [CLI reference](cli-reference.md).

## Token cache

An authenticating CLI re-authenticates on every invocation by default — the
token cache avoids that by persisting the SDK's OAuth access token to disk and
reusing it across commands, refreshing only on expiry or a `401`.

### The `cache:` knob

```yaml
configuration:
  cache:
    enabled: true
    # null -> ~/.<distribution>/cache/
    dir: null
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Cache the OAuth token across runs. Set `false` to re-authenticate every command. |
| `dir` | string \| `null` | `null` (→ `~/.<distribution>/cache/`) | Directory the token files are written under. |

### Environment variables

| Variable | Overrides |
|----------|-----------|
| `<PREFIX>_CACHE_ENABLED` | `configuration.cache.enabled` |
| `<PREFIX>_CACHE_DIR` | `configuration.cache.dir` |

(`<PREFIX>` is the CLI's env-var prefix, e.g. `PRISMA` for prisma-browser.)

### File location and permissions

Each distinct principal (token URL + client ID + scope) gets its own file:
`~/.<distribution>/cache/token-<key>.json`, written `0600`. The cache directory
itself is created `0700` on first write. A command that only reads the cache
(e.g. `show cli cache`) never creates the directory.

### Commands

- **`<dist> show cli cache`** — lists cached entries (key + expiry) without
  ever printing a token value.
- **`<dist> config cache-clear`** — deletes every cached token file.

### Security note

The cached file holds a short-lived bearer JWT — **never** the client
secret — but it is still a live credential for as long as it's valid. It's
written `0600` and the containing directory `0700`, but if that's still more
exposure than you want:

- Opt out entirely with `<PREFIX>_CACHE_ENABLED=false` (or `cache.enabled: false`
  in `config.yml`); the CLI re-authenticates every command instead.
- Consider excluding `~/.<distribution>/cache/` from dotfile backups or cloud
  sync tooling, the same way you would `~/.ssh/` or `~/.aws/credentials`.
