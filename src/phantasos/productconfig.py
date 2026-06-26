"""Load and validate a product's declarative sdk.yml into a ProductConfig."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass as _dataclass
from dataclasses import field
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import (
    BUILTIN_AUTH,
    BUILTIN_ERRORS,
    BUILTIN_FACADE,
    BUILTIN_PAGINATION,
    BUILTIN_RETRY,
    OperationOverride,
)

_BASE_DEPS = [
    "urllib3 >= 2.1.0, < 3.0.0",
    "python-dateutil >= 2.8.2",
    "pydantic >= 2.11",
    "typing-extensions >= 4.7.1",
]


def sdk_runtime_deps() -> list[str]:
    """The OAG-fixed runtime deps every generated SDK requires.

    Stable across regenerations; exposed so callers (e.g. the ``sdk-docs`` /
    ``live`` nox sessions) can pre-install them without depending on a built
    SDK's ``pyproject.toml``.
    """
    return list(_BASE_DEPS)


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    distribution: str
    author: str
    author_email: str
    repo_url: str
    description: str = ""
    license: str = "Apache-2.0"
    python_versions: list[str] = Field(
        default_factory=lambda: ["3.11", "3.12", "3.13", "3.14"]
    )
    dependencies: list[str] = Field(default_factory=lambda: list(_BASE_DEPS))


class DocsExamples(BaseModel):
    """Optional per-slot verbatim override of the showcase CRUD example block."""

    model_config = ConfigDict(extra="forbid")
    create: str | None = None
    read: str | None = None
    list: str | None = None
    update: str | None = None
    delete: str | None = None


class DocsConfig(BaseModel):
    """Opt-in user-documentation generation (sdk.yml `docs:` block)."""

    model_config = ConfigDict(extra="forbid")
    showcase_resource: str
    showcase_variant: str | None = None
    showcase_subpackage: str | None = None
    site_name: str | None = None
    examples: DocsExamples | None = None


class Hoist(BaseModel):
    # `schema` shadows a pydantic BaseModel attribute, so store it as schema_name
    # with a YAML alias of `schema`. populate_by_name lets tests pass either.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_name: str = Field(alias="schema")
    field: str
    item: str


class TagOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    method: str
    operation_id: str
    tag: str


class Transforms(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hoist: list[Hoist] = Field(default_factory=list)
    tag_operations: list[TagOperation] = Field(default_factory=list)


class GeneratorConfig(BaseModel):
    """OpenAPI Generator invocation options (sdk.yml `generator:` block)."""

    model_config = ConfigDict(extra="forbid")
    library: str = "urllib3"
    oneof_discriminator_lookup: bool = True


class NormalizeIds(BaseModel):
    """Per-sub operationId normalization (e.g. strip ``.v2``, dots->underscore)."""

    model_config = ConfigDict(extra="forbid")
    strip_suffix: str | None = None
    dots_to_underscore: bool = False
    unify_separator: str | None = None


class SubPackage(BaseModel):
    """One federated sub-package: its slug becomes a package/dir/import path."""

    model_config = ConfigDict(extra="forbid")
    slug: str
    spec: str
    normalize_operation_ids: NormalizeIds | None = None
    operations: dict[str, OperationOverride] = Field(default_factory=dict)
    skip_validate_spec: bool = False


_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ProductConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package: str
    output: str
    base_url: str
    generator: GeneratorConfig = Field(default_factory=GeneratorConfig)
    # Single-spec (legacy) products set `spec:`; federated products set
    # `subpackages:` instead. Exactly one is required — the validator restores
    # the legacy "./openapi.yml" default when neither is federated.
    spec: str | None = None
    subpackages: list[SubPackage] = Field(default_factory=list)
    apply_generic_patches: bool = True
    transforms: Transforms = Field(default_factory=Transforms)
    hooks: str | None = None
    # auth/pagination/errors are resolved to component models by the loader (Task 4);
    # at the raw-parse layer they are plain dicts.
    auth: dict[str, Any] | None = None
    pagination: dict[str, Any] | None = None
    errors: dict[str, Any] | None = None
    facade: bool | dict[str, Any] = True
    retry: bool | dict[str, Any] = True
    vars: dict[str, Any] = Field(default_factory=dict)
    include: dict[str, str] = Field(default_factory=dict)
    project: ProjectConfig | None = None
    operations: dict[str, OperationOverride] = Field(default_factory=dict)
    docs: DocsConfig | None = None

    @model_validator(mode="after")
    def _exactly_one_spec_mode(self) -> ProductConfig:
        federated = bool(self.subpackages)
        explicit_spec = self.spec is not None
        if federated and explicit_spec:
            raise ValueError(
                "set either `spec:` (single-spec) or `subpackages:` (federated), "
                "not both"
            )
        if not federated and self.spec is None:
            self.spec = "./openapi.yml"  # restore legacy default
        if federated:  # slug is a package/dir/import path — validate at the boundary
            seen: set[str] = set()
            for sub in self.subpackages:
                if not _SLUG_RE.match(sub.slug):
                    raise ValueError(
                        f"sub-package slug {sub.slug!r} must match {_SLUG_RE.pattern}"
                    )
                if sub.slug in seen:
                    raise ValueError(f"duplicate sub-package slug {sub.slug!r}")
                seen.add(sub.slug)
        return self


class CustomComponent(BaseModel):
    """A component backed by a per-product template path (arbitrary config)."""

    model_config = ConfigDict(extra="allow")
    type: str
    template: str = ""

    @property
    def extra(self) -> dict[str, Any]:
        # pydantic v2 stores extra="allow" fields here, not in __dict__.
        return dict(self.__pydantic_extra__ or {})


def resolve_component(
    block: dict[str, Any], registry: Mapping[str, type], base_dir: Path
) -> Any:
    """Turn a raw sdk.yml component block into a validated component model."""
    type_ = block.get("type")
    if isinstance(type_, str) and (type_.startswith("./") or type_.endswith(".jinja")):
        path = (base_dir / type_).resolve()
        if not path.exists():
            raise ValueError(f"{type_}: template not found at {path}")
        data = {**block, "template": str(path)}
        return CustomComponent(**data)
    model = registry.get(type_) if isinstance(type_, str) else None
    if model is None:
        raise ValueError(
            f"unknown component type {type_!r}; expected one of {sorted(registry)}"
        )
    return model(**block)


@_dataclass
class LoadedSubPackage:
    """One federated sub-package, resolved against its own spec.

    `config` carries the slug (`config.slug`) — there is no separate slug field.
    """

    package: str  # "prisma_access.objects"
    spec_path: Path
    context: dict[str, Any]  # per-sub jinja context (package, spec_title, spec_version)
    config: SubPackage


@_dataclass
class LoadedProduct:
    config: ProductConfig
    base_dir: Path
    spec_path: Path | None  # None for federated products (B5)
    output_dir: Path
    auth: Any | None
    pagination: Any | None
    errors: Any | None
    facade: Any | None
    retry: Any | None
    context: dict[str, Any]
    subpackages: list[LoadedSubPackage] = field(default_factory=list)


_AUTO_EXPOSED = {
    "package",
    "library",
    "base_url",
    "spec_version",
    "spec_title",
    "has_auth",
    "has_pagination",
    "has_errors",
    "has_facade",
    "config_class_name",
    "distribution",
    "description",
    "author",
    "author_email",
    "repo_url",
    "license",
    "python_versions",
    "dependencies",
    "has_docs",
}


def _read_yaml(path: Path) -> dict[str, Any]:
    from ruamel.yaml import YAML

    result: dict[str, Any] = YAML(typ="safe").load(path.open(encoding="utf-8"))
    return result


def load_product(name_or_path: str) -> LoadedProduct:
    p = Path(name_or_path)
    sdk_path = p if p.name == "sdk.yml" else Path("products") / name_or_path / "sdk.yml"
    sdk_path = sdk_path.resolve()
    if not sdk_path.exists():
        raise FileNotFoundError(f"no sdk.yml at {sdk_path}")
    base_dir = sdk_path.parent
    cfg = ProductConfig(**_read_yaml(sdk_path))

    auth = resolve_component(cfg.auth, BUILTIN_AUTH, base_dir) if cfg.auth else None
    pagination = (
        resolve_component(cfg.pagination, BUILTIN_PAGINATION, base_dir)
        if cfg.pagination
        else None
    )
    errors = (
        resolve_component(cfg.errors, BUILTIN_ERRORS, base_dir) if cfg.errors else None
    )
    facade = None
    if cfg.facade:
        block = {"type": "default"} if cfg.facade is True else dict(cfg.facade)
        block.setdefault("type", "default")
        facade = resolve_component(block, BUILTIN_FACADE, base_dir)

    retry = None
    if cfg.retry:
        block = {"type": "default"} if cfg.retry is True else dict(cfg.retry)
        block.setdefault("type", "default")
        retry = resolve_component(block, BUILTIN_RETRY, base_dir)

    # B5: only single-spec products carry a top-level spec; for federated
    # products each sub-package owns its spec, so the top-level read is skipped.
    if cfg.subpackages:
        spec_path: Path | None = None
        spec_version = spec_title = None
    else:
        # validator restores the legacy default, so cfg.spec is non-None here
        spec_path = (base_dir / cast(str, cfg.spec)).resolve()
        info = (
            (_read_yaml(spec_path) or {}).get("info", {}) if spec_path.exists() else {}
        )
        spec_version, spec_title = info.get("version"), info.get("title")

    context: dict[str, Any] = {
        "package": cfg.package,
        "library": cfg.generator.library,
        "base_url": cfg.base_url,
        "spec_version": spec_version,
        "spec_title": spec_title,
        "has_auth": auth is not None,
        "has_pagination": pagination is not None,
        "has_errors": errors is not None,
        "has_facade": facade is not None,
        "has_retry": retry is not None,
        "has_docs": cfg.docs is not None,
        "config_class_name": getattr(auth, "config_class_name", "SdkConfiguration"),
    }
    if cfg.project is not None:
        context.update(
            {
                "distribution": cfg.project.distribution,
                "description": cfg.project.description,
                "author": cfg.project.author,
                "author_email": cfg.project.author_email,
                "repo_url": cfg.project.repo_url,
                "license": cfg.project.license,
                "python_versions": cfg.project.python_versions,
                "dependencies": cfg.project.dependencies,
            }
        )
    collisions = set(cfg.vars) & _AUTO_EXPOSED
    if collisions:
        raise ValueError(
            f"vars keys {sorted(collisions)} shadow reserved auto-exposed names"
        )
    context.update(cfg.vars)

    for _dest, source in cfg.include.items():
        src_path = (base_dir / source).resolve()
        if not src_path.is_relative_to(base_dir):
            raise ValueError(f"include source {source!r} escapes the product dir")
        if not src_path.exists():
            raise ValueError(
                f"include source {source!r}: template not found at {src_path}"
            )

    sub_loaded: list[LoadedSubPackage] = []
    for sub in cfg.subpackages:
        sub_spec = (base_dir / sub.spec).resolve()
        sub_info = (
            (_read_yaml(sub_spec) or {}).get("info", {}) if sub_spec.exists() else {}
        )
        sub_pkg = f"{cfg.package}.{sub.slug}"
        sub_ctx = dict(context)
        sub_ctx["package"] = sub_pkg
        sub_ctx["spec_title"] = sub_info.get("title")
        sub_ctx["spec_version"] = sub_info.get("version")
        sub_loaded.append(
            LoadedSubPackage(
                package=sub_pkg, spec_path=sub_spec, context=sub_ctx, config=sub
            )
        )

    return LoadedProduct(
        config=cfg,
        base_dir=base_dir,
        spec_path=spec_path,
        output_dir=(base_dir / cfg.output).resolve(),
        auth=auth,
        pagination=pagination,
        errors=errors,
        facade=facade,
        retry=retry,
        context=context,
        subpackages=sub_loaded,
    )
