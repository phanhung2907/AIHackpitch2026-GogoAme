# F01 — QR, menu và tham gia bàn

P0; tables/menu services. Phụ thuộc F02/seed; triển khai theo [API fields](../api-design.md), [locks](../technical-design.md), [schema](../data-model.md).

## Mục tiêu, quyền và input

Khách mở `/t/:qrToken` không login, thấy đúng bàn và menu, không tự nhập số bàn. Token random256-bit base64url43; bootstrap POST kiểm Origin, token hash/disabled trước tạo session. Menu GET cần guest session; category_id optional UUID tồn tại, category không tồn tại trả404. Menu chỉ active; hết hàng vẫn hiển thị unavailable. Không response bill contents chỉ vì có QR.

Endpoints: POST guest/bootstrap, POST guest/join, GET guest/menu. Request/response chuẩn ở API design. Join có CSRF, expected_bill_id required nullable; không business key. Token không xuất hiện trong logs/audit/query analytics.

## Luồng chính

1. FE đọc token ở route, POST bootstrap; backend resolve hash→table enabled, tạo/reuse guest cookie12h;200 metadata bàn/current_bill_id/CSRF. Không membership/bill/order mới.
2. FE hiển thị bàn, nếu bill đang mở thì giải thích đang tham gia lượt đó; POST join với expected_bill_id vừa nhận. Khóa table, kiểm lại table enabled/current bill. Khớp UUID thì UPSERT membership; không bill và expected null thì trả null/false; commit membership đơn độc, không event nghiệp vụ.
3. FE GET menu (snapshot + cursor/shift_open); render categories, giá server, số lượng/note giỏ theo F03. Nếu chưa ca: xem menu được, CTA gửi bị disable có lời giải thích; backend F03 vẫn cưỡng chế.
4. Khi bàn đổi lượt giữa resolve/join:409 TABLE_VISIT_CHANGED chỉ metadata; giữ giỏ, yêu cầu khách xác nhận tham gia lượt hiện tại. Xác nhận → bootstrap/resolve lại, join expected mới; không loop tự động join.

## Đồng thời, lỗi và hậu điều kiện

Join khóa table cùng submit/payment nên membership gắn đúng bill. Expected UUID paid mà QR vẫn hợp lệ:409 TABLE_VISIT_CHANGED, không cấp membership paid. Guest đã có membership paid đọc receipt qua F04, không cần join lại. Join retry cùng session/bill không nhân membership (composite PK), không thay ownership items. Token sai/disabled404 không tạo cookie/membership mới; session expired401 ở menu/join thì bootstrap lại, không nhận quyền hủy của session cũ. Menu/QR GET không tạo bill ngay cả reload100 lần. DB lỗi503 rollback membership mới, UI retry read/join an toàn; không tự submit.

## UI và audit

Header tên bàn cố định; loading skeleton, empty menu “Chưa có món”, unavailable có chữ, error retry, route token sai hướng dẫn liên hệ thu ngân. Không lưu raw QR/CSRF vào sessionStorage; giỏ chỉ lưu table/visit/items theo F03. Giá/available refetch khi SSE menu event; không đổi giỏ âm thầm. Audit join chỉ bill/session IDs, không token; bootstrap log route template.

## Acceptance/test và triển khai

| Setup / hành động | Expected response và DB |
| --- | --- |
| QR1/QR3 hợp lệ, bootstrap/menu |200 đúng table1/3;0 bills/orders/memberships trước join |
| QR giả hoặc table disabled |404; không business rows/cookie mới |
| Join bill A hai lần |200 A; đúng1 membership, không order |
| Resolve null, browser khác tạo A rồi join null |409;0 membership mới, UI xác nhận trước join A |
| Bill A paid, guest mới dùng QR |Không đọc A; menu/submit tạo lượt mới theo F03 |
| Guest có session nhưng bill bàn khác không membership |GET bill404, stream404 |

Unit: token format/menu filters/visit matching; integration PostgreSQL: join-vs-payment và no-create-on-GET; contract: nullability/projection; UI: mobile360px/giữ giỏ/error states. Files dự kiến services/tables.py, repositories/tables.py, api/guest.py; FE route guest entry/menu. Không câu hỏi nghiệp vụ mở; C01/S01 là dependency triển khai.
