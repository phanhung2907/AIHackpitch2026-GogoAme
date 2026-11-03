# TapOrder — bộ thiết kế backend DESIGN-1

Ngày: 2026-11-03 (Asia/Bangkok). Baseline: [PLAN-2](../../plans/product-plan.md). Trạng thái: thiết kế để bàn giao, chưa có backend chạy, canonical OpenAPI, migrations hoặc kết quả runtime. Yêu cầu mới cho phép làm BD01 trước C01/S01; không cần scaffold để viết thiết kế. C01 vẫn là gate bắt buộc trước code và trước FE/BE làm song song. Không khởi chạy agent khác trong công việc này.

## Đọc theo thứ tự

1. [Luồng sản phẩm A–Z](product-flow.md): giải thích cho người mới, một sơ đồ Mermaid với cùng quy ước hình/mũi tên.
2. [Hệ thống tổng thể](system-design.md): thành phần, module, bảo mật, triển khai, tradeoff.
3. [Mô hình dữ liệu](data-model.md): schema đủ làm migration, constraint, index, dữ liệu bất biến.
4. [Thiết kế kỹ thuật](technical-design.md): thứ tự kiểm tra, transaction, lock, retry, SSE và các quyết định làm rõ PLAN.
5. [Thiết kế API](api-design.md): inventory, trường DTO, lỗi và gate C01; đây là đầu vào của OpenAPI, không giả định OpenAPI đã tồn tại.
6. Thiết kế từng chức năng bên dưới; [kế hoạch kiểm thử và bàn giao](test-plan.md) là checklist cho agent triển khai.

## Danh mục đủ 12 chức năng

| ID | Thiết kế | Mức | Module chính |
| --- | --- | --- | --- |
| F01 | [QR, menu, tham gia bàn](features/F01-guest-entry.md) | P0 | tables, menu |
| F02 | [Danh tính, phiên, phân quyền](features/F02-identity.md) | P0 | auth, security |
| F03 | [Giỏ, gửi món, gọi thêm](features/F03-ordering.md) | P0 | ordering |
| F04 | [Theo dõi bill, hủy dòng món](features/F04-bill-cancellation.md) | P0 | billing |
| F05 | [Hàng đợi và tiến độ pha chế](features/F05-kitchen.md) | P0 | kitchen |
| F06 | [Bật/tắt còn hàng](features/F06-availability.md) | P0 | menu |
| F07 | [Thu tiền, biên nhận, lượt mới](features/F07-payment.md) | P0 | payments, billing |
| F08 | [Mở và đóng ca](features/F08-shifts.md) | P0 | shifts |
| F09 | [SSE và phục hồi đồng bộ](features/F09-realtime.md) | P1 bắt buộc demo | events |
| F10 | [Xuất QR từng bàn](features/F10-qr-export.md) | P0 | tables |
| F11 | [Gợi ý món](features/F11-recommendations.md) | P2 | recommendations |
| F12 | [Đối soát ca](features/F12-shift-report.md) | P2 | reports |

P2 có thiết kế đầy đủ nhưng chưa trở thành điều kiện chặn demo P0/P1. Không thêm quản trị user, sửa giá, refund, split bill, nhiều quán hoặc gateway.

## Từ điển duy nhất

| Tên hiển thị | Tên kỹ thuật | Ý nghĩa |
| --- | --- | --- |
| Bàn | table | Vị trí vật lý, QR ổn định; demo chỉ bàn 1 và 3 |
| Hóa đơn / phiên bàn | bill | Một lượt phục vụ; `open` hoặc `paid` |
| Lượt gọi | order | Một lần gửi giỏ đã commit; nhiều order cùng bill |
| Dòng món | order item | Món, quantity, note; trạng thái áp dụng toàn dòng |
| Chờ / đang pha / xong / đã hủy | waiting / preparing / done / cancelled | Không quay lùi, không nhảy bước |
| Phiên khách | guest session | Cookie ẩn danh, khác bill; có thể tham gia nhiều bill |
| Ca | shift | Chỉ một ca mở; không đóng khi còn bill mở |
| Thanh toán | payment | Thu ngân xác nhận tiền mặt đã nhận, không gọi dịch vụ ngoài |

Tất cả ID là UUID trừ số thứ tự order/event; tiền VND là integer ở DB, chuỗi chữ số ở API; timestamp UTC, hiển thị giờ Asia/Bangkok. Tên trong sơ đồ là tiếng Việt kèm mã Fxx để tra đúng tài liệu; tên object kỹ thuật giữ nguyên ở API/schema/tests.

## Quyết định chi tiết cần mang sang C01

- Lần submit đầu có `expected_bill_id=null`: nếu đã xuất hiện bill mở thì **409**, không tự join. Xác nhận tham gia rồi mới gửi lệnh mới. Sửa cách viết rút gọn mâu thuẫn tại PLAN mục 5.3.
- Có một `shift_guard` bảo vệ cả trạng thái chưa có ca; `event_clock` bảo đảm cursor không bỏ sót giao dịch commit trễ. Đây là chi tiết nhất quán nội bộ, không mở rộng sản phẩm.
- Snapshot HTTP dùng cùng snapshot DB với cursor; không dùng sequence event đơn thuần làm thứ tự commit. Chi tiết ở technical design.
- GET menu không tạo bill; bootstrap POST chỉ tạo/tái dùng guest session, join POST chỉ cấp membership. Snapshot paid không đổi theo giá/menu hiện tại.

Agent tiếp theo bắt đầu C01: chuyển [API design](api-design.md) thành canonical schema/examples và kiểm tra máy; tiếp S01 rồi triển khai theo [test plan](test-plan.md). Không tự nhận interface đã freeze chỉ vì tài liệu này chi tiết.
