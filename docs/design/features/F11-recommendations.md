# F11 — Gợi ý món theo giờ và bán chạy

P2, không chặn demo khi P0/P1 đạt. Query-only recommendations service; F01/F02/F07. [API DTO](../api-design.md), [data](../data-model.md). Không dùng AI dịch vụ, không tự thêm vào giỏ/đổi giá.

## Quyền, input, thuật toán

GET /guest/recommendations cần guest session, không query clock/client budget. Server UTC now đổi Asia/Bangkok: [06:00,11:00) bucket coffee; [11:00,17:00) tea; [17:00,24:00) và [00:00,06:00) other. Category có recommendation_bucket seed explicit, không suy category bằng substring tên tiếng Việt.

1. REPEATABLE READ snapshot đọc cursor, now cố định một lần, active+available menu. Nếu không món trả[] không lỗi.
2. Candidate ưu tiên bucket đúng giờ, sort category.sort_order,item.sort_order,item.id, lấy tối đa3, reason time_of_day. Không để item xuất hiện hai lần.
3. Nếu thiếu, query quantity bán trong cửa sổ rolling `[now-7 ngày,now]` dựa payment.paid_at, chỉ bill paid và items!=cancelled; SUM quantity group menu_item_id. Chỉ món vẫn active+available, chưa chọn; sort qty giảm, item.id tăng; thêm tới3 reason bestseller.
4. Nếu vẫn thiếu, bổ sung active+available chưa chọn theo category.sort_order/item.sort_order/item.id reason seed_order. Trả GuestMenuItemDTO/price hiện tại, không snapshot price lịch sử cho menu. Không write/audit business/event.

## Đồng thời, failure và UI

Availability thay sau response có thể làm suggestion stale; submit F03 vẫn kiểm DB và reject toàn lượt; suggestion không giữ stock. DB lỗi503, UI chỉ hiển thị lỗi gợi ý/ẩn module có thông báo ngắn, menu chính không bị chặn. Empty không dựng món fixtures. Giờ lấy server, không tin timezone/clock client. Rate read120/phút/session, body no-store; không cached recommender toàn quán cần invalidation mới.

Menu `/t/:token` section “Gợi ý cho bạn”, reason text “Phù hợp buổi sáng / Được gọi nhiều / Gợi ý từ thực đơn”; click chỉ mở chọn qty/note hoặc add cart theo thao tác explicit. Loading không dịch layout lớn, unavailable refetch, không claim cá nhân hóa khi không có hồ sơ khách. Audit none cho read, log không QR.

## Acceptance/tests và dependency

| Setup / hành động | Expected response / DB |
| --- | --- |
| now05:59:59 /06:00 /10:59:59 /11:00 /16:59:59 /17:00 |Bucket other/coffee/coffee/tea/tea/other đúng biên |
| Có>=3 món bucket còn hàng |3 món unique, stable sort, reason time_of_day |
| Bucket chỉ1 món, bestseller có2 đủ điều kiện |1 theo giờ+2best, không trùng |
| Paid/open/cancelled orders trong7ngày |Chỉ quantity noncancelled của paid/payment window tính ranking |
| Không có paid hoặc menu hết hàng |Seed fallback hợp lệ hoặc[]; không DB writes |
| Món unavailable sau gợi ý trước submit |Submit409; không order partial |

Unit injected clock/ranking/dedupe/ties/window; integration query paid/cancelled/availability; contract max3/reasons; FE no auto cart. Files services/recommendations.py, repositories/recommendations.py, api/guest.py. C01 phải chốt P2 schema dù implementation có thể sau P0/P1; không câu hỏi sản phẩm mở.
