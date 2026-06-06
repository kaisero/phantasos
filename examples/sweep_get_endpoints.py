#!/usr/bin/env python3
"""Sweep every GET endpoint of the OAG SDK against a LIVE tenant (read-only).

Discovers GET operations by introspecting each generated method's `_serialize`
(method='GET'), resolves {id}/{type} params from list responses, calls them, and
accumulates enum values the live API returns but the spec omits (via the
LenientStrEnum registry). Writes findings/enum_gaps.{json,md}.

    ./examples/run.sh examples/sweep_get_endpoints.py
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

from _common import ROOT, get_client

from prisma_browser.extras.facade import _RESOURCES  # resource attr -> Api class
import prisma_browser._lenient as lenient
from prisma_browser.extras import ApiException

_SKIP_PARAMS = {"_request_timeout", "_request_auth", "_content_type", "_headers", "self"}


def is_get(api, method_name: str) -> bool:
    ser = getattr(api, f"_{method_name}_serialize", None)
    if ser is None:
        return False
    try:
        src = inspect.getsource(ser)
    except OSError:
        return False
    return "method='GET'" in src or 'method="GET"' in src


def required_params(api, method_name: str) -> list[str]:
    sig = inspect.signature(getattr(api, method_name))
    return [
        p for p, par in sig.parameters.items()
        if p not in _SKIP_PARAMS and par.default is inspect._empty
        and par.kind not in (par.VAR_KEYWORD, par.VAR_POSITIONAL)
    ]


def first_id(page):
    items = getattr(page, "data", None) or []
    if not items:
        return None
    it = items[0]
    inner = getattr(it, "actual_instance", it)  # unwrap oneOf
    return getattr(inner, "id", None) or getattr(inner, "device_group_id", None)


def policy_rule_section_ids(page):
    rule = section = None
    for it in getattr(page, "data", None) or []:
        inner = getattr(it, "actual_instance", it)
        iid = getattr(inner, "id", None)
        if type(inner).__name__ == "Section":
            section = section or iid
        else:
            rule = rule or iid
    return rule, section


def main() -> int:
    client = get_client()
    lenient.UNKNOWN_ENUM_VALUES.clear()

    # discover GET ops per resource
    get_ops = []  # (resource_name, api, method_name, required)
    for rname in _RESOURCES:
        api = getattr(client, rname)
        for mname in dir(api):
            if mname.startswith("_") or mname.endswith(("_with_http_info", "_without_preload_content")):
                continue
            if not callable(getattr(api, mname)) or not is_get(api, mname):
                continue
            get_ops.append((rname, api, mname, required_params(api, mname)))

    no_param = [(r, a, m) for r, a, m, req in get_ops if not req]
    param = [(r, a, m, req) for r, a, m, req in get_ops if req]
    cache = {}
    results = []

    print(f"== Phase 1: {len(no_param)} no-parameter GETs ==")
    for rname, api, mname in sorted(no_param):
        key = f"{rname}.{mname}"
        try:
            page = getattr(api, mname)()
            cache[key] = page
            n = len(getattr(page, "data", []) or [])
            results.append((key, "200", n, None))
            print(f"  {key:48s} 200  items={n}")
        except ApiException as e:
            results.append((key, str(e.status), None, None))
            print(f"  {key:48s} {e.status}")
        except Exception as e:  # noqa: BLE001  (deserialization failures are findings)
            results.append((key, "ERR", None, f"{type(e).__name__}: {e}"))
            print(f"  {key:48s} ERR  {type(e).__name__}: {str(e)[:80]}")

    # resolve params
    def page(res, meth):
        return cache.get(f"{res}.{meth}")
    apps = getattr(page("applications", "list_applications"), "data", None) or []
    app = getattr(apps[0], "actual_instance", apps[0]) if apps else None  # unwrap oneOf
    app_type = getattr(app, "type", None)
    sec = policy_rule_section_ids(page("security_policy", "get_security_policy"))
    si = policy_rule_section_ids(page("sign_in_policy", "get_sign_in_policy"))
    ad = policy_rule_section_ids(page("access_and_data_policy", "get_access_and_data_policy"))
    cu = policy_rule_section_ids(page("customization_policy", "get_customization_policy"))
    RESOLVE = {
        "users.get_user_by_id": {"id": first_id(page("users", "list_users"))},
        "devices.get_device_by_id": {"id": first_id(page("devices", "list_devices"))},
        "user_groups.get_user_group_by_id": {"id": first_id(page("user_groups", "list_user_groups"))},
        "application_groups.get_application_group_by_id": {"id": first_id(page("application_groups", "list_application_groups"))},
        "device_groups.get_device_group_by_id": {"device_group_id": first_id(page("device_groups", "list_device_groups"))},
        "applications.get_application_by_id": {"id": getattr(app, "id", None)},
        "applications.list_applications_by_type": {"type": app_type},
        "applications.get_application_by_type_and_id": {"type": app_type, "id": getattr(app, "id", None)},
        "plugins.get_application_plugin": {"id": first_id(page("plugins", "list_application_plugins"))},
        "user_requests.get_user_request_by_id": {"id": first_id(page("user_requests", "list_user_requests"))},
        "security_policy.get_security_rule_by_id": {"id": sec[0]},
        "security_policy.get_security_section_by_id": {"id": sec[1]},
        "sign_in_policy.get_sign_in_rule_by_id": {"id": si[0]},
        "sign_in_policy.get_sign_in_section_by_id": {"id": si[1]},
        "access_and_data_policy.get_access_and_data_rule_by_id": {"id": ad[0]},
        "access_and_data_policy.get_access_and_data_section_by_id": {"id": ad[1]},
        "customization_policy.get_customization_rule_by_id": {"id": cu[0]},
        "customization_policy.get_customization_section_by_id": {"id": cu[1]},
    }

    print(f"\n== Phase 2: {len(param)} parameterized GETs ==")
    for rname, api, mname, req in sorted(param):
        key = f"{rname}.{mname}"
        kwargs = RESOLVE.get(key)
        if kwargs is None or any(v in (None, "") for v in kwargs.values()):
            results.append((key, "SKIP", None, f"no source for {req}"))
            print(f"  {key:48s} SKIP ({req})")
            continue
        try:
            getattr(api, mname)(**kwargs)
            results.append((key, "200", None, None))
            print(f"  {key:48s} 200")
        except ApiException as e:
            results.append((key, str(e.status), None, None))
            print(f"  {key:48s} {e.status}")
        except Exception as e:  # noqa: BLE001
            results.append((key, "ERR", None, f"{type(e).__name__}: {e}"))
            print(f"  {key:48s} ERR  {type(e).__name__}: {str(e)[:80]}")

    # findings (accumulate across runs/tenants)
    findings = ROOT / "findings"
    findings.mkdir(exist_ok=True)
    gaps_file = findings / "enum_gaps.json"
    merged = {}
    if gaps_file.exists():
        try:
            merged = {k: set(v) for k, v in json.loads(gaps_file.read_text()).items()}
        except (ValueError, TypeError):
            pass
    for k, v in lenient.UNKNOWN_ENUM_VALUES.items():
        merged.setdefault(k, set()).update(v)
    gaps = {k: sorted(v) for k, v in sorted(merged.items())}
    gaps_file.write_text(json.dumps(gaps, indent=2) + "\n")
    md = ["# Enum gaps — values returned by the live API but missing from the spec", "",
          "_Accumulated across sweep runs/tenants._", ""]
    md += ["| Enum | Undeclared value(s) |", "|------|---------------------|"]
    md += [f"| `{k}` | {', '.join('`'+x+'`' for x in v)} |" for k, v in gaps.items()]
    (findings / "enum_gaps.md").write_text("\n".join(md) + "\n")

    ok = sum(1 for _, s, *_ in results if s == "200")
    errs = [r for r in results if r[1] == "ERR"]
    print("\n== Summary ==")
    print(f"  endpoints {len(results)} | 200 {ok} | errors {len(errs)} | "
          f"skipped {sum(1 for r in results if r[1]=='SKIP')}")
    print(f"  enum gaps (this run): {dict((k, sorted(v)) for k, v in lenient.UNKNOWN_ENUM_VALUES.items())}")
    for key, _s, _n, err in errs:
        print(f"  ERROR {key}: {err}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
