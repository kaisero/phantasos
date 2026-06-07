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


def ensure_jar() -> Path:
    jar = provision.cache_dir() / f"openapi-generator-cli-{OAG_VERSION}.jar"
    if not jar.exists():
        print(f"  fetching openapi-generator-cli {OAG_VERSION} -> {jar}")
        provision._download_verified(_JAR_URL, JAR_SHA256, jar)
    return jar


def generate(
    spec_path: str, out_dir: str, package: str, library: str = "urllib3"
) -> None:
    check_java()
    jar = ensure_jar()
    cmd = [
        "java",
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
