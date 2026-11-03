# Thiết kế hệ thống tổng thể

Revision DESIGN-1; đọc [index và glossary](README.md), [PLAN](../../plans/product-plan.md). Tài liệu mô tả hệ thống cần xây, không phải hệ thống đã triển khai.

## 1. Bối cảnh và ranh giới

TapOrder giúp khách quét QR bàn → gửi nhiều lượt món → pha chế xử lý từng dòng → thu ngân thu tiền và giải phóng bàn → xem lại biên nhận/đóng ca. Khách không login. Pha chế và thu ngân login tài khoản riêng, API và UI tách quyền. Một quán; hai bàn seed 1/3; tối đa mục tiêu 20 bàn, 50 khách, 5 màn nhân viên, 100 món, 1.000 lượt gọi/ca. Các con số là workload cần đo, chưa benchmark.

Không tích hợp payment gateway, AI, Supabase hoặc hệ thống kho. QR là capability: ai có URL có thể yêu cầu tham gia bill đang mở. QR không chứng minh vị trí thực tế; token không được quyền đọc bill paid trước đó. Guest có membership xem toàn bill hiện tại, chỉ hủy dòng do phiên mình tạo.

## 2. Thành phần và đường đi dữ liệu

| Thành phần | Trách nhiệm | Không sở hữu |
| --- | --- | --- |
| React SPA: guest, kitchen, cashier | Forms, giỏ tạm, hiển thị snapshot server, refetch khi có SSE | Quyền, giá cuối, trạng thái nghiệp vụ |
| Cùng-origin web entry | HTTPS ở edge khi public; static và `/api` cùng origin; proxy SSE nếu local Compose | Session/business data |
| FastAPI router/dependencies | Parse strict schema, session/CSRF/RBAC, status/DTO whitelist | Transaction rải rác hoặc trả ORM trực tiếp |
| Application service | Một use case = một transaction; resource scope, locks, idempotency, audit/event | HTTP/UI |
| Domain functions | State machine, tính tổng integer, can_cancel/can_pay, giới hạn | I/O, commit |
| Repository/SQLAlchemy | Parameterized queries, schema/index, locking, projections | Tin client total/role |
| PostgreSQL | Nguồn chuẩn mọi dữ liệu bền vững và phối hợp đồng thời | Cache giỏ chưa gửi |
| SSE reader | Đọc committed events theo cursor, lọc quyền, yêu cầu client refetch | Tạo order hoặc thực hiện thanh toán |

Đường đồng bộ: browser → `/api/v1` → auth/schema → service → repository/DB → commit → DTO. Đường cập nhật: transaction ghi event → reader đọc sau commit → SSE → browser GET snapshot. HTTP không chờ pha chế hoặc thu tiền; mỗi thao tác là request riêng.

## 3. Ranh giới module và cấu trúc dự kiến

`backend/app/` gồm `main.py`, `config.py`, `db/`, `models/`, `schemas/`, `api/`, `services/`, `domain/`, `repositories/`, `security/`, `events/`; migrations ở `backend/alembic/`, tests ở `backend/tests/{unit,integration,contract}`. Các tên này là nơi triển khai dự kiến.

| Module/use case | Sở hữu logic | Phụ thuộc đọc/gọi |
| --- | --- | --- |
| auth/security | Opaque sessions, Argon2, CSRF, staff role, guest membership | staff_users, sessions |
| tables | QR resolve/export, expected visit, join | auth, tables, billing reads |
| menu | Public menu, availability, item validation | menu schema |
| ordering | Submit/gọi thêm, snapshots, membership khi tạo bill | shifts, tables, menu, billing domain |
| billing | Bill projection/totals, cancel own waiting | orders/items, auth scope |
| kitchen | Queue projection, legal progress | billing locks, item state domain |
| payments | Atomic payment + paid receipt | shifts, billing totals |
| shifts | Open/close, guard chống race lúc chưa có ca | bills read |
| events/audit | Durable event append và scoped stream; audit append | UoW dùng chung, không gọi ngược business services |
| recommendations/reports | P2, query-only | menu, payments, paid bills/items |

Router không gọi router. Service không tự mở transaction lồng nhau: nhận một Unit of Work (UoW), commit đúng một lần ở use-case boundary; helper chỉ đọc/ghi qua cùng UoW. Không dùng event handler tạo payment hoặc bill. Audit/event/idempotency success cùng transaction với mutation.

## 4. Quyết định kiến trúc và đánh đổi

| Vấn đề | Quyết định và lý do | Đánh đổi / ảnh hưởng |
| --- | --- | --- |
| Thời gian demo ngắn | Modular monolith Python/FastAPI, SQLAlchemy 2 + psycopg 3, Alembic; DB PostgreSQL Docker local | Không tách microservices; migration/contract là ranh giới rõ |
| Cập nhật một chiều | SSE durable + HTTP snapshot + polling dự phòng | Dễ nhận trùng/trễ; client dedupe/refetch, không xem event là dữ liệu cuối |
| Chưa cần cache/queue | Một API worker/replica; query DB events mỗi 1 giây | Memory rate limit chỉ phù hợp cấu hình này; nhiều replica cần thiết kế lại limiter/capacity |
| Chống race tài chính | READ COMMITTED + row locks, DB uniqueness, order/payment atomic | Khóa ngắn; event clock serialize phần append cuối; cần đo contention |
| Triển khai ít cấu hình | Public: một container FastAPI phục vụ React build, DB service riêng; local dev Vite proxy API | Deploy vẫn là task riêng; không dựng cloud trong bước design |
| Dễ phục hồi | Dữ liệu lịch sử giữ nguyên, payment unique/bill, replay command thành công | Không sửa sai/refund qua UI trong MVP |

Frontend giữ React/TS/Vite/Tailwind/shadcn/Radix/TanStack/RHF/Zod/Zustand trong agent.md; reuse UI nguồn MIT theo PLAN, không port DB/auth nguồn. Pin version/lock thật ở S01, không coi danh sách này là dependencies đã cài.

## 5. Trust boundaries và kiểm soát bảo mật

- Chỉ nhận HTTPS public; cookie guest/staff HttpOnly riêng, SameSite=Lax, Path=/, Secure khi HTTPS; TTL guest12h/staff8h tuyệt đối. Không lưu cookie/CSRF/QR trong localStorage. Session lookup dùng hash token 256-bit, revoked/expiry/active staff kiểm mỗi request.
- Mutations kiểm exact Origin allowlist + CSRF của đúng principal. Preauth login có cookie/token10 phút, rotate sau login. Guest bootstrap là ngoại lệ CSRF có kiểm Origin, không tạo bill/membership. Replay vẫn phải auth/scope trước đọc kết quả cũ.
- Resource scope ở service gồm read/mutation/SSE. Guest không thuộc bill trả404; barista vào cashier trả403; thiếu session401. Barista DTO không giá/payment/doanh thu; guest không lộ actor ID khác.
- Body tối đa64KiB; unknown fields422; UUID/quantity/money strict; note plain text trim<=250; SQL parameterized, React escape. Không nhận total, role, status, table_id từ guest để tự cấp quyền.
- Redact URL `/t/{token}`, body bootstrap/join/submit, cookie, CSRF, password, DSN, ghi chú. `Referrer-Policy: no-referrer`, QR route không analytics/tài nguyên third-party. CSP cùng-origin phù hợp bundle; không tắt CSRF/CORS để sửa lỗi UI.
- Runtime DB user chỉ quyền app, migration dùng quyền riêng; DB private network, không publish port trên cloud. QR key riêng env và backup key; không lấy PUBLIC_BASE_URL từ Host header client.
- Rate limits: login5/phút/IP+username; bootstrap/join30/phút/IP; order10/phút/session; staff mutations60/phút/session; read120/phút/session; SSE tối đa5 connections/principal,429 Retry-After. Giới hạn memory demo không bền qua restart, ghi rõ trong runbook.

## 6. Topology, cấu hình và vận hành

Dev: React5173 proxy `/api` tới FastAPI8000, PostgreSQL5432; integration DB riêng5433/project riêng. Compose demo: Nginx8080 phục vụ/proxy, API/DB nội bộ, volume persistent. Public mục tiêu: edge HTTPS → một web container static+FastAPI nghe PORT → DB service private. Đây là ba môi trường, không chạy đồng thời hai static servers trong một topology.

Config cần: DATABASE_URL, SESSION_SECRET, QR_ENCRYPTION_KEY, APP_ENV, PUBLIC_BASE_URL, ALLOWED_ORIGINS/HOSTS, COOKIE_SECURE, DEMO_TIMEZONE, APP_VERSION, ENABLE_MOCKS=false; seed passwords qua private env. Fail startup khi thiếu secrets hoặc public cookie không Secure. Không có secret ở VITE_* hoặc Docker ARG.

Migration job trước API ready; seed idempotent không tạo orders/payments giả hoặc rotate QR. Health live không cần DB, ready kiểm DB/schema revision; thiếu schema503. Không tự migrate mỗi request. DB transaction timeout5s; request timeout phải lớn hơn budget transaction; SSE heartbeat15s và tắt proxy buffering/compression trên stream. Pool dự kiến5+overflow5, acquire timeout2s; load test rồi chỉnh, stream không giữ connection.

Log JSON: request_id, actor pseudonymous ID, route template, action/result, duration; audit mutation gồm resource/before-after state/version. Mục tiêu p95 read<=500ms, submit/pay<=1s, SSE<=2s, polling<=5s sau mất stream; cần đo và báo environment. Không gán status pass trước khi đo.

Backup DB và QR/session secret theo quyền vận hành trước migration có dữ liệu. Restore thử DB riêng, không xóa volume dev. Code rollback chỉ khi schema tương thích; không rollback payment bằng xóa row. PLAN mục8 giữ runbook deploy; không kiểm/chốt giá nhà cung cấp trong lượt design này.

## 7. Điều kiện để agent code bắt đầu

Canonical C01 từ API design được validate, examples chuẩn, DTO projection và error enum cùng revision; S01 có lockfiles/DB test/migrations harness/CI commands thực. Agent code triển khai P0/P1 theo test plan, ghi regression fail trước khi practical. Nếu interface lệch thiết kế, cập nhật contract/examples/design/tests cùng revision trước tích hợp. Không để agent tự đoán policy ở các cuộc đua dữ liệu.
