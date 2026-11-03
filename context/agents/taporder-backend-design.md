# Agent checkpoint — TapOrder backend DESIGN-1

- Task/owner/date: BD01 thiết kế backend, primary agent,2026-11-03 Asia/Bangkok. Yêu cầu chủ repo: system design trước feature design, một Mermaid A–Z nhất quán, chuẩn bị giao agent khác; không implementation.
- Branch/baseline: codex/taporder-backend-design từ main2397078; contract chưa canonical, API design là đầu vào C01. Không spawn agent hoặc deploy.
- Nguồn đã đọc: AGENTS.md, agent.md, context PROJECT/HANDOFF/WORKLOG gần nhất, context agent template; playbook index và danh sách10file; systemdesign/featuredesign/flowdesign/chartdrawing/backend/testing/CICD_CONTEXT; plans README/product-plan, docs feature template, README. Skills local git-workflow/security-review/verification-loop/agent-self-evaluation; không copy ECC.
- Quyết định: modular monolith/Python FastAPI/Postgres/stack FE giữ PLAN; thống nhất null submit race theo PLAN9.1; guard singleton+event_clock và repeatable snapshot chống race ca/SSE; no-op availability target explicit. Chi tiết ở technical design, không thêm scope sản phẩm.
- Artifacts: docs/design/index/system/data/technical/API/product-flow/test-plan;12 feature files; SVG render từ Mermaid; PLAN/README/plans README/context liên kết và trạng thái thống nhất. Không canonical OpenAPI hoặc app code.
- Mock/live: chưa app/cả hai chưa có; chưa tài khoản/QR môi trường thật; secrets/QR URLs thật không nằm trong artifacts.
- Checks: Python docs link/fence/feature/endpoint/graph check; Mermaid10.9.3 parse+Chrome render thành SVG50nodes/60edges; diff whitespace/review. Chi tiết cuối trong WORKLOG. Công cụ/renderer download local ignored, không thêm application dependency.
- Chưa chạy: application unit/integration/lint/types/build/dependency audit (chưa app/lock), hosted CI/deployed checks (chưa có môi trường). Test plan chỉ acceptance specification.
- Blocker: không blocker thiết kế; C01/S01 là gates còn phải làm trước code. Giới hạn kiểm chứng: concurrency/security là thiết kế đã review, chưa runtime chứng minh; Mermaid render không chứng minh nghiệp vụ chạy.
- Git: stage/commit/push đúng scope và xác minh SHA origin sau docs gates; SHA cuối tra history/ls-remote/báo cáo, không tự tham chiếu. Không merge main/force push/đổi remote.
- Next owner: agent được chủ repo giao →C01 contract từ API design→S01→BE01 theo test plan; không bắt đầu implementation bằng payload tự đoán. FE parallel sau baseline và worktree riêng khi được giao.
