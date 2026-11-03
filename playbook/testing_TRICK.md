# testing_TRICK — Test nhanh, đủ bằng chứng rồi chuyển bước

## Quy trình mặc định theo yêu cầu chủ repo

**Unit test phần thay đổi → integration test luồng liên quan → đạt thì chuyển bước.** Không lặp lại toàn bộ suite sau mỗi lần sửa nhỏ. Lint/type/build chạy theo loại thay đổi và công cụ đã có; không mở rộng sang browser E2E, load test, restore drill hoặc audit toàn bộ nếu task không cần và chưa có lỗi cụ thể.

Thời gian chạy lâu là tín hiệu cần chọn lại phạm vi, không phải lý do bỏ qua lỗi đã biết. Gate bắt buộc của repo/CI vẫn phải giữ; nếu quá nặng thì ghi rõ và đề xuất điều chỉnh trong một thay đổi riêng, không âm thầm bypass.

## Chọn đúng kiểm tra

| Thay đổi | Unit tối thiểu | Integration tối thiểu |
| --- | --- | --- |
| Fraud rule | Bình thường + đúng biên + vượt biên | Một lệnh tạo đúng status/evidence |
| Rút/chuyển | Validation và quyết định domain | DB thật: số dư/ledger/reservation, retry, rollback; concurrency khi thay logic lock |
| Auth/quyền | Client xử lý phiên/lỗi | Login + session + một endpoint đúng/sai quyền + logout |
| FE nối API | Header/payload/error/pagination | Browser-origin/proxy gọi server và đọc lại dữ liệu |
| Form/UI nhỏ | Logic đổi nếu có | Một happy path + lỗi liên quan; không dựng lại cả môi trường E2E |
| Markdown | Không cần application tests | Link, cấu trúc, Mermaid khi thay sơ đồ |

Với hệ thống tiền, unit mock repository không thay được integration PostgreSQL. SQLite không chứng minh row lock/transaction giống Postgres. Dùng DB test riêng, không xóa volume dev để test.

## Một vòng nhanh có điểm dừng

1. Chọn acceptance criteria của task và danh sách test chịu ảnh hưởng trước khi chạy.
2. Với bug, thêm regression fail trước khi practical; với feature, test domain/contract quan trọng.
3. Chạy unit nhỏ nhất. Fail thì sửa và chạy lại phần fail.
4. Chạy integration của feature/luồng vừa đổi. Kiểm tra cả response lẫn dữ liệu hậu điều kiện.
5. Chạy lint/type/build liên quan một lần sau thay đổi cuối.
6. Review diff. Nếu các gate đã chọn pass, không có lỗi mới hoặc thay đổi mới: dừng test, cập nhật context, commit/push và báo cáo.

Không chạy lại suite đã pass chỉ vì sắp viết câu trả lời. Chỉ mở rộng khi có thay đổi dùng chung, lỗi phát hiện, thiếu bằng chứng cho acceptance criteria hoặc yêu cầu CI cụ thể.

## Lệnh ví dụ theo repo

Từ `backend/`, dùng interpreter/uv của project:

```text
python -m pytest tests/test_domain.py -q
python -m pytest tests/test_features.py -q -k withdrawal
```

Tên test/filter phải kiểm tra theo cây file thực tế trước khi chạy; ví dụ trên minh họa cách chọn phạm vi, không là danh sách kết quả đã chạy. Từ `frontend/`: `npm run test:api`, `npm run lint`, `npm run build`. `test:api` chạy Node, không cần tải browser. `npm test` của template chạy browser mode, không dùng làm bước mặc định cho một API-client unit test.

## Những thứ làm mất thời gian cần tránh

- Cài browser/test framework mới khi Node unit test đủ kiểm tra payload/header.
- Build lại dependency khi chỉ cần sửa source; giữ lockfile và tận dụng cache Docker.
- Chạy full backend suite sau chỉnh câu chữ/frontend đơn lẻ không ảnh hưởng API.
- Test mock tự trả thứ implementation mong muốn mà không kiểm tra contract hoặc DB state.
- Dùng lại cùng một `Response` đã đọc body trong nhiều lần mock fetch: phải tạo Response mới mỗi lần.
- Cố chạy đường khác sau khi quyền thực thi bị từ chối. Báo rõ kiểm tra chưa chạy; không gọi là pass.

## Báo cáo ngắn, trung thực

```text
Unit: N/N pass — phạm vi ...
Integration: pass/fail/chưa chạy — luồng và môi trường ...
Lint/type/build: kết quả thực tế ...
Còn thiếu: ... (nếu có)
Quyết định: chuyển bước / đang bị chặn bởi lỗi cụ thể ...
```

Không suy ra integration pass từ TypeScript build; không suy ra hosted CI pass từ local. Không cần đuổi một tỷ lệ coverage toàn repo cho mọi task nhỏ; chỉ giữ ngưỡng đã cấu hình và bảo đảm case rủi ro được test.
