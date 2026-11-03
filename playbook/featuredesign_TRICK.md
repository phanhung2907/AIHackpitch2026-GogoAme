# featuredesign_TRICK — Một chức năng cần mô tả những gì?

## Template sao chép

```markdown
# Fxx — Tên chức năng
## Mục tiêu, actor, phạm vi
## Tiền điều kiện và quyền/ownership
## Input, validation, nguồn dữ liệu tin cậy
## API và examples (link OpenAPI)
## Luồng chính có đánh số
## Nhánh lỗi, pending, retry, đồng thời
## Dữ liệu đọc/ghi, transaction và lock
## Trạng thái trước/sau và hậu điều kiện
## UI: route, form, loading/empty/error/success/pending
## Audit/log và dữ liệu cần che
## Acceptance criteria và unit/integration tối thiểu
## Phụ thuộc, task FE/BE, quyết định còn mở
```

Mức chi tiết: đủ để người viết API biết thứ tự kiểm tra và ranh giới commit; người viết UI biết trường nào cần nhập, endpoint nào gọi, trạng thái/lỗi nào hiển thị; người test suy ra được kết quả mong đợi. Không cần mô tả cú pháp từng câu lệnh.

## Ví dụ rút tiền

1. Teller đăng nhập, chọn tài khoản và nhập số tiền dương dạng chuỗi VND.
2. FE tạo idempotency key cho nội dung lệnh; gửi cookie, CSRF và payload theo contract.
3. API kiểm tra session, quyền, schema và retry. Cùng key/cùng payload trả lại kết quả cũ; khác payload báo conflict.
4. Service mở transaction, khóa tài khoản, kiểm tra trạng thái và số dư khả dụng, đọc lịch sử theo ngữ nghĩa đã chốt.
5. Domain đánh giá các luật; lưu version của luật và bằng chứng. Nếu HOLD: tạo reservation, chưa debit. Nếu hợp lệ: ghi ledger và số dư nguyên tử.
6. Commit trạng thái/audit/idempotency cùng ranh giới đã thiết kế; trả kết quả server.
7. FE phân biệt `posted` và `pending_review`, refresh dữ liệu; lỗi thì giữ dữ liệu nhập. Không hiện “rút thành công” cho một lệnh chờ duyệt.

Nhánh cần viết rõ: số tiền không hợp lệ, thiếu tiền, tài khoản khóa, phiên hết hạn, mất mạng sau khi server commit, người dùng bấm hai lần, hai lệnh rút cùng lúc, lỗi rule engine. Retry sau mất mạng phải dùng lại key cũ cho cùng lệnh.

## Acceptance criteria viết được thành test

| Tình huống | Kết quả mong đợi |
| --- | --- |
| Đúng 1 tỷ | Không match HIGH_AMOUNT; các rule khác vẫn được xét |
| 1 tỷ + 1 | HOLD và evidence HIGH_AMOUNT; chưa ghi sổ |
| Rút quá khả dụng | Lỗi nghiệp vụ, không đổi ledger/số dư |
| Retry cùng key | Một kết quả, không có bút toán thứ hai |
| Analyst từ chối HOLD | Giải phóng reservation, không debit |
| Duyệt khi điều kiện đã thay đổi | Kiểm tra lại và phản hồi đúng; không ép ghi sổ |

## CRUD không đồng nghĩa sửa/xóa mọi thứ

Customer có thể sửa thông tin và archive theo điều kiện. Account có vòng đời active/frozen/closed và expected_version. Transaction đã ghi sổ không có sửa/xóa trực tiếp; có reversal. Mỗi feature phải ghi trường nào được sửa, điều kiện không được xóa và mã lỗi khi xung đột version.

Ví dụ đủ bộ: [12 feature designs](../../backend/design/README.md). Một chức năng đơn giản có thể chỉ cần 1–2 trang; chức năng tiền/review phải thêm transaction, retry và concurrency. Số trang không thay thế độ rõ của quyết định.
