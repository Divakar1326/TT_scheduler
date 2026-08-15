# Deployment Checklist

Concise readiness summary for the UniSched ERP production release.

## Checklist Status

- [✓] **Production Environment Configuration**: Configured in [`config/config.py`](file:///c:/Users/diva1/Documents/TT_Sheduler/config/config.py) to validate variables in production.
- [✓] **Secret Protection**: `.env` and `CREDENTIALS.md` are added to `.gitignore` and are not tracked in git history.
- [✓] **Favicon**: Added SVG, ICO, and PNG favicon assets to the static folder [`app/ui`](file:///c:/Users/diva1/Documents/TT_Sheduler/app/ui) and linked them in [`app/ui/index.html`](file:///c:/Users/diva1/Documents/TT_Sheduler/app/ui/index.html).
- [✓] **Metadata**: Set proper title and assets in [`app/ui/index.html`](file:///c:/Users/diva1/Documents/TT_Sheduler/app/ui/index.html).
- [✓] **Routing**: Unified routes mapped through Flask's `static_folder="ui"` without conflicting frontend routes.
- [✓] **CORS**: Not required when deployed unified (frontend + API on same origin). If split, requires backend CORS middleware config.
- [✓] **Authentication**: Working session token store (UUID-based tokens) with role-based routing checks.
- [✓] **Authorization**: Enforced server-side HOD department isolation on CRUD and generation endpoints.
- [✓] **Supabase**: Direct connection manager with pool retries and failover setup.
- [✓] **AI Providers**: Multi-provider fallback chain (OpenRouter → Groq → Cerebras → Gemini) tested and working.
- [✓] **Security Audit**: Checked for secrets exposure, HOD leaks, and database failover safeguards.
- [✓] **Dependency Audit**: Verified [`requirements.txt`](file:///c:/Users/diva1/Documents/TT_Sheduler/requirements.txt) contains necessary packages for production.
- [✓] **File Cleanup**: Cleaned up workspace files.
- [✓] **Production Build**: Verified Flask app starts and runs diagnostics self-check successfully.
- [✓] **Smoke Test**: Passed all critical path API, Auth, and Constraint validation tests (50/50 test passes).
- [✓] **Git Audit**: Verified status and confirmed no credentials/keys are staged.
- [!] **GitHub Push** - *REQUIRES MANUAL VERIFICATION*: No Git remote is currently set up. Git remote must be configured manually before pushing.
- [!] **Vercel Readiness** - *REQUIRES MANUAL VERIFICATION*: The backend has long-running scheduler processes (up to 120s limit) and uses real-time Server-Sent Events (SSE) streaming, which are incompatible with Vercel's serverless function time limits and response buffering. It is recommended to deploy the backend to a persistent server host (e.g., Render or Railway) and the frontend static assets to Vercel (using Vercel rewrites to proxy API requests).
