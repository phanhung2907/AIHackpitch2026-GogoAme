# backend_TRICK — FastAPI/PostgreSQL có ranh giới rõ

## Stack thực tế

Python 3.13, FastAPI/Uvicorn, SQLAlchemy 2 + psycopg 3, Alembic, PostgreSQL trong Docker Compose; Argon2 cho mật khẩu. OpenAPI YAML canonical và JSON Schema dùng kiểm tra contract. Pydantic có trong stack FastAPI nhưng payload nghiệp vụ hiện bám schema canonical, không sinh một hợp đồng thứ hai độc lập.

uv/lock cho dependency Python; pytest/httpx cho unit/integration, Ruff cho lint/format, mypy cho type checks. Exact versions/digests đọc từ lockfile và Dockerfile, không copy nguyên version mãi cho mọi dự án mới.

## Phân lớp đủ dùng

Route xử lý HTTP/session/schema → service điều phối use case và transaction → domain tính toán quy tắc thuần → repository/SQL lưu dữ liệu. Không đặt quy tắc số dư rải rác trong route. Không tách quá nhiều tầng chỉ để đủ tên pattern.

Domain fraud nhận số tiền, thời điểm server, vị trí và lịch sử hợp lệ; trả mã lý do + evidence + rule version. Hàm thuần giúp test biên nhanh không cần DB. Service chịu trách nhiệm chọn lịch sử và serialize đúng; unit domain không chứng minh concurrency DB.

## Transaction tiền phải thiết kế trước code

1. Xác thực, phân quyền, schema và retry theo chính sách.
2. Mở transaction; khóa tài khoản theo thứ tự ổn định.
3. Kiểm tra trạng thái/khả dụng; đọc lịch sử dưới ranh giới nhất quán.
4. Đánh giá fraud; HOLD thì reservation, posted thì ledger cân bằng.
5. Lưu command/evidence/audit/idempotency theo cùng thiết kế nhất quán.
6. Commit rồi trả response. Lỗi trước commit phải rollback.

Review phải kiểm tra lại quyền, người tạo, trạng thái lệnh và điều kiện tài khoản tại thời điểm duyệt. Reversal tạo bút toán bù và liên kết; không sửa ledger gốc. Runtime DB role giới hạn quyền sửa dữ liệu nhạy cảm thay vì chỉ tin code API.

## Hợp đồng và dữ liệu

- Trả envelope `{data: ...}`; list có `meta.next_cursor/limit`; lỗi có code/message/details/request_id theo contract.
- Dùng UUID ổn định cho định danh, tiền dạng chuỗi VND, timestamp UTC có múi giờ.
- PATCH quản trị có expected_version khi cần chống ghi đè; báo conflict rõ.
- Idempotency scope phải bao gồm actor/operation theo thiết kế; unique constraint bảo vệ race.
- Constraint DB bảo vệ bất biến; migration có thứ tự, seed demo riêng và có thể chạy lại an toàn.
- Không lấy role, balance hay vị trí chi nhánh từ dữ liệu tùy ý phía client. Chuyển tiền demo có provenance và chính sách thiếu vị trí rõ.

## Vận hành local

Tách DB dev có volume với DB test biệt lập. Migration chạy trước backend healthy; UI chờ backend healthy. Chỉ bind localhost cho demo. `.env` và credentials ignored, `.env.example` chỉ chứa placeholder an toàn. Không dùng `docker compose down -v` như cách sửa lỗi thông thường vì sẽ xóa dữ liệu.

Health live trả tiến trình sống; ready kiểm tra phụ thuộc cần thiết. Log request ID và lỗi có ngữ cảnh, che secrets. Ghi đúng nơi chạy lệnh và project Compose để tránh khởi tạo nhầm database.

## Bài học thực tế

FastAPI `/openapi.json` phải trả đúng canonical contract; sửa một attribute không đủ nếu cơ chế cache/schema generation vẫn chạy bản mặc định. Test public schema endpoint giúp bắt lỗi này. Có contract tests vẫn cần integration cho cookie/CSRF, transaction và quyền.

Không áp thêm queue, Redis hay microservices cho MVP khi chưa có yêu cầu. Ưu tiên ít thành phần, dữ liệu đúng và luồng có thể giải thích.
