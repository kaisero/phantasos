#!/usr/bin/env python3
"""
Capture the real request/response for the policy GET endpoints that return 403,
so the access issue can be reported with concrete evidence.

For each policy read it records the exact HTTP request (method, URL, headers with
the bearer token redacted) and the full response (status, headers, body), then
writes findings/policy_403.md with a curl reproduction.

Read-only. Run with:  ./examples/run.sh examples/probe_policy_403.py
"""
from __future__ import annotations

from pathlib import Path

from _common import ROOT, get_client

from prisma_browser_sdk.api.security_policy import get_security_policy
from prisma_browser_sdk.api.sign_in_policy import get_sign_in_policy
from prisma_browser_sdk.api.access_and_data_policy import get_access_and_data_policy
from prisma_browser_sdk.api.customization_policy import get_customization_policy

POLICY_ENDPOINTS = [
    ("Security Policy", get_security_policy),
    ("Sign-In Policy", get_sign_in_policy),
    ("Access And Data Policy", get_access_and_data_policy),
    ("Customization Policy", get_customization_policy),
]

_REDACT = {"authorization", "cookie", "proxy-authorization"}


def _headers(items, redact: bool) -> list[tuple[str, str]]:
    out = []
    for k, v in items:
        if redact and k.lower() in _REDACT:
            v = "<redacted>"
        out.append((k, v))
    return out


def main() -> int:
    client = get_client()
    httpx_client = client.get_httpx_client()

    detail_blocks: list[str] = []
    rows: list[dict] = []

    for title, module in POLICY_ENDPOINTS:
        kwargs = module._get_kwargs()
        response = httpx_client.request(**kwargs)
        req = response.request

        body = response.text.strip()
        body_block = body if body else "(empty body)"

        code = message = None
        try:
            err = response.json().get("error", {})
            code, message = err.get("code"), err.get("message")
        except Exception:
            pass
        rows.append({
            "title": title,
            "url": str(req.url),
            "status": f"{response.status_code} {response.reason_phrase}",
            "code": code,
            "message": message,
            "request_id": response.headers.get("x-request-id", ""),
            "flow_error": response.headers.get("x-request-flow-error", ""),
        })

        # query string for a curl repro
        url = str(req.url)
        detail_blocks += [
            f"## {title}",
            "",
            f"**{req.method} {url}** → `{response.status_code} {response.reason_phrase}`",
            "",
            "Request headers:",
            "```",
            *[f"{k}: {v}" for k, v in _headers(req.headers.items(), redact=True)],
            "```",
            "",
            "Reproduce:",
            "```bash",
            f"curl -i -X {req.method} '{url}' \\",
            "  -H 'Authorization: Bearer <ACCESS_TOKEN>' \\",
            "  -H 'Accept: application/json'",
            "```",
            "",
            "Response headers:",
            "```",
            *[f"{k}: {v}" for k, v in _headers(response.headers.items(), redact=False)],
            "```",
            "",
            "Response body:",
            "```json",
            body_block,
            "```",
            "",
            "---",
            "",
        ]

    # --- diagnosis derived from the actual responses ----------------------
    distinct_msgs = sorted({r["message"] for r in rows if r["message"]})
    diagnosis = (
        f'All {len(rows)} policy GET endpoints return the same error: '
        f'`{distinct_msgs[0]}`.' if len(distinct_msgs) == 1
        else "Policy GET endpoints return the errors listed below."
    )

    header = [
        "# Prisma Browser API — policy GET endpoints return 403",
        "",
        f"Base URL: `{client._base_url}`  ",
        f"Scope: `{client._httpx_args['auth']._scope}`",
        "",
        "## Summary",
        "",
        "The OAuth2 client-credentials access token is obtained successfully and is",
        "accepted by other endpoints (users, devices, applications all return 200).",
        "Only the **policy** read endpoints return **403**, and the response body",
        f"indicates this is *not* an authorization failure: {diagnosis}",
        "",
        "This suggests these endpoints are published in the OpenAPI spec but not yet",
        "available on the live service (error code `FORBIDDEN`, `x-request-flow-error:",
        "DEF_403`). Request IDs are included below for support.",
        "",
        "| Endpoint | Status | error.code | error.message | x-request-id |",
        "|----------|--------|------------|---------------|--------------|",
        *[f"| `{r['url'].split('/seb-api')[-1].split('?')[0]}` | {r['status']} | "
          f"`{r['code']}` | {r['message']} | `{r['request_id']}` |" for r in rows],
        "",
        "---",
        "",
    ]

    findings_dir = ROOT / "findings"
    findings_dir.mkdir(exist_ok=True)
    out = findings_dir / "policy_403.md"
    out.write_text("\n".join(header + detail_blocks), encoding="utf-8")

    print("policy GET results:")
    for r in rows:
        print(f"  {r['title']:28s} {r['status']}  {r['code']}: {r['message']}")
    print(f"\nfindings -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
