# API Connection Audit Report

This report confirms the stability and correctness of all frontend-backend API connections, verifying endpoints, HTTP methods, authentication headers, request bodies, response formats, CORS, and error handling.

---

## Connection Matrix & Verification Status

| Endpoint Path | HTTP Method | Auth Role | Request Body | Response Format | CORS / Same-Origin | Status |
| :--- | :---: | :---: | :--- | :--- | :---: | :---: |
| `/api/auth/login` | POST | Public | `{"username", "password"}` | `{"token", "role"}` | Same-Origin | Verified |
| `/api/dashboard/stats` | GET | HOD | None | `{ faculty_count, ... }` | Same-Origin | Verified |
| `/api/departments` | GET / POST | HOD / Admin | (Post) `Department` Dict | JSON List / Message | Same-Origin | Verified |
| `/api/faculties` | GET / POST | HOD / Admin | (Post) `Faculty` Dict | JSON List / Message | Same-Origin | Verified |
| `/api/courses` | GET / POST | HOD / Admin | (Post) `Course` Dict | JSON List / Message | Same-Origin | Verified |
| `/api/sections` | GET / POST | HOD / Admin | (Post) `Section` Dict | JSON List / Message | Same-Origin | Verified |
| `/api/rooms` | GET / POST | HOD / Admin | (Post) `Room` Dict | JSON List / Message | Same-Origin | Verified |
| `/api/laboratories` | GET / POST | HOD / Admin | (Post) `Lab` Dict | JSON List / Message | Same-Origin | Verified |
| `/api/rules` | GET | HOD | None | JSON List of Rules | Same-Origin | Verified |
| `/api/rules/parse-natural`| POST | HOD | `{"rule_text"}` | Structured Rule JSON | Same-Origin | Verified |
| `/api/rules/validate-structure`| POST | HOD | `{"parameter"}` | `{"valid", "errors"}` | Same-Origin | Verified |
| `/api/rules/save` | POST | Admin | Rule Object | `{"message", "rule_id"}` | Same-Origin | Verified |
| `/api/rules/toggle` | POST | Admin | `{"rule_id", "version"}`| `{"message"}` | Same-Origin | Verified |
| `/api/rules/versions/<id>`| GET | HOD | None | JSON List of Versions | Same-Origin | Verified |
| `/api/scheduler/generate` | POST | HOD | None | `{"message", "stats"}` | Same-Origin | Verified |
| `/api/scheduler/validate` | POST | HOD | `{"schedule"}` (Opt) | `{"is_valid", "errors"}`| Same-Origin | Verified |
| `/api/scheduler/repair` | POST | HOD | `{"schedule"}` (Opt) | `{"repaired_schedule"}` | Same-Origin | Verified |
| `/api/scheduler/export` | GET | HOD | None (Query Parameters) | CSV Attachment / HTML | Same-Origin | Verified |

---

## Connection Stability Audits

1. **Authentication**: All endpoints (except `/api/auth/login`) inspect request headers for `Authorization: Bearer <token>` using the `@require_role` decorator. If missing or invalid, an HTTP `401 Unauthorized` or `403 Forbidden` response is returned. Direct export attachments are allowed using URL parameters `?Authorization=Bearer ...` for secure downloads via browser redirection.
2. **Method & CORS Verification**: Flask app routes are configured same-origin with relative URLs (`API_BASE = ""`), avoiding CORS errors. Attempting unsupported HTTP verbs (e.g. GET on login) returns standard Flask HTTP `405 Method Not Allowed`.
3. **Error Handling**: Database exceptions, schema validation errors, and runtime failures are caught by Flask's global error handler (`@app.errorhandler(Exception)`) and mapped to standard JSON response objects: `{"error": "message"}` with appropriate HTTP status codes (e.g., `400 Bad Request` or `500 Internal Server Error`).
