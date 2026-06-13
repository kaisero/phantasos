"""`config environment` commands: manage named credential environments.

HAND-WRITTEN (copied verbatim into the emitted package by render_cli, NOT
rendered from Jinja). Its only product-specific part — the per-field options of
``create`` — is built DYNAMICALLY at runtime from the IR's credential fields, so
no field name is hardcoded here.

Environments live in an ISOLATED top-level ``environments:`` mapping of the user
config file (NOT in the validated ``configuration:`` tree); the active one is the
top-level ``default_environment`` key. Field values are stored VERBATIM — a
literal OR a ``${VAR}`` reference string — and resolved only at client-build time.
"""

from __future__ import annotations

import os
from typing import Any

import click
import typer
import yaml
from typer.core import TyperGroup

from . import config as _config
from . import diagnostics as _diag
from . import runtime as _rt


def _kebab(name: str) -> str:
    """``client_secret`` -> ``client-secret`` (the CLI flag spelling)."""
    return name.replace("_", "-")


def _credential_fields() -> list[Any]:
    """The IR's credential fields (each has ``.name`` / ``.secret``)."""
    return list(_rt._ir().credential_fields)


def _write_raw_config(data: dict[str, Any]) -> None:
    """Atomically dump the full raw config dict back to disk at 0o600.

    Preserves every other top-level key — we only ever mutate the caller's
    in-memory copy of the raw config before handing it here. The file may hold
    secret credentials, so it is created private (0o600) and written via a temp
    file + atomic rename so a crash mid-write can't corrupt an existing config."""
    path = _config.config_path()
    content = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        tmp.replace(path)
        path.chmod(0o600)  # tighten even if the file pre-existed
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        _diag.fail(f"cannot write {path}: {exc}", code=1)


def _create_environment(name: str, force: bool, **field_values: Any) -> None:
    """``create`` callback. Prompts for any field not supplied on the command
    line (secrets with input hidden), stores values verbatim under
    ``environments[name]``, and auto-activates the first environment."""
    fields = _credential_fields()
    raw = _config._raw_config()
    environments = raw.get("environments")
    if not isinstance(environments, dict):
        environments = {}

    if name in environments and not force:
        _diag.fail(
            f"environment '{name}' already exists (use --force to overwrite)",
            code=2,
        )

    values: dict[str, Any] = {}
    for f in fields:
        supplied = field_values.get(f.name)
        if supplied is not None:
            values[f.name] = supplied
        else:
            # Prompt interactively; hide input for secret fields (no echo).
            values[f.name] = typer.prompt(_kebab(f.name), hide_input=bool(f.secret))

    environments[name] = values
    raw["environments"] = environments
    first_environment = not isinstance(raw.get("default_environment"), str)
    if first_environment:
        raw["default_environment"] = name
    _write_raw_config(raw)

    _diag.info(f"wrote environment '{name}' to {_config.config_path()}")
    if first_environment:
        _diag.info(f"activated environment '{name}' (default_environment)")


def _build_create_command() -> click.Command:
    """A Click ``create`` command whose per-field options are derived from the
    IR's credential fields. Registered on the group via ``_EnvironmentGroup``."""
    params: list[click.Parameter] = [
        click.Argument(["name"]),
        click.Option(
            ["--force"],
            is_flag=True,
            default=False,
            help="Overwrite an existing environment.",
        ),
    ]
    for f in _credential_fields():
        params.append(
            click.Option(
                [f"--{_kebab(f.name)}", f.name],
                default=None,
                # NEVER echo a prompted/typed secret value back to the terminal.
                hide_input=bool(f.secret),
                help=f"Value for '{f.name}' (literal or ${{VAR}} reference).",
            )
        )
    return click.Command(
        "create",
        params=params,
        callback=_create_environment,
        help="Create (or overwrite with --force) a named environment.",
        short_help="Create a named environment.",
    )


class _EnvironmentGroup(TyperGroup):
    """Typer group that also carries the dynamically-built ``create`` command.

    Injecting it in ``__init__`` (rather than at module import) means it is baked
    into every conversion of the group — so it survives Typer/CliRunner rebuilding
    the Click tree from the registered Typer commands."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.add_command(_build_create_command())


environment_app = typer.Typer(
    no_args_is_help=True,
    help="Manage named credential environments.",
    cls=_EnvironmentGroup,
)


@environment_app.command("activate")
def activate(name: str) -> None:
    """Make NAME the active environment (sets default_environment)."""
    if name not in _config._raw_environments():
        _diag.fail(f"no such environment: '{name}'", code=2)
    raw = _config._raw_config()
    raw["default_environment"] = name
    _write_raw_config(raw)
    _diag.info(f"activated environment '{name}'")


@environment_app.command("list")
def list_environments() -> None:
    """List the defined environment names (never their field values)."""
    environments = _config._raw_environments()
    if not environments:
        _diag.info("no environments defined")
        return
    active = _config.default_environment()
    for name in environments:
        marker = " (active)" if name == active else ""
        typer.echo(f"{name}{marker}")


@environment_app.command("current")
def current() -> None:
    """Print the active environment name."""
    active = _config.default_environment()
    if not active:
        _diag.fail("no active environment", code=2)
    typer.echo(active)
