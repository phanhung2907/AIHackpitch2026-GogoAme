# Deploy frontend công khai, backend chạy local

Mục tiêu: người khác mở được UI TapOrder từ máy họ, bấm thật, và request đi về
FastAPI đang chạy trên máy của nhóm.

## 0. Trạng thái và mâu thuẫn với PLAN

- [plans/product-plan.md](../plans/product-plan.md) §8.1 chọn **cùng-origin**: một container chứa React build +
  FastAPI, một domain HTTPS cho cả ba UI, cookie và SSE. Bảng đánh đổi ở §8.1 xếp
  "Vercel/Netlify chỉ FE" vào **không chọn cho demo đầu** vì tách origin thêm
  cookie/proxy. Yêu cầu trong tài liệu này đúng là trường hợp đó, nên đây là
  **lệch PLAN có chủ ý**, phải ghi vào `context/HANDOFF.md` khi thực hiện.
- Backend chưa tồn tại trong repo. Mọi lệnh phía backend dưới đây là interface
  **dự kiến** theo §8.2, chưa chạy được hôm nay.
- Frontend hiện tại chạy độc lập bằng mock (`VITE_USE_MOCK=1`). Nếu chỉ cần cho
  người khác xem UI và bấm thử, mục 1 là đủ và không cần backend.

## 0b. Lần chạy thật đã thực hiện — 2026-11-03

Đã chạy phương án A bằng Cloudflare quick tunnel, không phải phương án B.

- `cloudflared` 2026.10.7 cài qua `winget install --id Cloudflare.cloudflared -e`.
- `frontend/vite.config.ts` đã có `host: true`, `strictPort: true` và
  `allowedHosts: ['.trycloudflare.com', '.ngrok-free.app']`, nên không phải truyền cờ khi chạy.
- Lệnh đã chạy: `cloudflared tunnel --url http://127.0.0.1:5173`, tunnel đăng ký qua QUIC ở `sin12`.
- URL cấp ra: `https://leader-weighted-africa-carroll.trycloudflare.com`.
- Kiểm chứng: `curl -sSL https://leader-weighted-africa-carroll.trycloudflare.com/t/t1`
  trả **200** trong 1,94 giây. Chưa mở thử từ thiết bị thứ hai.

Đây là **FE chạy mock**, backend chưa nối vào tunnel này, nên mỗi người truy cập có
dữ liệu riêng trong `localStorage` của họ. URL quick tunnel là tạm: tunnel chết thì
URL đổi, phải sinh lại và set lại `PUBLIC_BASE_URL` trước khi in QR.

Trước đó đã thử LAN cùng wifi và **thất bại**: wifi `FPT University Quy Nhon 3` chặn
thiết bị nói chuyện trực tiếp (client isolation), dù Vite đã bind mọi interface và
Windows Firewall có rule Allow cho `D:
odejs
ode.exe` ở profile Public. Hotspot
điện thoại `Xiaomi 14T` cho IP `10.232.251.127` và `curl` tới IP đó trả 200, nhưng
điện thoại khác vẫn không vào được, nên chuyển sang tunnel.

## 1. Chỉ cần người khác xem và bấm UI (mock, không backend)

Build tĩnh rồi đưa lên bất kỳ static host. Mỗi người xem có dữ liệu riêng trong
`localStorage` của họ.

```bash
cd frontend && VITE_USE_MOCK=1 npm run build
```

Deploy `frontend/dist` (Cloudflare Pages, Netlify, Vercel, GitHub Pages). Vì SPA
có deep link `/t/t1`, `/staff/...`, host phải rewrite mọi path về `index.html`:

| Host | Cấu hình |
| --- | --- |
| Cloudflare Pages / Netlify | file `frontend/public/_redirects` chứa `/*  /index.html  200` |
| Vercel | `vercel.json`: `{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }` |
| GitHub Pages | không có rewrite; phải dùng hash router hoặc copy `index.html` thành `404.html` |

Giới hạn phải nói trước với người xem: đây là mock trong browser của họ, hai
người **không** thấy order của nhau, nên không dùng được cho kịch bản demo hai
bàn của `DEMO.txt`. Muốn chung dữ liệu thì phải sang mục 2 hoặc 3.

## 2. Phương án A — khuyến nghị: một tunnel, cùng origin

Giữ đúng tinh thần §8.1: người ngoài chỉ thấy **một** domain HTTPS; domain đó
vừa trả SPA vừa proxy `/api` sang FastAPI local. Cookie, CSRF và SSE không phải
đổi gì.

```
Người dùng ──HTTPS──> tunnel (domain công khai)
                           │
                     máy của nhóm
                           ├── SPA (frontend/dist hoặc Vite dev)
                           └── /api ──> FastAPI 127.0.0.1:8000 ──> PostgreSQL Docker
```

### 2.1 Cách nhanh nhất hôm nay: Vite dev qua tunnel

`frontend/vite.config.ts` đã proxy `/api` sang `http://127.0.0.1:8000`, nên Vite
dev server chính là reverse proxy cùng-origin cần thiết.

1. Cho Vite nghe mọi interface và chấp nhận Host của tunnel. Thêm vào
   `vite.config.ts` → `server`:

   ```ts
   host: true,
   allowedHosts: ['.trycloudflare.com', '.ngrok-free.app'],
   ```

   Thiếu `allowedHosts`, Vite 5.4 trả `Blocked request. This host is not allowed.`

2. Chạy backend local (DB Docker + Uvicorn `127.0.0.1:8000`), rồi frontend ở chế
   độ live:

   ```bash
   cd frontend && VITE_USE_MOCK=0 npm run dev
   ```

3. Mở tunnel tới **cổng của Vite**, không phải cổng API:

   ```bash
   cloudflared tunnel --url http://127.0.0.1:5173
   ```

   hoặc `ngrok http 5173`. Lấy URL HTTPS in ra, ví dụ
   `https://abc-def.trycloudflare.com`.

Vite dev không phải cấu hình production (không nén, không cache header, HMR bật).
Chấp nhận được cho demo nội bộ; đừng gọi đây là deployment.

### 2.2 Bản sát production hơn: Caddy phục vụ dist + proxy

```bash
cd frontend && VITE_USE_MOCK=0 VITE_API_BASE=/api/v1 npm run build
```

`Caddyfile` ở gốc repo:

```
:8080 {
	handle /api/* {
		reverse_proxy 127.0.0.1:8000
	}
	handle {
		root * frontend/dist
		try_files {path} /index.html
		file_server
	}
}
```

```bash
caddy run --config Caddyfile
cloudflared tunnel --url http://127.0.0.1:8080
```

SSE: Caddy `reverse_proxy` stream mặc định, nhưng vẫn phải kiểm `text/event-stream`
đi tới browser và heartbeat 15 giây không bị gom buffer (§8.6 dòng "Không live").

### 2.3 Env backend cho phương án A

| Biến | Giá trị | Vì sao |
| --- | --- | --- |
| `PUBLIC_BASE_URL` | `https://<domain-tunnel>` | QR phải là URL public, không `localhost`/LAN (§8.6) |
| `ALLOWED_ORIGINS` | `https://<domain-tunnel>` | Exact origin, không `*` |
| `ALLOWED_HOSTS` | `<domain-tunnel>`, `127.0.0.1` | Host guard vẫn cho health probe local |
| `COOKIE_SECURE` | `true` | Tunnel là HTTPS |
| `COOKIE_SAMESITE` | `lax` | Cùng-origin nên không cần `none` |
| `ENABLE_MOCKS` | `false` | §8.2 mục 4 |

Domain tunnel tạm đổi mỗi lần chạy lại, nên **sinh lại QR sau khi có domain** và
set lại `PUBLIC_BASE_URL` trước khi in QR.

## 3. Phương án B — FE trên Vercel/Pages, API qua tunnel riêng

Chỉ chọn khi bắt buộc phải có domain FE riêng. Lúc này FE và API **khác origin**,
và đây là nơi demo hay chết.

```
Người dùng ──> https://taporder.pages.dev   (FE tĩnh)
                   │ fetch cross-origin, kèm cookie
                   v
             https://api-xyz.trycloudflare.com  ──> FastAPI local ──> PostgreSQL
```

### 3.1 Phải sửa code frontend

`frontend/src/api/client.ts` hiện dùng `credentials: 'same-origin'`. Cross-origin
thì cookie session **không được gửi**, nên mọi request sau login trả 401. Phải
đổi thành:

```ts
credentials: 'include',
```

Và build với API base tuyệt đối:

```bash
cd frontend && VITE_USE_MOCK=0 VITE_API_BASE=https://api-xyz.trycloudflare.com/api/v1 npm run build
```

`VITE_*` nằm trong bundle công khai — chỉ để URL, tuyệt đối không để secret
(§8.2 mục 1).

### 3.2 Phải sửa cấu hình backend

| Biến / cấu hình | Giá trị | Ghi chú |
| --- | --- | --- |
| `ALLOWED_ORIGINS` | `https://taporder.pages.dev` | Exact, không wildcard; CORS phải bật `allow_credentials=True` |
| CORS methods/headers | `GET, POST, PATCH` + `Content-Type`, `X-CSRF-Token`, `Idempotency-Key` | Thiếu header là preflight fail |
| `COOKIE_SAMESITE` | `none` | `lax` không gửi cookie cross-site |
| `COOKIE_SECURE` | `true` | `SameSite=None` bắt buộc `Secure`, nên cả hai đầu phải HTTPS |
| `PUBLIC_BASE_URL` | `https://taporder.pages.dev` | QR trỏ về FE, không trỏ về API |

Hệ quả phải chấp nhận: `SameSite=None` nới bảo vệ CSRF ở tầng cookie, nên kiểm
tra `X-CSRF-Token` và exact `Origin` ở server trở thành bắt buộc, không được tắt
để "cho chạy" (§8.6 dòng "Login lặp/CSRF 403"). Safari/iOS chặn cookie
cross-site mạnh hơn: phải thử trên đúng điện thoại sẽ dùng demo, không suy từ
Chrome desktop.

Vì các rủi ro trên, nếu không có lý do bắt buộc thì dùng phương án A.

## 4. Cảnh báo bảo mật trước khi mở tunnel

Mở tunnel là đưa một dịch vụ đang chạy trên máy cá nhân ra Internet công khai.
Trước khi chạy, hãy xác nhận từng điểm sau, và chỉ bật tunnel trong thời gian demo.

- Tunnel **chỉ** trỏ tới cổng web (5173 hoặc 8080). Không tunnel cổng PostgreSQL
  5432, không mở public DB.
- URL tunnel tạm là bí mật yếu: ai có link đều vào được. Không đăng link ra kênh
  công khai, và tắt tunnel (`Ctrl+C`) ngay sau khi demo xong.
- Mật khẩu `barista.demo`/`cashier.demo` đang là mật khẩu demo. Khi mở ra Internet
  phải đặt `DEMO_BARISTA_PASSWORD`/`DEMO_CASHIER_PASSWORD` thành giá trị mạnh,
  đặt ở env phía server, không commit, không in vào log (`DEMO.txt`).
- QR là capability (quyết định D10): ai có link bàn đều gửi order được vào bàn đó.
  Trên Internet công khai, rủi ro này lớn hơn tại quán — chấp nhận cho demo và nói
  rõ khi pitch.
- Giữ rate limit theo §10.1 (login 5/phút/IP, order 10/phút/session). Không tắt
  CSRF, RBAC hay Origin check để sửa lỗi nhanh.
- Không đưa `.env`, `accounts.txt`, DSN hay token tunnel vào Git hoặc vào báo cáo.

## 5. Nghiệm thu — chỉ tick khi đã tự tay thấy

Chạy từ **máy khác** (hoặc điện thoại dùng mạng di động), không phải từ máy host:

1. Mở `https://<domain>/` → trang chủ hiện, không lỗi mixed content.
2. Mở `https://<domain>/t/t1` trực tiếp (deep link, không qua trang chủ) → ra menu
   bàn 1. Reload F5 vẫn ra menu, không 404.
3. Thu ngân đăng nhập → mở ca. Reload trang vẫn còn đăng nhập.
4. Hai máy khác nhau mở bàn 1 và bàn 3, mỗi bên gửi order.
5. Pha chế thấy **cả hai** bàn trong một hàng đợi → đổi trạng thái một món →
   máy khách thấy trạng thái mới trong vài giây.
6. Thu ngân thanh toán bàn 1 → bill `paid`, bàn về trống, đúng một payment.
7. Mở lại `/t/t1` → vào menu lượt mới, bill cũ không đổi.
8. Thu ngân mở `/staff/kitchen` → bị từ chối. Guest mở `/staff/cashier` → bị từ chối.
9. Restart API → order và payment vẫn còn (dữ liệu ở PostgreSQL, không ở memory).

Bước 4–5 là bằng chứng duy nhất cho thấy đã thoát khỏi mock: mock `localStorage`
không bao giờ cho hai máy thấy dữ liệu của nhau. Nếu bước 5 không đạt, nghĩa là
FE vẫn chạy mock (`VITE_USE_MOCK` chưa về `0`) — đừng báo là đã nối backend.

## 6. Chẩn đoán nhanh

| Hiện tượng | Kiểm theo thứ tự |
| --- | --- |
| `Blocked request. This host is not allowed` | `server.allowedHosts` trong `vite.config.ts` chưa có domain tunnel |
| Mở được trang chủ, `/t/t1` reload ra 404 | thiếu SPA fallback ở static host (mục 1) hoặc `try_files` ở Caddy |
| Đăng nhập xong request nào cũng 401 | cross-origin mà `credentials` vẫn là `same-origin`, hoặc cookie thiếu `SameSite=None; Secure` |
| Preflight OPTIONS fail | CORS thiếu `X-CSRF-Token` / `Idempotency-Key` trong allow headers |
| Hai máy không thấy order của nhau | FE còn `VITE_USE_MOCK=1`, hoặc `VITE_API_BASE` trỏ sai |
| Trạng thái món không tự cập nhật | polling/SSE bị buffer ở proxy; kiểm `text/event-stream`, tắt buffering/compression |
| QR quét ra `localhost` | `PUBLIC_BASE_URL` chưa đặt theo domain tunnel; sinh lại QR sau khi có domain |
| Mất hết order sau khi restart | đang chạy mock hoặc DB không có volume |

## 7. Việc này không thay thế gì

Đây là đường tạm cho demo, không phải deployment theo §8. Nó phụ thuộc máy của
nhóm còn bật, còn mạng và tunnel còn sống; không có TLS riêng, không có backup,
không có health gate hay rollback. Khi cần một bản chạy độc lập, làm theo runbook
Railway ở §8.2–§8.4 với một domain cùng-origin.
