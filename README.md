<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/phantasos-logo-dark.svg">
    <img alt="phantasos" src="docs/images/phantasos-logo-light.svg">
  </picture>
</p>

<!-- pypi-readme-start -->

[![CI](https://github.com/kaisero/phantasos/actions/workflows/ci.yml/badge.svg)](https://github.com/kaisero/phantasos/actions/workflows/ci.yml)
[![Docs](https://github.com/kaisero/phantasos/actions/workflows/docs.yml/badge.svg)](https://kaisero.github.io/phantasos/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/kaisero/phantasos/blob/main/LICENSE)

Phantasos generates Python SDKs and command-line tools from OpenAPI specs for Palo Alto Networks products

You describe an API in a small `products/<name>/` folder. The OpenAPI spec plus a short `sdk.yml`. 
Phantasos runs [OpenAPI Generator](https://openapi-generator.tech/) and adds what the raw generator leaves out: 

* Spec cleanup,
* Fixes for known codegen bugs
* Ready-made auth
* Pagination
* Error handling
* Project Scaffold (tests, CI, docs)


From the built SDK you then generate a matching command-line interface. Each result is a 
standalone project that depends only on `httpx`, `urllib3` and `pydantic`.

## Quick start

```bash
git clone https://github.com/kaisero/phantasos && cd phantasos
pip install -e .

# generate an SDK from products/prisma-browser
phantasos sdk build prisma-browser

# generate a CLI from the built SDK
phantasos cli build prisma-browser
```

No Java setup needed: the first build downloads OpenAPI Generator and a pinned
JRE once into `~/.cache/phantasos`.

## Documentation

Guides, Configuration reference and architecture live at
**[kaisero.github.io/phantasos](https://kaisero.github.io/phantasos/)**.
