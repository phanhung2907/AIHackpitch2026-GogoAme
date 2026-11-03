# Bàn giao hiện tại

## Trạng thái

Theo yêu cầu chủ repo, đưa PLAN vào `main`. Trước thao tác remote chưa có main; tạo main từ toàn bộ lịch sử `codex/taporder-plan` tại `0f53293`, giữ nguyên các nhánh cũ và nhánh mặc định remote. Checkpoint này chỉ cập nhật Git/context, chưa triển khai app. Xem remote main và Git history để xác nhận SHA sau push.

SETUP và nội dung PLAN-2 hoàn tất trên `codex/taporder-plan`: [PLAN chung](../plans/product-plan.md) đủ system/quyền/data, reuse/deploy, feature/API dự kiến/FE/BE/flows/tasks/tests/CI và demo. [DEMO.txt](../DEMO.txt) có usernames dự kiến, cách xuất mật khẩu/URL thật ra TXT local ignored và script Hội đồng. Đúng hai bàn 1/3. Chưa có app/account thật/mock/live/canonical OpenAPI/hosted CI/cloud deploy. Xem Git history và remote SHA cho checkpoint đã push mới nhất.

## Đã chuẩn bị

`AGENTS.md`, `agent.md`, PLAN và feature templates, README, ignore local tools/secrets, quy trình context/commit/push và chia hai agent bằng worktree.

Đã đọc toàn bộ 10 file trong `playbook/`; stack và các lưu ý được chuyển vào hướng dẫn, không coi ví dụ banking là yêu cầu mới. Playbook giữ nguyên nội dung gốc.

## Công cụ và kiểm tra

Obsidian 1.15.0 đã được cài/cập nhật, root repo đã đăng ký vault, giữ bốn vault cũ; chưa mở UI xác nhận. ECC có đủ 314 skills/620 files local trùng upstream revision `b38be6a7f6350964d59328b52f0624e1d1d552d1`, không cần cài đè. Xem [setup](../docs/setup.md) và [WORKLOG](WORKLOG.md) cho verification.

Playbook có 14 link tới source của dự án cũ không tồn tại ở repo này. Giữ nguyên bản gốc; chỉ dùng nội dung kinh nghiệm, không dựa vào các link đó để kết luận thiết kế/code/test hiện tại đã có. Các link nội bộ của tài liệu setup mới đã kiểm tra hợp lệ.

## Việc tiếp theo

C01: tạo canonical OpenAPI/examples/validation từ PLAN-2, chốt CONTRACT-1; tiếp S01 scaffold/locks/CI rồi FE mock/UI song song backend detailed design ở worktrees riêng khi được giao. Lượt này chỉ PLAN, chưa chạy hai agent sản phẩm hay code app.

Nhánh/SHA: tra Git history và remote của checkpoint mới nhất; không nhúng SHA tự tham chiếu vào commit. Nếu remote chưa khớp, báo unsynced.
