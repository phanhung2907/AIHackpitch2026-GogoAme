# systemdesign_TRICK — Thiết kế hệ thống trước chức năng

## Những phần phải có

| Phần | Mức chi tiết cần đạt |
| --- | --- |
| Bối cảnh | Actor, mục tiêu, hệ thống ngoài, phạm vi demo/production |
| Thành phần | Browser → frontend → API → service/domain → PostgreSQL; nhiệm vụ mỗi khối |
| Triển khai | Cổng, container, mạng, volume, proxy, health, cấu hình/secrets |
| Module | Identity, customers, accounts, money, fraud, review, audit/admin; ai gọi ai |
| Dữ liệu | Entity, khóa, kiểu tiền/thời gian, FK, unique/check, index, version |
| Nhất quán | Transaction bắt đầu/kết thúc ở đâu, lock nào, thứ tự lock, rollback |
| Bảo mật | Cookie/session, CSRF/Origin, role, ownership, kiểm tra input và audit |
| Trạng thái | Danh sách trạng thái, transition hợp lệ, ai được chuyển và hiệu ứng dữ liệu |
| Lỗi/phục hồi | Retry, idempotency, conflict version, mất kết nối, lỗi DB/engine |
| Vận hành | Migration, seed, log/request ID, backup/restore, CI và rollback |

Mỗi lựa chọn ghi: vấn đề → quyết định → lý do → đánh đổi → ảnh hưởng FE/BE. Chỉ thêm queue/cache/microservice khi bài toán có nhu cầu cụ thể. Demo này phù hợp backend modular monolith và PostgreSQL làm ranh giới nhất quán.

## Bất biến làm xương sống

- Tiền không qua float; API là chuỗi chữ số, DB là số nguyên có giới hạn kiểm tra.
- `available_balance = posted_balance - reserved_amount`.
- HOLD chưa ghi sổ; rút/chuyển giữ tiền nguồn; gửi chưa cộng tiền.
- Chuyển nội bộ ghi debit/credit nguyên tử; thất bại phải rollback toàn bộ.
- Retry không tạo thêm bút toán; cùng key khác payload là conflict.
- Ledger bất biến; sửa sai bằng reversal liên kết và kiểm duyệt.
- Hai lệnh đồng thời phải được serialize theo tài khoản; khóa nhiều tài khoản theo thứ tự ổn định.
- UI không tự quyết định số dư, quyền, kết quả rule hay trạng thái posted.

## Thiết kế dữ liệu đủ để viết migration

Với mỗi bảng ghi cột/kiểu/null/default, PK/FK, unique/check, chính sách xóa, index theo truy vấn và trường version nếu dùng optimistic concurrency. Phân biệt user đăng nhập, customer và bank account. Liên kết transaction với ledger entries, reservations, rule evidence, review, reversal và audit.

Ghi cả truy vấn quan trọng: lịch sử theo tài khoản/thời gian, lệnh lớn trong cửa sổ, hàng đợi chờ duyệt, cursor pagination. Giải thích index phục vụ truy vấn nào, tránh index theo cảm tính.

## Bộ tài liệu đề xuất

```text
docs/design/
  README.md               # thứ tự đọc + glossary + feature index
  system-design.md        # thành phần, boundaries, deployment
  technical-design.md     # transaction, lock, retry, errors
  data-model.md           # schema, constraints, indexes
  product-flow.md         # luồng sản phẩm A–Z
  features/01-identity.md # một feature một file
contracts/openapi.yaml    # nguồn chuẩn payload
docs/decisions/            # quyết định có đánh đổi đáng lưu
```

Không chép cùng payload vào nhiều tài liệu; link tới contract. Sơ đồ kiến trúc dùng để biết thành phần nào liên hệ với thành phần nào; sơ đồ sản phẩm giải thích việc gì xảy ra tiếp theo. Tách hai mục đích để sơ đồ không thành một mạng mũi tên khó đọc.

Xem ví dụ thực tế: [system design](../../backend/design/system-design.md), [technical design](../../backend/design/technical-design.md), [data model](../../backend/design/data-model.md).
