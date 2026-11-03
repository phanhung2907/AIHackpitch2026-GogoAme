# F05 — Hàng đợi và tiến độ pha chế

P0; kitchen service. Phụ thuộc F02/F03; [API projections](../api-design.md), [lock/state protocol](../technical-design.md).

## Mục tiêu, quyền, input

Chỉ barista dùng GET /kitchen/queue và PATCH /kitchen/items/{id}/status. Queue không giá/doanh thu/payment/guest identity. Filter status waiting/preparing optional, table_id optional, limit1..100 default50, cursor opaque khớp filter; không có kết quả trả[]/next_cursor null. PATCH nhận expected_version/status preparing hoặc done, CSRF/key. FIFO theo order.created_at,id; lượt gọi thêm là ticket sau, không dùng thời gian mở bill. FIFO là thứ tự hiển thị, không cưỡng chế nhân viên phải làm xong ticket trước mới chọn ticket sau.

## Query và thuật toán

1. Snapshot read-only lấy cursor/shift_open; chọn order của bill open có ít nhất dòng waiting/preparing, áp filter EXISTS, seek cursor/order tuple, lấy limit+1 order IDs để xác định next.
2. Hydrate chỉ active items của các ticket, nếu status filter thì chỉ các dòng status đó. Không LIMIT rows JOIN làm cắt mất món; sort items ID ổn định. Bàn/note/qty đọc từ server, age tính bằng clock UI chỉ để hiển thị.
3. PATCH auth barista/scope resource tồn tại → replay → reserve key → bill FOR UPDATE → item FOR UPDATE; recheck bill open, expected_version rồi transition. waiting→preparing đặt started_at; preparing→done đặt done_at; không waiting→done, preparing→waiting, done→bất kỳ.
4. Tăng item/bill version, audit item.progress, events item.updated cho guest/kitchen/cashier, ghi key; commit200 KitchenItemDTO/cursor. Dòng done rời queue nhưng vẫn trong bill/history.
5. FE success invalidate/refetch; SSE F09 cập nhật màn khác. GET queue không đổi state; bấm card không tự đánh dấu bắt đầu.

## Error, race và hậu điều kiện

Unknown status422; stale version409 VERSION_CONFLICT trước legal transition; target không hợp lệ từ current409 INVALID_TRANSITION; bill paid409 BILL_CLOSED; resource missing404; cashier/guest403 theo role endpoint. Same-state command với key mới không success no-op: invalid transition409; retry key cũ replay success. Cancel/start cùng bill/item lock F04; hai barista start cùng version đúng1 success. Failed mutation không tăng version/audit/events. Queue là live view, cursor không giữ snapshot giữa các trang; event refetch page đầu, merge IDs nếu UI load-more, không coi done ticket là mất dữ liệu.

## UI, audit và acceptance

`/staff/kitchen`: ticket bàn/order_number/note lớn, trạng thái bằng chữ, Bắt đầu chỉ waiting/Xong chỉ preparing, pending theo item; empty “Chưa có món chờ”, error retry, disconnected badge. Không âm thanh tự động, không nút thanh toán/hủy hộ. Audit state/version không note/giá; DTO whitelist test không có money keys cả trong nested objects.

| Setup / hành động | Expected response / DB |
| --- | --- |
| Orders bàn1 lúcT1,bàn3 T2,gọi thêm1 T3 |Queue FIFO T1,T2,T3; tie dùng ID, không table/bill age |
| Một ticket60 dòng active trong fixtures, page limit1 |Toàn active items của1ticket, next cursor đúng; không bị cắt do JOIN |
| waiting v1 → preparing v1 → done v2 |200/200; timestamps/version2/3; bill tăng mỗi lần; done rời queue |
| waiting→done hoặc done→preparing |409 INVALID_TRANSITION; không DB change |
| Hai barista start / cancel-vs-start |Một mutation thắng, một409; trạng thái duy nhất |
| Barista nhận snapshot/event/error |Không unit_price/total/payment/creator IDs |

Unit transitions/filter/cursor; integration sort/pagination/locks/race/paid guard/replay; contract kitchen projection; FE state/pending/error. Files services/kitchen.py, repositories/queue.py, schemas/kitchen.py, api/kitchen.py. Phụ thuộc C01/S01, không policy mở.
