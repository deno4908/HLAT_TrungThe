"""Tạo báo cáo và 14 slide từ kết quả thực tế. Dùng Python riêng, không sửa Python QGIS."""
import csv
import json
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Inches, Pt as PptPt
from pptx.dml.color import RGBColor as PptColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tai_lieu"; OUT.mkdir(exist_ok=True)
ASSETS = ROOT / "assets"
info = json.loads((ROOT / "demo/ket_qua/hlat_bac_ninh_thong_tin.json").read_text(encoding="utf-8"))
metrics = info["metrics"]
with (ROOT / "demo/ket_qua/hlat_bac_ninh_thong_ke.csv").open(encoding="utf-8-sig", newline="") as f:
    zone_rows = list(csv.DictReader(f))


def number(value, digits=2):
    return (f"{float(value):,.{digits}f}").replace(",", "_").replace(".", ",").replace("_", ".")


doc = Document()
sec = doc.sections[0]; sec.top_margin=Cm(1.8); sec.bottom_margin=Cm(1.8); sec.left_margin=Cm(2.3); sec.right_margin=Cm(1.8)
sec.page_height=Cm(29.7); sec.page_width=Cm(21)
for name in ("Normal","Body Text","List Bullet","List Number"):
    style=doc.styles[name]; style.font.name="Times New Roman"; style.font.size=Pt(12)
    style.paragraph_format.space_after=Pt(6); style.paragraph_format.line_spacing=1.12
for name,size in (("Title",20),("Heading 1",15),("Heading 2",13)):
    doc.styles[name].font.name="Times New Roman"; doc.styles[name].font.size=Pt(size); doc.styles[name].font.color.rgb=RGBColor(0,0,0)
footer=sec.footer.paragraphs[0]; footer.alignment=2
footer.add_run("D18CNPM1 – Chủ đề 34  |  Trang ")
field=OxmlElement("w:fldSimple"); field.set(qn("w:instr"),"PAGE"); footer._p.append(field)


def paragraph(text, style=None):
    return doc.add_paragraph(text,style)


def heading(text): doc.add_heading(text,1)
def page(text): doc.add_page_break(); heading(text)
def bullets(items):
    for text in items: paragraph(text,"List Bullet")
def table(headers, rows):
    t=doc.add_table(rows=1, cols=len(headers)); t.style="Table Grid"
    for cell,text in zip(t.rows[0].cells,headers):
        cell.text=str(text)
        for run in cell.paragraphs[0].runs:run.bold=True
    for row in rows:
        for cell,text in zip(t.add_row().cells,row):cell.text=str(text)
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after=Pt(3)
                for run in p.runs:run.font.size=Pt(10.5)
    return t
def picture(filename, caption, width=16.5):
    doc.add_picture(str(ASSETS/filename),width=Cm(width))
    p=paragraph(caption); p.alignment=1
    for run in p.runs:run.italic=True;run.font.size=Pt(10)


p=paragraph("BÀI TẬP NHÓM\nHỆ THỐNG THÔNG TIN KHÔNG GIAN");p.alignment=1
for run in p.runs:run.bold=True;run.font.size=Pt(16)
paragraph("\n")
p=doc.add_heading("CHỦ ĐỀ 34",0);p.alignment=1
p=paragraph("XÂY DỰNG PLUGIN QGIS GIÁM SÁT VI PHẠM\nHÀNH LANG AN TOÀN LƯỚI ĐIỆN TRUNG THẾ\nTHEO PHÂN VÙNG QUẢN LÝ ĐIỆN LỰC");p.alignment=1
for run in p.runs:run.bold=True;run.font.size=Pt(16)
paragraph("\nLớp: D18CNPM1\nNhóm: ........................................\nGiảng viên: ........................................\nHọc kỳ 1 – Năm học 2026–2027")
table(["STT","Họ và tên","Mã sinh viên"],[(i,"................................","....................") for i in range(1,7)])
paragraph("Nhóm điền 5 hoặc 6 thành viên theo danh sách đăng ký; bỏ dòng 6 nếu nhóm có 5 người.")
paragraph("Tài liệu gồm báo cáo kỹ thuật và hướng dẫn cài đặt, sử dụng. Phiên bản plugin: 1.2.0. Môi trường kiểm thử: QGIS 3.44.13 trên Windows.")

page("1. Phân tích yêu cầu và phạm vi")
paragraph("Bài toán đặt ra là xác định phần nhà và khối nhà nằm trong hành lang an toàn của đường dây trung thế, sau đó lập danh mục và tổng hợp diện tích theo vùng quản lý điện lực. Người sử dụng là sinh viên thực hành và người khai thác dữ liệu trên QGIS Desktop.")
paragraph("Theo mục 2.1 của đề, bộ nộp gồm mã plugin/kết quả, hướng dẫn và báo cáo có phân công. Theo mục 2.2, phần sản phẩm – tài liệu chiếm 40%; slide và trình bày chiếm 60%. Chủ đề 34 được mô tả tại trang 12 của BaiTapNhom-HTTTKG-D18CNPM1.pdf.")
table(["Yêu cầu chủ đề 34","Cách đáp ứng","Bằng chứng"],[
 ("Chọn đường dây trung thế; nhập khoảng cách theo cấp điện áp","Chọn lớp/trường; ba ô 35 kV, 22 kV và cấp còn lại","Cửa sổ tham số; Processing algorithm"),
 ("Chọn nhà và khối nhà có khả năng gây nguy hiểm","Chọn lớp polygon; tùy chọn lọc phanLoai","Lớp KhoiNhaVaNha và bộ dữ liệu demo"),
 ("Chọn phân vùng quản lý điện lực","Chọn lớp và trường tên vùng","8 vùng Bắc Ninh; TenKVQLDL"),
 ("Buffer, Intersection; tính diện tích; hiển thị nhà vi phạm","Buffer → hợp nhất → giao nhà → giao vùng","4 lớp kết quả; bản đồ QGIS/PDF"),
 ("Chọn nơi lưu danh mục và bảng thống kê diện tích","GeoPackage và hai CSV cùng tên gốc","demo/ket_qua/; đối soát diện tích"),
])
doc.add_heading("Luồng sử dụng",2)
paragraph("Nạp dữ liệu → chọn ba lớp và hai trường → nhập khoảng cách → chọn tệp kết quả → phân tích → xem nhà trên bản đồ → kiểm tra bảng → xuất PDF hoặc bản đồ web. Plugin tính toán trong QGIS Desktop; bản đồ web là đầu ra tương tác để xem trên trình duyệt.")
paragraph("Mô hình của bài là giao hình học 2D. Khoảng cách 4/3/2 m được lấy từ ví dụ trong đề, cho phép chỉnh sửa; chương trình không suy luận chiều cao công trình hay khoảng cách đến dây ngoài cùng khi dữ liệu không cung cấp thông tin đó.")

page("2. Dữ liệu và template môn học")
table(["Lớp / nội dung","Số bản ghi","Trường quan trọng"],[
 ("DuongDayTrungThe_Noi – MultiLineString", "3.160", "capDienAp, soHieu, maDoiTuong"),
 ("KhoiNhaVaNha – MultiPolygon", "201.493", "maNhanDang, phanLoai, ten, dienTich"),
 ("BacNinh2025_KhuVucQLDienLuc – MultiPolygon", "17; lọc còn 8", "tentinh, TenKVQLDL"),
 ("Hệ tọa độ chung", "EPSG:32648", "WGS 84 / UTM zone 48N, đơn vị mét"),
 ("Cấp điện áp trên đường dây nổi", "1.822 / 1.334 / 4", "35 kV / 22 kV / 6 kV"),
])
bullets([
 "Dữ liệu lấy từ Bo du lieu thuc hanh QGIS 2026 đã giải nén trong thư mục làm việc. Demo đóng gói bản sao ba lớp vào dau_vao.gpkg để giữ đường dẫn tương đối và mở trên máy khác.",
 "Lớp nhà có 199.895 Nhà, 1.567 Khối nhà và 31 Cụm dân cư. Tùy chọn mặc định chỉ xét 201.462 Nhà/Khối nhà, phù hợp đối tượng chủ đề 34.",
 "Lớp phân vùng có cả Bắc Giang và Bắc Ninh theo dữ liệu môn học. Nạp dữ liệu mẫu lọc tentinh = 'Tỉnh Bắc Ninh', còn 8 vùng giống project mẫu BanDoLuoiDien_BacNinh.qgz.",
 "Có 39 đường suy biến với chiều dài bằng 0. Chương trình bỏ và ghi từng FID vào nhật ký; còn 3.121 đường dùng tạo hành lang.",
 "maDoiTuong và một số maNhanDang không duy nhất. Chương trình giữ source_fid từ mỗi bản ghi đầu vào để không gộp nhầm các nhà khác nhau.",
 "Template BanDoBacNinh.qpt được nạp làm bố cục gốc, kế thừa trang/khung và điều chỉnh thành A3; thay bản đồ, tiêu đề, chú giải, lưới tọa độ, tỷ lệ và nguồn dữ liệu cho chủ đề 34. Bản gốc được giữ trong assets của plugin.",
 "Ba style QML tương ứng được sao chép từ SanPhamMau/Style và áp dụng cho lớp đầu vào của demo. Kết quả dùng ký hiệu riêng để phân biệt hành lang, nhà và phần giao.",
])

page("3. Giải thuật và thiết kế chương trình")
paragraph("Với Lᵢ là đường dây, dᵢ là khoảng cách theo cấp điện áp, Hⱼ là nhà và Zₖ là vùng quản lý:")
paragraph("B = hợp nhất Buffer(Lᵢ, dᵢ);   Vⱼ = Hⱼ ∩ B;   Aⱼₖ = diện tích(Vⱼ ∩ Zₖ).")
table(["Bước","Xử lý"],[
 ("1. Kiểm tra", "Kiểm tra kiểu lớp, CRS, trường dữ liệu và khoảng cách. CRS tính toán phải có đơn vị mét."),
 ("2. Chuẩn hóa", "Chuyển hình học trên bản sao về CRS tính toán; bỏ hình học rỗng/suy biến; thử makeValid cho hình học lỗi."),
 ("3. Hành lang", "Buffer hai phía theo dᵢ, 8 đoạn mỗi góc phần tư, đầu và góc nối tròn; hợp nhất trước khi tính diện tích."),
 ("4. Giao nhà", "Dùng chỉ mục không gian của buffer để lọc ứng viên, sau đó giao chính xác với hành lang hợp nhất."),
 ("5. Giao vùng", "Chia diện tích giao theo vùng. Tính số nhà duy nhất trong từng vùng và tổng diện tích phẳng m²."),
 ("6. Đối soát / xuất", "Tổng diện tích theo vùng phải khớp tổng chi tiết, sai số tối đa 0,01 m². Ghi tệp qua thư mục tạm."),
])
bullets([
 "Chỉ tính phần giao có diện tích > 10⁻⁸ m². Chạm biên không tính vi phạm. Không dùng diện tích nguyên căn nhà để thay cho phần nằm trong hành lang.",
 "Một nhà qua ranh giới được chia diện tích cho từng vùng. Số nhà toàn bộ đếm duy nhất theo FID; tổng số nhà ở các vùng có thể lớn hơn tổng duy nhất.",
 "Nhà ngoài các vùng được giữ trong nhóm Chưa phân vùng. Hai vùng quản lý chồng diện tích sẽ làm tác vụ dừng để tránh thống kê lặp.",
 "core.py chứa xử lý; storage.py ghi kết quả; processing_provider.py công bố thuật toán; dialog.py cung cấp giao diện; maps.py hiển thị/in bản đồ. Các lớp giao diện QGIS chỉ được cập nhật trên luồng chính.",
 "QgsProcessingAlgRunnerTask chạy nền với feedback, tiến độ và hủy. Khi hủy hoặc ghi lỗi, thư mục tạm bị dọn; không sửa nguồn và không ghi đè bộ kết quả đã có.",
])

page("4. Cài đặt và chuẩn bị dữ liệu")
for text in [
 "Giải nén gói nộp vào một thư mục có quyền ghi. Giữ nguyên cấu trúc plugin, demo, tai_lieu và kiem_thu.",
 "Mở QGIS 3.44. Vào Plugins → Manage and Install Plugins → Install from ZIP. Chọn hlat_trungthe_34.zip ở thư mục gốc của bộ nộp rồi bấm Install Plugin. Nếu QGIS yêu cầu xác nhận nguồn ZIP cục bộ, xác nhận gói bài tập của nhóm.",
 "Trong tab Installed, bật HLAT Trung thế - Chủ đề 34. Mở từ menu Plugins → HLAT Trung thế hoặc biểu tượng cột điện trên thanh công cụ.",
 "Để xem demo có sẵn: Project → Open → demo/ChuDe34_BacNinh.qgz. Các lớp dùng đường dẫn tương đối tới data/ và ket_qua/.",
 "Để chạy mới: bấm Nạp dữ liệu Bắc Ninh…, chọn demo/data hoặc thư mục Bo du lieu thuc hanh QGIS 2026 gốc. Plugin nạp ba lớp và lọc 8 vùng Bắc Ninh.",
 "Không cần cài thêm gói Python vào QGIS, không cần tài khoản mạng. Thư viện tạo DOCX/PPTX chỉ dùng bởi script tạo tài liệu, không phải phụ thuộc của plugin.",
 ]: paragraph(text,"List Number")
picture("giao_dien_dau_vao.png","Hình 1. Cửa sổ chọn dữ liệu và khoảng cách trong plugin QGIS.",15)

page("5. Chạy phân tích và khai thác kết quả")
for text in [
 "Chọn đường dây trung thế nổi và trường capDienAp. Chọn lớp Nhà và khối nhà. Chọn phân vùng quản lý và trường TenKVQLDL.",
 "Giữ tùy chọn Chỉ lấy Nhà và Khối nhà khi dùng bộ dữ liệu môn học. Kiểm tra bộ lọc Bắc Ninh trên lớp vùng nếu bạn tự nạp lớp bằng QGIS.",
 "Nhập 4 m cho 35 kV, 3 m cho 22 kV và 2 m cho cấp còn lại. Đây là khoảng cách mỗi phía đường dây. Giữ CRS tính toán EPSG:32648.",
 "Chọn tệp .gpkg có tên chưa tồn tại và bấm Phân tích vi phạm. Có thể bấm Hủy xử lý; đọc thông báo trong nhật ký nếu tác vụ không hoàn tất.",
 "Khi xong, bốn lớp kết quả được thêm ngay lên bản đồ QGIS. Trong tab Kết quả và thống kê có bảng và biểu đồ theo vùng.",
 "Bấm Danh mục nhà và xem bản đồ; nhấp đúp một dòng để chọn nhà và phóng tới vị trí. Cửa sổ plugin ẩn đi để nhìn bản đồ; mở lại bằng nút plugin.",
 "Bấm Xuất bản đồ PDF để lưu hai trang tổng quan/chi tiết. Dùng Mở thư mục kết quả để lấy GeoPackage, hai CSV, nhật ký và JSON cấu hình.",
 ]: paragraph(text,"List Number")
picture("giao_dien_ket_qua.png","Hình 2. Bảng kết quả và biểu đồ trong plugin; bản đồ chính vẫn nằm trong QGIS.",15)

page("5a. Xuất bản đồ web tương tác")
paragraph("Sau khi phân tích, bấm Xuất bản đồ web… và chọn thư mục chứa. Plugin tạo một thư mục mới, xuất GeoJSON WGS84 cùng HTML, Leaflet 1.9.4 và JavaScript, rồi mở bản đồ bằng máy chủ HTTP cục bộ. Giữ QGIS mở khi dùng máy chủ này.")
bullets(["Kéo để di chuyển; cuộn chuột, nút +/− hoặc chụm hai ngón để thay đổi tỷ lệ.",
         "Bật/tắt vùng quản lý, đường dây, hành lang, nhà và phần giao ở góc phải; chọn nền OpenStreetMap hoặc nền trắng.",
         "Chọn vùng và điện áp để lọc đồng bộ bản đồ, danh mục và thống kê. Cả hai phương án dùng cùng bộ lọc. Tìm nhà theo FID hoặc mã nhận dạng trong phạm vi đang lọc.",
         "Nút Bảng thống kê hiển thị các vùng đang xét; Danh mục / So sánh mở bảng bên cạnh bản đồ. Mặc định thu gọn để dành chỗ cho bản đồ.",
         "Mở lại bản đã xuất bằng MoBanDoWeb.bat hoặc python serve.py. Nền OSM cần Internet; thư viện và lớp phân tích nằm trong bộ xuất.",
         "Đưa toàn bộ thư mục web lên hosting tĩnh để có đường link. Nếu bản mẫu được triển khai qua Sites, quyền truy cập và URL được ghi riêng trong tai_lieu/ThongTin_Web.txt."])
picture("web_tong_quan.png","Hình 2a. Bản đồ web với nền OpenStreetMap và lớp dữ liệu phân tích.",16)
paragraph("Kết quả ban đầu lấy từ QGIS. Khi đổi khoảng cách hoặc bộ lọc, GEOS-WASM tính lại trên CRS mét của bài; chỉ hình học hiển thị chuyển WGS84. HTTP/HTTPS là điều kiện để dùng Web Worker; mở file:// chỉ xem kết quả ban đầu.")

page("5b. Truy vết nhà và đường dây liên quan")
bullets(["Nhấp nhà trên bản đồ hoặc tìm FID/mã để mở chi tiết: diện tích nhà, diện tích trong hành lang, tỷ lệ và vùng quản lý.",
         "Danh sách đường dây liên quan hiển thị FID đường, số hiệu, cấp điện áp, khoảng cách ngắn nhất từ hình học nhà tới đường dây, chiều rộng mỗi phía và diện tích giao riêng từng đường.",
         "Nhấp một đường trong danh sách để tô sáng và phóng tới vị trí. Trên điện thoại bảng chi tiết tự ẩn khi xem đường dây.",
         "Diện tích giao từng đường có thể chồng nhau. Tổng diện tích vi phạm lấy theo hợp nhất hành lang, không cộng các diện tích giao riêng."])
picture("web_chi_tiet.png","Tra cứu nhà FID 73 và đường dây 22 kV liên quan; số liệu được đối chiếu với QGIS.",16)
paragraph("Dữ liệu đầu vào gồm toàn bộ Nhà/Khối nhà đã chọn khi chạy QGIS, giữ FID và hình học WKB đầy đủ độ chính xác. Các khối dữ liệu được nạp vào Worker, không chặn thao tác kéo/zoom trên luồng giao diện.")

page("5c. So sánh hai phương án hành lang")
bullets(["Mở Danh mục / So sánh → So sánh phương án. Nhập ba khoảng cách mỗi phía cho A và B rồi bấm Tính và so sánh A / B.",
         "Phạm vi nhập 0,001–10.000 m, giống giới hạn giao diện plugin. Phương án rộng có thể mất nhiều thời gian; Hủy tính toán giữ nguyên kết quả trước đó.",
         "Chuyển Phương án A/B để cập nhật bản đồ, danh mục và thống kê. Màu xanh lá là nhà tăng thêm ở B; màu tím là nhà không còn thuộc B. Tải CSV cho danh mục đang lọc hoặc bảng so sánh theo vùng."])
table(["Cấu hình 35/22/khác (m)","Số nhà","Diện tích (m²)"],[("A: 4 / 3 / 2","1.184","42.425,06"),("B: 6 / 5 / 3","1.636","74.586,37"),("Chênh lệch B − A","+452","+32.161,31")])
picture("web_so_sanh.png","So sánh A/B trên cùng toàn bộ dữ liệu đầu vào; phương án B tìm được thêm nhà.",16)
paragraph("Worker dùng GEOS 3.13: Buffer 8 đoạn/góc phần tư → UnaryUnion → Intersection nhà và vùng → đo diện tích phẳng. Đối chiếu native QGIS cho mặc định, mở rộng, khoảng cách tăng/giảm theo điện áp và lọc vùng/điện áp; sai số diện tích từng nhà dưới 0,01 m². Tổng diện tích vùng được đối soát với tổng chi tiết.")

page("5d. Khoanh vùng và công cụ GIS trên web")
bullets(["Nhấp trực tiếp nhà vi phạm để xem thông tin. Khi zoom từ 16, nhấp vào nhà trên nền bản đồ để nhận diện từ toàn bộ nhà nguồn; nhà ngoài kết quả hiện tại hiển thị diện tích trong HLAT đang lọc bằng 0.",
         "Ô tìm kiếm có hai phạm vi: Nhà vi phạm và Toàn bộ nhà nguồn. Tìm theo FID hoặc mã; kết quả nguồn có phân trang, không tự gộp các mã bị trùng.",
         "Mở Công cụ GIS → Đo khoảng cách / Đo diện tích / Khoanh vùng truy vấn. Nhấp các đỉnh rồi Kết thúc vẽ; Enter để kết thúc, Backspace để lùi điểm, Esc để hủy. Đa giác tự cắt bị từ chối.",
         "Vùng khoanh cắt hành lang và phần giao trước khi thống kê; cùng áp dụng cho A/B, bản đồ và danh mục. Bỏ vùng khoanh giữ bộ lọc vùng quản lý/điện áp.",
         "Xuất GeoJSON lấy lớp đang lọc: nhà, phần giao, đường dây hoặc hình vẽ. Lưu phiên làm việc giữ A/B, vùng khoanh, phép đo và khung nhìn; Mở phiên tính lại số liệu, kiểm tra đúng bộ dữ liệu trước khi áp dụng."])
picture("web_cong_cu_gis.png","Khoanh vùng, đo đường và diện tích trực tiếp. Số đo phẳng theo CRS mét; GeoJSON hiển thị WGS84.",16)

page("6. Cấu trúc kết quả và số liệu thực nghiệm")
table(["Tệp / lớp","Nội dung"],[
 ("hanh_lang", "MultiPolygon hợp nhất tất cả buffer; có diện tích m²."),
 ("nha_vi_pham", "Hình học nguyên nhà; source_fid, mã, loại, tên, diện tích nhà, diện tích vi phạm, tỷ lệ %, danh sách vùng."),
 ("phan_vi_pham", "Phần giao nhà – hành lang – vùng; một bản ghi cho mỗi nhà/vùng có diện tích dương."),
 ("thong_ke_vung", "Hình học vùng; số nhà, diện tích m² và ha."),
 ("*_danh_muc.csv", "source_fid, ma_nhan_dang, vung_ql, dt_nha_m2, dt_vp_m2."),
 ("*_thong_ke.csv", "vung_ql, so_nha, dt_vp_m2, dt_vp_ha. CSV có BOM UTF-8 để mở bằng Excel."),
 ("*_nhat_ky.csv / *_thong_tin.json", "FID bị bỏ/được sửa; phiên bản, thời gian +07:00, tham số, CRS và tổng kiểm tra."),
])
paragraph("Kết quả với cấu hình mặc định trên bản sao dữ liệu môn học:")
table(["Vùng quản lý","Số nhà","Diện tích vi phạm (m²)"],
      [(r["vung_ql"], r["so_nha"], number(r["dt_vp_m2"])) for r in zone_rows]
      + [("Tổng duy nhất", "1.184", number(metrics["violation_area_m2"]))])
paragraph("Tổng diện tích vi phạm là 42.425,06 m² (4,242506 ha). KV Kinh Bắc có diện tích lớn nhất, 15.174,71 m². Không có nhà vi phạm nằm ngoài 8 vùng trong lần chạy này. Dữ liệu gốc được đối chiếu SHA-256 trước/sau để kiểm tra không thay đổi.")

page("7. Bản đồ kết quả")
picture("ban_do_tong_quan.png","Hình 3. Bản đồ tổng quan, có tên vùng quản lý và lớp đường dây.",14)
picture("ban_do_chi_tiet.png","Hình 4. Bản đồ chi tiết: đường dây màu xanh, hành lang vàng, nhà vi phạm đỏ nhạt và phần giao đỏ đậm.",14)
paragraph("Tệp demo/BanDo_HLAT_TrungThe.pdf gồm hai trang A3. Có thể chỉnh lại vùng nhìn trong Print Layout của project demo để trình bày vị trí khác. Các bản đồ thể hiện lớp dữ liệu môn học theo hệ tọa độ của bộ dữ liệu.")

page("8. Kiểm thử và kiểm tra nghiệm thu")
table(["Nhóm kiểm thử","Kỳ vọng / bằng chứng"],[
 ("Giao hình học", "Nhà trong/ngoài/giao một phần; tiếp xúc biên; buffer trùng. Diện tích hình chữ nhật biết trước."),
 ("Phân vùng và nhận dạng", "Nhà qua 2 vùng; mã nhận dạng trùng; vùng chồng bị từ chối; phần ngoài vùng được giữ."),
 ("Dữ liệu và tham số", "Đường dài 0 bị bỏ; điện áp rỗng bị chặn; CRS địa lý không dùng tính mét; chuyển CRS đúng."),
 ("Vòng đời tác vụ / xuất", "Hủy; kết quả rỗng vẫn có lớp/bảng; không ghi đè; thuật toán Processing chạy được."),
 ("Dữ liệu thật", "1.184 nhà, 42.425,0601295 m²; 3.121 đường hợp lệ, 39 suy biến; 8 vùng; tổng chi tiết khớp."),
])
paragraph("Bộ tests/test_analysis.py gồm 13 ca tự động. tests/check_native.py đối chiếu buffer và intersection bằng thuật toán native của QGIS; kiem_thu/ chứa kết quả chạy và nhật ký kiểm tra cài ZIP/project. Khi bàn giao cần đọc các tệp bằng chứng trong thư mục này cùng với mã kiểm thử.")
doc.add_heading("Lệnh kiểm tra trên máy hiện tại",2)
paragraph('"C:\\Program Files\\QGIS 3.44.13\\bin\\python-qgis-ltr.bat" tests\\test_analysis.py')
paragraph("Thực hiện lệnh từ thư mục ChuDe34_HLAT_TrungThe. Nếu QGIS cài ở vị trí khác, thay phần đường dẫn tới python-qgis-ltr.bat.")
doc.add_heading("Xử lý lỗi thường gặp",2)
table(["Hiện tượng","Cách xử lý"],[
 ("Không có lớp để chọn", "Nạp ba lớp vector hoặc mở project demo; chọn đúng kiểu đường / vùng."),
 ("Kết quả cùng tên đã tồn tại", "Chọn tên .gpkg mới; giữ bộ cũ để đối chiếu."),
 ("CRS không hợp lệ / đơn vị không phải mét", "Gán đúng CRS nguồn; chọn hệ chiếu mét như EPSG:32648 cho tính toán."),
 ("Điện áp trống / vùng chồng nhau", "Đọc FID/tên vùng trong nhật ký; kiểm tra dữ liệu nguồn rồi chạy lại trên bản sao đã xử lý."),
 ("ZIP không đúng / không bật được", "Chọn ZIP plugin ở thư mục gốc, không chọn ZIP toàn bộ bài nộp; đọc QGIS Log Messages."),
])

page("9. Phân công và kịch bản thuyết trình")
paragraph("Bảng dưới là phương án phân công để nhóm hoàn thiện. Điền thành viên và cập nhật theo công việc thực sự đã làm trước khi nộp; không mặc định đây là lịch sử đóng góp.")
roles=[("1","Yêu cầu và dữ liệu","Đối chiếu chủ đề 34; khảo sát trường, CRS và chất lượng dữ liệu"),
       ("2","Giải thuật","Buffer theo điện áp, hợp nhất, giao nhà và vùng"),
       ("3","Giao diện QGIS","Chọn lớp, tác vụ nền, chọn nhà trên bản đồ"),
       ("4","Kết quả và bản đồ","GeoPackage/CSV; style và template; PDF"),
       ("5","Kiểm thử và đóng gói","Ca thử, đối soát native, ZIP và project tương đối"),
       ("6 (nếu có)","Tài liệu và trình bày","Báo cáo, hướng dẫn, slide và điều phối demo")]
table(["Thành viên","Phần việc","Sản phẩm"],[(f"{i}. ................",task,product) for i,task,product in roles])
paragraph("Nếu nhóm có 5 người, phân chia phần tài liệu/trình bày giữa các thành viên 1–5 và bỏ dòng 6.")
doc.add_heading("Kịch bản demo khoảng 3 phút",2)
bullets(["0:00–0:40: mở project, giới thiệu ba lớp và 8 vùng; mở plugin.",
         "0:40–1:20: chọn trường, giải thích 4/3/2 m mỗi phía; chọn tên tệp mới và chạy.",
         "1:20–2:20: đọc bảng thống kê; chọn một nhà để phóng tới bản đồ; bật/tắt hành lang và phần giao.",
         "2:20–3:00: mở CSV và PDF; nêu cách tránh cộng lặp buffer và cách đối soát diện tích."])

page("10. Câu hỏi bảo vệ và tài liệu tham khảo")
for q,a in [
 ("Vì sao phải hợp nhất buffer?", "Một nhà có thể giao nhiều đoạn đường dây. Hợp nhất hành lang trước khi giao giúp không cộng lặp phần diện tích chung."),
 ("Vì sao không dùng trường dienTich?", "Đề yêu cầu diện tích nhà nằm trong hành lang. Cần đo hình học phần giao sau khi chuẩn hóa CRS, thay vì dùng diện tích toàn nhà có sẵn."),
 ("Tại sao phải dùng CRS mét?", "Buffer dùng khoảng cách tuyến tính; EPSG:4326 có đơn vị độ nên không dùng trực tiếp giá trị mét. Bộ dữ liệu hiện có EPSG:32648."),
 ("Vì sao không nhóm nhà theo maNhanDang?", "Có mã bị trùng và trống. Khóa kỹ thuật theo đối tượng nguồn giữ được truy vết và tránh gộp nhầm."),
 ("39 bản ghi bị bỏ có ảnh hưởng thế nào?", "Đó là đường chiều dài 0 do các đỉnh trùng; không dùng làm đường để tạo hành lang. Nhật ký cho phép kiểm tra từng FID."),
 ("Có kết luận pháp lý đầy đủ từ bản đồ này không?", "Mô hình bài tập chỉ xét giao 2D theo khoảng cách cấu hình. Dữ liệu không có thông tin cần cho đánh giá chiều cao hoặc dây ngoài cùng."),
]:
    doc.add_heading(q,2); paragraph(a)
bullets(["BaiTapNhom-HTTTKG-D18CNPM1.pdf, trang 1–2 và trang 12 (chủ đề 34).",
         "Slide/Chuong 6 ... HTTTKG.2.pdf: PyQGIS, cấu trúc plugin, metadata và quy trình cài plugin.",
         "Slide/Chuong 7 ... Python va QGIS.pdf: yêu cầu, thiết kế, kiểm thử, đóng gói và hướng dẫn.",
         "Slide/Bai 5-2 ... QGIS quan ly CSDL GIS nganh dien.pdf: Buffer, Dissolve, Intersection và quản lý hành lang.",
         "Bo du lieu thuc hanh QGIS 2026: Data Goc, SanPhamMau/Style, Template/QGIS Layout/BanDoBacNinh.qpt và project mẫu.",
         "Leaflet API 1.9.4: https://leafletjs.com/reference-1.9.4.html; OSM Tile Usage Policy: https://operations.osmfoundation.org/policies/tiles/"])
doc.save(OUT / "BaoCao_HuongDan_ChuDe34.docx")

# Slide học thuật, nền trắng, chữ đen và đường kẻ; không dùng thẻ KPI hay bố cục dashboard.
prs=Presentation(); prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
BLACK=PptColor(20,20,20); BLUE=PptColor(28,65,100); GRAY=PptColor(100,100,100)

def textbox(slide,text,x,y,w,h,size=22,bold=False,color=BLACK):
    shape=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
    tf=shape.text_frame;tf.word_wrap=True
    for i,line in enumerate(text.split("\n")):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line
        p.font.name="Arial";p.font.size=PptPt(size);p.font.bold=bold;p.font.color.rgb=color;p.space_after=PptPt(10)
    return shape

def slide(title,notes):
    s=prs.slides.add_slide(prs.slide_layouts[6]); i=len(prs.slides)
    textbox(s,title,.55,.27,12.25,.65,28,True)
    line=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(.6),Inches(1.05),Inches(12.1),Inches(.018))
    line.fill.solid();line.fill.fore_color.rgb=BLUE;line.line.fill.background()
    textbox(s,"D18CNPM1 | Chủ đề 34 | Nhóm ..........",.6,7.12,10,.25,10,color=GRAY)
    textbox(s,str(i),12.2,7.1,.4,.25,10,color=GRAY)
    s.notes_slide.notes_text_frame.text=notes
    return s

def lines(s,items,x=.75,y=1.35,w=11.8,size=23):
    return textbox(s,"\n".join("• "+v for v in items),x,y,w,5.4,size)

def slide_picture(s,name,x=.7,y=1.25,w=11.9,h=5.65):
    from PIL import Image
    image=ASSETS/name; iw,ih=Image.open(image).size; ratio=min(w/iw,h/ih)
    return s.shapes.add_picture(str(image),Inches(x+(w-iw*ratio)/2),Inches(y+(h-ih*ratio)/2),width=Inches(iw*ratio),height=Inches(ih*ratio))

def slide_table(s,headers,rows,x=.7,y=1.4,w=11.9,h=4.8,size=18):
    t=s.shapes.add_table(len(rows)+1,len(headers),Inches(x),Inches(y),Inches(w),Inches(h)).table
    for i,row in enumerate([headers]+rows):
        for j,value in enumerate(row):
            cell=t.cell(i,j);cell.text=str(value);cell.fill.solid();cell.fill.fore_color.rgb=PptColor(235,235,235) if i==0 else PptColor(255,255,255)
            for p in cell.text_frame.paragraphs:
                p.font.name="Arial";p.font.size=PptPt(size);p.font.color.rgb=BLACK;p.font.bold=i==0
    return t

s=slide("BÀI TẬP NHÓM – HỆ THỐNG THÔNG TIN KHÔNG GIAN","35 giây. Giới thiệu nhóm, lớp, chủ đề. Nhấn mạnh đây là plugin chạy trong QGIS Desktop. Điền tên nhóm và thành viên trước buổi thi.")
textbox(s,"Chủ đề 34",.8,1.55,11.8,.7,30,True)
textbox(s,"Giám sát vi phạm hành lang an toàn\nlưới điện trung thế theo phân vùng quản lý điện lực",.8,2.4,11.7,1.6,29,True)
textbox(s,"QGIS 3.44.13 – Bộ dữ liệu thực hành Bắc Ninh\nNhóm: .......... | Thành viên: ................................................\nHọc kỳ 1 – Năm học 2026–2027",.8,4.6,11.5,1.7,20)
s=slide("1. Yêu cầu của chủ đề 34","45 giây. Đọc theo luồng nghiệp vụ thay vì đọc lại cả đề. Chỉ rõ mỗi yêu cầu đều có đầu vào hoặc đầu ra tương ứng trong plugin.")
lines(s,["Chọn đường dây trung thế và nhập khoảng cách theo cấp điện áp.","Chọn nhà/khối nhà và phân vùng quản lý điện lực.","Buffer, giao cắt và tính diện tích phần nhà trong hành lang.","Hiển thị nhà vi phạm trên bản đồ QGIS.","Lưu danh mục nhà và bảng thống kê diện tích theo vùng."])
s=slide("2. Dữ liệu đầu vào và kiểm tra chất lượng","45 giây. Các lớp đều EPSG:32648. Phân vùng có 17 bản ghi nhưng chỉ dùng 8 vùng Bắc Ninh như project mẫu. Có 39 đường dài 0 và mã nhận dạng trùng; không tự sửa dữ liệu gốc.")
slide_table(s,["Dữ liệu","Số bản ghi","Thông tin sử dụng"],[["Đường dây trung thế nổi","3.160","capDienAp; 3.121 đường hợp lệ"],["Nhà và khối nhà","201.493","201.462 Nhà/Khối nhà; bỏ 31 Cụm dân cư"],["Vùng quản lý điện lực","17 → 8","tentinh; TenKVQLDL"],["Hệ tọa độ","EPSG:32648","UTM 48N; đơn vị mét"]],h=3.7,size=19)
textbox(s,"Dùng template BanDoBacNinh.qpt và style QML từ bộ dữ liệu môn học.",.8,5.7,11.8,.8,21)
s=slide("3. Các chức năng và đầu ra","40 giây. Chức năng bắt buộc là chọn dữ liệu, tính toán và xuất hai bảng. Các phần bổ sung phục vụ kiểm tra: nạp mẫu, biểu đồ, phóng tới nhà, PDF và nhật ký.")
slide_table(s,["Nhóm chức năng","Kết quả"],[["Chọn dữ liệu / tham số","3 lớp, 2 trường; 4/3/2 m mỗi phía"],["Phân tích không gian","Hành lang hợp nhất, nhà và phần giao"],["Thống kê / truy vết","Số nhà, m², ha; source_fid; nhật ký"],["Khai thác","Bản đồ QGIS; danh mục, biểu đồ; PDF"]],h=4,size=21)
s=slide("4. Thiết kế chương trình","40 giây. Giao diện chỉ điều phối; thuật toán tách riêng để dùng lại trong Processing và kiểm thử. Worker dùng nguồn đặc trưng và hình học riêng, cập nhật UI trên luồng chính.")
lines(s,["dialog.py: chọn lớp, tham số, bảng kết quả và thao tác xem nhà.","processing_provider.py: thuật toán hlat34:phan_tich_vi_pham.","core.py: buffer, hợp nhất, giao nhà và phân vùng.","storage.py: GeoPackage, hai CSV, nhật ký và cấu hình JSON.","maps.py: lớp bản đồ và bố cục in kế thừa template môn học.","Tác vụ nền có tiến độ và hủy; dữ liệu gốc được giữ nguyên."],size=21)
s=slide("5. Quy trình xử lý không gian","55 giây. Giải thích công thức bằng một nhà có thể gần hai đường. Nếu không hợp nhất buffer, phần giao có thể bị cộng nhiều lần. Buffer dùng 8 đoạn mỗi góc phần tư, đầu/góc nối tròn.")
lines(s,["Chuẩn hóa CRS mét; kiểm tra hình học và cấp điện áp.","Tạo Buffer(Lᵢ, dᵢ): 35 kV = 4 m; 22 kV = 3 m; còn lại = 2 m.","Hợp nhất các buffer thành hành lang B.","Tính Vⱼ = Nhàⱼ ∩ B; chỉ lấy phần có diện tích dương.","Tính Aⱼₖ = diện tích(Vⱼ ∩ Vùngₖ).", "Tổng hợp theo vùng, đối soát và ghi tệp kết quả."],size=23)
s=slide("6. Quy tắc tính diện tích và đếm nhà","40 giây. Đây là các điểm dễ hỏi khi bảo vệ. Không nhầm diện tích cả căn nhà với diện tích phần giao. Không giả định mã nguồn là duy nhất.")
lines(s,["Đo diện tích phần giao trong CRS mét, không dùng sẵn dienTich.","Khóa theo FID đối tượng nguồn vì một số mã bị trùng.","Chạm biên không tính vi phạm.","Nhà qua hai vùng: chia diện tích; tổng nhà toàn bộ đếm duy nhất.","Bỏ 39 đường dài 0 và ghi rõ vào nhật ký.","Mô hình phân tích 2D theo khoảng cách cấu hình của bài tập."],size=23)
s=slide("7. Giao diện nhập dữ liệu trong QGIS","35 giây. Chỉ ba lớp, trường điện áp và tên vùng. Giải thích khoảng cách mỗi phía; nơi lưu phải là tên mới. Đây là cửa sổ bổ sung, bản đồ chính vẫn là QGIS.")
slide_picture(s,"giao_dien_dau_vao.png")
s=slide("8. Xem kết quả và chọn nhà trên bản đồ","35 giây. Bảng theo vùng, biểu đồ, danh mục. Nhấp đúp nhà để QGIS chọn và phóng tới vị trí. Các lớp kết quả có thể bật tắt từ Layers panel.")
slide_picture(s,"giao_dien_ket_qua.png")
s=slide("9. Bản đồ web tương tác trên trình duyệt","35 giây. Phần mở rộng dùng Leaflet và nền OSM. Giữ giao diện bản đồ đơn giản. Lọc vùng và điện áp đồng bộ bản đồ, danh mục, thống kê của A/B. Bộ tính GEOS chạy nền trên CRS mét; chỉ hình học hiển thị chuyển WGS84. Plugin xuất toàn bộ bộ web và dữ liệu để dùng cục bộ hoặc hosting.")
slide_picture(s,"web_tong_quan.png")
s=slide("9a. Chọn nhà, truy vết đường dây liên quan","40 giây. Tìm FID 73. Đọc cấp điện áp 22 kV, khoảng cách ngắn nhất từ hình học nhà tới đường dây và diện tích giao. Nhấp đường để phóng tới vị trí. Nhấn mạnh diện tích giao riêng từng đường có thể chồng nhau nên không cộng trực tiếp. Các giá trị đã đối chiếu độc lập trong QGIS.")
slide_picture(s,"web_chi_tiet.png")
s=slide("9b. So sánh hai phương án hành lang","45 giây. A dùng 4/3/2 m, B dùng 6/5/3 m. A có 1.184 nhà, 42.425,06 m²; B có 1.636 nhà, 74.586,37 m²; tăng 452 nhà và 32.161,31 m². B xét toàn bộ 201.462 nhà đầu vào, không chỉ 1.184 nhà ban đầu. Thử bộ lọc KV Kinh Bắc và 35 kV để chứng minh đồng bộ. Đây là mô phỏng tham số bài tập, không thay kết luận kiểm tra hiện trường.")
slide_picture(s,"web_so_sanh.png")
s=slide("9c. Thao tác GIS trực tiếp trên bản đồ","45 giây. Nhấp thẳng nhà để xem thông tin; phóng gần để nhận diện cả nhà nguồn ngoài HLAT. Mở Công cụ GIS, vẽ đường/đa giác, kết thúc để đo theo CRS mét. Khoanh vùng để chỉ thống kê phần giao trong vùng, đồng thời áp dụng cho A/B. Xuất GeoJSON hoặc lưu phiên JSON để mở lại khung nhìn và cấu hình. Nút quay lại riêng đã bỏ; chọn Tất cả vùng quản lý trong danh sách để bỏ lọc vùng.")
slide_picture(s,"web_cong_cu_gis.png")
s=slide("10. Bản đồ chi tiết phần nhà trong hành lang","45 giây. Chỉ đường dây xanh, vùng đệm vàng, nhà vi phạm đỏ nhạt, phần giao đỏ đậm và nhà hiện trạng xám. Phần đỏ đậm mới là diện tích đưa vào thống kê. Template gốc được điều chỉnh cho A3.")
slide_picture(s,"ban_do_chi_tiet.png")
s=slide("11. Thống kê trên dữ liệu Bắc Ninh","45 giây. Đọc tổng 1.184 nhà, 42.425,06 mét vuông. Kinh Bắc lớn nhất. Tổng diện tích các vùng khớp chi tiết; số nhà theo vùng không phải lúc nào cũng cộng thành tổng duy nhất.")
slide_table(s,["Vùng quản lý","Số nhà","Diện tích vi phạm (m²)"],[[r["vung_ql"],r["so_nha"],number(r["dt_vp_m2"])] for r in zone_rows]+[["Tổng duy nhất","1.184","42.425,06"]],h=4.65,size=18)
s=slide("12. Kiểm thử và cách kiểm tra kết quả","45 giây. Nêu ca tính bằng tay cho hình chữ nhật và đối chiếu độc lập với công cụ QGIS. Mở thư mục kiem_thu nếu cần bằng chứng cụ thể. Không chỉ dựa vào ảnh kết quả.")
lines(s,["13 ca tự động: giao một phần, chạm biên, buffer chồng, nhà qua vùng…", "Kiểm tra CRS, mã trùng, đường suy biến, hủy và kết quả rỗng.","Đối chiếu native:buffer + native:intersection của QGIS.","Dữ liệu thật: 1.184 nhà; 42.425,06 m²; 8 vùng.","Tổng diện tích chi tiết và thống kê khớp trong 0,01 m².","Cài ZIP, mở project đường dẫn tương đối, kiểm tra PDF/CSV."],size=22)
s=slide("13. Phân công và trình diễn","Khoảng 3 phút demo, sau 8–9 phút trình bày nội dung. Điền thành viên theo phân công thực tế, nhóm 5 người gộp phần tài liệu cho các thành viên. Chuẩn bị tên GeoPackage mới trước demo để tránh thông báo không ghi đè. Câu hỏi dự phòng nằm cuối báo cáo.")
slide_table(s,["Thành viên (điền tên)","Phần việc"],[["1. ................","Yêu cầu và dữ liệu"],["2. ................","Giải thuật không gian"],["3. ................","Giao diện và tác vụ nền"],["4. ................","Kết quả và bản đồ"],["5. ................","Kiểm thử và đóng gói"],["6. ............ (nếu có)","Tài liệu và thuyết trình"]],h=3.8,size=18)
textbox(s,"Demo: mở project → chọn 4/3/2 m → chạy → chọn nhà → xem CSV và PDF.",.8,5.65,11.8,.9,21)
prs.save(OUT / "ThuyetTrinh_ChuDe34.pptx")
(OUT / "KichBan_ThuyetTrinh.txt").write_text("\n\n".join(f"SLIDE {i+1}\n{s.notes_slide.notes_text_frame.text}" for i,s in enumerate(prs.slides)),encoding="utf-8")
assert len(prs.slides)==17
print("DOCUMENTS_OK", len(prs.slides))
