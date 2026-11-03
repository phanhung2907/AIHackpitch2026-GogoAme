# F09 — Cập nhật thời gian thực và phục hồi

P1 bắt buộc demo mục tiêu; events service, F03–F08. Đọc [SSE protocol](../technical-design.md#5-sse-không-bỏ-commit-và-không-lộ-quyền) trước code; đó là nguồn chuẩn thuật toán cursor, không thay bằng MAX(sequence).

## Quyền, input và dữ liệu

Bốn GET streams guest bill/menu, kitchen, cashier; cookie cùng-origin, after cursor optional decimal string, Last-Event-ID ưu tiên khi reconnect. Guest bill cần membership, kitchen barista, cashier cashier; role/expiry/revoke/scope kiểm khi connect và mỗi batch. Không token query string. Event chỉ id/type/resource_id/version/occurred_at; không snapshot bill hoặc giá/notes. Event scopes ở technical design; business event không cấp quyền đọc resource.

## Luồng main và resources

1. Business service append event_clock+domain_events cùng transaction, ID được cấp ở cuối trong serialized clock lock, không phát trước commit.
2. Client GET snapshot có event_cursor từ cùng REPEATABLE READ DB snapshot. Mở EventSource từ cursor đó; nếu mutate sau snapshot trước subscribe, replay vẫn bắt được event.
3. Reader mỗi1s mở transaction read-only ngắn, recheck session/scope; đọc H/retention và batch<=100 scoped events, release DB rồi gửi. Checkpoint cursor giúp tiến watermark khi không có event đúng scope; không giữ connection trong15s heartbeat hoặc khi client chậm.
4. Browser dedupe IDs, debounce150ms, invalidate bill/menu/queue/tables/shift đúng scope và GET snapshot. Không áp event thành state authoritative, không gửi POST/PATCH theo event. Mutation response cũng invalidate ngay.
5. Mất stream: badge reconnect, backoff1/2/4/8/15s+jitter, polling snapshot mỗi5s; healthy thì dừng polling. Focus refetch; stop/clear khi logout/role đổi.

## Reset, lỗi, retention và giới hạn

Cursor quá cũ hoặc >H gửi reset+close → full snapshot → stream mới. Cursor malformed422 trước stream. Missing membership404/auth401 lúc connect. Khi đã200, expiry gửi session_expired nếu còn socket rồi close, không đổi HTTP status; FE login/bootstrap theo principal. Reauth không auto replay business command. Event trùng/trễ không tạo order/payment; refetch version mới đủ.

Socket queue bound100; slow client bị đóng để refetch/reconnect, không RAM queue vô hạn. Max5streams/principal429 Retry-After; heartbeat comment15s. Proxy buffering/compression stream tắt; Cache-Control no-cache cho stream (JSON no-store), headers content-type text/event-stream. Retention ít nhất24h; cleanup prefix+watermark atomically. DB down: reader đóng stream có log request_id, client polling error rõ; không fallback mock. Auth revoke có độ trễ tối đa một batch trước kiểm tiếp, không tuyên bố tức thì zero latency.

## UI, audit và acceptance

Hiển thị “Đang đồng bộ / Đang kết nối lại / Đang tải định kỳ”, có chữ và live region debounce; không mỗi heartbeat toast. Stream read không business audit; log connect/disconnect reason không token/cursor chứa resource khác. Barista vẫn không được lấy tài chính qua event/errors.

| Setup / hành động | Expected state / DB |
| --- | --- |
| Snapshot cursorN rồi commit trước subscribe |Event>N đến, GET thấy mới; không mất update |
| Transaction A chậm, B nhanh ở bước cấp event |ID theo lock/commit, reader không bỏ A; chứng minh hai connections |
| Gửi trùng event hoặc reconnect10lần |Không thêm order/payment/audit mutation, snapshot đúng |
| Guest bàn1 subscribe bill bàn3 |404; không nhận event IDs/resource của bàn3 qua bill stream |
| Cursor trước retained_after / lớn hơn H |reset, full refetch, không loop giữ cursor lỗi |
| Revoke staff session đang stream |Batch kế tiếp close; connect mới401 |
| Tắt mạng rồi pha chế done |Polling/reconnect phản ánh done, không duplicate order |

Unit cursor/parser/scope/dedupe; integration snapshot-vs-subscribe, commit inversion, cleanup, session/slow client/pool release; E2E proxy SSE và fallback; benchmark delay mục tiêu<=2s khi healthy, chưa đo. Files events/reader.py, events/store.py, api/events.py; FE scoped event hook. C01/S01 trước code; không thêm Redis/message broker.
