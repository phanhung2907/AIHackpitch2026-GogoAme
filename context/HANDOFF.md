# Bàn giao hiện tại

## Trạng thái

SETUP hoàn tất trong phạm vi công cụ/tài liệu, đã push checkpoint `d2dd422` lên `origin/codex/setup-agent-workflow` và xác minh SHA local/remote khớp. Chờ đề bài trước PLAN. Chưa có app/mock/live/backend design hoàn chỉnh. Không có hosted CI/deploy. Commit bổ sung bàn giao nằm sau checkpoint này; tra Git để lấy HEAD mới nhất.

## Đã chuẩn bị

`AGENTS.md`, `agent.md`, PLAN và feature templates, README, ignore local tools/secrets, quy trình context/commit/push và chia hai agent bằng worktree.

Đã đọc toàn bộ 10 file trong `playbook/`; stack và các lưu ý được chuyển vào hướng dẫn, không coi ví dụ banking là yêu cầu mới. Playbook giữ nguyên nội dung gốc.

## Công cụ và kiểm tra

Obsidian 1.15.0 đã được cài/cập nhật, root repo đã đăng ký vault, giữ bốn vault cũ; chưa mở UI xác nhận. ECC có đủ 314 skills/620 files local trùng upstream revision `b38be6a7f6350964d59328b52f0624e1d1d552d1`, không cần cài đè. Xem [setup](../docs/setup.md) và [WORKLOG](WORKLOG.md) cho verification.

Playbook có 14 link tới source của dự án cũ không tồn tại ở repo này. Giữ nguyên bản gốc; chỉ dùng nội dung kinh nghiệm, không dựa vào các link đó để kết luận thiết kế/code/test hiện tại đã có. Các link nội bộ của tài liệu setup mới đã kiểm tra hợp lệ.

## Việc tiếp theo

Nhận đề từ chủ repo → đọc context + playbook PLAN → tạo `plans/product-plan.md` từ template → chốt scope/system/features/contract trước hai agent. Chưa cần khởi chạy hai agent ở SETUP.

Nhánh/SHA: tra Git history và remote của checkpoint mới nhất; không nhúng SHA tự tham chiếu vào commit. Nếu remote chưa khớp, báo unsynced.
