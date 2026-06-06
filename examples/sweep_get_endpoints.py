#!/usr/bin/env python3
"""
Sweep every GET endpoint against a LIVE tenant to surface spec drift.

Strategy:
  1. Call all no-parameter GET endpoints (lists + policy reads); cache results.
  2. Derive resource ids (and an application type) from those results.
  3. Call the parameterized GET endpoints (`{id}`, `{type}`) with derived values.
  4. Aggregate every enum value the live API returned that the spec omits
     (collected by the LenientStrEnum registry), plus any deserialization errors.

Read-only — issues only GETs. Writes findings to ./findings/enum_gaps.{json,md}.

Run with:  ./examples/run.sh examples/sweep_get_endpoints.py
"""
from __future__ import annotations

import importlib
import inspect
import json
import pkgutil
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT / "prisma-browser-sdk"))


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            __import__("os").environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def discover_get_endpoints() -> list[tuple[str, object, tuple[str, ...]]]:
    import prisma_browser_sdk.api as api
    out = []
    for mod in pkgutil.walk_packages(api.__path__, "prisma_browser_sdk.api."):
        if mod.ispkg:
            continue
        m = importlib.import_module(mod.name)
        if not hasattr(m, "sync_detailed") or not hasattr(m, "_get_kwargs"):
            continue
        if '"method": "get"' not in inspect.getsource(m._get_kwargs):
            continue
        sig = inspect.signature(m.sync_detailed)
        required = tuple(
            p for p, par in sig.parameters.items()
            if p != "client" and par.default is inspect._empty and par.kind != par.VAR_KEYWORD
        )
        out.append((mod.name.replace("prisma_browser_sdk.api.", ""), m, required))
    return sorted(out, key=lambda r: r[0])


def first_item(parsed):
    data = getattr(parsed, "data", None)
    if isinstance(data, list) and data:
        return data[0]
    return None


def first_id(parsed):
    item = first_item(parsed)
    if item is None:
        return None
    for attr in ("id", "device_group_id"):
        v = getattr(item, attr, None)
        if v:
            return v
    return None


def policy_ids(parsed):
    """(rule_id, section_id) from a policy GET response.

    The policy response exposes `.data: list[RuleSummary | Section]`; pick the
    first id of each kind (distinguished by class name).
    """
    rule_id = section_id = None
    for item in getattr(parsed, "data", None) or []:
        iid = getattr(item, "id", None)
        if type(item).__name__ == "Section":
            section_id = section_id or iid
        else:  # RuleSummary
            rule_id = rule_id or iid
    return rule_id, section_id


def call(module, client, **kwargs):
    """Call an endpoint; return (status, count, warn_count, error)."""
    with warnings.catch_warnings(record=True) as wlist:
        warnings.simplefilter("always")
        try:
            resp = module.sync_detailed(client=client, **kwargs)
        except Exception as exc:  # deserialization crash etc. — itself a finding
            return (None, None, len(wlist), f"{type(exc).__name__}: {exc}")
    status = int(resp.status_code)
    parsed = resp.parsed
    count = len(getattr(parsed, "data", []) or []) if parsed is not None else None
    return (status, count, len(wlist), None)


def main() -> int:
    load_dotenv(ROOT / ".env")
    import prisma_browser_sdk._lenient as lenient
    from prisma_browser_sdk.extras import client_from_env

    try:
        client = client_from_env()
    except RuntimeError as exc:
        print(f"✗ {exc}")
        return 2

    lenient.UNKNOWN_ENUM_VALUES.clear()
    endpoints = discover_get_endpoints()
    no_param = [(n, m) for n, m, req in endpoints if not req]
    param = [(n, m, req) for n, m, req in endpoints if req]

    cache = {}
    results = []  # (name, status, count, warns, error)

    print(f"== Phase 1: {len(no_param)} no-parameter GET endpoints ==")
    for name, m in no_param:
        status, count, warns, err = call(m, client)
        cache[name] = None
        if err is None and status == 200:
            cache[name] = m.sync_detailed(client=client).parsed
        results.append((name, status, count, warns, err))
        print(f"  {name:52s} {status if status else 'ERR':>4}  items={count}  warns={warns}"
              + (f"  {err}" if err else ""))

    # --- derive parameters from phase-1 data -------------------------------
    apps = getattr(cache.get("applications.list_applications"), "data", None) or []
    app = apps[0] if apps else None
    app_type = getattr(app, "type_", None) or getattr(app, "type", None)
    sec = policy_ids(cache.get("security_policy.get_security_policy"))
    si = policy_ids(cache.get("sign_in_policy.get_sign_in_policy"))
    ad = policy_ids(cache.get("access_and_data_policy.get_access_and_data_policy"))
    cu = policy_ids(cache.get("customization_policy.get_customization_policy"))

    PARAMS = {
        "users.get_user_by_id": {"id": first_id(cache.get("users.list_users"))},
        "devices.get_device_by_id": {"id": first_id(cache.get("devices.list_devices"))},
        "user_groups.get_user_group_by_id": {"id": first_id(cache.get("user_groups.list_user_groups"))},
        "application_groups.get_application_group_by_id": {"id": first_id(cache.get("application_groups.list_application_groups"))},
        "device_groups.get_device_group_by_id": {"device_group_id": first_id(cache.get("device_groups.list_device_groups"))},
        "applications.get_application_by_id": {"id": getattr(app, "id", None)},
        "applications.list_applications_by_type": {"type_": app_type},
        "applications.get_application_by_type_and_id": {"type_": app_type, "id": getattr(app, "id", None)},
        "plugins.get_application_plugin": {"id": first_id(cache.get("plugins.list_application_plugins"))},
        "user_requests.get_user_request_by_id": {"id": first_id(cache.get("user_requests.list_user_requests"))},
        "security_policy.get_security_rule_by_id": {"id": sec[0]},
        "security_policy.get_security_section_by_id": {"id": sec[1]},
        "sign_in_policy.get_sign_in_rule_by_id": {"id": si[0]},
        "sign_in_policy.get_sign_in_section_by_id": {"id": si[1]},
        "access_and_data_policy.get_access_and_data_rule_by_id": {"id": ad[0]},
        "access_and_data_policy.get_access_and_data_section_by_id": {"id": ad[1]},
        "customization_policy.get_customization_rule_by_id": {"id": cu[0]},
        "customization_policy.get_customization_section_by_id": {"id": cu[1]},
    }

    print(f"\n== Phase 2: {len(param)} parameterized GET endpoints ==")
    for name, m, req in param:
        kwargs = PARAMS.get(name)
        if kwargs is None or any(v in (None, "") for v in kwargs.values()):
            results.append((name, "SKIP", None, 0, f"no source value for {req}"))
            print(f"  {name:52s} SKIP  (no source for {req})")
            continue
        status, count, warns, err = call(m, client, **kwargs)
        results.append((name, status, count, warns, err))
        print(f"  {name:52s} {status if status else 'ERR':>4}  warns={warns}"
              + (f"  {err}" if err else ""))

    # --- report (accumulate across runs/tenants; never lose prior gaps) ----
    findings_dir = ROOT / "findings"
    findings_dir.mkdir(exist_ok=True)
    gaps_file = findings_dir / "enum_gaps.json"

    merged: dict[str, set] = {}
    if gaps_file.exists():  # fold in previously-recorded gaps (e.g. other tenants)
        try:
            for k, v in json.loads(gaps_file.read_text()).items():
                merged[k] = set(v)
        except (ValueError, TypeError):
            pass
    this_run = {k: set(v) for k, v in lenient.UNKNOWN_ENUM_VALUES.items()}
    for k, v in this_run.items():
        merged.setdefault(k, set()).update(v)

    gaps = {k: sorted(v) for k, v in sorted(merged.items())}
    gaps_file.write_text(json.dumps(gaps, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Enum gaps — values returned by the live API but missing from the OpenAPI spec",
        "",
        "_Accumulated across sweep runs (and tenants). Each row is a real value the API",
        "returned that the spec's enum does not declare._",
        "",
    ]
    if gaps:
        lines += ["| Enum | Undeclared value(s) returned by the API |", "|------|------------------------------------------|"]
        for enum, vals in gaps.items():
            lines.append(f"| `{enum}` | {', '.join(f'`{v}`' for v in vals)} |")
    else:
        lines.append("_No undeclared enum values observed in this sweep._")
    lines.append("")
    (findings_dir / "enum_gaps.md").write_text("\n".join(lines), encoding="utf-8")

    ok = sum(1 for _, s, *_ in results if s == 200)
    errs = [r for r in results if r[4] and r[1] != "SKIP"]
    skipped = [r for r in results if r[1] == "SKIP"]
    print("\n== Summary ==")
    print(f"  endpoints: {len(results)}  |  200 OK: {ok}  |  errors: {len(errs)}  |  skipped: {len(skipped)}")
    run_total = sum(len(v) for v in this_run.values())
    print(f"  enum gaps: this run {run_total} value(s); accumulated "
          f"{sum(len(v) for v in gaps.values())} across {len(gaps)} enum(s)")
    for enum, vals in gaps.items():
        new = sorted(this_run.get(enum, set()))
        marker = "  (new this run: " + ", ".join(new) + ")" if new else ""
        print(f"    - {enum}: {', '.join(vals)}{marker}")
    if errs:
        print("  deserialization/other errors:")
        for name, *_ , err in errs:
            print(f"    - {name}: {err}")
    print(f"\n  findings -> {findings_dir.relative_to(ROOT)}/enum_gaps.{{json,md}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
