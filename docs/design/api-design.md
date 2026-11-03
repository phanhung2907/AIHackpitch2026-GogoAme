# Đầu vào CONTRACT-1: API, DTO và lỗi

DESIGN-1; bổ sung PLAN mục10. **Chưa phải canonical OpenAPI đã freeze.** C01 phải tạo `contracts/openapi.yaml` và examples từ bảng này, validate schema/examples và generated client trước code/parallel work. Không có endpoint CRUD ngoài danh mục.

## 1. Quy ước wire

Base `/api/v1`; health ngoài version `/api/health/live`, `/api/health/ready`. JSON success `{data: object}`, list `{data: [], meta: {next_cursor: string|null, limit: integer}}`; endpoint snapshot list thêm `event_cursor` top-level. Snapshot object đặt event_cursor trong `data`. Không có trường ngầm: khi C01 chuyển schema phải giữ đúng vị trí này trong examples/client. Error `{error:{code:string,message:string,details:object,request_id:string}}`; 204 không body. Tất cả JSON/session/QR `Cache-Control: no-store`; static cache tách riêng.

UUID string; timestamp RFC3339 UTC Z; monetary string regex `^(0|[1-9][0-9]*)$`, bounds field tương ứng. ID event/order_number BIGINT cũng string để tránh mất độ chính xác JS; version/quantity/limit là strict integer (không bool/float/string). Unknown fields422, field nullable khai rõ. Null không đồng nghĩa omitted; required fields bên dưới không được bỏ. Note mặc định empty string khi omitted, trim Unicode whitespace trước kiểm<=250 code points. Payload text thuần, không HTML interpretation. Body64KiB, HTTP413 khi quá.

Business mutation có `Idempotency-Key: UUID`, `X-CSRF-Token`, cookie đúng principal và exact Origin. Login/bootstrap/join/logout theo policy riêng; join không cần idempotency key, UPSERT membership là tự nhiên idempotent. Schema API input không chứa client total tự do hay role. API response whitelist, không serialize ORM.

## 2. Các command schema (nguồn duy nhất của fields trong thiết kế)

| Tên | Fields, required trừ ghi optional |
| --- | --- |
| LoginInput | username string1..80 lowercase/trim, password string1..1024 không trim |
| BootstrapGuestInput | qr_token string base64url43 ký tự (256-bit, không padding) |
| JoinInput | qr_token như trên, expected_bill_id UUID nullable required |
| OrderInput | qr_token, expected_bill_id UUID nullable required, items array1..50; mỗi item menu_item_id UUID, quantity int1..20, note optional default empty <=250 sau trim, expected_unit_price_vnd string1..10000000 |
| ItemVersionInput | expected_version int>=1 |
| ItemStatusInput | expected_version, status enum preparing/done |
| AvailabilityInput | expected_version, available bool |
| PaymentInput | expected_bill_version int>=1, expected_total_vnd string0..1000000000, method enum cash |
| OpenShiftInput | object rỗng, unknown fields422 |
| CloseShiftInput | expected_version int>=1 |

Không merge các order items cùng món/note ở server; giữ thứ tự input khi tạo, display order theo item ID ổn định. Validation ưu tiên schema → auth/CSRF/resource → replay → business theo technical protocol. UUID bill của bàn khác hoặc thiếu membership404, không dùng QR để đọc lịch sử đó.

## 3. Endpoint inventory và response

| Method + path | Actor / input | Status / data |
| --- | --- | --- |
| GET /auth/bootstrap | Public; tái dùng/tạo preauth10m |200 csrf_token, expires_at; set preauth cookie |
| POST /auth/login | Preauth+CSRF+Origin; LoginInput |200 staff,csrf_token,expires_at; set staff cookie, consume preauth |
| GET /auth/session | Staff |200 staff,csrf_token,expires_at |
| POST /auth/logout | Staff+CSRF+Origin khi có session; repeat Origin-only |204 revoke, clear staff cookie |
| POST /guest/bootstrap | Public+Origin; BootstrapGuestInput |200 guest_id,csrf_token,expires_at,table:{id,number,label},current_bill_id nullable; set/reuse guest cookie |
| POST /guest/join | Guest+CSRF+Origin; JoinInput |200 bill_id nullable,membership bool; null/false nếu chưa bill |
| GET /guest/menu | Guest; category_id UUID optional |200 data:{categories:CategoryDTO[],items:GuestMenuItemDTO[],version:string,event_cursor:string,shift_open:bool}; không paginate |
| POST /guest/orders | Guest+QR+membership nếu UUID; OrderInput |201 data:{order:GuestOrderDTO,bill:BillSummaryDTO,event_cursor}; tạo/submit thêm |
| GET /guest/bills/{id} | Guest membership |200 BillDTO guest |
| POST /guest/items/{id}/cancel | Guest creator+membership; ItemVersionInput |200 data:{item:GuestItemDTO,bill:BillSummaryDTO,event_cursor} |
| GET /kitchen/queue | Barista; cursor?,limit int1..100 default50,status waiting/preparing optional,table_id UUID optional |200 data:KitchenTicketDTO[],meta,event_cursor,shift_open; empty [] hợp lệ |
| PATCH /kitchen/items/{id}/status | Barista; ItemStatusInput |200 data:{item:KitchenItemDTO,event_cursor} |
| GET /kitchen/menu | Barista |200 data:{items:KitchenMenuItemDTO[],event_cursor,shift_open} |
| PATCH /kitchen/menu/{id}/availability | Barista; AvailabilityInput |200 data:{item:KitchenMenuItemDTO,event_cursor} |
| GET /cashier/tables | Cashier |200 data:CashierTableDTO[],meta:{next_cursor:null,limit:2},event_cursor; limit bằng số bàn enabled thực tế |
| GET /cashier/bills/{id} | Cashier |200 BillDTO cashier |
| POST /cashier/bills/{id}/payments | Cashier; PaymentInput |201 data:{payment:PaymentDTO,bill:PaidBillSummaryDTO,table:{number,status:free},event_cursor} |
| GET /cashier/shifts/current | Cashier |200 data:{shift:ShiftDTO|null,event_cursor} |
| POST /cashier/shifts | Cashier; OpenShiftInput |201 data:{shift:ShiftDTO,event_cursor} |
| POST /cashier/shifts/{id}/close | Cashier; CloseShiftInput |200 data:{shift:ShiftDTO,event_cursor} |
| GET /cashier/tables/{id}/qr | Cashier |200 data:{table_number:int,url:string}; no-store, audit |
| GET /guest/bills/{id}/events | Guest membership; after string optional |200 text/event-stream; scoped bill |
| GET /guest/menu/events | Guest; after optional |200 stream menu/shift |
| GET /kitchen/events | Barista; after optional |200 stream kitchen/menu/shift |
| GET /cashier/events | Cashier; after optional |200 stream cashier/menu/shift |
| GET /guest/recommendations | Guest, P2 |200 data:{items:[{item:GuestMenuItemDTO,reason:time_of_day/bestseller/seed_order}],event_cursor} max3 |
| GET /cashier/shifts/{id}/report | Cashier, P2 |200 data:{shift:ShiftDTO,revenue_vnd,paid_bill_count:int,top_items:[{menu_item_id,name,quantity:int}],as_of,event_cursor} max5 |

Queue cursor opaque base64url JSON `{created_at,id,status,table_id}` với schema validation; không có secrets. Cursor chỉ dùng lại với filter khớp, sai422 INVALID_CURSOR. Seek tuple `(created_at,id)>cursor`, order FIFO tăng; không offset. Queue live thay đổi nên refetch page đầu khi có event, không giả định pagination là snapshot bất biến. Menu version là event_clock watermark string (coarse invalidation), không menu item version.

## 4. DTO projections

| DTO | Fields |
| --- | --- |
| StaffDTO | id,username,role barista/cashier; không password hash/session ID/token |
| CategoryDTO | id,name,sort_order |
| GuestMenuItemDTO | id,category_id,name,description,price_vnd,available,version,sort_order; chỉ active |
| KitchenMenuItemDTO | id,category_id,name,available,version,sort_order; không description/price |
| GuestItemDTO | id,menu_item_id,name (snapshot),unit_price_vnd,quantity,note,status,version,is_mine,can_cancel |
| CashierItemDTO | id,menu_item_id,name,unit_price_vnd,quantity,note,status,version; không guest identity/is_mine/can_cancel |
| KitchenItemDTO | id,menu_item_id,name,quantity,note,status,version,started_at nullable; không giá/total/payment/creator |
| GuestOrderDTO | id,order_number,created_at,items:GuestItemDTO[] |
| CashierOrderDTO | id,order_number,created_at,items:CashierItemDTO[] |
| KitchenTicketDTO | id (order ID),order_number,created_at,table:{id,number,label},bill_id,items:KitchenItemDTO[] chỉ waiting/preparing |
| BillSummaryDTO | id,table_number,status,version,total_vnd,can_pay; total derived khi open/frozen khi paid |
| PaidBillSummaryDTO | id,status paid,version,total_vnd |
| BillDTO | id,table_id,table_number,status,version,opened_at,paid_at nullable,total_vnd,can_pay,orders (projection theo role),payment nullable,event_cursor |
| PaymentDTO | id,bill_id,shift_id,amount_vnd,method cash,paid_at; không cashier credentials/guest identity |
| CashierTableDTO | id,number,label,status free/serving/ready_to_pay,bill_id nullable,total_vnd,version nullable,can_pay; no bill thì total "0",can_pay false |
| ShiftDTO | id,status,opened_at,closed_at nullable,version; không cần trả opened_by/closed_by trong MVP |

Guest BillDTO payment chỉ PaymentDTO, không staff identity. Bill can_pay là điều kiện nghiệp vụ, không cấp quyền thanh toán cho guest. is_mine dựa session ID ở server, can_cancel=is_mine AND bill.open AND item.waiting. Kitchen không reuse BillDTO rồi xóa fields tùy tiện: schema riêng và projection tests.

## 5. Lỗi cố định

| HTTP/code | Khi nào / details |
| --- | --- |
|401 SESSION_EXPIRED / INVALID_CREDENTIALS | Session mất/hết hạn; login generic không lộ username |
|403 FORBIDDEN / CSRF_INVALID / ORIGIN_INVALID | Sai role, CSRF hoặc Origin; không retry |
|404 NOT_FOUND | Token sai/disabled, resource không có hoặc sai guest scope; generic |
|409 TABLE_VISIT_CHANGED | expected null/UUID mở không còn khớp; details current_bill_id nullable, chỉ khi QR hợp lệ; không trả nội dung bill |
|409 BILL_CLOSED | Expected bill paid, payment lại key khác; details bill_id/status nếu có quyền |
|409 SHIFT_CLOSED / SHIFT_ALREADY_OPEN / OPEN_BILLS_EXIST | Không có ca; mở trùng; close còn bill (details open_bill_count) |
|409 ITEM_UNAVAILABLE / PRICE_CHANGED | details items:[{menu_item_id,reason}], PRICE_CHANGED thêm current_unit_price_vnd; không partial order |
|409 VERSION_CONFLICT / STATE_CONFLICT / INVALID_TRANSITION | Stale expected (details current_version), state không hủy được, transition không hợp lệ; version kiểm trước state |
|409 ITEMS_NOT_DONE / AMOUNT_CHANGED | details unfinished_count hoặc current_total_vnd; server kiểm sau bill version |
|409 IDEMPOTENCY_CONFLICT | Cùng principal/operation/key khác payload hash; không đổi DB |
|422 VALIDATION_ERROR / BILL_LIMIT_EXCEEDED / INVALID_CURSOR | Field errors paths không echo password/token/note; tổng>1e9 hoặc cursor sai |
|429 RATE_LIMITED | Retry-After số giây; không tạo business rows |
|503 RETRYABLE_CONFLICT / SERVICE_UNAVAILABLE | Lock/deadlock rollback hoặc DB/config dependency không sẵn; request_id |
|413 PAYLOAD_TOO_LARGE / 500 INTERNAL_ERROR | Body>64KiB hoặc lỗi bất ngờ, không stack/SQL |

Món không tồn tại/inactive trong submit trả422 VALIDATION_ERROR theo item path; disabled table404. Giá và availability cùng sai ưu tiên ITEM_UNAVAILABLE rồi PRICE_CHANGED. Membership/scope sai404 trước state để tránh IDOR. Không dành HTTP200 cho mutation thất bại.

## 6. Examples bắt buộc ở C01

Tạo fixture IDs ổn định trong `contracts/examples/`, không raw credentials/QR thật. Phải có: bootstrap null/open; join success/conflict; order initial/add/replay/soldout/price; own/other item bill; kitchen projection; cancelled zero bill; payment95.000 và0; shift open/close conflict; each409/error envelope; SSE business/checkpoint/reset/session_expired; empty queue/menu/report. OpenAPI3.1 schema strict, nullability rõ; generated TypeScript + Pydantic schemas hoặc generated DTO layer có một nguồn chuẩn. FastAPI `/openapi.json` phải được normalize so sánh canonical paths/methods/status/schema/security; không giữ hai schema độc lập chỉnh tay. SSE được mô tả text/event-stream và examples framing, JSON schemas riêng cho event data.

C01 done khi tất cả examples validate, role response fields khớp, route inventory đủ27 endpoints nghiệp vụ bên trên (health riêng), generated types tạo được, ghi CONTRACT-1 revision.
