# Session demo update — 2026-11-03

Owner confirmed cashier/barista in two tabs of same browser: shared staff cookie replaces prior login. Use separate browsers/profiles/devices. StaffLayout now only clears identity for SESSION_EXPIRED; connection/server errors block business UI with retry. Login screen explains browser separation. No tests run by owner request; TypeScript/Vite build passed. Hotspot latest IP is 10.232.251.33; Vite was restarted after hung process and root HTTP returned 200 on loopback and hotspot IP.

# Running demo update — 2026-11-03

Npm installed; FE TypeScript/Vite build passed. Backend Uvicorn started on 127.0.0.1:8000 with Docker PostgreSQL; migrate/seed completed. FE live running at http://10.12.3.127:5173. Accounts/QR: ignored .local-tools/demo/accounts.txt. No tests executed by owner request; no browser/HTTP acceptance. Existing deployed frontend still needs API proxy/redeploy. See [demo guide](../docs/backend-review-integration.md), latest section. Previous checkpoint descriptions below are historical.

# Latest integration checkpoint — 2026-11-03

Backend/design/contract snapshot and live FE integration now on main. No tests run by explicit request. Build unavailable: npm/dependencies missing. Backend not started and deployed frontend proxy not configured. See [integration checkpoint](agents/integration-live.md) and [demo guide](../docs/backend-review-integration.md). Earlier entries below describe historical state.

# Bàn giao hiện tại

## Trạng thái

FE01 xong trên nhánh `codex/frontend-taporder` (cắt từ `main` tại `2397078`): có `frontend/` chạy được cho cả ba vai trò của Đề 2 trên mock trong browser, kiểm tra bằng `tsc -b`, `vite build` và click trọn kịch bản `DEMO.txt` ở `127.0.0.1:5173`. Chưa có backend, chưa có canonical OpenAPI, chưa có test tự động, chưa deploy. Chi tiết và giới hạn: [WORKLOG mục FE01](WORKLOG.md) và [frontend/README.md](../frontend/README.md).

Lưu ý quy trình: frontend được làm trước CONTRACT theo yêu cầu chủ repo (thành viên khác làm backend rồi nối). `frontend/src/api/client.ts` giữ chữ ký theo contract dự kiến §10.2 để đổi sang live chỉ bằng `VITE_USE_MOCK=0`, nhưng đó là contract **dự kiến**, chưa phải CONTRACT-1 đã chốt.

Theo yêu cầu chủ repo, đưa PLAN vào `main`. Trước thao tác remote chưa có main; tạo main từ toàn bộ lịch sử `codex/taporder-plan` tại `0f53293`, giữ nguyên các nhánh cũ và nhánh mặc định remote. Checkpoint này chỉ cập nhật Git/context, chưa triển khai app. Xem remote main và Git history để xác nhận SHA sau push.

SETUP và nội dung PLAN-2 hoàn tất trên `codex/taporder-plan`: [PLAN chung](../plans/product-plan.md) đủ system/quyền/data, reuse/deploy, feature/API dự kiến/FE/BE/flows/tasks/tests/CI và demo. [DEMO.txt](../DEMO.txt) có usernames dự kiến, cách xuất mật khẩu/URL thật ra TXT local ignored và script Hội đồng. Đúng hai bàn 1/3. Chưa có app/account thật/mock/live/canonical OpenAPI/hosted CI/cloud deploy. Xem Git history và remote SHA cho checkpoint đã push mới nhất.

## Đã chuẩn bị

`AGENTS.md`, `agent.md`, PLAN và feature templates, README, ignore local tools/secrets, quy trình context/commit/push và chia hai agent bằng worktree.

Đã đọc toàn bộ 10 file trong `playbook/`; stack và các lưu ý được chuyển vào hướng dẫn, không coi ví dụ banking là yêu cầu mới. Playbook giữ nguyên nội dung gốc.

## Công cụ và kiểm tra

Obsidian 1.15.0 đã được cài/cập nhật, root repo đã đăng ký vault, giữ bốn vault cũ; chưa mở UI xác nhận. ECC có đủ 314 skills/620 files local trùng upstream revision `b38be6a7f6350964d59328b52f0624e1d1d552d1`, không cần cài đè. Xem [setup](../docs/setup.md) và [WORKLOG](WORKLOG.md) cho verification.

Playbook có 14 link tới source của dự án cũ không tồn tại ở repo này. Giữ nguyên bản gốc; chỉ dùng nội dung kinh nghiệm, không dựa vào các link đó để kết luận thiết kế/code/test hiện tại đã có. Các link nội bộ của tài liệu setup mới đã kiểm tra hợp lệ.

## Việc tiếp theo

Backend FastAPI theo §10.2/§12 rồi nối `VITE_USE_MOCK=0`; sau đó C01: tạo canonical OpenAPI/examples/validation từ PLAN-2, chốt CONTRACT-1; tiếp S01 scaffold/locks/CI rồi FE mock/UI song song backend detailed design ở worktrees riêng khi được giao. Lượt này chỉ PLAN, chưa chạy hai agent sản phẩm hay code app.

Nhánh/SHA: tra Git history và remote của checkpoint mới nhất; không nhúng SHA tự tham chiếu vào commit. Nếu remote chưa khớp, báo unsynced.
