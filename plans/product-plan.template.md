# Product PLAN — TEMPLATE, chưa có đề bài

Trạng thái: DRAFT. Không dùng template này như một plan đã duyệt.

## 1. Bài toán và tiêu chí thành công

Đề gốc, actor, nhu cầu, kết quả quan sát được, giới hạn demo/production. Liên kết nguồn và câu hỏi cần chủ repo quyết định.

## 2. Phạm vi và giả định

In/out scope, MVP/later, dữ liệu thật/demo, dependency ngoài, rủi ro và quyết định chặn (owner/hạn/ảnh hưởng). Không suy ra nghiệp vụ từ playbook ngân hàng.

## 3. Quyết định stack và môi trường

Giữ frontend stack trong agent.md; backend Python/FastAPI; PostgreSQL Docker. Chốt version/locks, template/license, auth, API origin/proxy, config, dev/test/staging, ports/volumes/health và secrets. Ghi lý do và đánh đổi.

## 4. Actor và quyền

Ma trận role × action × resource scope; ownership; nguồn danh tính; quyền backend và UI. Nếu không cần auth, ghi lý do/phạm vi.

## 5. Danh mục tính năng

| Feature ID | Mục tiêu | Actor | Ưu tiên | Phụ thuộc | Design | Acceptance |
| --- | --- | --- | --- | --- | --- | --- |

Mỗi feature phải có thiết kế theo `docs/templates/feature-design.md` trước khi code.

## 6. Hệ thống và dữ liệu

Component/deployment diagram; module ownership, request/data flow, external integrations; NFR đo được và ngân sách hiệu năng. Entity/relationship, schema chi tiết, constraints/indexes/query patterns, migrations/seed, UTC/units, retention, invariants, trạng thái và concurrency/transaction boundaries; backup/restore/rollback theo nhu cầu.

## 7. Contract dùng chung

Endpoint inventory, request/response/errors/status codes/examples, auth/permission, pagination/filter/sort, retry/idempotency theo nhu cầu. Nguồn chuẩn `contracts/openapi.yaml`, cách validate và đồng bộ FastAPI schema/types/fixtures. Chốt baseline trước hai agent.

## 8. Frontend chi tiết

Route × role × feature × endpoint, navigation/layout, component boundaries, form/validation, cache/invalidation, URL state, responsive/accessibility, loading/empty/error/retry/success. Mock scenarios theo contract, live switch và test kế hoạch. Không chọn UI độc lập với dữ liệu/quyền.

## 9. Backend chi tiết

Modules/routes/services/domain/repositories, thứ tự validation/authorization, thuật toán từng use case, DB writes/reads/locks/rollback, lifecycle/errors/log/audit, dependency failures và recovery. Liên kết design đủ để agent khác code/test, không để TODO ở quyết định cần cho implementation.

## 10. Luồng sản phẩm

A–Z, success/error/pending/cancel/recovery; sequence/state/ER theo nhu cầu, giải thích bằng lời và thuật ngữ thống nhất.

## 11. Task graph và hai agent

| Task ID | Owner | Branch/worktree | Input/revision | Artifact | Depends on | Done/checks |
| --- | --- | --- | --- | --- | --- | --- |

Coordinator giữ contracts/plans/context tổng; FE giữ frontend; BE design giữ docs/design. Ghi mốc chuyển BE design sang implementation agent, contract-change protocol và merge order.

## 12. Testing và CI/CD

Acceptance → test cases → cấp test → command → fixture/environment → expected response/DB state. Unit rồi integration đúng phạm vi; gates lint/type/build/contract, critical E2E khi cần. CI install locks, minimal permissions, branch/path filters, protected secrets, release/deploy authorization và rollback.

## 13. Tích hợp dữ liệu thật

Điều kiện FE/BE ready; tắt mock, origin/session/CORS/CSRF theo auth đã chọn, DB migrate/seed, create/update/read-back/reload, permissions/errors, no mock fallback. Ghi tiêu chí dừng, owner và bằng chứng live.

## 14. Bàn giao

Hướng dẫn chạy từ máy sạch, artifact index, context, checks đã/chưa chạy, quyết định mở, nhánh/remote, next task cụ thể cho agent code/testing.
