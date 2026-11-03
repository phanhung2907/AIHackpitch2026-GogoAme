# Playbook xây webapp: từ yêu cầu tới tích hợp

Bộ kinh nghiệm rút ra từ repo banking này, cập nhật 2026-11-03. Dùng cho người và agent; đọc theo thứ tự dưới đây. Các mẫu có thể sao chép sang dự án khác và thay phần đặc thù nghiệp vụ.

| Thứ tự | Tài liệu | Đầu ra cần có |
| --- | --- | --- |
| 1 | [PLAN_TRICK](PLAN_TRICK.md) | Phạm vi, quyết định, mốc, phân công, tiêu chí nghiệm thu |
| 2 | [systemdesign_TRICK](systemdesign_TRICK.md) | Kiến trúc, dữ liệu, ranh giới nhất quán và bảo mật |
| 3 | [featuredesign_TRICK](featuredesign_TRICK.md) | Đặc tả từng chức năng đủ để viết code và test |
| 4 | [flowdesign_TRICK](flowdesign_TRICK.md) | Luồng người dùng A–Z, nhánh lỗi, chờ và phục hồi |
| 5 | [chartdrawing_TRICK](chartdrawing_TRICK.md) | Quy chuẩn Mermaid và sơ đồ mẫu |
| 6 | [frontend_TRICK](frontend_TRICK.md) | Stack, template, mock theo contract và đổi sang API |
| 7 | [backend_TRICK](backend_TRICK.md) | Stack, module, transaction, migration và API |
| 8 | [testing_TRICK](testing_TRICK.md) | Unit → integration → chuyển bước khi đạt |
| 9 | [CICD_CONTEXT_TRICK](CICD_CONTEXT_TRICK.md) | Commit, push, checkpoint, bàn giao agent |

## Điều kiện xuyên suốt

Thiết kế hệ thống trước, sau đó thiết kế từng chức năng. Chốt hợp đồng API trước khi frontend/backend phát triển song song. Một thuật ngữ, trạng thái và mã lỗi phải giữ nguyên giữa plan, sơ đồ, contract, mock và code.

Đủ chi tiết nghĩa là hai người nhận cùng tài liệu có thể dựng frontend/backend tương thích mà không phải tự đoán payload, quyền, trạng thái hay điều kiện lỗi. Không cần viết trước từng dòng code hay từng component UI.

## Phân biệt kinh nghiệm với kết quả đã kiểm chứng

- Backend đã có báo cáo triển khai và kiểm thử: [implementation report](../../backend/implementation-report.md).
- Frontend ban đầu là fixtures tĩnh; mã nối API đã có trong commit `8d3ba8e` ở thời điểm chốt bộ này. Build, TypeScript, lint và 5 unit test API đã pass trong Docker. Đã quan sát UI đăng nhập chuyển sang trang chính; chưa xác nhận toàn bộ luồng UI qua trình duyệt.
- Kiểm tra HTTP qua cổng UI bị chặn quyền truy cập socket trong môi trường thực thi; yêu cầu chạy mở quyền đã bị từ chối. Không tính kiểm tra đó là pass, và không thử đường khác để vượt giới hạn.
- MSW là cách mock được khuyến nghị trong playbook; repo này chưa triển khai MSW. Không mô tả khuyến nghị thành việc đã làm.
- Local pass không có nghĩa hosted CI hoặc production pass. Sản phẩm này bàn giao demo local, chưa phải hệ thống ngân hàng vận hành tiền thật.

Nguồn hiện hành: [plan](../../plans/banking-webapp-plan.md), [thiết kế backend](../../backend/design/README.md), [OpenAPI](../../contracts/openapi.yaml), [package frontend](../../frontend/package.json), [package backend](../../backend/pyproject.toml). Nếu ghi chú cũ khác code/contract, kiểm tra và ghi quyết định điều chỉnh; không âm thầm chọn một bản.
