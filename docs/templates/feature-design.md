# Fxx — TEMPLATE chức năng

Trạng thái/owner/contract revision; mục tiêu, actor, phạm vi và phụ thuộc.

1. Preconditions, permissions/ownership và bất biến.
2. Input/validation (field, type, required/null/default, giới hạn và ví dụ), dữ liệu tin cậy.
3. Endpoint/status/error codes, link canonical schema/examples; không chép một payload thành nhiều nguồn chuẩn.
4. Luồng chính từng bước: ai gọi ai, thứ tự kiểm tra, thuật toán/pseudocode đủ quyết định, data reads/writes, response/UI.
5. Luồng sai input, không quyền/không thấy resource, conflict, pending, retry, mất mạng/DB, đồng thời và recovery; sau lỗi dữ liệu đổi gì.
6. Bảng/cột/constraints/index/query, transaction start/commit/rollback, lock ordering, idempotency nếu cần.
7. State transitions và hậu điều kiện, ai được chuyển và hiệu ứng; audit/log/redaction.
8. UI routes/forms/components/query/cache; loading/empty/error/retry/success và accessibility.
9. Acceptance Given/When/Then, boundary/negative/concurrency cases; unit/integration/contract test mapping, setup/actions/expected response và DB state.
10. Task FE/BE/testing, file/module dự kiến, dependencies, lệnh kiểm tra thực tế khi scaffold, câu hỏi mở/owner.

Gate: agent mới triển khai/test được mà không tự đoán quyền, payload, enum, thuật toán hoặc kết quả lỗi.
