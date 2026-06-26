"""Tests for sdk.yml parsing, validation, and the loader."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from phantasos.config import ScmOAuth
from phantasos.productconfig import (
    Hoist,
    ProductConfig,
    TagOperation,
    Transforms,
    load_product,
    resolve_component,
)


def test_productconfig_minimal() -> None:
    cfg = ProductConfig(package="acme", output="../acme-sdk", base_url="https://api/")
    assert cfg.generator.library == "urllib3"
    assert cfg.apply_generic_patches is True
    assert cfg.transforms == Transforms()


def test_generator_block_defaults() -> None:
    cfg = ProductConfig(package="acme", output="../acme-sdk", base_url="https://api/")
    assert cfg.generator.library == "urllib3"
    assert cfg.generator.oneof_discriminator_lookup is True


def test_generator_block_overrides() -> None:
    cfg = ProductConfig.model_validate(
        {
            "package": "acme",
            "output": "../acme-sdk",
            "base_url": "https://api/",
            "generator": {"library": "httpx", "oneof_discriminator_lookup": False},
        }
    )
    assert cfg.generator.library == "httpx"
    assert cfg.generator.oneof_discriminator_lookup is False


def test_top_level_library_rejected() -> None:
    # `library` migrated into the generator: block (2026-06-11); extra=forbid rejects it
    with pytest.raises(ValidationError):
        ProductConfig.model_validate(
            {"package": "a", "output": "o", "base_url": "b", "library": "httpx"}
        )


def test_transforms_parse() -> None:
    cfg = ProductConfig.model_validate(
        {
            "package": "acme",
            "output": "../acme-sdk",
            "base_url": "https://api/",
            "transforms": {
                "hoist": [{"schema": "S", "field": "f", "item": "I"}],
                "tag_operations": [
                    {"path": "/x", "method": "get", "operation_id": "GetX", "tag": "X"}
                ],
            },
        }
    )
    assert cfg.transforms.hoist == [Hoist(schema="S", field="f", item="I")]
    assert cfg.transforms.tag_operations[0] == TagOperation(
        path="/x", method="get", operation_id="GetX", tag="X"
    )


def test_unknown_top_level_key_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductConfig.model_validate(
            {"package": "a", "output": "o", "base_url": "b", "pagintion": {}}  # typo
        )


def test_resolve_builtin_auth() -> None:
    from phantasos.config import BUILTIN_AUTH

    c = resolve_component(
        {"type": "scm_oauth"},
        BUILTIN_AUTH,
        base_dir=Path(),
    )
    assert isinstance(c, ScmOAuth)
    assert c.token_url == "https://auth.apps.paloaltonetworks.com/oauth2/access_token"


def test_resolve_custom_path(tmp_path: Path) -> None:
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


def test_resolve_missing_custom_path(tmp_path: Path) -> None:
    from phantasos.config import BUILTIN_AUTH

    with pytest.raises(ValueError, match="template not found"):
        resolve_component(
            {"type": "./templates/missing.jinja"}, BUILTIN_AUTH, base_dir=tmp_path
        )


def test_resolve_unknown_builtin() -> None:
    from phantasos.config import BUILTIN_AUTH

    with pytest.raises(ValueError, match=r"unknown.*type"):
        resolve_component({"type": "magic"}, BUILTIN_AUTH, base_dir=Path())


_SDK_YML = """\
package: acme
output: ../acme-sdk
base_url: https://api.example.com
auth: {type: scm_oauth}
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
    assert isinstance(loaded.auth, ScmOAuth)
    assert (
        loaded.auth.token_url
        == "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
    )
    assert loaded.context["spec_version"] == "9.9.9"
    assert loaded.context["spec_title"] == "Acme"
    assert loaded.context["package"] == "acme"
    assert loaded.context["support_email"] == "sdk@example.com"
    assert loaded.context["has_auth"] is True
    assert loaded.context["library"] == "urllib3"


def test_load_product_by_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_product(tmp_path)
    monkeypatch.chdir(tmp_path)
    loaded = load_product("acme")
    assert loaded.config.package == "acme"


def test_load_product_missing_include_source(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8"
    )
    (d / "sdk.yml").write_text(
        "package: acme\noutput: o\nbase_url: b\n"
        "include: {x.py: ./templates/nope.jinja}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"template not found|not found"):
        load_product(str(d / "sdk.yml"))


def test_vars_collision_is_error(tmp_path: Path) -> None:
    d = _make_product(tmp_path)
    # A vars key that shadows an auto-exposed name (`package`) must error.
    (d / "sdk.yml").write_text(
        "package: acme\noutput: o\nbase_url: b\nvars: {package: oops}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"shadow|reserved"):
        load_product(str(d / "sdk.yml"))


def test_load_product_generator_library_httpx(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text(_OPENAPI, encoding="utf-8")
    (d / "sdk.yml").write_text(
        "package: acme\noutput: ../acme-sdk\nbase_url: https://api.example.com\n"
        "generator: {library: httpx}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.context["library"] == "httpx"


from phantasos.productconfig import ProjectConfig  # noqa: E402


def test_project_defaults() -> None:
    p = ProjectConfig(
        distribution="acme-sdk",
        author="A",
        author_email="a@b.c",
        repo_url="https://github.com/x/acme-sdk",
    )
    assert p.license == "Apache-2.0"
    assert p.python_versions == ["3.11", "3.12", "3.13", "3.14"]
    assert "pydantic >= 2.11" in p.dependencies


def test_retry_default_on(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8"
    )
    (d / "sdk.yml").write_text(
        "package: acme\noutput: ../acme-sdk\nbase_url: https://api/\n", "utf-8"
    )
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.retry is not None
    assert loaded.context["has_retry"] is True
    assert loaded.retry.max_retries == 3


def test_retry_disabled(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8"
    )
    (d / "sdk.yml").write_text(
        "package: acme\noutput: ../acme-sdk\nbase_url: https://api/\nretry: false\n",
        "utf-8",
    )
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.retry is None
    assert loaded.context["has_retry"] is False


def test_project_block_in_sdk_yml(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {title: Acme, version: '9'}\npaths: {}\n", "utf-8"
    )
    (d / "sdk.yml").write_text(
        "package: acme\noutput: ../acme-sdk\nbase_url: https://api/\n"
        "project: {distribution: acme-sdk, author: A, author_email: a@b.c, "
        "repo_url: https://github.com/x/acme-sdk}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.config.project is not None
    assert loaded.config.project.distribution == "acme-sdk"
    assert loaded.context["distribution"] == "acme-sdk"
    assert loaded.context["repo_url"] == "https://github.com/x/acme-sdk"
    assert loaded.context["license"] == "Apache-2.0"


from phantasos.productconfig import DocsConfig  # noqa: E402


def test_docs_config_defaults() -> None:
    d = DocsConfig(showcase_resource="applications")
    assert d.showcase_resource == "applications"
    assert d.site_name is None


def test_product_config_docs_absent_is_none() -> None:
    cfg = ProductConfig(package="p", output="o", base_url="https://x")
    assert cfg.docs is None


def test_product_config_docs_present() -> None:
    cfg = ProductConfig.model_validate(
        {
            "package": "p",
            "output": "o",
            "base_url": "https://x",
            "docs": {"showcase_resource": "applications"},
        }
    )
    assert cfg.docs is not None
    assert cfg.docs.showcase_resource == "applications"


def test_has_docs_in_context(tmp_path: Path) -> None:
    # Minimal product dir: sdk.yml + empty openapi.yml
    import textwrap

    (tmp_path / "openapi.yml").write_text("info: {title: T, version: '1'}\n")
    (tmp_path / "sdk.yml").write_text(
        textwrap.dedent("""
        package: p
        output: ./out
        base_url: https://x
        docs: {showcase_resource: applications}
        project: {distribution: p, author: A, author_email: a@b.c, repo_url: https://h/p}
    """)
    )
    from phantasos.productconfig import load_product

    loaded = load_product(str(tmp_path / "sdk.yml"))
    assert loaded.context["has_docs"] is True


def test_docs_examples_and_variant_parse() -> None:
    from phantasos.productconfig import DocsConfig

    cfg = DocsConfig.model_validate(
        {
            "showcase_resource": "applications",
            "showcase_variant": "CustomApplicationInput",
            "examples": {
                "create": "created = client.applications.create_application(...)"
            },
        }
    )
    assert cfg.showcase_variant == "CustomApplicationInput"
    assert cfg.examples is not None
    assert cfg.examples.create is not None
    assert cfg.examples.create.startswith("created =")
    assert cfg.examples.read is None


def test_federated_config_parses_subpackages() -> None:
    cfg = ProductConfig.model_validate(
        {
            "package": "prisma_access",
            "output": "../out",
            "base_url": "https://h",
            "project": {
                "distribution": "prisma-access-sdk",
                "author": "a",
                "author_email": "a@b.c",
                "repo_url": "https://x",
            },
            "subpackages": [
                {"slug": "objects", "spec": "openapi/objects.yaml"},
                {
                    "slug": "ztna_connector",
                    "spec": "openapi/ztna-connector.yaml",
                    "normalize_operation_ids": {
                        "strip_suffix": ".v2",
                        "dots_to_underscore": True,
                        "unify_separator": "_",
                    },
                },
            ],
        }
    )
    assert [s.slug for s in cfg.subpackages] == ["objects", "ztna_connector"]
    assert cfg.subpackages[1].normalize_operation_ids is not None
    assert cfg.subpackages[1].normalize_operation_ids.strip_suffix == ".v2"


def test_legacy_single_spec_still_parses() -> None:
    cfg = ProductConfig(
        package="prisma_browser",
        output="../out",
        base_url="https://h",
        spec="./openapi.yml",
    )
    assert cfg.subpackages == []
    assert cfg.spec == "./openapi.yml"


def test_cannot_set_both_spec_and_subpackages() -> None:
    with pytest.raises(ValidationError):
        ProductConfig.model_validate(
            {
                "package": "p",
                "output": "o",
                "base_url": "https://h",
                "spec": "./openapi.yml",
                "subpackages": [{"slug": "x", "spec": "x.yaml"}],
            }
        )


def test_federated_load_builds_per_sub_contexts(tmp_path: Path) -> None:
    (tmp_path / "openapi").mkdir()
    (tmp_path / "openapi" / "objects.yaml").write_text(
        "openapi: 3.0.0\ninfo: {title: Objects, version: '1.2.3'}\npaths: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "openapi" / "posture.yaml").write_text(
        "openapi: 3.0.0\ninfo: {title: Posture, version: '4.5.6'}\npaths: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "sdk.yml").write_text(
        "package: prisma_access\n"
        "output: ../out\n"
        "base_url: https://h\n"
        "project: {distribution: prisma-access-sdk, author: a, "
        "author_email: a@b.c, repo_url: https://x}\n"
        "subpackages:\n"
        "  - {slug: objects, spec: openapi/objects.yaml}\n"
        "  - {slug: posture, spec: openapi/posture.yaml}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(tmp_path / "sdk.yml"))
    assert loaded.context["package"] == "prisma_access"  # namespace root unchanged
    assert loaded.context["distribution"] == "prisma-access-sdk"
    assert loaded.spec_path is None  # B5: no top-level spec when federated
    subs = {s.config.slug: s for s in loaded.subpackages}
    assert subs["objects"].package == "prisma_access.objects"
    assert subs["objects"].context["package"] == "prisma_access.objects"
    assert subs["objects"].context["spec_title"] == "Objects"
    assert subs["objects"].context["spec_version"] == "1.2.3"
    assert subs["objects"].spec_path == (tmp_path / "openapi/objects.yaml").resolve()
    assert subs["posture"].context["spec_version"] == "4.5.6"


def test_rejects_bad_and_duplicate_slugs() -> None:  # rev-2: trust-boundary validation
    with pytest.raises(ValidationError):
        ProductConfig.model_validate(
            {
                "package": "p",
                "output": "o",
                "base_url": "https://h",
                # slug with a hyphen — rejected by the slug regex
                "subpackages": [{"slug": "network-services", "spec": "a.yaml"}],
            }
        )
    with pytest.raises(ValidationError):
        ProductConfig.model_validate(
            {
                "package": "p",
                "output": "o",
                "base_url": "https://h",
                "subpackages": [
                    {"slug": "objects", "spec": "a.yaml"},
                    {"slug": "objects", "spec": "b.yaml"},  # dup
                ],
            }
        )
