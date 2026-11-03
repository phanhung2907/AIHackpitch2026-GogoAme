# F03 — Giỏ, gửi món và gọi thêm

P0; ordering service. Phụ thuộc F01/F02/F08; [API fields](../api-design.md), [submit protocol](../technical-design.md#3-thuật-toán-submit-và-payment), [schema](../data-model.md).

## Phạm vi và preconditions

POST /guest/orders: guest session+CSRF+QR, expected_bill_id nullable, items1..50, Idempotency-Key. UUID bill cần membership và đúng QR bàn; null chỉ khi chưa bill mở. Ca phải open, table enabled. Quantity strict1..20, note trim<=250, expected unit price1..1e7, bill total<=1e9; unknown/client total fields422. Cùng món khác note hoặc giống note đều giữ dòng riêng. Server không nhận subtotal/tax/discount.

## Thuật toán chính và DB writes

1. FE giỏ scope table/visit, giá hiển thị từ menu, tạo UUID key cho snapshot command sau xác nhận; khóa nút pending, giữ payload/key khi network chưa rõ.
2. Backend auth/scope/replay trước current-state checks; reserve key trong transaction. Guard/shift share → table update → bill update; recheck expected visit và bill open. Không ca409 SHIFT_CLOSED, disabled404, paid expected409 BILL_CLOSED.
3. Null và chưa bill: chuẩn bị bill mới nhưng chưa commit. Null nhưng đã có bill:409 TABLE_VISIT_CHANGED, không tự join. UUID bill mở khớp: cần membership, gọi thêm vào bill đó.
4. Lock unique menu IDs sorted; kiểm tồn tại/active422, available409 trước giá409. Tính integer tổng từ snapshots hiện tại + dòng mới, không từ client total; tổng vượt422 BILL_LIMIT_EXCEEDED. Một món lỗi reject toàn lượt.
5. Insert bill khi cần + membership cho creator + order với order_number DB + order_items snapshot waiting; version bill mới1, bill cũ+1. Ghi audit order.create, events order.created cho guest/kitchen/cashier, key response201/cursor; commit atomically.
6. FE nhận201/replay mới clear giỏ, điều hướng `/guest/bills/:id`, render server order/tổng; refetch không cần chờ SSE. Server error giữ giỏ/note.

## Race, lỗi và hậu điều kiện

Hai submit đầu khác key/null:1 bill/1order thành công,1conflict; guest sau xác nhận/join/gửi key mới thì1bill/2orders. Cùng key/cùng payload retry: đúng1order, trả nguyên response kể cả bill đã paid; khác payload409 IDEMPOTENCY_CONFLICT. Submit vs payment serialize cùng table/bill: submit trước làm payment stale; payment trước submit BILL_CLOSED, không tạo lượt mới. Availability false commit trước →409 no partial; toggle sau commit không sửa order đã nhận.

DB failure trước commit:0 bill/order/items/membership/events/audit/key mới. Order number gap chấp nhận. Timeout sau commit: giữ command+key replay, không tạo key mới chỉ vì lỗi mạng. 409 cho khách sửa/xác nhận và dùng key mới;503 RETRYABLE_CONFLICT rollback retry cùng key tối đa2.401 session cũ hết hạn phải đối soát, không submit lại từ session mới tự động.

## UI, bảo mật và audit

Cart Drawer note/quantity RHF/Zod, không cho gửi empty; unavailable warning, giá thay đổi yêu cầu xác nhận; ngoài ca có thông báo. SessionStorage chỉ menu_item_id/qty/note/table/visit, không raw QR/cookie/CSRF; sau reload resolve visit/giá trước submit. Note là plain text trên kitchen/receipt, không HTML. Audit actor/order/bill/totals/version không note/token. Pending hiển thị “Đang gửi”, unknown result hiển thị đối soát, không toast thất bại rồi auto-create lệnh khác.

## Acceptance và tests

| Setup / hành động | Expected response / DB |
| --- | --- |
| Ca open, bàn1 chưa bill,2 cà phê30000 |201;1bill/open,total60000,1order,1item qty2 waiting,snapshot30000,membership1 |
| Gọi thêm1 trà35000 cùng bill |201; cùng bill,2orders,total95000,version+1; FIFO lượt mới phía sau |
| Qty0/21/1.5/bool, note251,51 dòng, total client |422;0 new rows |
| Một trong hai món unavailable hoặc giá đổi |409 code đúng;0 partial rows, giỏ giữ nguyên |
| Tổng bill đúng1e9 / vượt1 VND |Đúng giới hạn được nhận; vượt422 không tăng version |
| Cùng key replay trước/sau paid |Cùng order/payment history không đổi; không event/audit mới |
| Inject lỗi sau insert items/trước append hoặc commit |Rollback tất cả, retry cùng key thành công1lần |

Unit totals/limits/validation/visit; integration barriers hai connections cho null race, payment race, availability, idempotency/rollback; contract command/errors/201; FE tests clear-on-success-only. Files services/ordering.py, domain/totals.py, repositories/orders.py, api/guest.py. C01/S01 phải xong trước code.
