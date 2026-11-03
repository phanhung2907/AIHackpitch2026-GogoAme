# TapOrder — hành trình sản phẩm từ A đến Z

DESIGN-1. Người mới có thể đọc trang này trước; chi tiết kỹ thuật ở [system design](system-design.md) và [12 feature designs](README.md). Đây là luồng cần triển khai, chưa phải bằng chứng app chạy. [Bản PNG tương thích trình xem](assets/product-flow.png) và [SVG để phóng to](assets/product-flow.svg) được render từ đúng khối Mermaid dưới đây; sửa nguồn thì render lại SVG.

## Câu chuyện sản phẩm

**A — Chuẩn bị:** người vận hành migrate/seed đúng hai bàn1/3 và hai tài khoản staff. Nhân viên đăng nhập, role server quyết định màn hình. Thu ngân mở ca và xuất QR; pha chế mở hàng đợi. Không có bill/order giả từ seed.

**B — Khách gọi món:** quét QR của bàn, hệ thống xác nhận đúng bàn và tạo phiên khách ẩn danh. Nếu bill đang mở, khách xác nhận tham gia; chưa có bill thì chỉ xem menu. Khách chọn món/quantity/note rồi gửi. Server kiểm ca, bàn, bill dự kiến, giá/còn hàng; sai giữ giỏ, không nhận một phần. Thành công mới lưu hóa đơn/lượt gọi/dòng chờ.

**C — Pha chế và khách theo dõi:** pha chế thấy ticket theo FIFO, bấm bắt đầu rồi xong từng dòng. Khách xem toàn bill và chỉ hủy dòng của mình còn chờ; tranh chấp với pha chế chỉ một thao tác thắng. Pha chế bật/tắt hết hàng tác động lượt gọi sau. SSE thông báo refetch; mất SSE có polling, không tự tạo lại order. Khách có thể gọi thêm cùng bill mở.

**D — Thu tiền:** thu ngân đọc tổng từ server, chỉ xác nhận tiền mặt khi mọi dòng xong/đã hủy. Tổng loại dòng hủy, bill toàn hủy vẫn payment0. Server lưu một payment và bill paid nguyên tử. Mất mạng lúc gửi lệnh phải thử lại cùng mã lệnh/đối soát trước khi gửi mới, không thu tiền lần hai.

**E — Lượt mới hoặc kết thúc:** tab cũ là biên nhận read-only. QR vẫn dùng được nhưng không tự tạo bill; khách xác nhận lượt mới rồi submit mới sinh bill khác. Thu ngân đối soát ca (báo cáo chi tiết P2), chỉ đóng khi hết bill mở, cuối cùng logout. Không sửa/mở lại bill đã thanh toán.

## Quy ước vẽ duy nhất

| Hình / tên | Ý nghĩa |
| --- | --- |
| Bo tròn `(["..."])` | Bắt đầu, kết thúc, dừng một nhánh |
| Chữ nhật `["Chủ thể<br/>Động từ + đối tượng"]` | Hành động của khách/nhân viên/hệ thống |
| Thoi `{"Hệ thống<br/>Câu hỏi?"}` | Quyết định; mọi nhánh có nhãn rõ |
| Trụ `[("PostgreSQL<br/>Dữ liệu được lưu")]` | Dữ liệu commit bền vững, không phải bộ nhớ UI |
| `-->` | Bước tiếp theo; nhãn “Sau đó…” chỉ thao tác ở request/thời điểm khác |

Bản vẽ lại bỏ subgraph lồng và nhãn HTML để tăng tương thích renderer; các giai đoạn vẫn phân biệt bằng mã A–E. Không dùng mũi tên hai chiều, nét đứt hoặc cùng hình cho nhiều nghĩa. Màu chỉ hỗ trợ: xanh dương hành động, cam quyết định, tím dữ liệu, xanh lá điểm đầu/cuối; in đen trắng vẫn đọc được. Tên hóa đơn=bill, lượt gọi=order, dòng món=order item đúng glossary. ID A01…E08 ổn định để trao đổi; nhãn có Fxx để tra đặc tả. Điểm bo tròn “Tiếp tục tại B01/B07” kết thúc nhánh hiện tại và chỉ rõ bước quay lại, tránh mũi tên kéo xuyên toàn trang. Một mũi tên không có nghĩa giữ HTTP/DB transaction xuyên suốt đến bước kế tiếp.

## Sơ đồ Mermaid A–Z

```mermaid
flowchart TD
  A01(["A01 - Bắt đầu phục vụ"])
  A02["A02 - Nhân viên đăng nhập đúng vai trò"]
  A03["A03 - Thu ngân mở ca và xuất QR bàn 1, bàn 3"]
  B01["B01 - Khách quét QR của bàn"]
  B02{"B02 - QR hợp lệ?"}
  B03(["B03 - QR sai: liên hệ thu ngân"])
  B04["B04 - Khách xác nhận bàn và lượt phục vụ"]
  B07["B07 - Khách chọn món, số lượng và ghi chú"]
  B08["B08 - Khách gửi lượt gọi"]
  B09{"B09 - Ca, phiên bàn, món và giá hợp lệ?"}
  B10["B10 - Giữ giỏ, hiển thị lỗi để khách sửa hoặc xác nhận lại"]
  B11[("B11 - PostgreSQL: lưu hóa đơn mở và lượt gọi nguyên tử")]
  C01["C01 - Pha chế xem các lượt gọi theo thứ tự nhận"]
  C02["C02 - Pha chế bấm Bắt đầu, sau đó bấm Xong"]
  C05[("C05 - PostgreSQL: lưu tiến độ từng dòng món")]
  C06["C06 - Khách xem hóa đơn và tiến độ cập nhật"]
  C07{"C07 - Khách muốn làm gì tiếp?"}
  C08{"C08 - Dòng của khách còn chờ và hóa đơn mở?"}
  C09[("C09 - PostgreSQL: hủy dòng và trừ khỏi tổng")]
  C10["C10 - Thông báo không thể hủy, tải lại trạng thái"]
  C11(["C11 - Gọi thêm: quay lại bước chọn món B07"])
  D01["D01 - Thu ngân mở hóa đơn và xem tổng tiền"]
  D02{"D02 - Mọi dòng đã xong hoặc đã hủy?"}
  D03["D03 - Chờ pha chế hoàn tất rồi tải lại hóa đơn"]
  D04["D04 - Thu ngân nhận tiền mặt và xác nhận số tiền"]
  D05{"D05 - Ca, hóa đơn và tổng tiền vẫn hợp lệ?"}
  D06["D06 - Tải lại hóa đơn, kiểm tra trước khi xác nhận lại"]
  D07[("D07 - PostgreSQL: lưu một thanh toán và đóng hóa đơn")]
  D08["D08 - Khách nhận biên nhận, bàn trở về rảnh"]
  E01{"E01 - Khách muốn gọi lượt mới?"}
  E02(["E02 - Lượt mới: quay lại bước quét QR B01"])
  E03(["E03 - Khách kết thúc, biên nhận cũ giữ nguyên"])
  E04["E04 - Cuối ca: thu ngân đối soát và yêu cầu đóng ca"]
  E05{"E05 - Còn hóa đơn mở?"}
  E06["E06 - Giữ ca mở, xử lý các hóa đơn còn lại"]
  E07[("E07 - PostgreSQL: đóng ca, giữ lịch sử")]
  E08(["E08 - Nhân viên đăng xuất, kết thúc phục vụ"])
  A01 --> A02
  A02 --> A03
  A03 --> B01
  B01 --> B02
  B02 -->|Không| B03
  B02 -->|Có| B04
  B04 --> B07
  B07 --> B08
  B08 --> B09
  B09 -->|Không| B10
  B10 -->|Sau khi sửa hoặc xác nhận lại| B07
  B09 -->|Có| B11
  B11 -->|Sau khi lưu thành công| C01
  B11 -->|Khách theo dõi ngay sau khi gửi| C06
  C01 --> C02
  C02 --> C05
  C05 --> C06
  C06 --> C07
  C07 -->|Gọi thêm| C11
  C07 -->|Hủy một dòng| C08
  C08 -->|Có, kiểm tra lại khi lưu| C09
  C08 -->|Không hoặc trạng thái vừa đổi| C10
  C09 --> C06
  C10 --> C06
  C07 -->|Thanh toán| D01
  D01 --> D02
  D02 -->|Không| D03
  D03 -->|Sau khi món hoàn tất| D01
  D02 -->|Có| D04
  D04 --> D05
  D05 -->|Không| D06
  D06 --> D01
  D05 -->|Có| D07
  D07 --> D08
  D08 -->|Khách chọn| E01
  E01 -->|Có| E02
  E01 -->|Không| E03
  D08 -->|Thu ngân tiếp tục phục vụ, cuối ca đối soát| E04
  E04 --> E05
  E05 -->|Có| E06
  E06 -->|Xử lý xong rồi thử đóng ca| E04
  E05 -->|Không| E07
  E07 --> E08
  classDef action fill:#e8f1ff,stroke:#2563eb,color:#102040
  classDef decision fill:#fff0d8,stroke:#d97706,color:#482500
  classDef storage fill:#f1eaff,stroke:#7c3aed,color:#301050
  classDef terminal fill:#e6f6ee,stroke:#16803c,color:#103020
  class A02,A03,B01,B04,B07,B08,B10,C01,C02,C06,C10,D01,D03,D04,D06,D08,E04,E06 action
  class B02,B09,C07,C08,D02,D05,E01,E05 decision
  class B11,C05,C09,D07,E07 storage
  class A01,B03,C11,E02,E03,E08 terminal
```

## Các nhánh kỹ thuật dùng chung không lặp đầy sơ đồ

- **Lỗi nghiệp vụ trước commit:** không đổi bill/order/payment; sửa input/đọc lại state rồi chủ động tạo command mới.409 giữ giỏ, không xóa món âm thầm.
- **Mất mạng chưa biết server đã lưu hay chưa:** giữ nguyên payload+Idempotency-Key, thử lại cùng key hoặc GET đối soát. Không đi nhánh B10 như đã chắc chắn reject. Business success replay không tạo thêm order/payment.
- **Phiên hết hạn/quyền sai:**401 khôi phục đúng phiên,403 không tự retry,404 không tiết lộ bill bàn khác. Khôi phục session mới không lấy lại quyền hủy dòng của session cũ.
- **SSE trễ/mất:** snapshot HTTP mới là nguồn chuẩn; polling/reconnect không gửi mutation. F09 có cursor/reset/session expiry chi tiết.
- **Pha chế bấm Xong:** là request riêng sau Bắt đầu, phải preparing+version đúng, lock/recheck như start; không waiting→done tự động. C05 tóm hai lần lưu để giữ sơ đồ mức nghiệp vụ.
- **Hai thao tác cùng lúc:** cancel/start, submit/pay, close/create được khóa theo technical design; chỉ kết quả đã commit hiện là thành công. Không vẽ mũi tên như cả hai thắng.

## Traceability

| Giai đoạn | Feature | Acceptance trọng tâm |
| --- | --- | --- |
| A | F02/F08/F10 | Đúng role, đúng ca, đúng hai QR, không seed order giả |
| B | F01/F03/F11 | Đúng bàn, không bill khi browse, submit atomic, P2 gợi ý optional |
| C | F04/F05/F06/F09 | FIFO, state hợp lệ, own waiting cancel, realtime đúng scope |
| D | F07/F08/F09 | Tổng server, payment unique, paid terminal, replay an toàn |
| E | F02/F07/F08/F12 | Lượt mới ID mới, receipt bất biến, hết bill mới close, report paid-only |
