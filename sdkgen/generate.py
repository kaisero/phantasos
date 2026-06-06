"""Run OpenAPI Generator (python) — jar fetch/pin + invocation."""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

OAG_VERSION = "7.7.0"
_JAR_URL = (
    "https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/"
    f"{OAG_VERSION}/openapi-generator-cli-{OAG_VERSION}.jar"
)


def _cache_dir() -> Path:
    base = Path(os.environ.get("SDKGEN_CACHE", Path.home() / ".cache" / "sdkgen"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def ensure_jar() -> Path:
    jar = _cache_dir() / f"openapi-generator-cli-{OAG_VERSION}.jar"
    if not jar.exists():
        print(f"  fetching openapi-generator-cli {OAG_VERSION} -> {jar}")
        urllib.request.urlretrieve(_JAR_URL, jar)
    return jar


def check_java() -> None:
    if shutil.which("java") is None:
        raise RuntimeError("java (JRE 11+) not found on PATH — required by OpenAPI Generator")


def generate(spec_path: str, out_dir: str, package: str, library: str = "urllib3") -> None:
    check_java()
    jar = ensure_jar()
    cmd = [
        "java", "-jar", str(jar), "generate",
        "-g", "python",
        "-i", spec_path,
        "-o", out_dir,
        "--package-name", package,
        "--additional-properties",
        f"library={library},disallowAdditionalPropertiesIfNotPresent=false",
        "--global-property",
        "modelDocs=false,apiDocs=false,modelTests=false,apiTests=false",
        "--inline-schema-options", "RESOLVE_INLINE_ENUMS=true",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
