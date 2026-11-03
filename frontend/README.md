# TapOrder — frontend (Đề 2)

React 18 + TypeScript + Vite + Tailwind + React Router + TanStack Query + Zustand.

## Chạy

```bash
cd frontend
npm install
npm run dev
```

Mở http://127.0.0.1:5173 — trang chủ là lối vào nhanh ba vai trò khi demo.

Tài khoản nhân viên (chỉ dùng cho demo, nằm trong mock): `barista` / `barista123`, `cashier` / `cashier123`.

## Chế độ dữ liệu

`VITE_USE_MOCK=1` (mặc định) chạy mock backend trong browser, lưu ở `localStorage`
key `taporder.db.v1`, nên không cần FastAPI để demo. `src/api/client.ts` giữ đúng
chữ ký của contract trong `plans/product-plan.md` §10.2: đặt `VITE_USE_MOCK=0` là
client gọi `/api/v1` qua Vite proxy sang `127.0.0.1:8000`, UI không phải sửa.

**Giới hạn đã biết:** `localStorage` chỉ dùng chung giữa các tab/cửa sổ của **cùng một
browser profile**. Kịch bản demo hai bàn vì vậy phải mở hai cửa sổ cùng browser. Hai
browser khác nhau (Chrome và Firefox) cần backend thật mới thấy chung dữ liệu.

Cập nhật trạng thái dùng polling 2 giây của TanStack Query, chưa phải SSE. Khi backend
có `/events`, đổi ở `src/api/client.ts` và các `refetchInterval`.

## Kịch bản demo bắt buộc

1. Thu ngân đăng nhập → `/staff/cashier/shift` → **Mở ca** (chưa mở ca thì không nhận order).
2. Cửa sổ A mở `/t/t1`, cửa sổ B mở `/t/t3`; mỗi bên chọn món, ghi chú, **Gửi order**.
3. Pha chế đăng nhập → `/staff/kitchen` thấy đủ hai bàn theo FIFO → **Bắt đầu pha** → **Xong**;
   khách thấy trạng thái đổi trong 2 giây.
4. Thu ngân → bàn 1 → **Xác nhận đã thu tiền mặt** (nút chỉ bật khi mọi món đã xong).
5. Mở lại `/t/t1`: vào menu cho lượt mới, bill đã trả tiền không bị sửa (quyết định D02).

Hết hàng: pha chế `/staff/kitchen/menu` tắt một món khi khách đang chọn → khách gửi
order bị chặn cả lượt kèm tên món (D03), giỏ giữ nguyên.

## Quyết định nghiệp vụ thể hiện trong code

| ID | Nơi cưỡng chế |
| --- | --- |
| D01 hủy món chỉ khi `waiting` và đúng người gọi | `src/mocks/store.ts` `cancelItem` |
| D02 QR sau thanh toán mở lượt mới, GET không tạo bill | `guestBootstrap`, `submitOrder` |
| D03 một món hết hàng làm cả lượt thất bại | `submitOrder` |
| D05 một bàn tối đa một bill `open` | `openBillOf` trong `submitOrder` |
| D06 chỉ thu khi mọi món chưa hủy đã `done` | `recompute` (`can_pay`) + `pay` |
| D07 một payment duy nhất, không mở lại bill `paid` | `pay` |
| D08 hàng đợi FIFO theo `created_at` rồi `id` | `kitchenQueue` |

## Nguồn tham khảo

Bố cục menu/cart/ticket/report tham khảo [roshanx0/restaurant-ordering-saas](https://github.com/roshanx0/restaurant-ordering-saas)
(MIT). Không copy nguyên file: Supabase client, login RPC, thuế 5% và nhập bàn thủ công
đã bị thay bằng QR theo bàn, API client chung và tiền do server tính — xem
`plans/product-plan.md` §7.

## Lệch so với plan (cần ghi nhận)

- Plan §3.2 chọn TanStack Router; bản này dùng `react-router-dom` để port nhanh theo repo
  tham khảo. Đổi router là việc một task riêng, không chặn demo.
- Chưa có MSW, Vitest, shadcn/ui, SSE. Chưa chạy test nào; chỉ `tsc -b` và `vite build` đã pass.
