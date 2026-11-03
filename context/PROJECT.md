# Context bền vững

Ngày thiết lập: 2026-11-03 (Asia/Bangkok).

- Workspace/vault: `E:\AIHackpitch2026-GogoAme`.
- Remote đã có: `origin` → `https://github.com/phanhung2907/AIHackpitch2026-GogoAme.git`.
- Ban đầu repo chưa có commit, chỉ có `playbook/` chưa tracked; chưa có source, manifests, locks, tests hoặc CI.
- Chủ repo yêu cầu Obsidian + ECC local; cập nhật context sau mỗi việc; commit/push mỗi bước hoàn chỉnh; đọc playbook đúng task trước khi làm.
- Backend Python/FastAPI; PostgreSQL Docker. Frontend giữ stack cũ từ playbook; xem `agent.md`. Chưa có package cài trong repo.
- PLAN phải chi tiết FE/BE/system/features. Sau contract baseline, FE mock/UI song song BE detailed design; tiếp theo agent code/test backend rồi tích hợp thật.
- Đã nhận Đề 2 TapOrder: gọi món theo QR bàn; khách không login, pha chế và thu ngân có tài khoản/quyền/UI riêng. Nội dung PLAN-2 hoàn tất, chưa triển khai app. Nguồn chuẩn quyết định sản phẩm: [product plan](../plans/product-plan.md).
- Demo đúng hai bàn 1 và 3; usernames dự kiến barista.demo/cashier.demo, mật khẩu từ env khi seed; xuất account/QR thật vào TXT ignored tại DEMO01. [Hướng dẫn demo](../DEMO.txt). Reuse QRCodeSVG/export từ RestaurantSettings nguồn, thay QR chung quán thành capability từng bàn; DB hash lookup + encrypted token để cashier xuất lại.
- PLAN chọn một quán, FastAPI modular monolith, PostgreSQL, frontend stack giữ nguyên; SSE là sáng tạo ưu tiên. Khách hủy dòng của mình khi waiting; QR sau paid dùng cho lượt mới, chỉ tạo bill khi submit; món hết hàng làm reject toàn lượt. Chi tiết quyền/state/race trong PLAN.
- Bộ [DESIGN-1](../docs/design/README.md) chi tiết system/data/technical/API/F01–F12/test plan và [luồng A–Z](../docs/design/product-flow.md) đã có theo yêu cầu thiết kế backend trước khi bàn giao agent khác. Chưa code/canonical OpenAPI. Null submit đến sau bill mới phải409/xác nhận join; guard ca và commit-ordered event cursor theo detailed design. C01 rồi S01 vẫn là gate trước implementation/FE-BE song song.
- Chủ repo bổ sung ưu tiên deploy nhanh và tái sử dụng repo cùng đề. Đã clone 3 repo nguồn local ignored; chọn UI roshanx0/restaurant-ordering-saas (MIT, revision trong PLAN), thay Supabase bằng FastAPI. Railway một Docker web cùng origin + PostgreSQL service là hướng chính; Render dự phòng. Chưa tạo cloud resource/deploy.
- Các ví dụ banking và kết quả test trong playbook là từ dự án khác, không phải trạng thái repo này.
- Markdown trong repo là context chuẩn và có thể đọc ngoài Obsidian. UI settings/ECC local/tools/secrets bị ignore.

Nguồn quy trình: [AGENTS](../AGENTS.md), [agent guide](../agent.md), [playbook](../playbook/README.md). Trạng thái thay đổi nhanh xem [HANDOFF](HANDOFF.md).
