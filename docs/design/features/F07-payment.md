# F07 — Thu tiền, biên nhận và lượt mới

P0; payments/billing services. Phụ thuộc F02/F03/F05/F08. [API PaymentInput/DTO](../api-design.md), [payment protocol](../technical-design.md#3-thuật-toán-submit-và-payment), [schema](../data-model.md).

## Mục tiêu và preconditions

Chỉ cashier GET tables/bills, POST /cashier/bills/{id}/payments. Tiền mặt được thu thực tế rồi cashier xác nhận; không gateway/poll bank/split/refund/reopen. Input method=cash, expected_bill_version>=1, expected_total_vnd string0..1e9, key/CSRF. Ca mở, bill open đúng ca, có>=1order, mọi dòng done/cancelled. Toàn cancelled vẫn đóng payment0. Không nhận giá/discount/thuế do client.

## Luồng chính và commit boundary

1. GET tables snapshot: free khi không bill open; serving khi còn waiting/preparing; ready_to_pay khi all done/cancelled. Đây là trạng thái dẫn xuất, không lưu table.status. GET bill trả nhiều lượt, cancelled có nhãn không cộng tiền.
2. FE modal số tiền từ snapshot server, hỏi xác nhận đã nhận tiền mặt, không editable total; can_pay false disable kèm số dòng chưa xong. Khách không có nút payment dù BillDTO có can_pay.
3. POST auth/replay → reservation → guard/shift share → table/bill update locks. Kiểm bill open trước version, shift khớp, version khớp, all done/cancelled, tính sum snapshots, so expected total. Lỗi theo thứ tự technical design.
4. Cùng transaction insert payments UNIQUE bill, set bill paid/paid_at/total/version+1, audit bill.pay, bill.closed events guest/kitchen/cashier, key receipt; commit201. Payment timestamp==bill.paid_at, shift_id==bill.shift_id. Chỉ sau commit FE receipt và grid free.
5. Guest tab cũ refetch paid receipt, ngừng nút cancel/gọi thêm trên bill đó. QR mở menu lượt mới không tạo bill; CTA Bắt đầu lượt mới phải xác nhận draft cũ, resolve/join hiện tại rồi F03 submit với expected mới. Paid bill trước giữ nguyên.

## Race, lỗi, retry và bất biến

Hai payment khác key: đúng1payment, sau409 BILL_CLOSED; cùng key replay nguyên receipt201 không thêm payment/audit/event. Submit thêm trước pay làm version stale hoặc item unfinished, payment409 không partial; pay trước submit expected bill cũ409 BILL_CLOSED, không tạo bill mới. Cancel/status khóa cùng bill nên payment đọc trạng thái đã commit.

Stale version409 VERSION_CONFLICT; all item chưa done409 ITEMS_NOT_DONE; expected money sai409 AMOUNT_CHANGED khi version đúng; ca không open409 SHIFT_CLOSED; cashier scope bill missing404. DB lỗi503 rollback payment+paid+auds/key; timeout chưa rõ commit retry cùng key hoặc GET bill để đối soát, không yêu cầu khách trả lần nữa. Payment paid terminal, không endpoint DELETE/update; restart không làm mất receipts.

## UI/audit và acceptance

`/staff/cashier`, `/staff/cashier/bills/:id`: loading/empty/error, pending modal khóa confirm,409 giữ modal và refetch/hiện số tiền mới để xác nhận lệnh mới. Receipt amount server, dòng hủy rõ, không giả “đã thu” từ click. Audit payment ID/bill/shift/amount/state/version, không guest note/password/token. Staff payment DTO không lộ danh tính khách.

| Setup / hành động | Expected response / DB |
| --- | --- |
| Bill2càphê+1trà đều done |201 payment95000, bill paid total95000, table free, bàn3 không đổi |
| Bill toàn cancelled |201 payment0 duy nhất, bill paid total0 |
| Có waiting/preparing |409 ITEMS_NOT_DONE (version đúng),0 payment,bill open |
| Expected total khác với version đúng |409 AMOUNT_CHANGED; không thay rows/version |
| Hai cashier khác key/cùng key |Khác:1success/1closed; cùng:replay cùng ID; payments count1 |
| Inject fault sau payment insert trước bill update |Rollback payment,bill vẫn open; retry thành công1lần |
| QR sau paid; guest mở/reload chưa submit |Không bill mới; submit explicit tạo ID mới, receipt cũ bất biến |

Unit can_pay/totals/payment preconditions; integration races/unique/rollback/replay/persistence/zero; contract receipt/error projections; E2E hai bàn/new visit. Files services/payments.py, repositories/payments.py, api/cashier.py; C01/S01 trước implementation.
