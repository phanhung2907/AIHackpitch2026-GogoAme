# Chuẩn bị PLAN khi nhận đề

Trước hết đọc playbook PLAN/system/feature/flow và context. Sao chép [template](product-plan.template.md) thành `product-plan.md` sau khi nhận đề; điền nội dung thực tế, đánh dấu unknown và giải quyết phần chặn trước khi song song.

Trình tự: yêu cầu → hệ thống tổng thể → chức năng và luồng → contract baseline → hai agent FE mock + BE detailed design → backend code/test → tích hợp thật → verification/handoff.

Đầu ra thiết kế cần có: `docs/design/README.md`, `system-design.md`, `technical-design.md`, `data-model.md`, `product-flow.md`, `test-plan.md`, `features/Fxx-name.md`; `contracts/openapi.yaml` và `contracts/examples/` do coordinator quản lý. Đây là đường dẫn dự kiến, chưa phải tài liệu thiết kế hoàn tất.
