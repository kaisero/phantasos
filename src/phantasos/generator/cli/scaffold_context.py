"""Build the scaffold context for an emitted CLI project (reuses the SDK scaffold)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_CLI_DEPS = ["typer>=0.12", "rich>=13", "pyyaml>=6"]


def _auth_env_vars(loaded: Any) -> list[dict[str, str]]:
    """Best-effort {name, example} list from the SDK auth component for .env.example."""
    auth = getattr(loaded, "auth", None)
    pairs = [
        (getattr(auth, "client_id_env", None) or "CLIENT_ID", "<client-id>"),
        (getattr(auth, "client_secret_env", None) or "CLIENT_SECRET",
         "<client-secret>"),
        (getattr(auth, "scope_env", None), "<scope>"),
        (getattr(auth, "base_url_env", None), "<base-url>"),
    ]
    return [{"name": str(n), "example": ex} for n, ex in pairs if n]


def build_cli_scaffold_context(loaded: Any, ir: Any, cli_cfg: Any) -> dict[str, Any]:
    """CLI scaffold context = the SDK product context, overridden for the CLI.

    Starting from `loaded.context` guarantees every scaffold variable is present
    (the scaffold renders with StrictUndefined).
    """
    base = dict(loaded.context)
    _pkg = base["package"].replace("_", "-")
    sdk_distribution = base.get("distribution") or f"{_pkg}-sdk"
    cli_package = f"{base['package']}_cli"
    cli_distribution = (
        f"{sdk_distribution[:-4]}-cli" if sdk_distribution.endswith("-sdk")
        else f"{sdk_distribution}-cli"
    )
    sdk_source_path = f"../{Path(loaded.output_dir).name}"

    project = getattr(cli_cfg, "project", None) if cli_cfg is not None else None
    distribution = project.distribution if project else cli_distribution

    ctx = dict(base)
    ctx.update(
        package=cli_package,
        distribution=distribution,
        description=(project.description if project and project.description
                     else f"CLI for {base.get('spec_title') or base['package']}"),
        dependencies=[*_CLI_DEPS, sdk_distribution],
        scripts={distribution: f"{cli_package}.main:app"},
        sdk_dist=sdk_distribution,
        sdk_source_path=sdk_source_path,
        has_auth=False, has_pagination=False, has_errors=False, has_facade=False,
        auth_env_vars=_auth_env_vars(loaded),
    )
    if project is not None:
        ctx.update(
            author=project.author, author_email=project.author_email,
            repo_url=project.repo_url, license=project.license,
            python_versions=project.python_versions,
        )
    return ctx
