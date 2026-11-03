# Review backend và tích hợp — 2026-11-03

Review tĩnh, không chạy test theo yêu cầu chủ repo. Đã đọc design system/F03 và source routes/config/auth/ordering/menu/kitchen/payments/shifts/events/seed/migration. Không kết luận backend hoàn thiện 100% khi chưa chạy thực tế.

Backend có triển khai F01–F12: session/CSRF/RBAC, QR capability mã hóa, join membership, order và cancel có expected version, lock/idempotency, payment và shift, event SSE, recommendation/report, Alembic và PostgreSQL. Điểm cần lưu ý: queue phân trang; FE hiện chỉ hiện trang đầu tối đa 100 lượt. FE dùng polling, chưa nối SSE. Chưa xác minh race/rollback/migration/runtime. Backend lấy canonical OpenAPI từ contracts nên spec được công bố không tự chứng minh code conform.

Đã sửa FE: mặc định live, ánh xạ menu price_vnd/category_id, bootstrap.table.number, join hóa đơn hiện tại, expected_bill_id, flatten kitchen order tickets, unwrap shift, QR qua endpoint cashier, can_cancel từ server, QR thật khi gọi thêm, khôi phục staff session và CSRF sau reload. Cookie vẫn cùng origin, không fallback mock khi API lỗi.

## Demo cùng Wi-Fi, backend ở máy local

1. Mở Docker Desktop. Dùng PowerShell 7 tại root repo; chạy `ipconfig` lấy IPv4 của Wi-Fi, ví dụ 192.168.1.20.
2. Chạy `./scripts/demo-lan.ps1 -LanIp 192.168.1.20`. Script build/start DB + backend, migrate, hỏi hai mật khẩu demo, seed rồi chạy FE Vite live. Cần npm dependencies đã cài (`cd frontend; npm ci` nếu chưa có). Seed chỉ dùng DB demo của Compose.
3. Cho phép cổng 5173 qua Windows Firewall trên mạng Private khi Windows hỏi. Các thiết bị dùng cùng Wi-Fi, không có client isolation. Backend/DB chỉ bind loopback; Vite proxy API tới backend.
4. Thu ngân mở `http://192.168.1.20:5173/staff/login`, login cashier.demo với mật khẩu vừa nhập, mở ca rồi vào QR lấy QR thật bàn 1/3. Không dùng token mock t1/t3.
5. Điện thoại quét QR, chọn món/gửi. Thiết bị hoặc browser profile riêng login barista.demo, Bắt đầu pha rồi Xong. Thu ngân thu tiền khi đủ điều kiện, xem báo cáo, đóng ca sau khi hết bill mở. Không login hai staff trong cùng browser profile vì dùng chung cookie.
6. Giữ terminal Vite và Docker chạy; Ctrl+C dừng FE. `docker compose stop backend postgres_dev` dừng server, giữ dữ liệu. Không xóa volume.

## Frontend đã deploy trên HTTPS

Chỉ cùng Wi-Fi không làm domain deploy gọi được backend loopback. Cần rewrite `/api/*` tại host frontend tới một HTTPS tunnel trỏ về 127.0.0.1:8000 trên máy local; giữ nguyên path, forward cookie/Set-Cookie, không cache API. Giữ VITE_USE_MOCK=0, VITE_API_BASE=/api/v1 rồi rebuild/redeploy. Backend đặt PUBLIC_BASE_URL và ALLOWED_ORIGINS đúng origin frontend đã deploy, COOKIE_SECURE=true. Không gọi thẳng HTTP LAN từ trang HTTPS (mixed content/cookie). Chưa cấu hình host vì chưa có URL/quyền host trong phiên này. Phương án LAN ở trên dùng ngay source frontend cùng backend local, không phải bằng chứng bản deploy đã cập nhật.

## Xác minh

Không chạy unit/integration/browser test theo yêu cầu. Build/type và diff được ghi ở checkpoint; không claim hosted CI hay deployed acceptance. Review và tích hợp là snapshot backend đang được agent khác xây dựng, giữ nguyên worktree nguồn.

## Trạng thái chạy thật trên máy — cập nhật cuối phiên

- Đã cài npm 12.2.1 từ registry npm chính thức vào .local-tools/npm, lệnh npm tại .local-tools/bin, thêm user PATH cho terminal mới. `npm ci` cài 144 packages. `npm run build --prefix frontend` (TypeScript + Vite) thành công sau thay đổi cuối.
- Docker PostgreSQL dev đang healthy. Docker build backend bị chậm lúc tải dependencies nên đã dừng build; dùng Python virtualenv sẵn có tại `.local-tools/worktrees/taporder-backend/backend/.venv/Scripts/python.exe` chạy source backend của main.
- `alembic upgrade head` và `python -m app.seed --export-demo-txt` hoàn tất. Không xóa/rotate dữ liệu cũ. Tài khoản và QR thật nằm tại `.local-tools/demo/accounts.txt` (ignored).
- Backend Uvicorn đã báo application startup complete trên 127.0.0.1:8000; frontend Vite đang chạy live tại http://10.12.3.127:5173. Mở http://10.12.3.127:5173/staff/login ngay trên máy này hoặc máy cùng Wi-Fi. Chưa chạy HTTP/browser test theo yêu cầu; startup/build không chứng minh luồng nghiệp vụ đã pass.
- Trình tự demo: cashier mở ca → mục QR → điện thoại quét → gửi món → barista ở profile/browser riêng nhận và hoàn tất → cashier thu tiền → báo cáo ca. Không mở /t/t1 hoặc /t/t3 trong live.
- Nếu mở terminal mới chưa nhận npm, tại root chạy `$env:PATH = "$PWD/.local-tools/bin;" + $env:PATH`.
