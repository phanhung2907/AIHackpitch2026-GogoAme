# flowdesign_TRICK — Diễn giải luồng từ A tới Z

## Viết bằng lời trước khi vẽ

Mỗi bước trả lời: **ai làm → nhập/đọc gì → hệ thống kiểm tra gì → trạng thái/dữ liệu đổi thế nào → người dùng thấy gì → đi đâu tiếp**. Dùng cùng thuật ngữ với glossary và contract.

Luồng sản phẩm phải bắt đầu từ mở ứng dụng/đăng nhập, đi qua lựa chọn nghiệp vụ, xử lý, kết quả, rồi xem lại lịch sử/đăng xuất. Một giao dịch chờ duyệt có thời gian chờ giữa hai yêu cầu; không vẽ như một HTTP request chạy xuyên suốt tới khi analyst quyết định.

## Phân nhánh A–Z của demo ngân hàng

- **A — Vào hệ thống:** mở UI, đăng nhập, sai thông tin thì hiện lỗi; đúng thì tải phiên và vai trò.
- **B — Chọn việc:** teller quản lý khách hàng/tài khoản và giao dịch tại quầy; customer chuyển tiền/xem dữ liệu của mình; analyst xem hàng đợi; admin quản lý cấu hình.
- **C — Tạo lệnh tiền:** kiểm tra quyền/input/retry; khóa và kiểm tra tài khoản/khả dụng; chạy fraud rules. Lỗi thì không thay đổi tiền. Lệnh hợp lệ đi ghi sổ; lệnh nghi ngờ lưu chờ duyệt, giữ tiền nguồn nếu cần.
- **D — Kiểm duyệt sau đó:** analyst đọc bằng chứng, nhập lý do. Từ chối thì giải phóng tiền giữ. Duyệt thì kiểm tra lại điều kiện hiện tại; nếu đạt mới ghi sổ, nếu chưa đạt phản hồi rõ và giữ trạng thái phù hợp.
- **E — Kết quả:** cập nhật lịch sử, số dư đã ghi sổ/tiền giữ/khả dụng và audit; UI đọc kết quả thật, không tự suy ra đã thành công.
- **F — Sửa sai:** yêu cầu đảo giao dịch đã ghi sổ, người khác có quyền kiểm duyệt, tạo bút toán bù có liên kết. Không xóa lịch sử gốc.

## Những nhánh hay bị quên

Phiên hết hạn; không đủ quyền; dữ liệu rỗng; input sai; không tìm thấy đối tượng; conflict version; retry; thiếu vị trí; không đủ tiền; lỗi DB/engine; từ chối; duyệt thất bại; tải lại trang sau khi đã tạo lệnh.

Với mỗi nhánh ghi “đã thay đổi gì chưa?”. Sau lỗi trước commit: không đổi tiền. Sau mất mạng chưa rõ kết quả: truy vấn lại/retry cùng key. Đừng hướng người dùng tạo lệnh mới ngay vì có thể nhân đôi thao tác.

## Chọn loại sơ đồ đúng câu hỏi

| Câu hỏi | Sơ đồ |
| --- | --- |
| Người dùng đi qua sản phẩm ra sao? | Flowchart A–Z |
| Ai gọi ai và gọi lúc nào? | Sequence diagram cho một use case |
| Trạng thái đổi hợp lệ ra sao? | State diagram |
| Bảng liên kết thế nào? | ER diagram |
| Hệ thống gồm những thành phần nào? | Component/container flowchart |

Sơ đồ tổng quan giữ mức nghiệp vụ; transaction/lock chi tiết đưa vào sequence riêng. Luôn có đoạn giải thích bằng lời ngay cạnh sơ đồ. Ví dụ: [luồng sản phẩm](../../backend/design/product-flow.md).
