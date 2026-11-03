# Chuẩn bị PLAN khi nhận đề

Trước hết đọc playbook PLAN/system/feature/flow và context. Sao chép [template](product-plan.template.md) thành `product-plan.md` sau khi nhận đề; điền nội dung thực tế, đánh dấu unknown và giải quyết phần chặn trước khi song song.

Trình tự: yêu cầu → hệ thống tổng thể → chức năng và luồng → contract baseline → hai agent FE mock + BE detailed design → backend code/test → tích hợp thật → verification/handoff.

Đầu ra thiết kế đã có tại [DESIGN-1](../docs/design/README.md): system/technical/data/API, product flow, test plan và đủ F01–F12. Theo yêu cầu chủ repo, hoàn tất thiết kế trước khi giao agent code; chưa có canonical `contracts/openapi.yaml`/examples. Coordinator làm C01 từ API design trước khi scaffold/code hoặc FE/BE song song.
