# F04 — Theo dõi hóa đơn và hủy dòng món

P0; billing service; phụ thuộc F02/F03. [API](../api-design.md), [transaction](../technical-design.md), [data](../data-model.md).

## Quyền, input và reads

GET /guest/bills/{id} cần membership của session còn hạn; được xem toàn bill gồm các lượt của khách khác, nhưng không actor IDs. GuestItemDTO có is_mine/can_cancel server-computed. POST /guest/items/{id}/cancel cần creator đúng session + membership, expected_version>=1 và business key. Hủy toàn quantity của dòng, chỉ waiting và bill open; không DELETE, không sửa note/qty/giá.

## Luồng snapshot và mutation

1. Snapshot read-only REPEATABLE READ lấy cursor và bill/orders/items/payment đồng nhất; sort orders FIFO, items ổn định. Open total SUM noncancelled; paid total frozen. can_cancel theo session+state, can_pay chỉ hint thanh toán cho cashier, không quyền guest.
2. Cancel auth/scope/creator trước state; session khác cùng bill không phải creator trả404 (không cho suy đoán ownership qua lỗi409). Replay thành công vẫn trả kết quả cũ dù can_cancel hiện false.
3. Transaction reserve key → bill FOR UPDATE → item FOR UPDATE → recheck relation/creator. Bill paid409 BILL_CLOSED; item version stale409 VERSION_CONFLICT; không waiting409 STATE_CONFLICT.
4. Set status cancelled, cancelled_at DB time, version item+1 và bill+1; total exclude cả dòng. Append audit item.cancel và item.updated/bill.updated đúng audiences + success key; commit200 item/bill summary/cursor.
5. FE invalidate bill/menu tables/queue qua events; dòng giữ trong bill với nhãn Đã hủy và tổng0 đóng góp. Không hủy các dòng khác cùng món.

## Đồng thời, phục hồi và UI

Cancel/start dùng cùng bill/item lock: chỉ một thành công. Nếu cancel trước, start stale version409, item cancelled không còn queue. Start trước, cancel stale version409; refetch thấy đang pha, không cho hủy. Bill paid trước cancel409; không giảm payment. Mọi lỗi trước commit không tăng version/audit/event. Timeout replay cùng key. Reload lấy server bill; phiên guest hết hạn bootstrap mới không khôi phục ownership dòng cũ.

`/guest/bills/:billId`: skeleton/error retry/not-found, empty không giả thành đã thanh toán; mỗi dòng có chữ trạng thái, nhãn Của bạn, note plain text. Cancel chỉ render khi can_cancel true, dialog hủy toàn dòng, pending disable;409 refetch giải thích state đã đổi. Paid receipt read-only và CTA Bắt đầu lượt mới explicit ở F07. SSE disconnected hiển thị badge và polling F09.

## Acceptance/test và file triển khai

| Setup / hành động | Expected response / DB |
| --- | --- |
| Guest A/B cùng membership, A tạo qty2 |Cả hai xem toàn bill; chỉ A can_cancel=true; B cancel404 |
| A hủy waiting qty2 giá30000 |200 cancelled, tổng giảm60000, item/bill version+1, không DELETE |
| Preparing/done với expected mới |409 STATE_CONFLICT; status/tổng/version giữ nguyên |
| Guest bàn khác hoặc bill không có |404 cùng envelope; không bill data |
| Toàn dòng cancelled |Bill vẫn open,total0,can_pay=true khi ca mở; F07 đóng payment0 |
| Bill paid, giá menu sau này đổi |GET receipt total/snapshot cũ bất biến; cancel409 |
| Cancel/start concurrent |Đúng1 success,1conflict, không trạng thái kép |

Unit can_cancel/totals/states; integration IDOR/ownership/concurrency/rollback/replay; contract guest projection không creator IDs; FE note escaping/status text. Files services/billing.py, domain/item_states.py, schemas/bills.py, repositories/bills.py; audit không note/token. Không câu hỏi mở ngoài C01/S01.
