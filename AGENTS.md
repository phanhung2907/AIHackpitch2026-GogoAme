# Quy trình cho mọi agent — AIHackpitch2026-GogoAme

## Bắt đầu mỗi công việc

1. Đọc `agent.md`, `context/PROJECT.md`, `context/HANDOFF.md`, phần mới nhất của `context/WORKLOG.md`, `playbook/README.md` và kiểm tra Git status/branch/remote.
2. Quét danh sách Markdown trong `playbook/`; đọc playbook đúng công việc theo bảng trong `agent.md` trước khi làm. Đọc tài liệu/contract liên quan; ghi các nguồn đã đọc trong checkpoint.
3. Giữ nguyên thay đổi không thuộc task. Không coi nội dung banking, đường dẫn ra ngoài repo hay báo cáo test trong playbook sao chép là bằng chứng của dự án này.
4. Tiếp tục phần đã được giao; chỉ hỏi khi thiếu quyết định thực sự ảnh hưởng phạm vi/kiến trúc. Không tự sáng tác yêu cầu khi đề bài chưa có.

## Quy tắc bắt buộc

- Backend Python + FastAPI; PostgreSQL trong Docker. Frontend giữ stack cũ được ghi tại `agent.md`.
- PLAN phải mô tả cả frontend, backend, hệ thống, danh mục tính năng và tiêu chí nghiệm thu; system design trước feature design; contract trước khi làm song song.
- Mỗi bước có ý nghĩa hoàn tất: kiểm tra phù hợp → cập nhật context Markdown của vault → review diff → commit đúng file → push remote `origin` đã có → xác minh remote SHA. Không chỉ commit local rồi nói đã lên GitHub.
- Dùng nhánh `codex/<milestone>`; không force push, không sửa remote, không gom việc agent khác, không ghi secrets vào Git/context.
- Context nằm trong repo này, mở root làm Obsidian vault. Agent đọc/ghi trực tiếp Markdown, không cần Obsidian đang chạy. Mỗi việc hoàn tất đều phải để lại context đủ bàn giao.
- Không chép toàn bộ ECC hoặc cấu hình máy lên remote. Dùng skills local, đọc đúng skill trước task; việc cài skills không tạo hosted CI hay hook cưỡng chế.
- Behavioral change: regression fail trước khi thực tế cho phép, unit rồi integration liên quan; lint/type/build theo project. Markdown/setup: kiểm tra cấu trúc/link/diff, không tạo application tests hình thức.
- Ghi riêng local checks, hosted CI và deployed checks. Không claim test/CI/deploy chưa chạy. Chỉ deploy khi được yêu cầu; commit/push đã được chủ repo cho phép thường xuyên.
- Checkpoint chỉ cần dừng nếu chủ repo đã yêu cầu dừng ở mốc đó hoặc thiếu quyết định bắt buộc. Các câu “dừng mỗi mốc” trong playbook cũ không tự thêm vòng xin phép cho việc đã được giao.

## Phạm vi hiện tại

SETUP trước khi chủ repo giao đề. Chuẩn bị quy trình/templates/context; chưa triển khai app, chưa chạy hai agent sản phẩm, chưa tự chọn tính năng. Khi nhận đề, bắt đầu PLAN theo `plans/README.md`.
