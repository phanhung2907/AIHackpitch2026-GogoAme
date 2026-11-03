## Slide 1
Mở đầu 20 giây: TapOrder kết nối khách, pha chế và thu ngân trong một luồng phục vụ. Nguồn: PLAN-2.

## Slide 2
Đây là vấn đề sản phẩm hướng tới, chưa có số liệu khảo sát định lượng. Không tuyên bố mức tiết kiệm đã đo.

## Slide 3
Nguồn: PLAN mục4; DESIGN-1 F01–F08. Guest không login.

## Slide 4
Nguồn: e04bd4b:docs/design/product-flow.md và product-flow.png. Ảnh Mermaid gốc, không vẽ lại bằng boxes. Sơ đồ dài nên có bản ảnh riêng để phóng to.

## Slide 5
Nguồn: F03/F04/F05/F06. Hủy chỉ toàn dòng do session khách tạo khi waiting. Availability không phải tồn kho định lượng.

## Slide 6
Nguồn: DESIGN-1 system-design. Kiến trúc mục tiêu; chưa khẳng định main đã có backend triển khai. SSE báo refetch, HTTP snapshot authoritative.

## Slide 7
Nguồn: DESIGN-1 data-model và backend/app/models/__init__.py. Mỗi FK child tham chiếu đúng một parent. Số con tối thiểu0; payment optional trước khi paid. bills.table_id unique có điều kiện khi open, không unique lịch sử.

## Slide 8
Nguồn: DESIGN-1 và foreign keys trong backend models. sessions.staff_user_id nullable: guest không có staff_user; staff session có đúng1 staff_user. Thể hiện các FK liên quan trong sơ đồ; không phải mọi cột. orders.created_by_session_id tham chiếu sessions; payments.cashier_id tham chiếu staff_users.

## Slide 9
Nguồn: technical-design F02/F03/F07/F09. Đây là thiết kế phải được chứng minh bằng integration PostgreSQL; chưa claim đã pass.

## Slide 10
Bàn1: 2 cà phê 30000=60000; gọi thêm trà35000=95000. Bàn3 độc lập35000. Các dòng cần done trước pay.

## Slide 11
Nguồn: main context/HANDOFF.md tại lúc tạo deck: FE mock; DESIGN-1 e04bd4b đọc từ Git. Main không có docs/design/backend. Không claim CI/deploy/backend acceptance.

## Slide 12
Kết thúc 15giây. Giá trị kỳ vọng, chưa đo tác động định lượng.

## Slide 13
Nguồn: e04bd4b:docs/design/assets/product-flow.png và product-flow.md. Hình gốc là ảnh nhúng; bản pitch ở slide4 và schema ở slide7 có objects chỉnh sửa được.