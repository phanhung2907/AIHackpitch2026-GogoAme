# Integration live — 2026-11-03

Owner: current main agent. User authorized combining backend and frontend on main; explicitly prohibited tests; limited to five minutes. Synced main before edits. Backend copied as snapshot from existing backend worktree; original worktree unchanged. Design/contract imported from codex/taporder-backend (7f49043). Sources: agent/context/playbook routing; frontend/backend/system/feature/CI/testing playbooks; git-workflow, tdd-workflow (test steps overridden by user), security-review, deployment-patterns, verification-loop; backend design/system/F03, canonical contract and implementation routes/services/config/security/schema/seed.

FE default is live; menu/category/price, guest join/current visit, kitchen tickets, shift envelopes, server cancel permission, QR export and staff CSRF restore wired to actual backend. Idempotency key retained on network/server uncertainty. Demo script and detailed static review: [review](../../docs/backend-review-integration.md).

Checks: git diff whitespace review; no tests run. Frontend build attempted but npm unavailable and frontend node_modules absent, so build/type not verified. Backend and Docker not started; no runtime/hosted CI/deployed acceptance. Existing deployment origin/rewrite unavailable; published frontend still requires rebuild and proxy to local backend over HTTPS. LAN demo uses local Vite same-origin proxy; not a verified deployed demo. Known gap: FE polling rather than SSE and first kitchen queue page only.

Next: run demo-lan.ps1 with real Wi-Fi IP and npm installed; configure deployed host rewrite if requiring existing public URL; verify runtime when owner permits.
