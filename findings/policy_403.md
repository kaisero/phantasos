# Prisma Browser API — policy GET endpoints return 403

Base URL: `https://api.sase.paloaltonetworks.com`  
Scope: `tsg_id:1902164213`

## Summary

The OAuth2 client-credentials access token is obtained successfully and is
accepted by other endpoints (users, devices, applications all return 200).
Only the **policy** read endpoints return **403**, and the response body
indicates this is *not* an authorization failure: All 4 policy GET endpoints return the same error: `This endpoint is not yet available`.

This suggests these endpoints are published in the OpenAPI spec but not yet
available on the live service (error code `FORBIDDEN`, `x-request-flow-error:
DEF_403`). Request IDs are included below for support.

| Endpoint | Status | error.code | error.message | x-request-id |
|----------|--------|------------|---------------|--------------|
| `/v1/policy/security` | 403 Forbidden | `FORBIDDEN` | This endpoint is not yet available | `55d04446-eb16-4047-872b-a03f4385c48f` |
| `/v1/policy/sign-in` | 403 Forbidden | `FORBIDDEN` | This endpoint is not yet available | `63d66b23-62da-4752-8f3e-36e59bd815d7` |
| `/v1/policy/access-and-data` | 403 Forbidden | `FORBIDDEN` | This endpoint is not yet available | `63a5dd1a-199d-4b3b-9843-5acd6bd311f2` |
| `/v1/policy/customization` | 403 Forbidden | `FORBIDDEN` | This endpoint is not yet available | `0d35be38-ebe6-47b6-a12f-23d6ebb82e2c` |

---

## Security Policy

**GET https://api.sase.paloaltonetworks.com/seb-api/v1/policy/security?configurationVersion=draft&limit=100** → `403 Forbidden`

Request headers:
```
host: api.sase.paloaltonetworks.com
accept: */*
accept-encoding: gzip, deflate
connection: keep-alive
user-agent: python-httpx/0.28.1
authorization: <redacted>
```

Reproduce:
```bash
curl -i -X GET 'https://api.sase.paloaltonetworks.com/seb-api/v1/policy/security?configurationVersion=draft&limit=100' \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -H 'Accept: application/json'
```

Response headers:
```
date: Sat, 06 Jun 2026 16:22:17 GMT
content-type: application/json; charset=utf-8
content-encoding: gzip
vary: Origin,Accept-Encoding
x-talon-freshness: 2026-06-06T16:22:17.874648808Z;OJ7m3tukCFXlsT8YCy3L238Gc8AhUfABbybk1KqhPHLxOTnuXPAowq0U5K7E3bXqV/sAzsAFXnzgu7i660ku7nF/uIxjkZXHifdwchP1NjGcB9hMEvVD55FejxWExhSt
access-control-allow-origin: 
access-control-allow-credentials: true
access-control-allow-methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS
access-control-allow-headers: origin, x-requested-with, accept, content-type, authorization, x-tsg-id, x-panw-region, feature-flag-names, feature-flag-values
access-control-max-age: 1728000
x-request-flow-error: DEF_403
x-request-id: 55d04446-eb16-4047-872b-a03f4385c48f
via: 1.1 google
alt-svc: h3=":443"; ma=2592000
transfer-encoding: chunked
```

Response body:
```json
{"error":{"code":"FORBIDDEN","message":"This endpoint is not yet available","timestamp":"2026-06-06T16:22:17Z"}}
```

---

## Sign-In Policy

**GET https://api.sase.paloaltonetworks.com/seb-api/v1/policy/sign-in?configurationVersion=draft&limit=100** → `403 Forbidden`

Request headers:
```
host: api.sase.paloaltonetworks.com
accept: */*
accept-encoding: gzip, deflate
connection: keep-alive
user-agent: python-httpx/0.28.1
authorization: <redacted>
```

Reproduce:
```bash
curl -i -X GET 'https://api.sase.paloaltonetworks.com/seb-api/v1/policy/sign-in?configurationVersion=draft&limit=100' \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -H 'Accept: application/json'
```

Response headers:
```
date: Sat, 06 Jun 2026 16:22:18 GMT
content-type: application/json; charset=utf-8
content-encoding: gzip
vary: Origin,Accept-Encoding
x-talon-freshness: 2026-06-06T16:22:18.39318639Z;26NNWpefVL3n34lTppI2RUTmHmo8eqcYmYM3s5vUQTm2RymRsuCGH1X7MlfIxGYplVny+QIMbpVrr9Zml5liy7g6rseDZNEyDILJJKZaejqIcCTlMgn5K/+2r5rw6wPn
access-control-allow-origin: 
access-control-allow-credentials: true
access-control-allow-methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS
access-control-allow-headers: origin, x-requested-with, accept, content-type, authorization, x-tsg-id, x-panw-region, feature-flag-names, feature-flag-values
access-control-max-age: 1728000
x-request-flow-error: DEF_403
x-request-id: 63d66b23-62da-4752-8f3e-36e59bd815d7
via: 1.1 google
alt-svc: h3=":443"; ma=2592000
transfer-encoding: chunked
```

Response body:
```json
{"error":{"code":"FORBIDDEN","message":"This endpoint is not yet available","timestamp":"2026-06-06T16:22:18Z"}}
```

---

## Access And Data Policy

**GET https://api.sase.paloaltonetworks.com/seb-api/v1/policy/access-and-data?configurationVersion=draft&limit=100** → `403 Forbidden`

Request headers:
```
host: api.sase.paloaltonetworks.com
accept: */*
accept-encoding: gzip, deflate
connection: keep-alive
user-agent: python-httpx/0.28.1
authorization: <redacted>
```

Reproduce:
```bash
curl -i -X GET 'https://api.sase.paloaltonetworks.com/seb-api/v1/policy/access-and-data?configurationVersion=draft&limit=100' \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -H 'Accept: application/json'
```

Response headers:
```
date: Sat, 06 Jun 2026 16:22:18 GMT
content-type: application/json; charset=utf-8
content-encoding: gzip
vary: Origin,Accept-Encoding
x-talon-freshness: 2026-06-06T16:22:18.814026343Z;rpcwN+PutqrPefvDmPjSR8zGAGZzB/CUjvrFIRNr5gjaa3eP1JITv0LNeu/veHBjS9S9lxJGEAFukGHSOHbJ9dh9Sg9kFGSHbeCIB6ACw69xIz8lI6N2Os1G91JokRti
access-control-allow-origin: 
access-control-allow-credentials: true
access-control-allow-methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS
access-control-allow-headers: origin, x-requested-with, accept, content-type, authorization, x-tsg-id, x-panw-region, feature-flag-names, feature-flag-values
access-control-max-age: 1728000
x-request-flow-error: DEF_403
x-request-id: 63a5dd1a-199d-4b3b-9843-5acd6bd311f2
via: 1.1 google
alt-svc: h3=":443"; ma=2592000
transfer-encoding: chunked
```

Response body:
```json
{"error":{"code":"FORBIDDEN","message":"This endpoint is not yet available","timestamp":"2026-06-06T16:22:18Z"}}
```

---

## Customization Policy

**GET https://api.sase.paloaltonetworks.com/seb-api/v1/policy/customization?configurationVersion=draft&limit=100** → `403 Forbidden`

Request headers:
```
host: api.sase.paloaltonetworks.com
accept: */*
accept-encoding: gzip, deflate
connection: keep-alive
user-agent: python-httpx/0.28.1
authorization: <redacted>
```

Reproduce:
```bash
curl -i -X GET 'https://api.sase.paloaltonetworks.com/seb-api/v1/policy/customization?configurationVersion=draft&limit=100' \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -H 'Accept: application/json'
```

Response headers:
```
date: Sat, 06 Jun 2026 16:22:18 GMT
content-type: application/json; charset=utf-8
content-encoding: gzip
vary: Origin,Accept-Encoding
x-talon-freshness: 2026-06-06T16:22:18.990764632Z;3GgPw1FStyXnCra00dHQ6k/0QFBsI1U0sNIMZNVFK25BEtvbFfWjQsbmxTPumT6op4DZ5kPHtbUE6XtAh9KqYdcn5V9mQnKMk42pyfdGObPth7+95MKPITJcBI4aFWsh
access-control-allow-origin: 
access-control-allow-credentials: true
access-control-allow-methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS
access-control-allow-headers: origin, x-requested-with, accept, content-type, authorization, x-tsg-id, x-panw-region, feature-flag-names, feature-flag-values
access-control-max-age: 1728000
x-request-flow-error: DEF_403
x-request-id: 0d35be38-ebe6-47b6-a12f-23d6ebb82e2c
via: 1.1 google
alt-svc: h3=":443"; ma=2592000
transfer-encoding: chunked
```

Response body:
```json
{"error":{"code":"FORBIDDEN","message":"This endpoint is not yet available","timestamp":"2026-06-06T16:22:18Z"}}
```

---
