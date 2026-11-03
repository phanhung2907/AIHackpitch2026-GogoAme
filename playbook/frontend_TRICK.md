# frontend_TRICK — Xây UI bằng mock rồi nối backend

## Stack thực tế và quyết định giữ template

Repo dùng React 19, TypeScript 6, Vite 8, Tailwind CSS 4, shadcn/ui/Radix, TanStack Router, TanStack Query, TanStack Table, React Hook Form/Zod và Zustand cho trạng thái phiên trong bộ nhớ. Kiểm thử API dùng Vitest ở Node. Nguồn phiên bản tái lập là `package-lock.json`, không chỉ khoảng version trong `package.json`.

Template là **satnaing/shadcn-admin**, MIT, upstream `e16c87f`; giữ [LICENSE](../../frontend/LICENSE) và [README upstream](../../frontend/README.upstream.md). Plan ban đầu nêu React Router; template thực tế dùng TanStack Router. Giữ router đang có để tránh đổi cả khung chỉ vì tên thư viện trong plan cũ; phải ghi nhận quyết định này khi đồng bộ tài liệu.

## Cấu trúc đề xuất

```text
frontend/src/
  routes/                  # route và guard
  components/ui/           # primitive từ shadcn
  components/layout/       # sidebar/header/layout
  features/<feature>/      # page, components, hooks
  features/banking/api/    # generated schema, client, query adapters
  mocks/                   # MSW handlers + scenarios (khi áp dụng)
  stores/                  # state giao diện/phiên tối thiểu
contracts/                 # ở root repo, dùng chung với backend
```

## Cách làm song song có thể hợp nhất

1. Shared chốt OpenAPI, enum, example success/empty/error/hold và quyền trước.
2. FE generate types, viết một API client dùng đường dẫn thật `/api/v1/...`.
3. Khuyến nghị MSW chặn cùng request ở dev/test; handler trả đúng envelope, pagination, cookie/error semantics cần mô phỏng. Không để page import fixtures trực tiếp nếu mục tiêu là đổi sang live nhanh.
4. Dựng UI loading/empty/error/retry/success/pending; bảng, form và reviewer dùng cùng DTO với backend.
5. BE triển khai API theo contract; FE tiếp tục xây UI mà không chờ server.
6. Tích hợp: tắt mock, giữ API client/page, dùng proxy cùng origin; kiểm tra session, quyền, một mutation và refresh. Nếu phải sửa mọi page mới gọi được live thì mock boundary đã đặt quá sâu trong UI.

Repo này ban đầu dùng fixtures trực tiếp; bước nối thật phải thay dữ liệu ở các page bằng query/provider. MSW chưa được cài, nên đây là bài học cho lần sau, không phải thành quả đã kiểm chứng.

## Ràng buộc giao diện tiền

- Định dạng tiền bằng chuỗi/BigInt; không `Number(amount)` để tính số dư.
- Server trả trạng thái nào thì hiện trạng thái đó; HOLD phải ghi rõ chờ duyệt.
- Mutation tiền không optimistic update số dư; thành công mới invalidate/refetch query liên quan.
- Giữ idempotency key khi retry cùng lệnh sau lỗi mạng; đổi key khi người dùng tạo lệnh mới. Không tạo key mới cho mỗi lần bấm retry.
- Cookie phiên HttpOnly; CSRF trong bộ nhớ, khôi phục qua session endpoint; không token đăng nhập giả trong localStorage.
- Guard/sidebar theo role để dễ sử dụng; server vẫn là nơi thực thi quyền.
- Mất phiên phải xóa cache liên quan; đổi user không được thấy dữ liệu cache của người trước.
- Recipient lookup theo số tài khoản trước khi gửi UUID đích; không yêu cầu người dùng đoán UUID cho thao tác chuyển tiền thông thường.

## Tips từ lần tích hợp này

Nginx phục vụ UI và proxy `/api` tới FastAPI, nên browser cùng origin cho cookie/CSRF. Vite dev cũng cần proxy và origin được backend cho phép. UI Docker dùng cổng `8080`; API docs vẫn ở `8000/docs`.

TanStack route tree cần sinh trước TypeScript check ở clean build; script hiện chạy `vite build && tsc -b`. Generator OpenAPI 7 yêu cầu TypeScript 5 trong khi template dùng TS6: chạy generator trong môi trường tool riêng có version khóa, đừng dùng `--force` để bỏ qua peer conflict. Sinh type xong không có nghĩa đã gọi đúng endpoint; vẫn cần integration test.

Gỡ nút đăng nhập/đăng xuất giả, sidebar không liên quan, dashboard giả và thao tác chỉ toast mà không lưu. Template là nền giao diện; từng hành động nghiệp vụ phải có endpoint, payload, lỗi và kết quả thật.
