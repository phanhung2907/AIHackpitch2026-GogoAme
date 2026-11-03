# F08 — Mở và đóng ca

P0; shifts service, phụ thuộc F02. [API fields](../api-design.md), [guard lock](../technical-design.md#2-thứ-tự-khóa-thống-nhất), [schema](../data-model.md).

## Quyền và phạm vi

Cashier GET /cashier/shifts/current; POST /cashier/shifts body{}; POST /cashier/shifts/{id}/close expected_version. Mutations CSRF/key; chỉ1ca open toàn quán, không sửa thời gian/mở lại. Ca cần để submit/payment, không bắt buộc để browse menu hoặc barista chỉnh availability. Barista/guest nhận shift_open qua snapshot/SSE, không đọc report/cashier endpoint.

## Thuật toán và trạng thái

1. Current snapshot trả shift hoặc null + cursor. Không tự mở ca khi login/seed/GET.
2. Open: auth/replay/reserve → shift_guard FOR UPDATE → query ca open. Nếu tồn tại409 SHIFT_ALREADY_OPEN. Nếu không insert shift open/version1/opened_by/time DB; guard.version+1; audit shift.open, shift.updated audiences menu/kitchen/cashier; key/commit201. Partial unique index open là hàng rào cuối.
3. Close: auth/replay/reserve → guard FOR UPDATE → shift FOR UPDATE theo ID; missing404. Nếu closed409 STATE_CONFLICT; stale expected409 VERSION_CONFLICT (trong trường hợp còn open). COUNT bills.status=open; nếu>0 trả409 OPEN_BILLS_EXIST + count, không auto pay/cancel.
4. Không open bills: shift closed/closed_by/time, shift.version+1, guard.version+1, audit shift.close/events/key; commit200. Không sửa payment quá khứ. Ca sau là row mới, không reopen ca cũ.

## Race, lỗi và phục hồi

Order/payment giữ guard SHARE và shift SHARE tới commit; close exclusive đợi tất cả kết thúc. Create trước→close thấy bill open và409. Close trước khi không bill→submit sau thấy không ca409 SHIFT_CLOSED; không orphan bill/shift. Guard tồn tại ngay khi chưa có ca nên open/create cũng được serialize. Hai open khác key→1shift/1conflict; cùng key replay. Hai close cùng key replay; khác key sau close STATE_CONFLICT, không đổi closed_at. Failure rollback guard version/events/shift; timeout giữ key.

## UI và acceptance/test

`/staff/cashier/shift`: current state rõ, mở ca pending, đóng ca disabled nếu snapshot còn bill và server vẫn kiểm. Conflict hiển thị count và link bảng bàn, không popup chỉ “thất bại”. No current ca: banner menu/kitchen/cashier và CTA cashier mở ca. Event refetch shift status, không tự gửi lại cart sau ca mở. Audit actor/shift/state/version, không credentials.

| Setup / hành động | Expected response / DB |
| --- | --- |
| DB seed chưa ca, GET current |200 shift null,0 rows mới |
| Open {} hai request khác key |1success201,1SHIFT_ALREADY_OPEN;1open row |
| Close có bill waiting/done/toàn cancelled nhưng vẫn open |409 OPEN_BILLS_EXIST; shift open/time null |
| Mọi bill paid, close version đúng |200 closed,version+1; payment totals giữ nguyên |
| Close-vs-first-order hai hướng |Không bill sau closed; hoặc close conflict nếu order trước |
| Order ngoài ca |409 SHIFT_CLOSED,0bill/order/membership mới |

Unit open/close predicates; integration guard khi chưa ca, close/create/payment races/unique/replay; contract null/shift_open; FE banner/empty/error. Files services/shifts.py, repositories/shifts.py, api/cashier.py. Không thêm shift scheduling/time input; C01/S01 là gate.
