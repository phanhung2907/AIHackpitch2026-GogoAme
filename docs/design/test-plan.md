# Kế hoạch triển khai, kiểm thử và bàn giao

DESIGN-1; đây là **test specification**, chưa có unit/integration/E2E thực thi. [PLAN mục15](../../plans/product-plan.md), [API](api-design.md), [features](README.md) là nguồn acceptance.

## 1. Trình tự giao agent tiếp theo

| Bước | Đầu ra / gate | Không được coi là done khi |
| --- | --- | --- |
| C01 contract | Canonical OpenAPI/examples đủ endpoints/DTO/errors, validation và generation type pass, revision CONTRACT-1 | Chỉ copy bảng Markdown mà chưa schema/examples máy kiểm |
| S01 scaffold | Python/Node locks, DB Docker dev/test riêng, Alembic baseline, scripts checks thật, CI nền phù hợp | Chưa clean install, chưa kiểm test DSN an toàn |
| BE-A foundation | F02 + schema/seed + F08 + QR/menu F01/F10; migration sạch, seed2lần, auth negatives | Có login nhưng role/scope/CSRF chưa kiểm |
| BE-B core | F03/F04/F05/F06/F07, unit→PostgreSQL integration/races/replay | Happy path pass nhưng chưa rollback/race/payment0 |
| BE-C realtime | F09 cursor commit ordering, scope, snapshot/subscribe, pooling/reconnect | Chỉ thấy một event nhưng chưa chứng minh không bỏ commit |
| BE-D optional | F11/F12 nếu P0/P1 gates đạt; boundaries/ranking/reports tests | Fixtures giả hoặc P2 trì hoãn critical flow |
| INT01 | FE live cùng contract, mock tắt, hai bàn E2E+reload/restart+negative role/Origin | FE build pass nhưng chưa gọi DB/API thật |
| DEMO01 | Hai QR đúng môi trường, account/QR TXT ignored, rehearsal evidence | Account dự kiến bị trình bày như đã tạo |

Không spawn agent hoặc deploy trong task design này. Chủ repo giao agent tiếp theo; agent đó đọc index→system/data/technical/API→feature→test plan, thực hiện C01 trước code. FE/BE parallel chỉ sau cùng contract/scaffold baseline và file ownership/worktree riêng. Mọi step hoàn chỉnh cập nhật context, review/stage đúng scope, commit/push origin và xác minh SHA; không merge main hoặc deploy khi chưa giao.

## 2. Môi trường và fixture

- DB thật PostgreSQL trong Docker test riêng, không SQLite thay lock/partial indexes. Test harness từ chối DSN dev/demo; unique database/schema per worker, teardown chỉ test-owned resources. Không drop/reset dev volumes.
- Seed fixture deterministic: tables1/3, guestA/B/C, users barista/cashier,12 món/3bucket; menu cà phê30000,trà35000. Demo seed không có business rows; integration tạo fixtures riêng.
- Clock injection cho TTL/time buckets/window; timestamps DB cho transactions. Hai DB connections + barriers kiểm concurrency, không dùng sleep hy vọng race. Fault injection ngay trước commit/giữa writes, assert DB cuối.
- Unit pure domain không mock ORM để tự chứng minh lock. Integration asserts rows/state/version/audit/event/key; contract validates payload/status/security/projected fields. E2E browser origin thực, cookies/CSRF/SSE/proxy; hosted CI chạy thật sau pipeline có, không suy từ local.

## 3. Coverage T01–T16 từ PLAN được cụ thể hóa

| ID / feature | Setup + hành động | Expected HTTP và DB / loại test |
| --- | --- | --- |
| T01 F01/F10 |QR1/3/invalid/disabled, GET và bootstrap/join nhiều lần |Đúng bàn; invalid404;0bill khi browse;1membership khi join lại; unit+integration+QR decode |
| T02 F02 |Login đúng/sai/inactive; role sai, CSRF/Origin sai; expiry/logout |200/401/403 đúng; hash/cookie rotation/TTL, revoke stream; unit+integration+contract |
| T03 F03/F06 |Qty0/20/21/float/bool, note250/251,1/50/51dòng,unknown total,soldout/giá đổi |Boundaries đúng;422/409 không partial rows/version/events;giỏ giữ;unit+contract+integration |
| T04 F03 |Hai null submits cùng bàn,explicit join sau conflict,gọi thêm |1bill/1order trước join;1bill/2orders sau submit hợp lệ;totals/snapshot đúng;PostgreSQL barriers |
| T05 F03/F07 |Retry samekey/hash,samekey/different hash;timeout sau commit |Một order/payment,replay cùng ID/body/status kể cả paid;409 different;integration |
| T06 F04/F05 |A/B cùng bill,A cancel own vs B;cancel/start cùng v |A200/B404;1race winner/1conflict,state/tổng/version đúng;integration+unit |
| T07 F05 |FIFO tie/gọi thêm,page limit1 nhiều dòng,invalid transitions |Không cắt dòng;tuple sort;waiting→done409,legal chain200;unit+integration |
| T08 F06 |Toggle false trước/sau submit;hai toggle cùng v;no-op |Trước409 toàn lượt/sau không sửa order;stale409;no-op không event/version;integration |
| T09 F07 |Pay done/cancelled/unfinished,amount sai,two cashiers,zero bill |201 unique payment;409 unfinished/amount/closed;total frozen;unit+integration |
| T10 F03/F07 |Submit thêm đua pay hai chiều,stale total/version |Serialize;không order vào paid;409 đúng và0partial rows;PostgreSQL barriers |
| T11 F08 |Open2 lần khác/cùng key,close còn bill/hết bill,close-vs-create |1open shift;conflict đúng;không bill mới sau closed;unit+integration |
| T12 F09 |Snapshot→mutation→subscribe,commit inversion,prune/future cursor,disconnect/expiry |Không bỏ event,reset/scope đúng,poll5s,no duplicate POST;integration+E2E |
| T13 F01/F07 |Paid receipt,reload,QR same,new submit |0newbill khi GET;explicit new submit ID mới;old paid unchanged;integration+E2E |
| T14 F11/F12 |Clock biên06/11/17,bestseller paid7d,report multiitems/cancelled/zero/open |Max3/5 stable,paid-only sums không nhân JOIN,as_of consistent;unit+integration |
| T15 F03/F07/F10 |Submit/gọi thêm/reload/restart/readback;seed2lần,QR export/wrong key |DB còn dữ liệu,mock off;stable tokens,QR decode đúng,no secret log;integration+browser |
| T16 F01–F10 |Hai guest contexts/hai staff profiles,chạy toàn rehearsal bên dưới |Bill1=95000/bill3=35000,negative permissions,new visit/SSE/live persistence đúng;E2E |

Các ID giữ đúng ý nghĩa T01–T16 trong PLAN, bổ sung boundaries ở cùng hàng; không khẳng định test files đã tồn tại. Acceptance cross-cutting bên dưới bắt buộc cho implementation P0/P1. Domain totals/transitions/auth giữ mục tiêu coverage>=80% theo PLAN khi cấu hình, không thay thế concurrency cases.

## 4. Cases kỹ thuật bổ sung quan trọng

| Case | Evidence phải lưu khi implementation |
| --- | --- |
| Event ID/commit inversion |A giữ event_clock lock chưa commit,B đợi; snapshot/reader không nhảy qua A; assert event và snapshot cuối |
| Snapshot cursor consistency |Mutation xen giữa các query snapshot vẫn all-before/all-after theo REPEATABLE READ, không payload cũ+cursor mới |
| Rollback fault |Sau insert order/payment và trước append/commit gây exception: zero partial rows, reservation rollback, retry1success |
| Multi-tenant scope trong cùng quán |GuestA bill1 không đọc/hủy/stream bill3; staff role matrix mọi endpoint, response no leaked financial data cho kitchen |
| Secret redaction |Capture structured/access logs từ bootstrap/order/login/QR export và exceptions, không raw QR/password/cookie/CSRF/note/DSN |
| Pool và socket budget |Stream50 clients + HTTP reads/mutations: không exhausted pool do giữ connection, slow clients bounded, expiry batch closes |
| Money overflow/limits |Price1..1e7,qty1..20,line max2e8,bill==1e9/vượt1; API strings không float/scientific/negative |
| Migration/seed/restart |DB clean upgrade/seed2lần không duplicate/rotate; API restart preserves payments; khi revision2 có upgrade-from-previous |
| Session retry limitations |Session cũ expired không replay bằng session mới; UI chuyển đối soát thay auto resubmit |

## 5. Quality gates thực tế sau scaffold

S01 phải tạo và ghi chính xác commands trong backend/frontend README và CI từ manifests thật: backend Ruff format/check, type checker đã chọn, pytest unit/integration/contract; frontend lint/tsc/unit/build; OpenAPI validate/examples/client generation/drift check. Cài từ uv.lock/package-lock frozen. Không chạy command giả từ playbook hoặc đánh dấu pass vì tài liệu đã mô tả. Dependency audit theo tools/lock thực, không blind auto-fix nâng bản.

CI permissions tối thiểu contents:read, PostgreSQL service riêng, test secrets giả, không pull_request_target chạy untrusted code, không cloud credentials cho unit tests. Required-gates job phải báo failure nếu check cần thiết bị bỏ qua. Pipeline/branch protection/hosted success chỉ báo khi có evidence; task này chưa tạo CI vì chưa app.

E2E live bắt buộc: login2staff →open shift →QR1/3→order60000/35000→barista càphê done→gọi thêm trà35000→done→pay95000→new visit30000→cancel waiting/deny preparing→soldout atomic→SSE off/on→receipt persistence→pay mọi bill→close/logout. Lưu timestamps/environment/SHA, không credentials/screenshots raw QR vào public artifact.

## 6. Mẫu checkpoint agent code

Ghi feature/task IDs, design+contract revision, files đúng ownership, failing regression và sau sửa, unit/integration/lint/type/build thực chạy cùng kết quả, local-vs-hosted-vs-deployed riêng, mock/live status, migration revision, known issues/owner/next task. Diff review secrets/foreign changes, commit/push nhánh codex và remote SHA verified. Không gọi toàn backend done khi chỉ skeleton/build pass.
