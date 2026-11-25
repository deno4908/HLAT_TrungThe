"""Xuất PDF bằng Word/PowerPoint đã cài, chạy ẩn và đóng riêng các ứng dụng tạo ra."""
from pathlib import Path
import win32com.client
import pywintypes
root=Path(__file__).resolve().parents[1]/'tai_lieu'
word=win32com.client.DispatchEx('Word.Application');word.Visible=False;word.DisplayAlerts=0
try:
    document=word.Documents.Open(str(root/'BaoCao_HuongDan_ChuDe34.docx'),ReadOnly=True,AddToRecentFiles=False)
    try:document.ExportAsFixedFormat(str(root/'BaoCao_HuongDan_ChuDe34.pdf'),17)
    finally:document.Close(False)
finally:
    try:word.Quit()
    except (AttributeError, pywintypes.com_error):pass
powerpoint=win32com.client.DispatchEx('PowerPoint.Application')
try:
    presentation=powerpoint.Presentations.Open(str(root/'ThuyetTrinh_ChuDe34.pptx'),ReadOnly=True,WithWindow=False)
    try:presentation.SaveAs(str(root/'ThuyetTrinh_ChuDe34.pdf'),32)
    finally:presentation.Close()
finally:
    try:powerpoint.Quit()
    except (AttributeError, pywintypes.com_error):pass
print('OFFICE_PDF_OK',flush=True)
