# Bàn giao hiện tại — TapOrder DESIGN-1

## Kết quả và nơi bắt đầu

Theo yêu cầu thiết kế backend thật kỹ trước khi giao agent khác, đã hoàn tất [DESIGN-1](../docs/design/README.md) trên nhánh `codex/taporder-backend-design`, từ main baseline `2397078`. Chưa merge main. [PLAN-2](../plans/product-plan.md) giữ scope sản phẩm, cập nhật race và trình tự milestone theo yêu cầu mới.

Đọc: [luồng A–Z](../docs/design/product-flow.md) ([SVG phóng to](../docs/design/assets/product-flow.svg)) → [system](../docs/design/system-design.md) → [data](../docs/design/data-model.md) → [technical](../docs/design/technical-design.md) → [API](../docs/design/api-design.md) → F01–F12 trong index → [test plan và thứ tự giao việc](../docs/design/test-plan.md). Nguồn/decisions ở [agent note](agents/taporder-backend-design.md).

## Quyết định không được đoán lại khi code

- Khách hủy toàn dòng của chính session khi waiting; pha chế chỉ waiting→preparing→done; bill paid terminal; payment unique kể cả tổng0.
- Submit expected null nếu bill mới vừa xuất hiện phải409 TABLE_VISIT_CHANGED, explicit join rồi submit key mới. Không tự chuyển lượt; replay command đã commit vẫn được sau paid khi principal/scope hợp lệ.
- Singleton guard ca bảo vệ open/close/create kể cả khi chưa ca; locks theo thứ tự toàn cục, event_clock cuối transaction. REPEATABLE READ snapshot+commit-ordered cursor để không mất SSE update. Partial mutation cursor không thay cursor stream.
- Availability cùng target/version là200 no-op, không tăng business version/event. DTO guest/kitchen/cashier riêng; kitchen không money/guest identity.
- Demo chỉ bàn1/3, usernames dự kiến barista.demo/cashier.demo; password/QR thật chỉ xuất TXT ignored khi demo. Xem [DEMO.txt](../DEMO.txt).

## Trạng thái kiểm chứng

Local docs: đủ12features/27endpoints, Mermaid parsed/rendered bằng Mermaid10.9.3+Chrome headless,50nodes/60edges; decisions có nhánh có nhãn, nodes có đường vào/ra hoặc điểm dừng; hình/màu theo glossary. Link/fence/whitespace/diff kiểm ở checkpoint cuối, số lượng trong WORKLOG. SVG từ đúng Mermaid source; renderer/ảnh kiểm tra nằm `.local-tools/design-render/` ignored, không dependency app.

Chưa có app/manifests/locks/migrations/canonical OpenAPI/accounts thật/mock/live/hosted CI/cloud deploy. Application unit/integration/lint/type/build chưa chạy và không áp dụng task Markdown; test plan không phải test results. Obsidian/ECC local giữ nguyên như setup. Playbook gốc có14link nguồn dự án khác không tồn tại, không dùng làm bằng chứng TapOrder.

## Việc giao agent tiếp theo

1. **C01 CONTRACT-1:** canonical OpenAPI/examples từ API design, validate examples/DTO/errors/security/nullability và generated types; freeze revision. Markdown chưa thay schema máy kiểm.
2. **S01:** scaffold/locks/DB test guard/Alembic/seed/harness/CI commands thật theo stack đã chốt.
3. **BE01:** foundation→order/cancel/kitchen/availability/pay→SSE, P2 sau theo test plan; regression fail khi practical, unit rồi PostgreSQL integration/contract/races, lint/type/build. FE01 có thể song song sau cùng C01/S01 baseline bằng worktree riêng khi được giao.
4. INT01 live/no mocks/two-table E2E/persistence; DEMO01 TXT ignored/rehearsal. Deploy chỉ khi được giao theo PLAN mục8.

Không quyết định nghiệp vụ chặn thiết kế. Contract/scaffold là việc tiếp theo, chưa hoàn thành. Không spawn agent khác trong task này. Nhánh/commit cuối tra history và remote SHA verification ở báo cáo cuối; không nhúng SHA tự tham chiếu. Nếu push chưa verified phải báo unsynced.
