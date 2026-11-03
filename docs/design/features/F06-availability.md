# F06 — Bật/tắt còn hàng

P0; menu service, F02. [API fields](../api-design.md), [menu locks](../technical-design.md), [schema](../data-model.md).

## Quyền và input

Chỉ barista PATCH /kitchen/menu/{id}/availability, body available bool + expected_version>=1, CSRF/business key. GET kitchen/menu không giá; guest/cashier chỉ đọc menu/tình trạng. Không quản lý số lượng tồn, không menu CRUD hoặc thay giá. Inactive item không xuất hiện ở UI; PATCH inactive/missing404. Không bắt buộc ca mở để chỉnh availability trước ca.

## Luồng và transaction

1. FE lấy kitchen/menu snapshot, hiển thị mỗi switch availability theo server version. Click gửi target bool explicit, không gửi lệnh “toggle” khó retry.
2. Auth barista/replay → transaction reserve key → lock menu row FOR UPDATE → recheck active/version. Stale409 VERSION_CONFLICT; bool sai type422.
3. Nếu target trùng current và version khớp: trả200 no-op, lưu idempotency response, không tăng menu version/không business audit/event mới. Nếu khác: update available, version+1, audit menu.availability, menu.updated cho menu/kitchen/cashier; append/key/commit200. Không sửa order items/snapshots/bill totals.
4. Guest nhận event rồi refetch menu; giỏ giữ món nhưng báo hết hàng; submit luôn kiểm DB dù event chưa tới.

## Race, retry, lỗi

Submit khóa cùng menu rows; toggle commit trước→submit reject toàn lượt409 ITEM_UNAVAILABLE. Submit commit trước→order giữ waiting và giá cũ, toggle chỉ tác động lượt sau. Hai barista gửi opposite target cùng expected version: một update, sau409; no-op thành công không khóa UI ở version tăng giả. Timeout/retry cùng key trả nguyên result không đảo ngược trạng thái. DB rollback không menu/event/audit partial. No-op không cần event_clock lock nếu lấy cursor committed snapshot hiện tại trong transaction; event cursor có thể refetch thừa, không áp dụng business state mới qua SSE.

## UI và acceptance/test

`/staff/kitchen/menu`: loading/error retry/empty, switch có label tên món + Còn hàng/Hết hàng dạng chữ, pending disabled từng item.409 refetch và báo thay đổi từ màn khác, không auto gửi target lại. Không cho cashier thấy control có thể thao tác; API vẫn403.

| Setup / hành động | Expected response / DB |
| --- | --- |
| available true v1 → false v1 |200,false,v2; menu event/audit, bills không đổi |
| false v2 → false v2 key mới |200 no-op,v2; không event/audit mới |
| v1 stale khi DB v2 |409 VERSION_CONFLICT; không overwrite |
| False commit trước order nhiều món có món đó |Order409,0 bill/order partial; giỏ giữ |
| Order accepted rồi false |Order vẫn waiting/price snapshot; không bị hủy tự động |
| Cashier PATCH / guest PATCH |403; không rows/events |

Unit target/version behavior; integration submit race, no-op, replay/rollback; contract KitchenMenuItemDTO no price; FE switch status/conflict. Files services/menu.py, repositories/menu.py, api/kitchen.py, schemas/menu.py. Audit không QR/note; C01/S01 trước code.
