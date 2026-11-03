# F12 — Đối soát và thống kê ca

P2; query-only reports, F02/F07/F08. [API report fields](../api-design.md), [schema/query](../data-model.md). Chỉ cashier; không dashboard doanh thu giả từ fixtures.

## Input, quyền và thuật toán

GET /cashier/shifts/{id}/report với UUID shift tồn tại, open hoặc closed. Missing404; barista/guest403. Không nhận arbitrary SQL/date range/client total. Output shift/revenue_vnd/paid_bill_count/top_items<=5/as_of/event_cursor.

1. REPEATABLE READ snapshot đọc clock/as_of UTC và shift. Tính `SUM(payments.amount_vnd)` và `COUNT(payments.id)` WHERE shift_id, mặc định0 khi chưa payment. paid_bill_count vẫn gồm payment0 của bill toàn cancelled.
2. Query riêng top items từ payments→bills paid→orders→order_items!=cancelled trong shift; SUM quantity theo menu_item_id, sort qty giảm/menu_item_id tăng, limit5. Không JOIN items vào revenue query gây nhân tổng.
3. Tên display lấy name_snapshot dòng mới nhất của item trong ca theo order.created_at,item.id; tiền từ payments, không current menu prices; zero-cancelled bill không thêm top items.
4. Return revenue string integer, quantities integer, same snapshot/as_of. Không update shift closed/counters/materialized totals; không background job cần queue.

## Đồng thời, lỗi và UI

Payment concurrent read report nằm trước hoặc sau transaction snapshot; không count bill paid mà payment chưa có hoặc ngược lại. Shift open report là tạm tính tới as_of; close không tự thêm revenue. Version menu/availability thay không sửa doanh thu đã thu. DB error503 và UI error retry, không trả0 để che lỗi. Endpoint read rate120/phút/session, no-store; SSE cashier bill.closed/shift.updated invalidate report nếu đang mở.

`/staff/cashier/shift` hoặc panel report theo shift: tên ca/thời gian trạng thái rõ, nhãn “Tạm tính” khi open, tổng VND, số bill/top5. Empty “Chưa có thanh toán”, không chart giả. Barista UI không link/report hoặc giá trong cache; logout clear cache. Audit none cho read, log request_id không credentials.

## Acceptance/test và files

| Setup / hành động | Expected response / DB |
| --- | --- |
| ShiftA paid95000 và35000, ShiftB paid30000 |ReportA130000/count2, B30000/count1; không lẫn ca |
| Có open bill60000 chưa payment |Không cộng revenue/count/top items |
| Payment0 toàn cancelled |Revenue không tăng,count+1,top không tăng |
| Một bill nhiều orders/items |Revenue chỉ cộng1payment, không bị nhân JOIN |
| Qty bằng nhau |Top theo menu_item_id tăng, tối đa5; snapshot name ổn định |
| Menu price đổi sau paid |Revenue/payment/snapshot bill không đổi |
| Payment commit giữa các query report |Snapshot thấy toàn trước hoặc toàn sau, không mixed |

Unit ranking/format/default0; integration real PostgreSQL separate aggregates/MVCC/paid-only; contract schema max5/projection; FE empty/error/tạm tính. Files services/reports.py, repositories/reports.py, api/cashier.py; C01/S01 là gate trước implementation. Không thêm báo cáo ngày/tháng ngoài PLAN.
