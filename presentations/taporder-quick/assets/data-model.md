# Mô hình dữ liệu PostgreSQL

DESIGN-1; [glossary](README.md), [transaction protocol](technical-design.md). Đây là đặc tả migration, chưa có migration thực thi.

## 1. Quy ước chung

UUID PK server tạo trừ nơi ghi khác. `timestamptz` UTC; `now()` DB là default created_at; version int default1 CHECK>0, tăng đúng một mỗi mutation của aggregate. `?` là nullable, còn lại NOT NULL. Default chỉ có khi ghi rõ. FK dùng RESTRICT, không cascade lịch sử; không hard-delete business/audit rows. Boolean phải true/false. Dùng text+CHECK cho enum để migration rõ và không nhận trạng thái tự do. Tiền BIGINT, không float; API decimal string canonical, không dấu/phần thập phân/leading zero trừ "0".

## 2. Schema chi tiết

| Bảng | Cột (ngoài PK id UUID nếu không ghi khác) | Constraint và index |
| --- | --- | --- |
| tables | number int; label varchar60; qr_token_hash bytea; qr_token_encrypted text; enabled bool default true; created_at | UNIQUE number CHECK>0; UNIQUE hash; hash SHA256 length32; ciphertext gồm key_id/nonce/tag; sort number |
| staff_users | username varchar80; password_hash text; role text; active bool default true; created_at | UNIQUE username lowercase canonical; CHECK role IN barista,cashier; username seed ASCII, không auto tạo user qua API |
| sessions | token_hash bytea; kind text; staff_user_id UUID?; csrf_hash bytea; created_at; expires_at; revoked_at? | UNIQUE token_hash length32; kind guest/staff, guest FK null/staff FK not null; expires_at>created_at; FK staff; index expiry; không xóa row còn FK business |
| preauth_sessions | token_hash bytea PK (không UUID id); csrf_hash bytea; created_at; expires_at; consumed_at? | TTL10 phút; token/CSRF length32; consumed_at chỉ set sau login thành công; cleanup row hết hạn không FK |
| shift_guard | id smallint PK (không UUID), version int default1 | CHECK id=1; đúng một row seed trong migration, không DELETE; khóa hàng này trước shifts |
| shifts | status text; opened_by UUID FK staff; opened_at default now; closed_by UUID? FK staff; closed_at?; version | CHECK open/closed; open thì cả closed fields null, closed thì cả hai not null và closed_at>=opened_at; UNIQUE constant expression `(1)` WHERE status='open'; index opened_at,id |
| bills | table_id UUID FK; shift_id UUID FK; status text default open; version; opened_at default now; paid_at?; total_vnd BIGINT? | CHECK open: paid_at/total null; paid: hai trường nonnull, total0..1e9, paid_at>=opened_at; UNIQUE table_id WHERE status='open'; index shift_id,status; index table_id,opened_at,id |
| bill_memberships | bill_id UUID FK + guest_session_id UUID FK composite PK (không id); joined_at default now | index guest_session_id,bill_id; service chỉ nhận guest kind; không tự cấp quyền qua số bàn |
| menu_categories | name varchar80; sort_order int default0; recommendation_bucket text | UNIQUE name; bucket coffee/tea/other; index sort_order,id |
| menu_items | category_id UUID FK; name varchar120; description varchar500 default empty; price_vnd BIGINT; available bool default true; active bool default true; sort_order int default0; version; created_at | price>0 AND<=1e7; index category_id,active,sort_order,id; không sửa snapshots khi thay availability |
| orders | bill_id UUID FK; created_by_session_id UUID FK; created_at default now; order_number BIGINT GENERATED identity | UNIQUE order_number; index bill_id,created_at,id; index created_at,id cho FIFO; số thứ tự có gap hợp lệ khi rollback |
| order_items | order_id UUID FK; menu_item_id UUID FK; name_snapshot varchar120; unit_price_vnd BIGINT; quantity int; note varchar250 default empty; status text default waiting; version; started_at?; done_at?; cancelled_at? | price1..1e7; qty1..20; status CHECK; index order_id,id; index status,order_id; time checks bên dưới |
| payments | bill_id UUID FK UNIQUE; shift_id UUID FK; cashier_id UUID FK staff; method text; amount_vnd BIGINT; paid_at default now | method=cash, amount0..1e9; index shift_id,paid_at,id; service kiểm shift==bill.shift_id và staff cashier |
| idempotency_records | principal_kind text; principal_id UUID FK sessions; operation varchar160; key UUID; payload_hash bytea; response_status smallint?; response_json jsonb?; created_at; expires_at | UNIQUE principal_kind,principal_id,operation,key; hash length32; response fields cùng null/cùng nonnull; success status200/201; index expires_at; row chưa complete chỉ tồn tại trong transaction chưa commit |
| event_clock | id smallint PK (không UUID); last_id BIGINT default0; retained_after BIGINT default0 | CHECK id=1; 0<=retained_after<=last_id; singleton row tạo migration; không dùng identity cho commit cursor |
| domain_events | id BIGINT PK cấp bởi event_clock; bill_id UUID? FK; audience text; event_type varchar60; resource_type varchar40; resource_id UUID; aggregate_version int; created_at | audience guest/kitchen/cashier/menu; guest bắt buộc bill_id; version>0; index audience,id và bill_id,id; payload whitelist, không giá/note/QR |
| audit_events | id UUID; request_id varchar80; principal_kind text; principal_id UUID? FK sessions; action varchar80; resource_type varchar40; resource_id UUID; before_state jsonb?; after_state jsonb?; created_at | index resource_type,resource_id,created_at; index request_id; chỉ state/version/amount nếu cần đối soát cashier, không password/cookie/note/QR |

Các hash dùng bytea; kiểm độ dài tránh lưu raw token nhầm chỗ. FK không tự bảo đảm role/kind hoặc bảng thuộc ca: service có test liên bảng. Cross-row SUM/one-payment consistency không giả vờ là CHECK SQL: cùng service transaction + unique/FK + integration assertions; runtime không có đường ghi DB tùy ý ngoài service.

## 3. State constraints và tiền

Order item time CHECK: waiting thì ba timestamp null; preparing thì started_at nonnull, done/cancel null; done thì started/done nonnull, done>=started, cancelled null; cancelled thì cancelled nonnull, started/done null. Cancelled chỉ từ waiting. Quan hệ timestamp order created_at được kiểm trong service khi mutation, không dùng CHECK truy vấn bảng khác.

`line_total = unit_price_vnd * quantity` (max200.000.000); bill mở SUM dòng status!=cancelled qua orders; total<=1.000.000.000. Max50 dòng/order ở service. Không lưu line total riêng. Bill paid lưu total_vnd frozen, payment.amount phải bằng; không sửa order/items của paid bill. Bill toàn cancelled tổng0 vẫn có một payment0. Snapshot name/price bất biến sau insert; note cũng không có endpoint sửa.

Bill version tăng một lần mỗi submit/cancel/status/payment thành công; item version tăng khi cancel/status, menu version tăng availability, shift version tăng khi close. Tạo bill/order/items bắt đầu1; submit đầu để bill version1, các submit sau +1. Availability không tăng bill version. Join/read/replay không tăng version. `shift_guard.version` tăng khi open/close, chỉ phục vụ vận hành nội bộ, không thay shift version.

## 4. Truy vấn chuẩn và index

- Resolve QR: hash token → tables unique index, enabled=true; không lookup number do client cung cấp.
- Bill snapshot: scope membership trước → bill + orders sort created_at,id + items sort id + payment; aggregate bằng snapshot price, không JOIN menu.price để tính tiền.
- Queue: orders JOIN bills open, EXISTS items waiting/preparing; filter status/table nếu có; sort orders.created_at,id; paginate **orders**, sau đó hydrate active items của đúng order IDs, không LIMIT joined rows làm mất dòng. Index orders(created_at,id), items(status,order_id); EXPLAIN trên workload demo ở implementation.
- Cashier tables: tables LEFT JOIN bill open; total derived, no bill → free/total0/version null; can_pay nếu bill có order, ca open, không waiting/preparing.
- Report: payments WHERE shift_id; SUM/COUNT không join items để tránh nhân doanh thu. Top items query riêng JOIN bills paid + orders/items không cancelled và payments.shift_id, group menu_item_id; tên display từ snapshot mới nhất trong phạm vi, tie created_at/id.
- SSE: audience filter và guest bill scope, id>cursor ORDER BY id LIMIT100; đọc watermark event_clock cùng snapshot để không bỏ cursor. Report/menu snapshot cũng có cursor dù chưa dùng SSE.

## 5. Seed, retention và migration

Migration tạo singleton guard/clock trước app; seed đúng tables1/3, ba category buckets/ít nhất12 món (cà phê sữa30000, trà đào35000), users barista.demo/cashier.demo Argon2 từ env. Upsert theo natural key; không thay password/QR/ciphertext mỗi lần chạy, không tạo shift/bill/order/payment. Password rotate phải là thao tác explicit ngoài UI. Tokens random256-bit; authenticated encryption QR có key_id, key env; hash lookup SHA256.

Sessions hết hạn: clear/revoke token material khi hết hạn và không còn cần replay, giữ row/ID cho FK/audit; không DELETE sessions còn business refs. Giữ financial rows/audit trong suốt demo. Maintenance explicit dọn idempotency/events tối thiểu24h; event prune chỉ prefix committed, khóa event_clock, cập nhật retained_after nguyên tử. Cursor<retained_after phải reset; không reset clock về0 sau cleanup. Dọn preauth hết hạn độc lập. Không chạy cleanup từ GET/stream loop.

Migration/test DB riêng; upgrade từ DB sạch + seed hai lần phải giữ IDs/QR và không thêm business rows. Khi có migration thứ hai, test upgrade từ revision trước. Không tự downgrade destructive schema; backup và restore thử DB riêng trước release có thay schema. API ready503 nếu DB revision chưa khớp image.
