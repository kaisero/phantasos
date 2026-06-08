"""Run OpenAPI Generator (python) — jar fetch/verify + invocation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import provision

OAG_VERSION = "7.22.0"
_JAR_URL = (
    "https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/"
    f"{OAG_VERSION}/openapi-generator-cli-{OAG_VERSION}.jar"
)
# Maven publishes only .sha1/.md5 for this jar; this SHA256 was computed from the
# authentic artifact (SHA1 cross-checked against Maven) and pinned.
JAR_SHA256 = "3f1e6ce5c6ad4f15242c6170ab43aad4bad771622617eeece4a7d4f72ffaf329"


_OAG_IGNORE = [
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "test-requirements.txt",
    "tox.ini",
    "git_push.sh",
    ".gitlab-ci.yml",
    ".travis.yml",
    ".github/workflows/python.yml",
    "README.md",
]


def write_openapi_generator_ignore(out_dir: Path) -> None:
    """Suppress OAG's supporting files so phantasos's scaffold owns them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    body = "# Written by phantasos — these are provided by the project scaffold.\n"
    body += "\n".join(_OAG_IGNORE) + "\n"
    (out_dir / ".openapi-generator-ignore").write_text(body, encoding="utf-8")


def prune_suppressed_files(out_dir: Path) -> None:
    """Delete any pre-existing copies of the suppressed OAG files.

    `.openapi-generator-ignore` stops OAG from *writing* these, but does not remove
    ones left by earlier builds — this cleans them so the SDK stays junk-free.
    """
    for rel in _OAG_IGNORE:
        target = out_dir / rel
        if target.is_file():
            target.unlink()


def ensure_jar() -> Path:
    jar = provision.cache_dir() / f"openapi-generator-cli-{OAG_VERSION}.jar"
    if not jar.exists():
        print(f"  fetching openapi-generator-cli {OAG_VERSION} -> {jar}")
        provision._download_verified(_JAR_URL, JAR_SHA256, jar)
    return jar


def generate(
    spec_path: str, out_dir: str, package: str, library: str = "urllib3"
) -> None:
    java = provision.resolve_java()
    jar = ensure_jar()
    cmd = [
        str(java),
        "-jar",
        str(jar),
        "generate",
        "-g",
        "python",
        "-i",
        spec_path,
        "-o",
        out_dir,
        "--package-name",
        package,
        "--additional-properties",
        f"library={library},disallowAdditionalPropertiesIfNotPresent=false",
        "--global-property",
        "modelDocs=false,apiDocs=false,modelTests=false,apiTests=false",
        "--inline-schema-options",
        "RESOLVE_INLINE_ENUMS=true",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
