# F02 — Danh tính, session và phân quyền

P0; auth/security. Gắn mọi feature; [API](../api-design.md), [CSRF protocol](../technical-design.md#6-session-và-csrf-có-thể-khôi-phục-khi-reload).

## Mục tiêu và quyền

Guest session ẩn danh12h; staff barista/cashier8h tuyệt đối, riêng cookie. Không signup/đổi role/admin UI. Role lấy DB, active check mỗi request/batch SSE. Khách và một staff có thể cùng browser; hai staff role khác nhau dùng profile riêng. Endpoints auth/bootstrap/login/session/logout và guest/bootstrap; command fields/TTL/cookies từ API/technical design.

## Thuật toán và ranh giới dữ liệu

1. GET auth/bootstrap tái dùng preauth hợp lệ hoặc tạo token256-bit và hash/CSRF10m, no-store; không staff principal.
2. Login parse username trim/lowercase, password giữ nguyên; check Origin/preauth CSRF, rate5/phút/IP+username. Lookup user, Argon2 verify (dummy check khi không tồn tại), active/role phải hợp lệ. Sai trả401 INVALID_CREDENTIALS generic.
3. Hash verification ngoài business locks. Transaction login khóa preauth để chống dùng đồng thời; recheck TTL/consumed và user active/role. Consume preauth, revoke staff session cookie cũ nếu có, insert staff session/token hash/csrf hash, audit login, commit. Set cookie chỉ sau commit. Cùng preauth login lần hai sau consume403 CSRF_INVALID, không tạo session thứ hai.
4. GET auth/session kiểm hash/expiry/revoke/staff active, trả staff/CSRF/expires_at từ protocol, không rotate khi reload. Middleware chọn principal theo endpoint, không staff→guest fallback.
5. Logout session sống yêu cầu CSRF/Origin, revoke+audit commit, clear cookie204. Cookie đã mất/hết hạn/revoked: Origin hợp lệ thì204 clear cookie, không lỗi do CSRF không còn. Đóng SSE/clear staff cache ở FE; session guest không bị ảnh hưởng.

## Validation, failure và phục hồi

Unknown fields422; username1..80/password1..1024; không echo secrets. API không tin role/staff_user_id client. Guest bill/item scope service kiểm membership/creator;404 che resource; staff sai role403; thiếu phiên401. CSRF wrong principal403 ngay cả cookie guest/staff cùng hiện diện. Không extend expiry khi GET. Token expired không nhận lại ownership dòng cũ khi bootstrap mới.

Login network timeout sau commit: GET auth/session nếu browser đã nhận cookie, nếu chưa thì preauth mới/login lại; không có order/payment nên không cần business idempotency. Argon2 error/DB503 không consume preauth/không session dở. Audit auth không password/token/IP đầy đủ không cần thiết. Session material trong DB hash; raw chỉ HttpOnly cookie. No localStorage identity như source tham khảo.

## UI và acceptance

`/staff/login`: fields label/autocomplete, generic error, pending khóa nút;200 role redirect kitchen hoặc cashier. Loader session trước render protected route, tránh lộ UI/cache role cũ.403 có link về màn đúng role;401 giữ thông tin form nghiệp vụ nhưng không tự chạy lại mutation. Logout đóng streams/clear query cache.

| Setup / hành động | Expected response và DB |
| --- | --- |
| barista.demo login hợp lệ |200 role barista,1 new hashed session, audit1; không clear guest cookie |
| Sai username/password/inactive |401 cùng message; không session mới/không password trong log |
| Không CSRF/sai Origin hoặc guest CSRF cho staff |403;0 business writes |
| Barista gọi payment/cashier QR/report |403; DTO không bị lộ |
| Guest gọi bill không membership |404; stream cũng404 |
| Expire/revoke/disable staff rồi GET hoặc stream batch |401 ở GET/new stream; stream đang mở close, không event sau kiểm quyền |
| Reload hai tab lấy CSRF |Token dùng được cả hai, TTL không đổi |
| Logout hai lần |204; staff revoked, guest còn nguyên |

Unit: TTL/token/CSRF/role predicates; integration: cookie rotation, consumed preauth race, negative endpoints và SSE; contract DTO no secrets. Files security/session.py, csrf.py, permissions.py, services/auth.py, api/auth.py. Không endpoint seed public; seed accounts/env ở S01/BE seed.
