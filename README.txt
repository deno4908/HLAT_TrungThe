BÀI NỘP CHỦ ĐỀ 34 – D18CNPM1
Plugin QGIS giám sát vi phạm hành lang an toàn lưới điện trung thế

MỞ NHANH
1. Chạy Mo_Demo_QGIS.bat để mở project demo bằng profile QGIS chude34 riêng.
   Script tìm QGIS trong Program Files, cài ZIP vào profile dành cho bài tập và bật plugin.
2. Hoặc mở QGIS → Plugins → Manage and Install Plugins → Install from ZIP,
   chọn hlat_trungthe_34.zip (không chọn ZIP toàn bộ bài nộp).
3. Mở demo/ChuDe34_BacNinh.qgz. Bản đồ, lớp đầu vào, kết quả và hai Print Layout đã có sẵn.
4. Mở plugin từ biểu tượng cột điện hoặc menu Plugins → HLAT Trung thế.
5. Muốn tính lại: bấm Nạp dữ liệu Bắc Ninh…, chọn demo/data; chọn tên .gpkg mới và chạy.

THÀNH PHẦN
- hlat_trungthe_34.zip: plugin cài trực tiếp vào QGIS 3.44.
- plugin/hlat_trungthe_34/: mã nguồn plugin và template môn học.
- demo/data/dau_vao.gpkg: bản sao ba lớp đầu vào, có đủ thuộc tính nguồn.
- demo/ket_qua/: GeoPackage, danh mục CSV, thống kê CSV, nhật ký và cấu hình JSON.
- demo/ChuDe34_BacNinh.qgz: project dùng đường dẫn tương đối.
- demo/BanDo_HLAT_TrungThe.pdf: bản đồ tổng quan và chi tiết A3.
- demo/HLAT34_A3.qpt: template đã điều chỉnh từ BanDoBacNinh.qpt.
- demo/styles/: ba style QML đầu vào từ bộ mẫu môn học.
- demo/web/: bản đồ HTML tương tác; chạy MoBanDoWeb.bat để xem qua HTTP cục bộ.
- tai_lieu/: báo cáo/hướng dẫn DOCX và PDF, 17 slide PPTX/PDF, kịch bản trình bày.
- tests/, kiem_thu/: mã kiểm thử và bằng chứng chạy thực tế.
- scripts/: công cụ tái tạo demo, tài liệu, PDF và đóng gói.
- SHA256.json: mã kiểm tra các tệp bàn giao.

THAM SỐ VÀ KẾT QUẢ THAM CHIẾU
Đường dây nổi; Nhà và Khối nhà; 8 vùng Bắc Ninh; EPSG:32648.
Khoảng cách mỗi phía: 35 kV = 4 m; 22 kV = 3 m; cấp còn lại = 2 m, theo ví dụ trong đề.
3.121 đường hợp lệ, bỏ 39 đường suy biến; 1.184 nhà/khối nhà; 42.425,06 m² giao hành lang.
Mã nhà có thể trùng; source_fid là khóa đối chiếu. Chỉ tính diện tích phần giao 2D.

BẢN ĐỒ WEB
Link bản mẫu đã triển khai (quyền riêng tư của chủ sở hữu):
https://bac-ninh-hlat34-d18cnpm1.cuppedridge7.chatgpt.site
Chi tiết trạng thái và quyền truy cập: tai_lieu/ThongTin_Web.txt.
Plugin có nút Xuất bản đồ web… sau khi phân tích. Thư mục xuất chứa HTML, JavaScript,
Leaflet 1.9.4 và dữ liệu đã chuyển sang WGS84. Kéo/zoom, bật tắt lớp, chọn vùng,
tìm FID hoặc mã nhà, nhấp xem thuộc tính và bảng thống kê.
Nhấp nhà để truy vết đường dây liên quan (điện áp, khoảng cách, diện tích giao); nhấp đường để xem vị trí.
Khi zoom từ 16, nhấp nhà trên bản đồ để nhận diện từ toàn bộ nhà nguồn, kể cả nhà không thuộc HLAT hiện tại.
Ô tìm kiếm có phạm vi Nhà vi phạm hoặc Toàn bộ nhà nguồn.
Danh mục / So sánh cho nhập khoảng cách A/B và tính lại, hiển thị số nhà/diện tích tăng giảm cùng các nhà mới.
Bộ lọc vùng và điện áp cập nhật đồng bộ bản đồ, danh mục và thống kê của cả A/B; tải được CSV.
Kết quả mặc định từ QGIS; các phương án và bộ lọc mới dùng GEOS-WASM tính trên CRS mét, không đo bằng độ.
Toàn bộ 201.462 Nhà/Khối nhà đầu vào được xuất trong source/, không chỉ các nhà vi phạm ban đầu.
Web Worker cần HTTP/HTTPS. Nền OpenStreetMap cần Internet. Khoảng cách nhập từ 0,001–10.000 m mỗi phía.
Công cụ GIS: vẽ đường/đa giác để đo mét/m²; khoanh vùng để giới hạn phép tính, thống kê, danh mục và cả A/B.
Nhấp các đỉnh rồi Kết thúc vẽ; Enter kết thúc, Backspace lùi điểm, Esc hủy. Bỏ vùng khoanh giữ các bộ lọc khác.
Xuất GeoJSON cho lớp đang lọc; Lưu/Mở phiên JSON giữ khung nhìn, A/B, phép đo và vùng truy vấn.
Đến tọa độ sử dụng vĩ độ/kinh độ WGS84. Chọn Tất cả vùng quản lý để bỏ lọc vùng.
Để có link, đưa toàn bộ thư mục web lên hosting tĩnh; không chỉ tải riêng index.html.
Nếu mở index.html qua file://, nền trắng được dùng; máy chủ HTTP/HTTPS hỗ trợ nền OSM.

TRƯỚC KHI NỘP
Điền tên nhóm, giảng viên, họ tên/MSSV và phân công thực tế trong DOCX/PPTX.
Nhóm có 5 người bỏ dòng thành viên thứ 6; bảng phân công hiện là phương án để nhóm cập nhật.
Các file dữ liệu và slide bài giảng gốc trong thư mục GIS không bị sửa.

TÁI TẠO / KIỂM TRA
Chạy Python đi kèm QGIS cho tests/test_analysis.py, tests/check_native.py,
scripts/build_demo.py và scripts/prepare_web.py. Sửa đường dẫn QGIS nếu máy cài khác.
Tạo DOCX/PPTX: Python riêng có python-docx, python-pptx, Pillow.
Xuất PDF tài liệu: Word và PowerPoint cùng pywin32. Các phụ thuộc này không cần cho plugin.
Kiểm tra web: Python riêng có playwright và Microsoft Edge.

NGUỒN THAM KHẢO
BaiTapNhom-HTTTKG-D18CNPM1.pdf trang 12; Slide chương 6.2, 7 và bài 5.2.
Bo du lieu thuc hanh QGIS 2026: dữ liệu, QML, project mẫu và BanDoBacNinh.qpt.
Leaflet: https://leafletjs.com/reference-1.9.4.html
OpenStreetMap tiles: https://operations.osmfoundation.org/policies/tiles/
