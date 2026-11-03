# F10 — Xuất QR riêng từng bàn

P0; tables service. F01/F02/seed, [schema](../data-model.md), [API](../api-design.md). Reuse UI QRCodeSVG/export pattern từ source MIT pin trong PLAN mục9.4; không port Supabase/auth của nguồn.

## Quyền, input và bảo mật

Chỉ cashier GET /cashier/tables/{id}/qr, UUID table enabled. Response table_number,url; URL dựng từ PUBLIC_BASE_URL allowlisted config + `/t/{raw_token}`. Không lấy Host header; no-store/no analytics. Chỉ demo tables1/3 seed, không thêm bàn mới qua UI. Khách/barista403; missing/disabled404; cấu hình key/base URL thiếu hoặc decrypt lỗi503 SERVICE_UNAVAILABLE generic, không raw ciphertext/secret.

## Thuật toán và storage

1. Seed tạo token256-bit một lần/bàn, SHA256 lookup + authenticated encryption ciphertext có key_id/nonce/tag. Rerun seed không rotate; QR vẫn đúng sau restart.
2. Cashier mở `/staff/cashier/qr`, lấy danh sách tables rồi GET QR từng table ID. Service auth/role → enabled lookup → decrypt với QR_ENCRYPTION_KEY đúng key_id → đối chiếu hash raw token với hash DB → dựng URL.
3. Ghi audit qr.export/access với cashier session/table ID/request_id, không URL/token/ciphertext; transaction audit commit trước trả200. GET nhạy cảm này là ngoại lệ có access audit, không business state mutation/key/CSRF; exact same-origin credentials và no-store. GET không tạo/rotate token.
4. FE TableQrCard render QRCodeSVG ref riêng từng card, caption “Bàn 1/Bàn 3”, copy link, download PNG qua SVG→canvas; SVG fallback nếu PNG lỗi. Filename table-1.png/table-3.png; không ảnh dùng chung ref gây tải nhầm QR.

## Lỗi, vận hành và UI

Mất key không regenerate âm thầm:503 và thông báo khôi phục key backup; explicit rotate/in lại QR là maintenance riêng nếu được giao. URL localhost chỉ dành local; public demo phải base HTTPS thật và seed token giữ nguyên, endpoint URL đổi theo env. Không lưu QR URL trong context/public TXT/logs; file account/QR thật chỉ output local ignored theo DEMO.txt. Loading từng card/error retry, nút export disabled nếu chưa URL; copy thành công feedback, camera scan là gate thực tế.

## Acceptance/test và file triển khai

| Setup / hành động | Expected response / DB |
| --- | --- |
| Cashier export1/3 |200 hai URL khác token, resolve đúng table, không bill/order mới |
| Restart/seed hai lần/export lại |Token/QR không đổi; table/user/menu không duplicate |
| PUBLIC_BASE_URL thay local→public |URL cùng token khác base, không hardcode localhost |
| Sai/mất key hoặc hash mismatch |503 generic; không rotate token, không lộ ciphertext |
| Barista/guest GET QR |403, không token trong response/log |
| Export PNG/SVG từng card + scan |Filename/caption/table khớp; bootstrap đúng1/3 |

Unit URL builder/token hash/encryption roundtrip/wrong key; integration authorization/no-store/audit/seed idempotency; FE independent refs/fallback; E2E decode exported QR thật. Files security/qr.py, services/tables.py, api/cashier.py, seed CLI; FE TableQrCard. Không cần dependency scanner mới cho design; thư viện crypto/QR lock tại S01, C01 trước code.
