"""Snapshot a freshly generated project into a git repo on a per-build branch.

When a product's ``project.git_remote`` is set, the emitted SDK/CLI is turned into
a git repository ready to push upstream: `git init`, `origin` pointed at the
configured remote, a unique per-build branch checked out, and every file committed
with a message recording *when* it was generated, *who* generated it, and *from
which phantasos commit + branch*. The user can then ``cd`` into the output and
``git push origin <branch>`` to open a PR against the upstream project.

Runs after finalize (so uv.lock and the formatted tree are part of the commit).
Honors ``PHANTASOS_SKIP_FINALIZE`` — the same switch that turns off the other
post-generation side effects in the test suite. Degrades gracefully if git is not
on PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# src/phantasos/generator/gitrepo.py -> repo root
_PHANTASOS_ROOT = Path(__file__).resolve().parents[3]


def _run(args: list[str], cwd: Path, **kw: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **kw} if kw else None
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=False, env=env)


def _phantasos_sha_and_branch() -> tuple[str | None, str | None]:
    """The phantasos HEAD sha + branch, or ``(None, None)`` when not a git checkout."""
    try:
        sha = _run(["git", "-C", str(_PHANTASOS_ROOT), "rev-parse", "HEAD"], _PHANTASOS_ROOT)
        branch = _run(
            ["git", "-C", str(_PHANTASOS_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
            _PHANTASOS_ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    return (
        sha.stdout.strip() if sha.returncode == 0 else None,
        branch.stdout.strip() if branch.returncode == 0 else None,
    )


def _build_branch(now: datetime, short_sha: str | None) -> str:
    """A unique, sortable per-build branch name."""
    return f"phantasos/{now:%Y%m%d-%H%M%S}-{short_sha or 'nosha'}"


def _commit_message(
    *,
    distribution: str,
    now: datetime,
    author: str,
    author_email: str,
    sha: str | None,
    branch: str | None,
) -> str:
    generator = f"{sha or 'unknown'} (branch {branch or 'unknown'})"
    return (
        f"Generate {distribution} from phantasos {(sha or 'unknown')[:12]}\n"
        "\n"
        f"Generated: {now.isoformat()}\n"
        f"By: {author} <{author_email}>\n"
        f"phantasos commit: {generator}\n"
    )


def snapshot(
    project_dir: Path,
    *,
    distribution: str,
    author: str,
    author_email: str,
    remote: str | None,
) -> dict[str, str]:
    """Init a git repo, branch, and commit the whole project for pushing upstream.

    No-op (returns a skip status) when ``remote`` is unset, when the test switch is
    on, or when git is unavailable.
    """
    if not remote:
        return {"skipped": "no git_remote configured"}
    if os.environ.get("PHANTASOS_SKIP_FINALIZE"):
        return {"skipped": "PHANTASOS_SKIP_FINALIZE"}
    git = shutil.which("git")
    if not git:
        return {"skipped": "git not found"}

    now = datetime.now(timezone.utc)
    sha, branch = _phantasos_sha_and_branch()
    build_branch = _build_branch(now, sha[:12] if sha else None)
    message = _commit_message(
        distribution=distribution,
        now=now,
        author=author,
        author_email=author_email,
        sha=sha,
        branch=branch,
    )

    _run([git, "init", "-q"], project_dir)
    _run([git, "checkout", "-q", "-B", build_branch], project_dir)
    _run([git, "remote", "remove", "origin"], project_dir)  # idempotent on rebuild
    _run([git, "remote", "add", "origin", remote], project_dir)
    _run([git, "add", "-A"], project_dir)
    # Identity passed inline so the commit never depends on the machine's global
    # git config; author and committer are both the configured project author.
    commit = _run(
        [
            git,
            "-c",
            f"user.name={author}",
            "-c",
            f"user.email={author_email}",
            "commit",
            "-q",
            "--author",
            f"{author} <{author_email}>",
            "-m",
            message,
        ],
        project_dir,
    )
    if commit.returncode != 0:
        return {"error": (commit.stdout + commit.stderr).strip()}
    return {"branch": build_branch, "remote": remote}
