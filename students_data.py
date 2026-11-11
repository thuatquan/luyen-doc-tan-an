# -*- coding: utf-8 -*-
"""
DỮ LIỆU HỌC SINH TOÀN TRƯỜNG (TRÍCH XUẤT TỪ PHẦN MỀM CSDL NGÀNH GD&ĐT)
Chỉ lấy 2 trường cần thiết: Mã lớp và Họ tên.
Hỗ trợ nạp tự động từ file CSV/Excel xuất trực tiếp từ CSDL ngành mà không cần chỉnh sửa.
"""
import csv
import io
import json
import os
import re

DEFAULT_STUDENTS_BY_CLASS = {
    "1A1": [
        "Ma Bảo An", "Hoàng Đức Anh", "Ma Việt Anh", "Ma Duy Bảo", "Trần Phúc Đăng",
        "Vương Thúy Hà", "Đỗ Huỳnh Hiếu", "Bùi Văn Hưng", "Quan Gia Hưng", "Nguyễn Minh Khang",
        "Bàn Thị Mai Lan", "Cứ Thị Máy", "Quan Hà My", "Hoàng Hải Nam", "Ma Kim Ngân",
        "Trần Bách Nhiên", "Hoàng Quan Khải Phong", "Cứ A Sàng", "Lương Anh Thư", "Hoàng Đức Tuyên",
        "Ma Thị Tố Uyên", "Bùi Văn Việt", "Quan Văn Việt"
    ],
    "1B1": [
        "Hà Thùy Chi", "Nông Quỳnh Chi", "Đỗ Gia Hân", "Hoàng Trung Hiếu", "Hoàng Đức Hùng",
        "Chu Quốc Huy", "Ma Minh Khang", "Lý Thanh Khương", "Hoàng Trung Kiên", "Ma Thùy Lâm",
        "Quan Văn Mạnh", "Tô Duy Mạnh", "Nông Khánh Ngân", "Nguyễn Trung Nghĩa", "Lý Văn Quốc",
        "Triệu Hữu Quý", "Nguyễn Phạm Anh Thư", "Ma Thị Thanh Trúc", "Nông Đức Trung", "Hoàng Anh Tú"
    ],
    "1C1": [
        "Vương Huyền Anh", "Quan Việt Bách", "Hoàng Thị Thùy Chang", "Hoàng Quỳnh Diễm", "Triệu Thị Dung",
        "Triệu Quang Hải", "Lưu Nhật Khang", "Vương Minh Khôi", "Vương Phúc Lâm", "Triệu Càn Linh",
        "Vương Đặng Minh Nhật", "Vàng Nguyệt Nhi", "Lưu Đức Thành", "Lưu Mạnh Thường"
    ],
    "1D1": [
        "Triệu Gia Bảo", "Đặng Khánh Duy", "Trần Văn Đức"
    ],
    "2A1": [
        "Triệu Tường An", "Bàn Hải Anh", "Hoàng Băng Băng", "Tô Ngọc Quỳnh Chi", "Ma Công Duy",
        "Chẩu Văn Hậu", "Đỗ Gia Huy", "Ma Trí Kiên", "Ma Việt Lâm", "Ma Doãn Long",
        "Quan Thị Trà My", "Chẩu Thị Thiên Mỹ", "Hoàng Mai Ngân", "Phạm Duy Nhất", "Nông Diễm Nhi",
        "Nguyễn Hoàng Oanh", "Nông Thiên Phúc", "Ma Xuân Quang", "Hoàng Thái Sơn", "Đặng Thị Thùy Tâm",
        "Mai Duy Thịnh", "Hoàng Thị Thơ", "Hoàng Anh Thư", "Hoàng Minh Vương", "Ma Hà Xuân"
    ],
    "2B1": [
        "Hoàng Trâm Anh", "Ma Quỳnh Anh", "Trần Văn Ân", "Hoàng Quốc Bảo", "Dương Minh Châu",
        "Hoàng Khánh Chi", "Cứ A Cử", "Hoàng Ánh Dương", "Triệu Ánh Dương", "Hoàng Ngọc Hân",
        "Triệu Gia Hưng", "Lý Bảo Khang", "Ma Minh Khôi", "Hoàng Tuấn Kiệt", "Lý Thu Liễu",
        "Ma Thị Huyền My", "Ma Trọng Nghĩa", "Hoàng Bích Ngọc", "Vương Văn Phong", "Hoàng Đức Phúc",
        "Ma Đình Quân", "Hoàng Mai Tâm", "Quan Tiến Thành", "Hồ Sỹ Tiến", "Ma Đức Toàn",
        "Lý Ngọc Tường Vy", "Quan Thị Tường Vy"
    ],
    "2C1": [
        "Lưu Nguyễn Ngọc Hà", "Vương Gia Hào", "Hoàng Văn Hòa", "Lưu Thanh Kiều", "Vương Linh Lan",
        "Quan Bảo Long", "Quan Yến Nhi", "Bàn Thừa Phong", "Vương Kiều Nhã Phương", "Quan Tú Thanh"
    ],
    "2D1": [
        "Bàn Hữu Hưởng", "Bàn Hữu Khiển", "Bàn Hữu Nhân", "Bàn Hữu Phúc", "Đặng Thúy Phương",
        "Hoàng Đức Quân", "Triệu Thị Hồng Thơm"
    ],
    "3A1": [
        "Hoàng Hoài An", "Ma Thị Hoài An", "Bùi Phạm Bảo Anh", "Đặng Ngọc Anh", "Nguyễn Gia Bảo",
        "Chu Bảo Công", "Ma Ngọc Diễm", "Lý Anh Dũng", "Triệu Tiến Dũng", "Trần Duy Đạt",
        "Triệu Tiến Đạt", "Ma Ngọc Hân", "Hoàng Phúc Hiếu", "Hoàng Đức Hòa", "Chẩu Duy Hùng",
        "Nguyễn Gia Hưng", "Đặng Tuấn Khương", "Đoàn Lê Tiến Minh", "Ma Hoàng Nam", "Hà Hạnh Nguyên",
        "Quan Thị Quỳnh Như", "Hoàng Thúy Phượng", "Ma Thị Như Quỳnh", "Ma Quang Thái", "Quan Thị Thục",
        "Hoàng Minh Thư", "Hoàng Minh Toàn", "Vương Bảo Trâm", "Lý Nhã Uyên", "Hoàng Thế Việt"
    ],
    "3B1": [
        "Hoàng Gia Bảo", "Hoàng Quốc Bảo", "Quan Quốc Bảo", "Vương Ngọc Diệp", "Lý Văn Duy",
        "Phùng Nguyên Hải", "Quan Khả Hân", "Nguyễn Xuân Hòa", "Tạ Minh Hoàng", "Hà Đăng Khoa",
        "Quan Ngọc Lan", "Bàn Thị Hương Linh", "Đinh Trúc Linh", "Đỗ Nhật Minh", "Ma Nguyễn Nhật Minh",
        "Vương Thị Trà My", "Ma Khánh Ngân", "Hoàng Bảo Ngọc", "Quan Đình Phong", "Đặng Trường Quyết",
        "Ma Ngọc Trường Sơn", "Bàn Kim Thanh", "Hứa Văn Thanh", "Lý Thị Hoài Thu", "Ma Thu Thủy",
        "Bàn Thanh Thượng", "Quan Văn Toàn", "Hoàng Minh Tú", "Quan Việt Tuấn", "Hoàng Khánh Vy"
    ],
    "3C1": [
        "Thào Yến Chi", "Lưu Gia Hân", "Quan Nhật Lân", "Bàn Thị Nga", "Đoàn An Nhiên",
        "Quan Nhã Phương", "Lưu Xuân Thái", "Sùng Đức Thanh", "Quan Hà Trúc", "Chúc Anh Tuấn",
        "Quan Anh Tuấn"
    ],
    "3D1": [
        "Chúc Thanh Dương", "Đặng Thị Bảo Hân", "Trần Duy Khang", "Trần Thị Lai", "Trần An Nhiên",
        "Đặng Hồng Nhung", "Trần Thị Hà Phương", "Trần Việt Thắng", "Triệu Phúc Thịnh"
    ],
    "4A1": [
        "Lý Thị Ngọc Ánh", "Hứa Anh Bảo", "Mai Gia Bảo", "Triệu Tiến Bảo", "Trần Thanh Bình",
        "Lý Ngọc Chung", "Quan Hoàng Dân", "Hoàng Kim Ánh Dương", "Ma An Đông", "Ma Thị Ngọc Hà",
        "Cứ A Hùng", "Ma Văn Huy", "Quan Hán Khang", "Nguyễn Bảo Lộc", "Nguyễn Thị Thảo Ly",
        "Đặng Thị Trúc Mai", "Hoàng Hà My", "Ma Thị Kim Ngân", "Trương Thị Kim Ngân", "Chẩu Thị Bảo Ngọc",
        "Nông Thị Khánh Ngọc", "Lý Khánh Nguyên", "Nguyễn Bá Thanh", "Quàng Ngọc Thành", "Đinh Thanh Thảo",
        "Lý Quốc Thịnh", "Quan Việt Tùng", "Bàn Thị Mỹ Tư"
    ],
    "4B1": [
        "Luân Thị Phương Anh", "Đặng Quốc Bảo", "Chu Yến Chi", "Quan Khánh Chi", "Hoàng Đức Cương",
        "Trương Cao Cường", "Nguyễn Hồng Diễm", "Đặng Thị Định", "Hoàng Mai Hải", "Tô Quang Hiếu",
        "Lý An Hưng", "Hoàng Bảo Khang", "Nguyễn Duy Khánh", "Triệu Duy Khiêm", "Nguyễn Bá Kim",
        "Ma Thị Thảo Ly", "Hoàng Hà My", "Hoàng Thị Tâm Như", "Lý Ngọc Kiều Oanh", "Lý Bảo Quang",
        "Quan Văn Quý", "Trần Xuân Quý", "Nguyễn Trọng Thanh", "Nguyễn Khánh Thi", "Ma Văn Tiến",
        "Hoàng Thị Thanh Trúc", "Ma Mạnh Tùng", "Hoàng Đức Uy"
    ],
    "4C1": [
        "Lưu Thế Anh", "Hoàng Thu Hương", "Trần Thị Thùy Linh", "Vàng Hiếu Minh", "Vương Trọng Phú",
        "Vương Văn Quyền", "Quan Hà Trang", "Lưu Tiểu Tuệ", "Vương Phương Uyên"
    ],
    "4D1": [
        "Triệu Gia Bảo", "Trần Văn Đạt", "Đặng Tân Hưng", "Bàn Tiến Kim", "Trần Bảo Nam",
        "Đặng Quỳnh Nga", "Trần Văn Phúc", "Triệu Tuấn Thành"
    ],
    "5A1": [
        "Ma Việt Anh", "Bùi Gia Bảo", "Ma Thị Ngọc Bích", "Cứ Thị Chiên", "Bàn Văn Cương",
        "Ma Hoàng Diễn", "Hoàng Thị Bích Diệp", "Chẩu Thị Hiền Diệu", "Hoàng Đức Duy", "Ma Văn Giang",
        "Lý Thị Hà", "Lý Khánh Huy", "Quan Quốc Hưng", "Ma Duy Khang", "Hoàng Quốc Khánh",
        "Lý Bảo Khánh", "Ma Duy Khôi", "Lý Thị Kim Khuyên", "Quan Ngọc Lan", "Nông Ngọc Lân",
        "Ma Duy Mạnh", "Ma Khôi Nguyên", "Quan Văn Phát", "Bùi Thu Thủy", "Ma Thị Thanh Thúy",
        "Tô Anh Việt"
    ],
    "5B1": [
        "Đặng Thị Hoài An", "Hoàng Ngọc Bích", "Lương Thanh Bình", "Hà Bảo Duy", "Hoàng Đức Hân",
        "Ma Gia Hiếu", "Sằm Việt Hoàng", "Lý Thị Hồng Huệ", "Bàn Khánh Huy", "Chu Văn Khánh",
        "Ma Bảo Khánh", "Ma Trung Kiên", "Ma Hoàng Long", "Nguyễn Phúc Lộc", "Hoàng Tuệ Minh",
        "Hoàng Minh Ngọc", "Hoàng Linh Nhi", "Hoàng Quốc Phong", "Vương Ngọc Thái", "Quan Việt Thanh",
        "Vương Thị Thu Thảo", "Quan Thanh Trà", "Ma Thành Tuyên", "Hoàng Văn Tự", "Lý Công Vinh",
        "Ma Bích Xuân"
    ],
    "5C1": [
        "Hoàng Yến Cúc", "Nguyễn Thị Thanh Hà", "Hoàng Bảo Lan", "Vàng Văn Phong", "Quan Hào Sang",
        "Bàn Anh Thiện"
    ],
    "5D1": [
        "Đặng Thị Chang", "Trần Mạnh Cường", "Triệu Phúc Cường", "Trần Duy Khánh", "Bàn Văn Long",
        "Triệu Hảo Minh", "Bàn Thị Quỳnh Như", "Trần Thúy Thảo"
    ],
}

CUSTOM_STUDENTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_students.json")


def load_students_by_class():
    """Trả về dict {'1A1': ['Ma Bảo An', ...], ...} từ file cập nhật hoặc mặc định."""
    if os.path.exists(CUSTOM_STUDENTS_PATH):
        try:
            with open(CUSTOM_STUDENTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        except Exception:
            pass
    return {k: list(v) for k, v in DEFAULT_STUDENTS_BY_CLASS.items()}


def save_students_by_class(data):
    """Lưu danh sách học sinh mới import vào custom_students.json."""
    try:
        with open(CUSTOM_STUDENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _is_valid_class_code(code):
    """Kiểm tra mã lớp hợp lệ của bậc Tiểu học (ví dụ: 1A, 1A1, 2B1, 5D1...)."""
    if not code:
        return False
    code = str(code).strip().upper()
    return bool(re.match(r"^[1-5][A-ZĐ]\d*$", code))


def parse_csdl_rows(rows):
    """
    Quét danh sách các dòng (từ CSV hoặc Excel xuất trực tiếp của CSDL ngành).
    Tự động tìm dòng tiêu đề có 'Mã lớp' và 'Họ tên' (bỏ qua toàn bộ các bảng danh mục Tỉnh/Xã/Dân tộc),
    lọc bỏ học sinh 'Chuyển đi' hoặc 'Thôi học', và trích xuất {'1A1': ['Họ tên', ...]}.
    """
    col_class, col_name, col_status = None, None, None
    extracted = {}

    for row in rows:
        cells = [str(c or "").strip() for c in row]
        if not any(cells):
            continue

        # Tìm dòng header chứa cả "Mã lớp" và "Họ tên" (hoặc "Họ và tên")
        lower_cells = [c.lower() for c in cells]
        if "mã lớp" in lower_cells and any(h in lower_cells for h in ("họ tên", "họ và tên")):
            col_class = lower_cells.index("mã lớp")
            for idx, h in enumerate(lower_cells):
                if h in ("họ tên", "họ và tên"):
                    col_name = idx
                    break
            for idx, h in enumerate(lower_cells):
                if "trạng thái" in h:
                    col_status = idx
                    break
            continue

        # Nếu đã tìm thấy dòng tiêu đề của bảng học sinh
        if col_class is not None and col_name is not None:
            if len(cells) <= max(col_class, col_name):
                continue
            cls_code = cells[col_class].strip().upper()
            full_name = " ".join(cells[col_name].split())
            if not _is_valid_class_code(cls_code) or not full_name:
                continue
            # Kiểm tra trạng thái học sinh (bỏ qua nếu đã chuyển đi / thôi học)
            if col_status is not None and len(cells) > col_status:
                st_text = cells[col_status].lower()
                if "chuyển đi" in st_text or "thôi học" in st_text:
                    continue
            extracted.setdefault(cls_code, [])
            if full_name not in extracted[cls_code]:
                extracted[cls_code].append(full_name)

    return extracted


def _merge_extracted(target, source):
    for cls_code, names in source.items():
        target.setdefault(cls_code, [])
        for name in names:
            if name not in target[cls_code]:
                target[cls_code].append(name)


def import_csdl_file(uploaded_file):
    """
    Nhận file upload từ Streamlit (.xls, .xlsx, .csv, .txt) xuất trực tiếp từ phần mềm CSDL ngành.
    Tự động quét các sheet, chỉ lấy 'Mã lớp' và 'Họ tên' mà không cần giáo viên chỉnh sửa file.
    Trả về (dict_ket_qua, thong_bao_loi).
    """
    try:
        raw = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
        fname = getattr(uploaded_file, "name", "").lower()
        merged = {}

        # 1. File Excel .xls (BIFF8 - định dạng chuẩn xuất từ CSDL ngành GD&ĐT)
        if raw[:4] == b"\xd0\xcf\x11\xe0" or fname.endswith(".xls"):
            import xlrd
            wb = xlrd.open_workbook(file_contents=raw)
            for sh in wb.sheets():
                rows = [sh.row_values(r) for r in range(sh.nrows)]
                _merge_extracted(merged, parse_csdl_rows(rows))
            if not merged:
                return {}, "Không tìm thấy cột 'Mã lớp' và 'Họ tên' hợp lệ của khối 1-5 trong file Excel (.xls)."
            return dict(sorted(merged.items())), ""

        # 2. File Excel .xlsx
        if raw[:4] == b"PK\x03\x04" or fname.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            for sh in wb.worksheets:
                rows = list(sh.iter_rows(values_only=True))
                _merge_extracted(merged, parse_csdl_rows(rows))
            if not merged:
                return {}, "Không tìm thấy cột 'Mã lớp' và 'Họ tên' hợp lệ của khối 1-5 trong file Excel (.xlsx)."
            return dict(sorted(merged.items())), ""

        # 3. File CSV / TXT
        text = None
        for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1258", "latin1"):
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue
        if text is None:
            return {}, "Không đọc được bảng mã ký tự của file."
        reader = csv.reader(io.StringIO(text))
        result = parse_csdl_rows(reader)
        if not result:
            return {}, "Không tìm thấy cột 'Mã lớp' và 'Họ tên' hợp lệ của khối 1-5 trong file."
        return dict(sorted(result.items())), ""
    except Exception as e:
        return {}, f"Lỗi khi đọc file: {e}"
