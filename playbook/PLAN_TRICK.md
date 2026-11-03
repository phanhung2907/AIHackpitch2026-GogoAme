# PLAN_TRICK — Viết kế hoạch để hai phía làm song song

## Trình tự và ràng buộc từng bước

| Bước | Công việc | Chỉ chuyển bước khi |
| --- | --- | --- |
| 0 | Đọc repo, Git status, context, stack và CI hiện có | Biết phần đã có, phần thiếu, thay đổi của người khác |
| 1 | Chốt mục tiêu, phạm vi, vai trò, quy tắc và stack | Các câu hỏi ảnh hưởng kiến trúc đã có quyết định hoặc được đánh dấu chặn |
| 2 | Thiết kế hệ thống tổng thể, dữ liệu, trạng thái, bảo mật | Mỗi thành phần có trách nhiệm và ranh giới dữ liệu rõ |
| 3 | Thiết kế từng feature và hợp đồng API | Có request/response/error mẫu, quyền và acceptance criteria |
| 4 | Chốt luồng A–Z và Mermaid | Người mới đọc hiểu cả thành công, lỗi và chờ duyệt |
| 5 | Frontend mock/UI và backend/API song song | Hai phía dùng cùng contract/fixtures; task có owner và phụ thuộc |
| 6 | Tích hợp bằng adapter/proxy | Không còn mock trong đường chạy thật; phiên/quyền/lỗi hoạt động |
| 7 | Unit rồi integration phần liên quan | Đạt tiêu chí thì dừng test và bàn giao |
| 8 | Context, diff review, commit/push, báo cáo | Remote được xác minh; dừng tại checkpoint chủ repo yêu cầu |

Ở repo này mỗi mốc được duyệt phải commit/push và dừng để chủ repo kiểm tra. Làm song song nằm trong mốc được duyệt, không bỏ qua checkpoint.

## Bố cục một plan đủ dùng

1. **Bài toán:** ai sử dụng, cần đạt kết quả gì, tiêu chí thành công quan sát được.
2. **Phạm vi:** in scope/out of scope; dữ liệu demo hay thật; giới hạn phiên bản đầu.
3. **Quyết định:** frontend/backend/database/template, môi trường chạy, auth, tiền/thời gian; lý do ngắn gọn và ngày chốt.
4. **Vai trò và quyền:** ma trận role × thao tác × phạm vi dữ liệu; UI ẩn nút không thay thế kiểm tra API.
5. **Danh mục chức năng:** ID F01…, mục tiêu, phụ thuộc, ưu tiên, link thiết kế.
6. **Bất biến:** điều không được sai dù lỗi, retry hoặc đồng thời.
7. **Dữ liệu và trạng thái:** entity, quan hệ, enum, transition, đơn vị và nguồn thời gian.
8. **Hợp đồng tích hợp:** link OpenAPI, examples, mã lỗi, cookie/CSRF, pagination, idempotency.
9. **Màn hình:** route, quyền, dữ liệu cần đọc, thao tác, loading/empty/error/success/pending.
10. **Phân rã thực thi:** task ID, owner FE/BE/shared, artifact, phụ thuộc, điểm hợp nhất và tiêu chí done.
11. **Kiểm thử nhanh:** unit nào, integration nào; điều kiện dừng và lỗi nào chặn bàn giao.
12. **Vận hành:** cấu hình, migration/seed, mở UI, log, CI, rollback khi có thay đổi dữ liệu.
13. **Rủi ro/giả định:** quyết định còn mở, người quyết định, ảnh hưởng; không để TODO mơ hồ ở chỗ FE/BE cần dùng ngay.

## Chi tiết tới đâu để không phải đoán?

Ví dụ F05 rút tiền: ghi rõ `POST /api/v1/withdrawals`, `amount` là chuỗi số nguyên VND, ID tài khoản là UUID, cookie phiên, header CSRF/idempotency, role teller. Response `201` có thể là `posted` hoặc `pending_review`; UI phải hiển thị theo trạng thái trả về. Lỗi thiếu tiền, tài khoản khóa, phiên hết hạn và retry khác payload phải có mã thống nhất trong OpenAPI. Không chỉ viết “làm chức năng rút tiền”.

Các ngưỡng phải có toán tử: `> 1 tỷ`, mỗi lệnh `> 500 triệu`, thời gian `<= 30 giây`, khoảng cách `> 500 km`. Ghi tài khoản nào được xét, lịch sử nào được tính, nguồn tọa độ và cách xử lý thiếu vị trí. Những chữ “lớn”, “gần”, “xa” chưa đủ để triển khai.

## Bảng task mẫu

| Task | Owner | Phụ thuộc | Đầu ra | Done |
| --- | --- | --- | --- | --- |
| SH-01 | Shared | Quy tắc nghiệp vụ | OpenAPI + examples + enum | FE/BE cùng đọc hiểu, không còn payload đoán |
| FE-05 | Frontend | SH-01 | Form rút + mock handler + trạng thái UI | Mock success/hold/error đúng schema |
| BE-05 | Backend | SH-01, DB | API + transaction + tests | Unit/integration liên quan pass |
| INT-05 | Tích hợp | FE-05, BE-05 | Đổi API thật + proxy | Luồng đọc/ghi/refresh đúng dữ liệu server |

Nếu thay contract: sửa contract/examples trước, thông báo hai phía, regenerate types và sửa mock/API theo cùng thay đổi. Không để frontend tự đổi enum để làm UI chạy.
