# Hướng dẫn thực thi và bàn giao

File hướng dẫn chính cho workflow của chủ repo; `AGENTS.md` là điểm vào để công cụ agent tự phát hiện. Nếu thay quy trình, cập nhật cả hai cho nhất quán.

## Nguồn chuẩn và stack

- Yêu cầu trực tiếp của chủ repo → quyết định đã chốt trong context/plan → contract và design → implementation đã kiểm chứng. Nếu khác nhau, ghi xung đột và giải quyết, không âm thầm chọn.
- Backend: Python, FastAPI/Uvicorn; SQLAlchemy + psycopg, Alembic là hướng mặc định theo playbook, xác nhận trong PLAN; PostgreSQL chạy Docker Compose, DB test riêng.
- Frontend giữ stack trong `playbook/frontend_TRICK.md`: React, TypeScript, Vite, Tailwind CSS, shadcn/ui/Radix, TanStack Router/Query/Table, React Hook Form + Zod, Zustand. Template cũ là satnaing/shadcn-admin (MIT). Chưa có source/lock frontend trong repo: khi scaffold kiểm tra upstream/license/compatibility và khóa version thực tế; không coi các số version trong playbook là package đã cài.
- Không áp nghiệp vụ banking/tiền/auth đặc thù từ ví dụ sang đề mới. Không thêm Redis/queue/microservices nếu không có nhu cầu.

## Đọc playbook theo task

| Task | Playbook phải đọc |
| --- | --- |
| PLAN/phân rã | `PLAN_TRICK.md`, `systemdesign_TRICK.md`, `featuredesign_TRICK.md` |
| Thiết kế hệ thống/DB | `systemdesign_TRICK.md`, `backend_TRICK.md` |
| Thiết kế tính năng | `featuredesign_TRICK.md`, `flowdesign_TRICK.md` |
| Frontend/mock/tích hợp | `frontend_TRICK.md`, `featuredesign_TRICK.md` |
| Backend implementation | `backend_TRICK.md`, `systemdesign_TRICK.md` |
| Sơ đồ | `chartdrawing_TRICK.md`, `flowdesign_TRICK.md` |
| Kiểm thử | `testing_TRICK.md` |
| CI/CD, commit, bàn giao | `CICD_CONTEXT_TRICK.md`, `testing_TRICK.md` |

Các tên trên nằm trong `playbook/`. Luôn xem index/danh sách hiện tại để phát hiện playbook mới; tips là kinh nghiệm, không thay yêu cầu hoặc bằng chứng test.

## Các mốc và điều kiện hoàn tất

| Mốc | Đầu ra | Gate |
| --- | --- | --- |
| SETUP | Agent guide, vault/context, local tools, templates | Kiểm tra docs, cài đặt thực tế, commit/push được xác minh |
| PLAN | `plans/product-plan.md` từ template | Scope, feature/screen/role matrix, kiến trúc, data, contracts, task graph, acceptance rõ; câu hỏi chặn có quyết định |
| CONTRACT | `contracts/openapi.yaml`, examples, `docs/design/README.md` | Request/response/error/permissions/enum thống nhất; schema/examples hợp lệ, không TODO ở interface dùng chung |
| PARALLEL | FE mock/UI + BE detailed design | Hai nhánh độc lập, cùng contract revision, owner file rõ; BE đủ bàn giao code/test |
| IMPLEMENT | BE theo design, FE hoàn thiện | Unit/integration phù hợp, migration/seed, contract compliance, lint/type/build |
| INTEGRATE | FE gọi FastAPI/DB thật | Tắt mock, API client giữ nguyên interface; luồng đọc/ghi/refetch/quyền/lỗi qua browser origin thực tế |
| VERIFY/HANDOFF | Báo cáo + context + Git | Gate project pass, remote SHA, rủi ro và việc tiếp theo rõ; deployment chỉ khi được giao |

Mỗi task nhỏ trong một mốc cũng phải cập nhật context khi xong; commit/push theo bước hoàn chỉnh có thể review. Task thất bại ghi trạng thái blocked/partial, không đánh dấu done.

## Hai agent sau khi PLAN và contract sẵn sàng

Chủ repo đã định hướng làm song song; chưa khởi chạy ở SETUP. Coordinator tạo hai worktree/nhánh từ cùng baseline đã push, tránh hai agent checkout trên một working tree.

- **Frontend agent** sở hữu `frontend/**`: dựng layout/routes/forms/state, API client chung, generated types, MSW handlers dùng endpoint/schema thật và fixtures chung. Có loading/empty/error/retry/success, kiểm tra quyền ở UI, responsive/accessibility theo yêu cầu. Mock chỉ ở dev/test; không import fixtures trực tiếp vào page.
- **Backend design agent** sở hữu `docs/design/**`, `docs/decisions/**`: thiết kế system/technical/data/feature/test plan thật chi tiết, chưa tự đổi mục tiêu thành code khi chỉ được giao thiết kế. Mỗi feature có thuật toán, validation, authorization, state, transaction/concurrency/retry, lỗi, expected DB state và acceptance/test cases để agent khác code mà không đoán.
- **Coordinator** sở hữu `contracts/**`, `plans/**`, context tổng hợp và integration. Contract thay đổi phải thông báo cả hai, sửa examples, regenerate types và cập nhật mock/design/tests cùng revision trước merge. Backend agent đề xuất sửa contract qua coordinator.
- Mỗi agent ghi context riêng `context/agents/<task-id>.md` theo template, commit/push nhánh mình sau gate. Coordinator hợp nhất notes vào HANDOFF/WORKLOG; không để hai agent cùng sửa context tổng hợp gây đè nhau.
- Agent tiếp theo triển khai backend từ bộ design đã kiểm tra, có tests. Merge FE và design/BE vào nhánh tích hợp theo dependency, kiểm tra conflict/ngữ nghĩa, chạy gates; merge source đơn thuần chưa phải tích hợp dữ liệu thật. Không tự merge nhánh được bảo vệ ngoài quyền repo.

## Hợp đồng và integration

OpenAPI là nguồn chuẩn payload; examples chung cho mock và backend tests. PLAN chốt cách dùng canonical schema với FastAPI và kiểm tra `/openapi.json` khớp; không duy trì hai schema lệch nhau. Ghi rõ status codes, error envelope, auth/session, pagination, nullability, timestamps, ID, retry/idempotency nếu cần.

Live mode không được im lặng fallback về mock khi API hỏng. Giữ API client, tắt MSW ở production, cấu hình base URL/proxy/origin. Kiểm tra tối thiểu luồng tạo/sửa → tải lại → DB còn dữ liệu, lỗi validation/quyền/phiên nếu feature có, và migration từ DB sạch. Không dùng volume dev để test hoặc xóa volume như cách sửa lỗi.

## Context + Git sau mỗi bước

1. Ghi task, mục tiêu, nguồn đã đọc, quyết định/lý do, file thay đổi, trạng thái mock/live, checks thực sự chạy và kết quả, blockers, next action/owner.
2. Cập nhật PROJECT khi sự thật bền vững đổi; HANDOFF cho trạng thái mới nhất; WORKLOG append theo ngày giờ Asia/Bangkok. Link nguồn chuẩn, không nhân bản payload.
3. Review/stage chỉ file task và context liên quan, chạy `git diff --cached --check`, Conventional Commit. Ghi commit bằng Git history/checkpoint kế tiếp, không tạo vòng commit chỉ để ghi SHA của chính nó.
4. Fetch `origin`, xem diverge và reconcile an toàn; push nhánh hiện tại với upstream. Nếu push lỗi, giữ commit, ghi/báo lỗi và bước khắc phục; không claim synced, không force push.
5. Xác minh SHA local bằng `git rev-parse HEAD` và SHA nhánh tương ứng từ `git ls-remote origin refs/heads/<branch>`. Báo nhánh/commit cho chủ repo.

## CI/CD sau khi có app

Tái sử dụng pipeline nếu có. Khi scaffold app, tạo GitHub Actions phù hợp stack đã chốt: install từ locks, format/lint/typecheck, affected unit/integration với PostgreSQL service, FE build, contract checks cho hai phía; quyền tối thiểu, secrets qua cấu hình bảo vệ. Chốt branch/path filters và required checks. Thiết kế deploy/rollback trong PLAN; không tự triển khai production. SETUP hiện chưa có app nên chưa dựng pipeline giả.
