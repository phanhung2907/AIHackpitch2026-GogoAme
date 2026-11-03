# Context bền vững

Ngày thiết lập: 2026-11-03 (Asia/Bangkok).

- Workspace/vault: `E:\AIHackpitch2026-GogoAme`.
- Remote đã có: `origin` → `https://github.com/phanhung2907/AIHackpitch2026-GogoAme.git`.
- Ban đầu repo chưa có commit, chỉ có `playbook/` chưa tracked; chưa có source, manifests, locks, tests hoặc CI.
- Chủ repo yêu cầu Obsidian + ECC local; cập nhật context sau mỗi việc; commit/push mỗi bước hoàn chỉnh; đọc playbook đúng task trước khi làm.
- Backend Python/FastAPI; PostgreSQL Docker. Frontend giữ stack cũ từ playbook; xem `agent.md`. Chưa có package cài trong repo.
- PLAN phải chi tiết FE/BE/system/features. Sau contract baseline, FE mock/UI song song BE detailed design; tiếp theo agent code/test backend rồi tích hợp thật.
- Đã nhận Đề 2 TapOrder: gọi món theo QR bàn; khách không login, pha chế và thu ngân có tài khoản/quyền/UI riêng. Đang PLAN, chưa triển khai app. Nguồn chuẩn quyết định sản phẩm: [product plan](../plans/product-plan.md).
- PLAN chọn một quán, FastAPI modular monolith, PostgreSQL, frontend stack giữ nguyên; SSE là sáng tạo ưu tiên. Khách hủy dòng của mình khi waiting; QR sau paid dùng cho lượt mới, chỉ tạo bill khi submit; món hết hàng làm reject toàn lượt. Chi tiết quyền/state/race trong PLAN.
- Các ví dụ banking và kết quả test trong playbook là từ dự án khác, không phải trạng thái repo này.
- Markdown trong repo là context chuẩn và có thể đọc ngoài Obsidian. UI settings/ECC local/tools/secrets bị ignore.

Nguồn quy trình: [AGENTS](../AGENTS.md), [agent guide](../agent.md), [playbook](../playbook/README.md). Trạng thái thay đổi nhanh xem [HANDOFF](HANDOFF.md).
