# Thiết kế kỹ thuật: nhất quán, lỗi và phục hồi

DESIGN-1; áp dụng cho mọi [feature](README.md). API fields ở [api-design](api-design.md), không định nghĩa payload khác tại feature.

## 1. Request pipeline và transaction

1. Middleware gán request_id, giới hạn body64KiB, route log có redaction; rate limit theo principal/IP đã chuẩn hóa qua proxy đáng tin.
2. Parse strict schema (unknown field422), xác thực đúng guest/staff session, kiểm Origin+CSRF, RBAC; lookup resource scope. Request không có quyền không được đọc idempotency response.
3. Với mutation nghiệp vụ, mở READ COMMITTED transaction, INSERT reservation idempotency unique. Operation chứa method+route template+resource UUID (không raw QR). Cùng key/cùng hash đã complete thì trả response đã lưu, không kiểm state/version mới; khác hash409. Quyền replay là quyền đọc resource của principal gốc, không đòi bill còn open/can_cancel hiện tại. Order replay principal gốc có membership sau commit, kể cả bill đã paid.
4. Lấy locks theo thứ tự dưới, đọc lại scope/state/version sau lock. Validate domain; ghi state + audit + events + response idempotency trong cùng transaction. Exception rollback toàn bộ, kể cả reservation, không cache4xx. Commit rồi mới gửi HTTP success.
5. Repository/helper không tự commit. Request cancellation/DB error trước commit rollback. Network error sau commit không xác nhận thất bại nghiệp vụ: FE giữ payload/key, replay hoặc đối soát trước command mới.

Idempotency hash SHA256 của canonical JSON theo schema: sort object keys, giữ thứ tự array items, canonical decimal strings, note đã trim; có version schema + operation, không hash cookie/CSRF. UUID key bắt buộc cho submit/cancel/status/availability/payment/open-close ca; join/bootstrap/login/logout không dùng business key, có semantics riêng. Reservation concurrent cùng key chờ transaction đầu kết thúc; nếu rollback, contender được thực thi; nếu commit, replay. Lock timeout5s/deadlock rollback →503 RETRYABLE_CONFLICT. Không commit reservation pending rồi tách transaction.

Giữ records tối thiểu24h; command quá24h từ lần gửi đầu FE không auto retry, phải đối soát. Nếu expiry nhưng record vẫn còn, tiếp tục replay; không thực thi lại chỉ vì expires_at đã qua. Giữ nguyên status200/201 và body khi replay, thêm response header `Idempotency-Replayed: true`. CSRF/expiry vẫn kiểm trên request mới. Sau401 guest tạo session mới không được replay command của session cũ; phải đọc lại current bill và nhờ staff đối soát nếu không xác định được kết quả.

## 2. Thứ tự khóa thống nhất

`idempotency reservation → shift_guard → shift hiện tại → table → bill → menu_items UUID tăng → order_items UUID tăng → event_clock`.

- Open/close ca: shift_guard FOR UPDATE; close còn khóa shift FOR UPDATE. Order/payment: guard FOR SHARE, shift FOR SHARE; giữ tới commit. Guard tồn tại cả khi chưa có shift để chặn race close/open với create. Chỉ các thao tác phụ thuộc ca cần guard; cancel/status không tạo bill/payment nên không cần ca lock, vẫn khóa bill.
- Submit/payment: table FOR UPDATE rồi bill FOR UPDATE. Join chỉ table FOR UPDATE, đọc bill đã ổn định vì payment/submit cũng phải khóa table; cấp membership cùng transaction. Cancel/status: bill FOR UPDATE rồi item FOR UPDATE. Lookup item→bill ban đầu chỉ để tìm parent, phải revalidate sau lock.
- Submit khóa menu rows FOR UPDATE theo UUID để serialize với availability; không đọc menu trước lock rồi dùng stale availability. Availability chỉ khóa menu row, không gọi ngược bill/shift.
- event_clock FOR UPDATE lấy **sau** mọi business lock/validation; append các audience events, tăng last_id theo số event, lưu response cursor; không có network/Argon2 hoặc lock business mới sau event_clock. Shared row locks cho guard/shift không serialize tất cả orders; table/bill giữ riêng từng bàn. Clock chỉ serialize phần append ngắn, tradeoff phù hợp demo, cần đo.
- Snapshot read không lấy business write locks. Retry DB không tự động ở service sau khi response không rõ; client tối đa2 retries với cùng key/backoff rồi thông báo cần đối soát. Không retry4xx tự động.

Availability là lệnh set explicit: target bằng current và expected_version đúng thì200 no-op, chỉ ghi key response; không tăng version/audit/event. Các lệnh transition status/cancel không có no-op tương tự; key mới ở state không hợp lệ phải409, key cũ replay. Chi tiết này làm rõ “mutation” trong PLAN là thay đổi state thật.

## 3. Thuật toán submit và payment

Submit: xác thực/replay → guard+shift open → resolve QR enabled, table lock → lookup expected bill (nếu UUID phải đúng table và membership) → kiểm bill paid trước version → current bill phải khớp expected. Null+current open trả TABLE_VISIT_CHANGED; null+không current tạo bill. UUID paid trả BILL_CLOSED; UUID không thuộc guest404. Lock items menu → validate tồn tại/active, available, giá, số dòng/qty/note, tổng bill cộng mới<=1e9 → insert bill nếu cần + membership + order/items waiting → bill version → audit/events/key → commit201. Không tự join bill do browser khác vừa tạo.

Payment: replay → guard+shift open → table/bill lock → bill open và bill.shift_id=current shift → expected_bill_version khớp → mọi dòng done/cancelled và có>=1 order → tính tổng từ snapshot → expected_total khớp → insert unique payment cash → bill paid/total/paid_at/version+1 → audit/events/key → commit201. Chọn cùng timestamp DB cho payment.paid_at và bill.paid_at. can_pay chỉ là hint ở snapshot, service kiểm lại toàn bộ. Thứ tự lỗi cố định: closed → version → unfinished → amount; không trả amount mismatch khi version đã stale.

## 4. Ma trận race bắt buộc

| Hai lệnh cạnh tranh | Lệnh trước thắng | Lệnh sau / hậu điều kiện |
| --- | --- | --- |
| Submit đầu/null cùng bàn | Tạo1 bill+1order |409 TABLE_VISIT_CHANGED; explicit join rồi submit key mới →1bill+2order |
| Submit expected UUID và payment | Submit thêm waiting, bill version tăng |Payment409 VERSION_CONFLICT; không payment |
| Payment và submit expected UUID |Bill paid,1payment |Submit409 BILL_CLOSED; không bill mới tự động |
| Cancel và start cùng item |waiting→cancelled |Start409 VERSION_CONFLICT (nếu stale); refetch thấy cancelled; không resurrect |
| Start và cancel |waiting→preparing |Cancel409 VERSION_CONFLICT hoặc STATE_CONFLICT khi version mới; không cancelled |
| Availability=false và submit |Menu hết hàng |Submit409 ITEM_UNAVAILABLE; không partial order |
| Submit và availability=false |Order được chấp nhận |Toggle không sửa snapshot/order trước đó |
| Hai payment khác key |Một payment |Sau409 BILL_CLOSED; cùng key replay đúng payment |
| Close shift và create bill |Close thành công khi chưa bill |Sau guard submit thấy không ca →409 SHIFT_CLOSED |
| Create bill và close shift |Bill mở đã commit |Close409 OPEN_BILLS_EXIST, ca vẫn open |
| Hai open shift |Một shift |Sau409 SHIFT_ALREADY_OPEN; unique là hàng rào cuối |
| Snapshot/subscribe và mutation |Snapshot thấy trước hoặc sau toàn transaction |Cursor không bỏ event, refetch eventual đúng |

Mỗi error trước commit giữ nguyên business rows/version/audit/events. Sequence order_number có thể nhảy do rollback, không phải lỗi. Không dùng table_number làm idempotency scope hay quyền.

## 5. SSE không bỏ commit và không lộ quyền

Vấn đề: sequence identity có thể cấp10 rồi11 nhưng11 commit trước10; lấy MAX(id)=11 sẽ bỏ10. Quyết định DESIGN-1: event_clock row serialized đến commit; id tăng theo commit của giao dịch có event. Đây là đề xuất thiết kế phải chứng minh bằng test hai connections, chưa có runtime verification.

Snapshot HTTP dùng read-only REPEATABLE READ: đọc event_clock.last_id trước, rồi đọc toàn projection trong cùng DB snapshot, trả cursor decimal string. Mutation response cursor từ clock trong transaction của chính nó. Event reader mỗi tick1s dùng transaction read-only REPEATABLE READ: check session/role/membership, đọc watermark H và retained_after, query events `cursor<id<=H` đúng scope ORDER BY id LIMIT100. Nếu đủ100, advance tới ID cuối batch; nếu ít hơn100, advance H nội bộ (đã scan hết scoped events). Gửi `checkpoint` chỉ cursor khi cần giúp client tiến qua các event không đúng scope; không lộ resource khác. Cursor là số toàn cục, chấp nhận chỉ lộ mức hoạt động tổng quát, không có payload chéo bàn.

SSE event business chỉ `id,type,resource_id,version,occurred_at` (timestamp UTC), không note/giá/guest ID. Loại: order.created, item.updated, bill.updated, bill.closed, menu.updated, shift.updated. Cùng mutation có thể append nhiều row audience, tất cả atomic. Guest bill nhận order/item/bill của đúng bill; guest menu nhận menu/shift; kitchen nhận order/item/menu/shift/bill.closed; cashier nhận order/item/bill/payment qua bill.closed/menu/shift. Events không có webhook hoặc xử lý mutation.

Resource/version mapping cố định: order.created→order ID/version1 (order bất biến), item.updated→item ID/item.version, bill.updated/bill.closed→bill ID/bill.version, menu.updated→menu item ID/menu item.version, shift.updated→shift ID/shift.version. `bill_id` nội bộ trên events của order/item/bill là bill liên quan, null cho menu/shift. Duplicates khác audience có ID riêng; filter theo scope trước gửi. Payment không có event riêng ngoài bill.closed, payment DTO chỉ lấy qua snapshot có quyền.

EventSource initial `after` hoặc Last-Event-ID reconnect; nếu có cả hai ưu tiên Last-Event-ID hợp lệ. Cursor malformed422; cursor>H hoặc cursor<retained_after gửi `reset` và close, client full snapshot rồi stream mới. Heartbeat comment15s; reset/session-expired là control events không fake business version. Đọc DB release connection sau mỗi batch, không giữ transaction khi await sleep hoặc gửi socket. Mỗi batch kiểm session; khi đã stream200 không đổi HTTP status: gửi `session_expired` nếu có thể rồi close; kết nối mới401/404. Backpressure bounded100 events/socket; client chậm đóng stream để reconnect/refetch, không queue RAM vô hạn.

FE load snapshot → stream từ cursor; dedupe ID, debounce150ms rồi invalidate scoped query; mutation success cũng invalidate ngay. Reconnect backoff1/2/4/8/15s+jitter, fallback GET mỗi5s khi stream unhealthy, stop polling khi healthy, window focus/refetch. Cursor reset refetch tất cả active pages; queue events refetch page đầu, không dùng cursor pagination cũ làm snapshot bền. Reconnect không gửi lại POST/PATCH.

Chỉ full snapshot của đúng scope được dùng khởi tạo stream cursor; response mutation là projection một phần, cursor của nó phục vụ đối soát, không thay cursor stream đang chạy hoặc bỏ qua events khác trước đó. Khi full refetch đang chạy, giữ stream active/dedupe; chỉ restart cursor sau snapshot mới nếu cần reset, tránh khoảng mù do partial response.

## 6. Session và CSRF có thể khôi phục khi reload

Opaque raw token random256-bit, DB SHA256; CSRF có thể tái tạo bằng HMAC SESSION_SECRET trên raw cookie+kind+session ID, hash CSRF lưu DB, compare constant-time. Bootstrap/session trả CSRF qua same-origin JSON no-store; secret không tới browser. Không rotate CSRF mỗi GET (tránh phá tab khác). Login rotate session, revoke staff session cũ nếu có, consume preauth thành công cùng transaction; failed login không consume token đến TTL. Password không trim, hash Argon2; generic401, thực hiện dummy hash check nếu username không tồn tại. Preauth GET idempotent tái dùng cookie hợp lệ, nếu mới sinh token/hash; không tạo staff/guest membership.

Guest bootstrap Origin hợp lệ + QR xác thực trước khi tạo/tái dùng guest session; giữ expires_at tuyệt đối, không kéo TTL khi reload. Guest bootstrap trả table/current bill metadata tối thiểu, **không trả bill contents**; session mới phải join. Guest session cũ membership hợp lệ dùng lại, không cấp ownership của session đã hết hạn. Logout lần hai204 khi Origin hợp lệ, không yêu cầu cookie đã mất; khi cookie còn sống cần CSRF. Revocation chặn stream ở batch kế tiếp.

## 7. Lỗi, audit và giao diện

Error envelope ở API design. Validation422 field details; no permission403; missing resource/scope404; state/version409; rate429 Retry-After; unavailable DB503 request_id. Không trả SQL/trace/secret. Unhandled500 rollback và request_id, FE giữ command để đối soát nếu không rõ commit.

Audit mỗi business mutation một action gốc, gồm state/version trước-sau, actor, resource và request ID; QR export audit access, auth login/logout audit không password/token. Replay không thêm business audit/event; request logs vẫn thể hiện replay. Snapshot GET không audit business. Audit không chứa notes, QR URL, CSRF hay credentials.

UI không optimistic order/payment/status; pending khóa nút theo resource nhưng server key/lock vẫn cưỡng chế.401 cần khôi phục phiên;403 route về màn đúng role;404 không tiết lộ resource;409 refetch và giữ form/giỏ, khách xác nhận trước lệnh mới;503/timeout giữ command+key. Khi bill paid, tab cũ receipt read-only; bắt đầu lượt mới explicit reset draft/resolve/join, không chuyển âm thầm.
