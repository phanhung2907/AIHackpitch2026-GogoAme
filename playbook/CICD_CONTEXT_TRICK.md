# CICD_CONTEXT_TRICK — Giữ nhịp làm việc và context giữa agent

## Một mốc hoàn tất

Đọc context/Git → xác định phạm vi → thiết kế/contract nếu cần → implement → unit/integration liên quan → diff review → cập nhật context → commit → fetch/reconcile → push → xác minh remote → báo cáo và dừng tại checkpoint đã hẹn.

ECC cung cấp hướng dẫn local; cài skills không tự tạo CI/CD hay chứng minh pipeline pass. Skills và cấu hình riêng local phải được ignore theo yêu cầu repo. Không đưa cả kho skills lên GitHub để chia sẻ context.

## Bố cục Markdown có thể dùng lại

```text
AGENTS.md                         # quy trình, quyền, checkpoint
README.md                         # mở UI/chạy app và đường dẫn chính
plans/product-plan.md             # mục tiêu, stack, scope, task FE/BE
docs/design/README.md              # index + glossary
docs/design/system-design.md
docs/design/technical-design.md
docs/design/data-model.md
docs/design/product-flow.md
docs/design/features/Fxx-name.md
contracts/openapi.yaml
contracts/examples/               # fixture/scenario chung khi cần
docs/playbook/                    # kinh nghiệm tái sử dụng
context/PROJECT.md                # sự thật bền vững
context/HANDOFF.md                # trạng thái hiện tại, việc còn lại
context/WORKLOG.md                # lịch sử ngắn theo mốc
frontend/README.md                # chạy FE, mock/live, role/routes
backend/README.md                 # DB, migration/seed, API, tests
```

Đây là cấu trúc mẫu; repo hiện tại đặt thiết kế trong `backend/design/`. Link đến nguồn chuẩn thay vì nhân bản payload/quy tắc ở nhiều file. Obsidian mở root repo bằng “Open folder as vault”; agent chỉ cần đọc Markdown, không phụ thuộc app Obsidian.

## Handoff phải trả lời được ngay

Đã làm gì, artifact ở đâu, test nào thực sự pass, test nào chưa chạy/vì sao, nhánh/commit/remote, app đang mở ở đâu, việc tiếp theo đã được duyệt chưa, chỗ nào còn mock và chỗ nào live. Không ghi “xong toàn bộ” nếu mới build pass hoặc chỉ quan sát trang login.

Không ghi secrets/password/PII vào context; chỉ ghi tên biến và cách tìm trên máy. Phiên bản và ngưỡng đã chốt cần có nguồn/link; ghi chú cũ phải được sửa hoặc đánh dấu đã lỗi thời.

## Commit và CI gọn

Stage đúng file của task, giữ công việc người khác, Conventional Commit, không force push. Nếu code task trước còn dở khi chuyển sang task tài liệu, giữ nguyên và ghi rõ; không gom vào commit tài liệu như thể đã nghiệm thu tích hợp.

Pipeline nên lọc đường dẫn FE/BE/contracts, cài dependency từ lock, chạy checks phù hợp, quyền tối thiểu, secrets từ môi trường bảo vệ. Contract đổi thì cần kiểm tra cả hai phía. CI là một nơi chạy gate đã thống nhất, không thêm việc deploy ngoài phạm vi yêu cầu.

Khi báo cáo: phân biệt local verification, hosted CI, local app đang chạy và production. Có thể commit tài liệu hướng dẫn dù integration còn chưa nghiệm thu, miễn trạng thái ghi trung thực và không đánh dấu task tích hợp hoàn tất.
