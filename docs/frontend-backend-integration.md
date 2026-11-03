# Nối frontend với backend FastAPI

Tài liệu cho người làm backend. Đây là **mô tả đúng những gì `frontend/` đang gửi
và đang đọc hôm nay**, không phải contract đã chốt. Contract chuẩn vẫn là
[plans/product-plan.md](../plans/product-plan.md) §10.2; `contracts/openapi.yaml` chưa tồn tại (mốc CONTRACT-1
chưa làm). Chỗ nào FE lệch §10.2, mục 6 ghi rõ.

Nguồn sự thật phía FE: [frontend/src/api/client.ts](../frontend/src/api/client.ts) và
[frontend/src/api/types.ts](../frontend/src/api/types.ts). Nếu sửa backend khác tài liệu này, sửa luôn hai file đó.

## 1. Bật chế độ live

FE có hai chế độ trong một client. Mặc định `VITE_USE_MOCK=1` chạy mock trong
browser. Để gọi backend thật:

```bash
cd frontend && VITE_USE_MOCK=0 npm run dev
```

`frontend/vite.config.ts` đã proxy `/api` sang `http://127.0.0.1:8000`, nên backend
chỉ cần nghe `127.0.0.1:8000` và FE/BE **cùng origin** từ góc nhìn browser. Nhờ đó
không cần CORS, cookie `SameSite=Lax` chạy bình thường. Đừng đổi FE sang gọi
`http://127.0.0.1:8000` tuyệt đối — làm vậy là cross-origin và cookie sẽ bị chặn.

Base path mọi endpoint: `/api/v1` (biến `VITE_API_BASE`).

## 2. Quy ước chung

### 2.1 Envelope

Thành công: `{"data": ...}`. Lỗi: `{"error": {"code","message","details","request_id"}}`.

FE **hiện ra thẳng `error.message` cho người dùng**, nên `message` phải là tiếng
Việt, ngắn, nói được người dùng phải làm gì. `code` dùng để phân nhánh logic.

### 2.2 Tiền

Truyền **chuỗi decimal** VND, ví dụ `"30000"`. FE gửi lên dạng chuỗi và parse cả
chuỗi lẫn số khi đọc về, nên số nguyên cũng không vỡ — nhưng cứ gửi chuỗi cho
đúng §10.1.

### 2.3 Headers trên mutation

FE tự thêm, backend phải chấp nhận:

| Header | Khi nào | Ghi chú |
| --- | --- | --- |
| `Content-Type: application/json` | mọi mutation | |
| `X-CSRF-Token` | khi FE đã nhận được `csrf_token` | FE lấy token từ bất kỳ response có `data.csrf_token` và giữ trong memory |
| `Idempotency-Key` | order, cancel, status, availability, payment, shift | UUID v4 mới mỗi lần bấm; retry cùng lệnh thì FE sinh key mới, nên key **không** dùng để chống double-click — FE đã disable nút khi pending |

`credentials: 'same-origin'`, nên session phải là cookie HttpOnly cùng origin.

### 2.4 Enum

- `status` của dòng món: `waiting` | `preparing` | `done` | `cancelled`
- `status` của bill: `open` | `paid`
- `status` của bàn: `free` | `serving`
- `role`: `barista` | `cashier`
- `method` của payment: `cash`

## 3. Endpoint FE đang gọi

Thứ tự ưu tiên để demo chạy: nhóm A trước, B sau, C cuối.

### Nhóm A — tối thiểu để kịch bản `DEMO.txt` chạy

| Method / path | Request body | FE đọc gì trong `data` |
| --- | --- | --- |
| `GET /auth/bootstrap` | — | `csrf_token` |
| `POST /auth/login` | `{username, password}` | `staff: {id, username, role}`, `csrf_token` |
| `POST /auth/logout` | `{}` | — |
| `POST /guest/bootstrap` | `{qr_token}` | `table_number`, `qr_token`, `current_bill_id` (nullable) |
| `GET /guest/menu` | — | `items: MenuItem[]` |
| `POST /guest/orders` | `{qr_token, expected_bill_id, items}` | `bill.id`, `order.order_number` |
| `GET /guest/bills/{id}` | — | `BillDTO` |
| `GET /kitchen/queue` | — | `tickets: Ticket[]` (hoặc mảng trần) |
| `PATCH /kitchen/items/{id}/status` | `{status, expected_version}` | — |
| `GET /cashier/tables` | — | `tables: Table[]` (hoặc mảng trần) |
| `GET /cashier/bills/{id}` | — | `BillDTO` |
| `POST /cashier/bills/{id}/payments` | `{expected_bill_version, expected_total_vnd, method:"cash"}` | `payment.amount_vnd` |
| `GET /cashier/shifts/current` | — | `Shift` hoặc `null` |
| `POST /cashier/shifts` | `{}` | `Shift` |

### Nhóm B — các nút còn lại trong UI

| Method / path | Request body | FE đọc gì |
| --- | --- | --- |
| `POST /guest/items/{id}/cancel` | `{expected_version}` | không đọc, chỉ refetch bill |
| `GET /kitchen/menu` | — | `items: MenuItem[]`, không cần giá |
| `PATCH /kitchen/menu/{id}/availability` | `{available, expected_version}` | không đọc, chỉ refetch |
| `POST /cashier/shifts/{id}/close` | `{expected_version}` | `Shift` |
| `GET /cashier/shifts/{id}/report` | — | `revenue_vnd`, `paid_bill_count`, `top_items[{name, quantity}]` |

### Nhóm C — chưa bắt buộc

| Method / path | Trạng thái FE |
| --- | --- |
| `GET /guest/recommendations` | FE gọi, đọc `items[{item, reason}]`; thiếu thì khối gợi ý rỗng, không vỡ trang |
| `GET /guest/bills/{id}/events`, `/guest/menu/events`, `/kitchen/events`, `/cashier/events` | **FE chưa gọi.** Đang polling 2 giây. Session `fe-polish` đang thêm lớp SSE |
| `GET /cashier/tables/{id}/qr` | **FE chưa gọi** — xem mục 6.2 |
| `POST /guest/join` | **FE không gọi** — xem mục 6.1 |

## 4. DTO — đúng field FE đọc

Field nào FE đọc mà thiếu thì UI hiện sai hoặc trắng. Field thừa bị bỏ qua.

### MenuItem

```json
{
  "id": "uuid",
  "category": "Cà phê",
  "name": "Cà phê sữa",
  "unit_price_vnd": "30000",
  "available": true,
  "version": 1
}
```

`category` là **chuỗi trên từng món**: FE tự nhóm tab theo field này, không đọc
mảng `categories` riêng. `version` bắt buộc vì FE gửi lại nó khi bật/tắt hết hàng.

### BillDTO

```json
{
  "id": "uuid",
  "table_number": 1,
  "status": "open",
  "version": 5,
  "opened_at": "2026-11-03T09:04:00Z",
  "paid_at": null,
  "total_vnd": "60000",
  "can_pay": false,
  "orders": [
    {
      "id": "uuid",
      "order_number": 1,
      "created_at": "2026-11-03T09:04:00Z",
      "items": [
        {
          "id": "uuid",
          "menu_item_id": "uuid",
          "name": "Cà phê sữa",
          "unit_price_vnd": "30000",
          "quantity": 2,
          "note": "Ít đá",
          "status": "waiting",
          "version": 1,
          "can_cancel": true
        }
      ]
    }
  ],
  "payment": null
}
```

- `can_pay` do server tính (§10.3). FE chỉ enable nút thanh toán theo field này,
  không tự suy từ danh sách món.
- `total_vnd` là tổng của server. FE không bao giờ gửi tổng lên.
- `payment` khi đã trả: `{"id","bill_id","shift_id","amount_vnd","method","paid_at"}`.
- Dòng `cancelled` **phải vẫn trả về** để FE gạch ngang và không tính tiền; đừng xoá khỏi response.
- `can_cancel`: xem mục 6.1, FE hiện chưa dùng field này.

### Ticket (kitchen)

```json
{
  "item_id": "uuid",
  "table_number": 1,
  "name": "Cà phê sữa",
  "quantity": 2,
  "note": "Ít đá",
  "status": "waiting",
  "version": 1,
  "created_at": "2026-11-03T09:04:00Z",
  "order_number": 1
}
```

Không có giá, không có payment, không có danh tính khách (§4.2). Queue sort theo
`created_at` tăng rồi `item_id` — FE sort lại y như vậy, nhưng cứ trả đúng thứ tự.
Dòng `done` và `cancelled` rời khỏi queue.

### Table (cashier)

```json
{
  "number": 1,
  "qr_token": "<token>",
  "status": "serving",
  "bill_id": "uuid",
  "total_vnd": "60000",
  "can_pay": true
}
```

### Shift và Staff

```json
{"id": "uuid", "opened_at": "2026-11-03T09:00:00Z", "closed_at": null, "version": 1}
{"id": "uuid", "username": "cashier.demo", "role": "cashier"}
```

`Shift.version` bắt buộc: FE gửi lại khi đóng ca.

## 5. Error code FE phân nhánh theo tên

Các code này FE hiểu và xử lý (giữ giỏ, giữ dialog, refetch). Code lạ vẫn hiện
`message` nên không vỡ, nhưng mất hành vi đúng.

| Code | Khi nào | FE làm gì |
| --- | --- | --- |
| `SHIFT_CLOSED` | chưa mở ca mà gửi order hoặc thu tiền | giữ nguyên giỏ, hiện lỗi |
| `ITEM_UNAVAILABLE` | một món trong lượt hết hàng | giữ giỏ; `details` nên có danh sách món |
| `PRICE_CHANGED` | giá khác `expected_unit_price_vnd` | giữ giỏ, yêu cầu xác nhận lại |
| `BILL_CLOSED` | thêm món hoặc thu tiền trên bill `paid` | hiện lỗi |
| `STATE_CONFLICT` | hủy món không còn `waiting` | refetch bill |
| `VERSION_CONFLICT` | `expected_version` lệch | refetch rồi thử lại |
| `INVALID_TRANSITION` | đổi trạng thái sai thứ tự | refetch queue |
| `ITEMS_NOT_DONE` | thu tiền khi còn món chưa xong | giữ trang, hiện lỗi |
| `AMOUNT_CHANGED` | tổng lệch `expected_total_vnd` | refetch bill |
| `SHIFT_ALREADY_OPEN` / `OPEN_BILLS_EXIST` | mở/đóng ca sai điều kiện | hiện lỗi |
| `INVALID_CREDENTIALS` | login sai | hiện lỗi chung, không nói sai user hay sai pass |
| `FORBIDDEN` / `NOT_FOUND` | sai quyền hoặc sai scope | hiện lỗi |

Status code: 401 khi chưa có phiên, 403 sai role, 404 sai scope, 409 các conflict
trên, 422 field errors, 429 rate limit, 503 rollback. Đừng trả 200 kèm `error`.

## 6. Ba chỗ FE hiện lệch — phải chốt trước khi nối

### 6.1 Quyền hủy món: `guest_id` vs `can_cancel`

FE hiện so `item.guest_id` với một id ngẫu nhiên FE tự sinh trong
`sessionStorage` (`guestId()` trong `client.ts`). Id đó **không bao giờ khớp** id
phía server, nên khi chạy live nút "Hủy món" sẽ không hiện cho ai.

Cách đúng theo §10.3: server trả `can_cancel` (và `is_mine`) trên từng dòng, FE
đổi điều kiện ở `frontend/src/features/guest/BillPage.tsx` từ
`item.guest_id === me` sang `item.can_cancel`. Backend cứ trả `can_cancel`; phần
sửa FE là một dòng và thuộc việc của FE.

FE cũng **không gọi** `POST /guest/join`. Luồng hiện tại là `bootstrap` rồi
`submit` thẳng. Backend phải cấp membership ngay trong `POST /guest/orders` dựa
trên `qr_token`, không được bắt join trước, nếu không mọi order sẽ 403.

### 6.2 QR token trong danh sách bàn

Trang `/staff/cashier/qr` dựng URL `${origin}/t/${table.qr_token}` từ
`GET /cashier/tables`. §9.4 lại nói token phải mã hóa, chỉ giải mã ở endpoint
riêng cho cashier, không log URL/token.

Chọn một, rồi ghi vào context:

- **(a)** `GET /cashier/tables` trả `qr_token` (chỉ cashier, `Cache-Control: no-store`). FE không phải sửa.
- **(b)** Giữ `GET /cashier/tables/{id}/qr` trả `{table_number, url}`. FE phải sửa trang QR để gọi endpoint đó. An toàn hơn, đúng §9.4.

### 6.3 Menu response

FE đọc `data.items` và nhóm theo `item.category`. §10.2 ghi menu trả
`categories/items/version/event_cursor`. Backend cứ trả đủ theo §10.2, miễn là
`items[].category` có mặt; FE bỏ qua phần còn lại. `event_cursor` hiện FE không dùng.

## 7. Kiểm tra sau khi nối

Chạy theo thứ tự, dừng ở bước đầu tiên fail:

1. `GET /api/v1/health/ready` trả 200 từ DB sạch đã migrate và seed.
2. Mở `http://127.0.0.1:5173/staff/login`, đăng nhập `cashier.demo`. DevTools
   Network: `POST /api/v1/auth/login` trả 200, có `Set-Cookie`.
3. Mở ca. `GET /cashier/shifts/current` sau đó trả shift khác `null`.
4. Mở `/t/t1`, thêm món, **Gửi order**. `POST /guest/orders` trả 201. Đây là bước
   chứng minh membership cấp trong submit chứ không cần join.
5. Đăng nhập `barista.demo` ở cửa sổ khác, `/staff/kitchen` thấy đúng ticket của bàn 1.
6. Bấm **Bắt đầu pha** rồi **Xong**. Trang khách đổi trạng thái trong vài giây.
7. Thu ngân: nút thanh toán chỉ bật khi `can_pay` true. Thu tiền, bill thành `paid`.
8. Gửi `POST /cashier/bills/{id}/payments` lần hai với key mới → `BILL_CLOSED`, và
   DB chỉ có **một** payment.
9. Mở lại `/t/t1` → menu, và `GET /guest/bootstrap` trả `current_bill_id: null`
   (GET không tạo bill).
10. Guest gọi `GET /api/v1/cashier/tables` bằng curl → 401 hoặc 403. Barista gọi
    endpoint cashier → 403. Guest đọc bill bàn khác → 404.
11. Restart API → order và payment vẫn còn.

Bước 5–6 là bằng chứng duy nhất cho thấy đã thoát mock: mock `localStorage` không
cho hai cửa sổ khác profile thấy dữ liệu của nhau. Nếu bước 5 trống, kiểm
`VITE_USE_MOCK` có đúng `0` chưa.

## 8. Những gì backend không được nhận từ FE

- Tổng tiền, thuế, giảm giá: FE không gửi, server tự tính.
- `role`, `table_id`, `guest_id`, `status` do client tự đặt: không tin, lấy từ
  session và DB.
- `expected_*` chỉ để phát hiện conflict, không phải giá trị để ghi.
- Không có CRUD menu, không có đăng ký tài khoản, không có admin UI.
