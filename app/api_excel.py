"""محرك الاستيراد والتصدير الشامل لملفات Excel (.xlsx / .csv) لجميع أقسام النظام (100% Offline، معزول بنظام Modular Plug-and-Play) مع معاينة ومقارنة وحوار حفظ أصلي."""
import base64
import csv
import datetime
import io
import pathlib
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import escape as _xml_esc

import db
import erp_hooks
from api_common import ApiError, _STATE, _fmt_money, _int, _money


def _col_letter(idx: int) -> str:
    res = ""
    n = idx + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        res = chr(65 + rem) + res
    return res


def _build_xlsx_bytes(sheets: list[tuple[str, list[str], list[list]]]) -> bytes:
    """بناء ملف Excel OpenXML (.xlsx) أصلي متعدد الأوراق بدون أي مكتبات خارجية."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        sheet_overrides = []
        wb_sheets = []
        wb_rels = []
        for idx, (title, headers, rows) in enumerate(sheets, start=1):
            safe_title = "".join(ch for ch in str(title) if ch not in r'[]:*?/\\')[:31] or f"Sheet{idx}"
            sheet_overrides.append(
                f'<Override PartName="/xl/worksheets/sheet{idx}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )
            wb_sheets.append(f'<sheet name="{_xml_esc(safe_title)}" sheetId="{idx}" r:id="rId{idx}"/>')
            wb_rels.append(
                f'<Relationship Id="rId{idx}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{idx}.xml"/>'
            )

            col_widths = [max(14, min(42, len(str(h)) + 6)) for h in headers]
            for r in rows[:200]:
                for c_i, val in enumerate(r):
                    if c_i < len(col_widths):
                        col_widths[c_i] = max(col_widths[c_i], min(45, len(str(val if val is not None else "")) + 4))
            cols_xml = "<cols>" + "".join(
                f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>'
                for i, w in enumerate(col_widths)
            ) + "</cols>"

            xml_rows = []
            all_rows = [headers] + list(rows)
            for r_i, row_vals in enumerate(all_rows, start=1):
                cells = []
                for c_i, val in enumerate(row_vals):
                    ref = f"{_col_letter(c_i)}{r_i}"
                    style = ' s="1"' if r_i == 1 else ""
                    if r_i > 1 and isinstance(val, (int, float)) and not isinstance(val, bool):
                        cells.append(f'<c r="{ref}"{style}><v>{val}</v></c>')
                    else:
                        txt = _xml_esc("" if val is None else str(val))
                        cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{txt}</t></is></c>')
                xml_rows.append(f'<row r="{r_i}">' + "".join(cells) + "</row>")

            sheet_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetViews><sheetView rightToLeft="1" workbookViewId="0"/></sheetViews>'
                f"{cols_xml}<sheetData>{''.join(xml_rows)}</sheetData></worksheet>"
            )
            zf.writestr(f"xl/worksheets/sheet{idx}.xml", sheet_xml.encode("utf-8"))

        zf.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                + "".join(sheet_overrides)
                + "</Types>"
            ).encode("utf-8"),
        )
        zf.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                "</Relationships>"
            ).encode("utf-8"),
        )
        zf.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f"<sheets>{''.join(wb_sheets)}</sheets></workbook>"
            ).encode("utf-8"),
        )
        wb_rels.append(
            f'<Relationship Id="rId{len(sheets)+1}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + "".join(wb_rels)
                + "</Relationships>"
            ).encode("utf-8"),
        )
        zf.writestr(
            "xl/styles.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<fonts count="2">'
                '<font><sz val="11"/><name val="Calibri"/></font>'
                '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
                '</fonts>'
                '<fills count="3">'
                '<fill><patternFill patternType="none"/></fill>'
                '<fill><patternFill patternType="gray125"/></fill>'
                '<fill><patternFill patternType="solid"><fgColor rgb="FF137FEC"/><bgColor indexed="64"/></patternFill></fill>'
                '</fills>'
                '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
                '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                '<cellXfs count="2">'
                '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
                '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
                '</cellXfs></styleSheet>'
            ).encode("utf-8"),
        )
    return buf.getvalue()


def _col_index_from_ref(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - 64)
    return max(0, idx - 1)


def _parse_xlsx_bytes(raw: bytes) -> list[list[str]]:
    """قراءة الورقة الأولى من ملف .xlsx الأصلي باستخدام مكتبة بايثون القياسية فقط."""
    rows_out = []
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.iter():
                if si.tag.endswith("}si") or si.tag == "si":
                    parts = []
                    for t in si.iter():
                        if (t.tag.endswith("}t") or t.tag == "t") and t.text:
                            parts.append(t.text)
                    shared.append("".join(parts))

        sheet_names = sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        if not sheet_names:
            raise ApiError("ملف Excel لا يحتوي على أي ورقة عمل صالحة")
        ws_root = ET.fromstring(zf.read(sheet_names[0]))
        for row_el in ws_root.iter():
            if not (row_el.tag.endswith("}row") or row_el.tag == "row"):
                continue
            row_map = {}
            max_c = -1
            for c_el in row_el:
                if not (c_el.tag.endswith("}c") or c_el.tag == "c"):
                    continue
                ref = c_el.attrib.get("r", "")
                c_idx = _col_index_from_ref(ref) if ref else (max_c + 1)
                max_c = max(max_c, c_idx)
                c_type = c_el.attrib.get("t", "")
                val = ""
                if c_type == "inlineStr":
                    parts = [t.text for t in c_el.iter() if (t.tag.endswith("}t") or t.tag == "t") and t.text]
                    val = "".join(parts)
                elif c_type == "s":
                    v_el = next((ch for ch in c_el if ch.tag.endswith("}v") or ch.tag == "v"), None)
                    if v_el is not None and v_el.text is not None:
                        try:
                            val = shared[int(v_el.text)]
                        except Exception:
                            val = v_el.text
                else:
                    v_el = next((ch for ch in c_el if ch.tag.endswith("}v") or ch.tag == "v"), None)
                    if v_el is not None and v_el.text is not None:
                        val = v_el.text
                row_map[c_idx] = str(val).strip()
            if max_c >= 0:
                row_list = [row_map.get(i, "") for i in range(max_c + 1)]
                if any(cell != "" for cell in row_list):
                    rows_out.append(row_list)
    return rows_out


def _parse_csv_bytes(raw: bytes) -> list[list[str]]:
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1256", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        raise ApiError("تعذر قراءة ترميز ملف CSV")
    sample = text[:2048]
    delim = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    return [[str(c).strip() for c in r] for r in reader if any(str(c).strip() for c in r)]


def _parse_spreadsheet_payload(file_base64: str, filename: str = "import.xlsx") -> list[list[str]]:
    if not file_base64 or not isinstance(file_base64, str):
        raise ApiError("ملف الاستيراد فارغ أو غير صالح")
    b64 = file_base64.split(",", 1)[1] if "," in file_base64 else file_base64
    try:
        raw = base64.b64decode(b64)
    except Exception:
        raise ApiError("تعذر فك تشفير بيانات الملف المرفوع")
    if len(raw) > 15 * 1024 * 1024:
        raise ApiError("حجم الملف يتجاوز الحد الأقصى المسموح (15 ميجابايت)")
    fn_low = str(filename or "").lower()
    if raw[:2] == b"PK" or fn_low.endswith(".xlsx"):
        return _parse_xlsx_bytes(raw)
    return _parse_csv_bytes(raw)


def _exports_dir() -> pathlib.Path:
    d = pathlib.Path(db.db_path()).resolve().parent / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_active_webview_window():
    win = _STATE.get("window")
    if win is not None:
        return win
    try:
        import webview
        wins = getattr(webview, "windows", None) or []
        if wins:
            return wins[0]
    except Exception:
        pass
    return None


def _save_xlsx_with_dialog(xlsx_bytes: bytes, default_filename: str, prompt_save: bool = True) -> dict:
    """فتح نافذة الحفظ الأصلية في ويندوز (Save As) عند تشغيل التطبيق، مع حفظ احتياطي تلقائي في وضع الاختبار."""
    win = _get_active_webview_window() if prompt_save else None
    if win is not None:
        try:
            import webview
            save_type = getattr(getattr(webview, "FileDialog", None), "SAVE", getattr(webview, "SAVE_DIALOG", 30))
            desktop_dir = pathlib.Path.home() / "Desktop"
            start_dir = str(desktop_dir if desktop_dir.exists() else _exports_dir())
            chosen = win.create_file_dialog(
                save_type,
                directory=start_dir,
                save_filename=default_filename,
                file_types=("Excel Workbook (*.xlsx)", "All files (*.*)"),
            )
            if isinstance(chosen, (list, tuple)):
                chosen = chosen[0] if chosen else ""
            chosen_str = str(chosen or "").strip()
            if not chosen_str:
                return {
                    "cancelled": True,
                    "saved_via_dialog": True,
                    "file_name": default_filename,
                    "file_path": "",
                }
            target = pathlib.Path(chosen_str)
            if target.suffix.lower() != ".xlsx":
                target = target.with_suffix(".xlsx")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(xlsx_bytes)
            return {
                "cancelled": False,
                "saved_via_dialog": True,
                "file_name": target.name,
                "file_path": str(target),
            }
        except Exception:
            pass

    fpath = _exports_dir() / default_filename
    fpath.write_bytes(xlsx_bytes)
    return {
        "cancelled": False,
        "saved_via_dialog": False,
        "file_name": default_filename,
        "file_path": str(fpath),
    }


def _norm_header(h: str) -> str:
    return " ".join(str(h or "").strip().lower().replace("_", " ").replace("-", " ").split())


def _fmt_num_diff(v) -> str:
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v if v is not None else "")


# خريطة الأقسام المدعومة في محرك الاستيراد والتصدير الشامل (مع ربط كل قسم بوحدته المعزولة Modular Plug-and-Play)
EXCEL_ENTITIES = [
    {
        "key": "products",
        "title_ar": "المنتجات والمخزون",
        "title_en": "Products & Inventory",
        "module": "inventory",
        "perm_export": "inventory_view",
        "perm_import": "inventory_edit",
        "can_import": True,
        "headers": ["الكود / SKU", "اسم المنتج", "التصنيف", "سعر البيع", "التكلفة", "الكمية", "الحد الأدنى", "متتبع بالسيريال (0/1)", "ملاحظات"],
        "sample": ["SKU-1001", "شاحن سريع 65 واط", "إكسسوارات", 450, 300, 15, 3, 0, "صنف تجريبي"],
    },
    {
        "key": "categories",
        "title_ar": "التصنيفات والفئات",
        "title_en": "Categories",
        "module": "inventory",
        "perm_export": "inventory_view",
        "perm_import": "inventory_edit",
        "can_import": True,
        "headers": ["اسم التصنيف", "عدد المنتجات"],
        "sample": ["إكسسوارات الهواتف", 0],
    },
    {
        "key": "customers",
        "title_ar": "العملاء وحدود الائتمان",
        "title_en": "Customers & Credit Limits",
        "module": "customers",
        "perm_export": "customers_view",
        "perm_import": "customers_edit",
        "can_import": True,
        "headers": ["اسم العميل", "رقم الهاتف", "حد الائتمان", "إجمالي المشتريات", "المديونية الحالية"],
        "sample": ["أحمد محمد علي", "01012345678", 5000, 0, 0],
    },
    {
        "key": "suppliers",
        "title_ar": "الموردون",
        "title_en": "Suppliers",
        "module": "purchases",
        "perm_export": "purchases_view",
        "perm_import": "purchases_create_post",
        "can_import": True,
        "headers": ["اسم المورد", "اسم الشركة", "رقم الهاتف", "الرقم الضريبي", "فترة الائتمان (أيام)", "العنوان", "الرصيد الافتتاحي"],
        "sample": ["شركة النور للتوريدات", "النور تكنولوجي", "01099988877", "123-456-789", 30, "القاهرة", 0],
    },
    {
        "key": "accounts",
        "title_ar": "شجرة الحسابات (COA)",
        "title_en": "Chart of Accounts (COA)",
        "module": "accounting",
        "perm_export": "accounting_view",
        "perm_import": "accounting_coa_manage",
        "can_import": True,
        "headers": ["كود الحساب", "اسم الحساب", "النوع (asset/liability/equity/revenue/expense)", "كود الحساب الأب", "حساب رئيسي (0/1)"],
        "sample": ["5299", "مصروفات نثرية مخصصة", "expense", "52", 0],
    },
    {
        "key": "translations",
        "title_ar": "قاموس الترجمة (عربي / إنجليزي)",
        "title_en": "Translations Dictionary (AR/EN)",
        "module": "settings",
        "perm_export": "settings_view_edit",
        "perm_import": "settings_view_edit",
        "can_import": True,
        "headers": ["النص العربي", "الترجمة الإنجليزية", "القسم"],
        "sample": ["تسجيل الدخول", "Sign In", "login"],
    },
    {
        "key": "sales",
        "title_ar": "سجل المبيعات والفواتير",
        "title_en": "Sales Invoices History",
        "module": "history",
        "perm_export": "history_view_all",
        "perm_import": None,
        "can_import": False,
        "headers": ["رقم الفاتورة", "التاريخ", "العميل", "الهاتف", "المجموع الفرعي", "الخصم", "الضريبة", "الإجمالي", "الحالة", "الموظف"],
        "sample": [],
    },
    {
        "key": "expenses",
        "title_ar": "المصروفات التشغيلية",
        "title_en": "Operating Expenses",
        "module": "accounting",
        "perm_export": "accounting_view",
        "perm_import": None,
        "can_import": False,
        "headers": ["رقم السند", "التاريخ", "الوصف / البيان", "المبلغ", "طريقة الدفع", "ملاحظات"],
        "sample": [],
    },
    {
        "key": "repairs",
        "title_ar": "تذاكر مركز الصيانة",
        "title_en": "Repair Tickets",
        "module": "repair",
        "perm_export": "repair_view",
        "perm_import": None,
        "can_import": False,
        "headers": ["رقم التذكرة", "التاريخ", "العميل", "الهاتف", "الجهاز", "العطل", "الحالة", "التكلفة"],
        "sample": [],
    },
    {
        "key": "installments",
        "title_ar": "عقود نظام الأقساط",
        "title_en": "Installment Contracts",
        "module": "installments",
        "perm_export": "installments_view",
        "perm_import": None,
        "can_import": False,
        "headers": ["رقم العقد", "التاريخ", "العميل", "إجمالي الفاتورة", "المقدم", "المبلغ الممول", "عدد الأقساط", "الحالة"],
        "sample": [],
    },
]

_ENTITY_MAP = {e["key"]: e for e in EXCEL_ENTITIES}


class ExcelMixin:
    def _entity_meta(self, conn, entity: str) -> dict:
        key = str(entity or "").strip().lower()
        meta = _ENTITY_MAP.get(key)
        if not meta:
            raise ApiError(f"القسم غير مدعوم للاستيراد/التصدير: {entity}")
        mod = meta["module"]
        if mod != "settings" and not erp_hooks.is_module_active(self, conn, mod):
            raise ApiError(f"القسم ({meta['title_ar']}) معطل حالياً من إعدادات المالك")
        return meta

    def _collect_export_rows(self, conn, key: str) -> list[list]:
        rows = []
        if key == "products":
            show_cost = self._has_perm("cost_view")
            for r in conn.execute(
                """SELECT p.sku, p.name, COALESCE(c.name,'') cat, p.price, p.cost, p.qty, p.min_qty, p.tracked, COALESCE(p.notes,'') notes
                   FROM products p LEFT JOIN categories c ON c.id=p.category_id
                   WHERE p.active=1 ORDER BY p.name"""
            ).fetchall():
                rows.append([
                    r["sku"], r["name"], r["cat"],
                    round((r["price"] or 0) / 100.0, 2),
                    round((r["cost"] or 0) / 100.0, 2) if show_cost else 0,
                    int(r["qty"] or 0), int(r["min_qty"] or 0), int(r["tracked"] or 0), r["notes"],
                ])
        elif key == "categories":
            for r in conn.execute(
                """SELECT c.name, COUNT(p.id) cnt FROM categories c
                   LEFT JOIN products p ON p.category_id=c.id AND p.active=1
                   GROUP BY c.id ORDER BY c.name"""
            ).fetchall():
                rows.append([r["name"], int(r["cnt"] or 0)])
        elif key == "customers":
            can_debt = self._has_perm("customers_debt_view")
            for r in conn.execute(
                "SELECT name, COALESCE(phone,'') phone, COALESCE(credit_limit,0) cl, total_purchases, debt FROM customers ORDER BY name"
            ).fetchall():
                rows.append([
                    r["name"], r["phone"],
                    round((r["cl"] or 0) / 100.0, 2) if can_debt else 0,
                    round((r["total_purchases"] or 0) / 100.0, 2) if can_debt else 0,
                    round((r["debt"] or 0) / 100.0, 2) if can_debt else 0,
                ])
        elif key == "suppliers":
            for r in conn.execute(
                "SELECT name, COALESCE(company,'') company, COALESCE(phone,'') phone, COALESCE(tax_reg_no,'') tax_reg, COALESCE(credit_terms_days,30) terms, COALESCE(address,'') addr, COALESCE(opening_balance,0) ob FROM suppliers WHERE active=1 ORDER BY name"
            ).fetchall():
                rows.append([r["name"], r["company"], r["phone"], r["tax_reg"], int(r["terms"] or 0), r["addr"], round((r["ob"] or 0) / 100.0, 2)])
        elif key == "accounts":
            by_id = {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM accounts").fetchall()}
            for r in conn.execute("SELECT code, name, type, parent_id, is_group FROM accounts WHERE active=1 ORDER BY code").fetchall():
                rows.append([r["code"], r["name"], r["type"], by_id.get(r["parent_id"], ""), int(r["is_group"] or 0)])
        elif key == "translations":
            for r in conn.execute("SELECT ar_text, en_text, section FROM translations ORDER BY section, id").fetchall():
                rows.append([r["ar_text"], r["en_text"], r["section"]])
        elif key == "sales":
            for r in conn.execute(
                """SELECT s.invoice_no, s.created_at, COALESCE(s.customer_name,'') cname, COALESCE(s.customer_phone,'') cph,
                          s.subtotal, s.discount, s.tax, s.total, s.status, COALESCE(u.name,'') uname
                   FROM sales s LEFT JOIN users u ON u.id=s.user_id ORDER BY s.id DESC LIMIT 5000"""
            ).fetchall():
                rows.append([
                    r["invoice_no"], r["created_at"], r["cname"], r["cph"],
                    round((r["subtotal"] or 0) / 100.0, 2), round((r["discount"] or 0) / 100.0, 2),
                    round((r["tax"] or 0) / 100.0, 2), round((r["total"] or 0) / 100.0, 2),
                    r["status"], r["uname"],
                ])
        elif key == "expenses":
            for r in conn.execute(
                "SELECT expense_no, expense_date, description, amount, payment_method, COALESCE(notes,'') notes FROM expenses ORDER BY id DESC LIMIT 5000"
            ).fetchall():
                rows.append([r["expense_no"], r["expense_date"], r["description"], round((r["amount"] or 0) / 100.0, 2), r["payment_method"], r["notes"]])
        elif key == "repairs":
            for r in conn.execute(
                "SELECT ref, created_at, COALESCE(customer_name,'') cn, COALESCE(customer_phone,'') cp, device_type, problem, status, cost FROM repairs ORDER BY id DESC LIMIT 5000"
            ).fetchall():
                rows.append([r["ref"], r["created_at"], r["cn"], r["cp"], r["device_type"], r["problem"], r["status"], round((r["cost"] or 0) / 100.0, 2)])
        elif key == "installments":
            for r in conn.execute(
                """SELECT ip.plan_no, ip.created_at, COALESCE(c.name,'') cn, ip.total_amount, ip.down_payment, ip.financed_total, ip.months, ip.status
                   FROM installment_plans ip LEFT JOIN customers c ON c.id=ip.customer_id ORDER BY ip.id DESC LIMIT 5000"""
            ).fetchall():
                rows.append([
                    r["plan_no"], r["created_at"], r["cn"],
                    round((r["total_amount"] or 0) / 100.0, 2), round((r["down_payment"] or 0) / 100.0, 2),
                    round((r["financed_total"] or 0) / 100.0, 2), int(r["months"] or 0), r["status"],
                ])
        return rows

    def excel_entities_list(self):
        """إرجاع قائمة الأقسام المفعّلة المتاحة للاستيراد والتصدير مع عدد السجلات الحالي لكل قسم."""
        self._user()
        table_count_sql = {
            "products": "SELECT COUNT(*) c FROM products WHERE active=1",
            "categories": "SELECT COUNT(*) c FROM categories",
            "customers": "SELECT COUNT(*) c FROM customers",
            "suppliers": "SELECT COUNT(*) c FROM suppliers WHERE active=1",
            "accounts": "SELECT COUNT(*) c FROM accounts WHERE active=1",
            "translations": "SELECT COUNT(*) c FROM translations",
            "sales": "SELECT COUNT(*) c FROM sales",
            "expenses": "SELECT COUNT(*) c FROM expenses",
            "repairs": "SELECT COUNT(*) c FROM repairs",
            "installments": "SELECT COUNT(*) c FROM installment_plans",
        }
        out = []
        with db.connect() as conn:
            for meta in EXCEL_ENTITIES:
                mod = meta["module"]
                if mod != "settings" and not erp_hooks.is_module_active(self, conn, mod):
                    continue
                if not self._has_perm(meta["perm_export"]):
                    continue
                cnt = 0
                try:
                    cnt = conn.execute(table_count_sql[meta["key"]]).fetchone()["c"]
                except Exception:
                    cnt = 0
                out.append({
                    "key": meta["key"],
                    "title_ar": meta["title_ar"],
                    "title_en": meta["title_en"],
                    "module": mod,
                    "count": cnt,
                    "can_export": True,
                    "can_import": bool(meta["can_import"] and meta["perm_import"] and self._has_perm(meta["perm_import"])),
                    "headers": meta["headers"],
                })
        return out

    def excel_template(self, entity="products", prompt_save=True):
        """توليد ملف قالب Excel (.xlsx) جاهز للتعبئة والاستيراد مع فتح نافذة الحفظ الأصلية لاختيار المسار."""
        with db.connect() as conn:
            meta = self._entity_meta(conn, entity)
            self._perm(meta["perm_export"])
        sample_rows = [meta["sample"]] if meta.get("sample") else []
        xlsx_bytes = _build_xlsx_bytes([(meta["title_ar"], meta["headers"], sample_rows)])
        fname = f"template_{meta['key']}.xlsx"
        saved = _save_xlsx_with_dialog(xlsx_bytes, fname, prompt_save=bool(prompt_save))
        if saved.get("cancelled"):
            return {
                "entity": meta["key"],
                "cancelled": True,
                "saved_via_dialog": True,
                "file_name": fname,
                "file_path": "",
            }
        return {
            "entity": meta["key"],
            "cancelled": False,
            "saved_via_dialog": bool(saved.get("saved_via_dialog")),
            "file_name": saved["file_name"],
            "file_path": saved["file_path"],
            "base64_data": base64.b64encode(xlsx_bytes).decode("ascii"),
        }

    def excel_export_preview(self, entity="products"):
        """معاينة بيانات أي قسم مفعّل قبل التصدير لتمكين المستخدم من البحث وتحديد الصفوف والأعمدة المطلوبة."""
        with db.connect() as conn:
            meta = self._entity_meta(conn, entity)
            self._perm(meta["perm_export"])
            rows = self._collect_export_rows(conn, meta["key"])
        return {
            "entity": meta["key"],
            "title_ar": meta["title_ar"],
            "title_en": meta["title_en"],
            "headers": meta["headers"],
            "total": len(rows),
            "rows": [{"idx": i, "cells": r} for i, r in enumerate(rows)],
        }

    def excel_export(self, entity="products", selected_indices=None, selected_columns=None, prompt_save=True):
        """تصدير البيانات المحددة من أي قسم مفعّل إلى ملف Excel (.xlsx) أصلي مع فتح نافذة الحفظ (Save As)."""
        with db.connect() as conn:
            meta = self._entity_meta(conn, entity)
            self._perm(meta["perm_export"])
            key = meta["key"]
            all_rows = self._collect_export_rows(conn, key)

            if selected_indices is not None:
                if not isinstance(selected_indices, (list, tuple)):
                    raise ApiError("قائمة العناصر المحددة غير صالحة")
                idx_set = {int(i) for i in selected_indices if str(i).lstrip("-").isdigit()}
                rows = [r for i, r in enumerate(all_rows) if i in idx_set]
                if not rows:
                    raise ApiError("يرجى تحديد عنصر واحد على الأقل للتصدير")
            else:
                rows = all_rows

            headers = list(meta["headers"])
            if selected_columns is not None:
                if not isinstance(selected_columns, (list, tuple)):
                    raise ApiError("قائمة الأعمدة المحددة غير صالحة")
                col_idxs = sorted({int(c) for c in selected_columns if str(c).isdigit() and 0 <= int(c) < len(headers)})
                if not col_idxs:
                    raise ApiError("يرجى تحديد عمود واحد على الأقل للتصدير")
                headers = [headers[c] for c in col_idxs]
                rows = [[(r[c] if c < len(r) else "") for c in col_idxs] for r in rows]

            xlsx_bytes = _build_xlsx_bytes([(meta["title_ar"], headers, rows)])
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"export_{meta['key']}_{ts}.xlsx"
            saved = _save_xlsx_with_dialog(xlsx_bytes, fname, prompt_save=bool(prompt_save))
            if saved.get("cancelled"):
                return {
                    "entity": meta["key"],
                    "cancelled": True,
                    "saved_via_dialog": True,
                    "file_name": fname,
                    "file_path": "",
                    "rows_count": 0,
                }

            self._log_activity(
                conn,
                "excel_export",
                key,
                saved["file_name"],
                f"تصدير {len(rows)} سجل من قسم «{meta['title_ar']}» إلى ملف Excel",
                {"entity": key, "rows": len(rows), "file_path": saved["file_path"]},
                module_key=meta["module"],
            )

        return {
            "entity": meta["key"],
            "cancelled": False,
            "saved_via_dialog": bool(saved.get("saved_via_dialog")),
            "file_name": saved["file_name"],
            "file_path": saved["file_path"],
            "rows_count": len(rows),
            "base64_data": base64.b64encode(xlsx_bytes).decode("ascii"),
        }

    def excel_import_preview(self, entity="products", file_base64="", filename="import.xlsx"):
        """معاينة ومقارنة صفوف ملف Excel/CSV مع قاعدة البيانات الحالية (جديد / تعديل مع مقارنة الحقول / مطابق / خطأ) قبل التنفيذ."""
        self._user()
        with db.connect() as conn:
            meta = self._entity_meta(conn, entity)
            if not meta.get("can_import") or not meta.get("perm_import"):
                raise ApiError(f"قسم «{meta['title_ar']}» يدعم التصدير فقط حفاظاً على سلامة القيود المالية")
            self._perm(meta["perm_import"])

            raw_rows = _parse_spreadsheet_payload(file_base64, filename)
            if len(raw_rows) < 2:
                raise ApiError("الملف فارغ أو لا يحتوي على صفوف بيانات بعد صف العناوين")

            headers = [_norm_header(h) for h in raw_rows[0]]
            data_rows = raw_rows[1:]

            def col_idx(aliases: list[str], fallback: int | None = None) -> int | None:
                for al in aliases:
                    nal = _norm_header(al)
                    for i, h in enumerate(headers):
                        if h == nal or nal in h:
                            return i
                return fallback

            def cell(r: list[str], idx: int | None, default: str = "") -> str:
                if idx is None or idx < 0 or idx >= len(r):
                    return default
                return str(r[idx]).strip()

            key = meta["key"]
            preview_rows = []
            counts = {"total": 0, "new": 0, "update": 0, "unchanged": 0, "error": 0}

            def _add_row(row_idx: int, line_no: int, status: str, key_label: str, title: str, cells: list, diffs: list | None = None, note: str = ""):
                counts["total"] += 1
                counts[status] += 1
                preview_rows.append({
                    "row_idx": row_idx,
                    "line_no": line_no,
                    "status": status,
                    "key_label": key_label,
                    "title": title,
                    "cells": cells,
                    "diffs": diffs or [],
                    "note": note,
                })

            if key == "categories":
                i_name = col_idx(["اسم التصنيف", "التصنيف", "الفئة", "اسم الفئة", "category", "name"], 0)
                existing_cats = {r["name"] for r in conn.execute("SELECT name FROM categories").fetchall()}
                seen = set()
                for idx, r in enumerate(data_rows):
                    r_no = idx + 2
                    cname = cell(r, i_name)
                    if not cname:
                        _add_row(idx, r_no, "error", "", "", ["", 0], note="اسم التصنيف فارغ")
                        continue
                    if cname in existing_cats or cname in seen:
                        _add_row(idx, r_no, "unchanged", cname, cname, [cname, 0], note="موجود مسبقاً")
                    else:
                        seen.add(cname)
                        _add_row(idx, r_no, "new", cname, cname, [cname, 0], note="تصنيف جديد")

            elif key == "products":
                i_sku = col_idx(["الكود / sku", "sku", "الكود", "الباركود", "barcode", "code", "internal reference"], 0)
                i_name = col_idx(["اسم المنتج", "المنتج", "الاسم", "name", "product"], 1)
                i_cat = col_idx(["التصنيف", "الفئة", "category"], 2)
                i_price = col_idx(["سعر البيع", "السعر", "sales price", "price"], 3)
                i_cost = col_idx(["التكلفة", "سعر الشراء", "cost"], 4)
                i_qty = col_idx(["الكمية", "الرصيد", "qty", "quantity", "stock"], 5)
                i_min = col_idx(["الحد الأدنى", "حد التنبيه", "min qty", "min_qty"], 6)
                i_trk = col_idx(["متتبع بالسيريال", "سيريال", "tracked"], 7)
                i_notes = col_idx(["ملاحظات", "notes", "description"], 8)

                existing_cats = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM categories").fetchall()}
                existing_cat_names = set(existing_cats.values())
                existing_prods = {
                    r["sku"]: r
                    for r in conn.execute(
                        "SELECT id, sku, name, category_id, price, cost, qty, min_qty, tracked, COALESCE(notes,'') notes, active FROM products"
                    ).fetchall()
                }
                for idx, r in enumerate(data_rows):
                    r_no = idx + 2
                    sku = cell(r, i_sku)
                    name = cell(r, i_name)
                    if not name and not sku:
                        continue
                    if not name:
                        _add_row(idx, r_no, "error", sku, "", [sku, "", "", 0, 0, 0, 0, 0, ""], note="اسم المنتج مفقود")
                        continue
                    try:
                        price_m = _money(cell(r, i_price, "0") or 0)
                        cost_m = _money(cell(r, i_cost, "0") or 0)
                        qty_v = max(0, int(float(cell(r, i_qty, "0") or 0)))
                        min_v = max(0, int(float(cell(r, i_min, "5") or 5)))
                        trk_v = 1 if cell(r, i_trk, "0").lower() in ("1", "true", "yes", "نعم") else 0
                        notes_v = cell(r, i_notes)
                        cat_name = cell(r, i_cat)
                    except Exception as ex_err:
                        _add_row(idx, r_no, "error", sku, name, [sku, name, cell(r, i_cat), cell(r, i_price), cell(r, i_cost), cell(r, i_qty), cell(r, i_min), cell(r, i_trk), cell(r, i_notes)], note=str(ex_err))
                        continue

                    cells = [
                        sku or "(تلقائي)",
                        name,
                        cat_name,
                        round(price_m / 100.0, 2),
                        round(cost_m / 100.0, 2),
                        qty_v,
                        min_v,
                        trk_v,
                        notes_v,
                    ]
                    note_parts = []
                    if cat_name and cat_name not in existing_cat_names:
                        note_parts.append(f"سيُنشأ تصنيف جديد: {cat_name}")

                    ex = existing_prods.get(sku) if sku else None
                    if ex:
                        diffs = []
                        old_cat = existing_cats.get(ex["category_id"], "")
                        if (ex["name"] or "") != name:
                            diffs.append({"field": "اسم المنتج", "old": ex["name"] or "", "new": name})
                        if old_cat != cat_name:
                            diffs.append({"field": "التصنيف", "old": old_cat or "—", "new": cat_name or "—"})
                        if int(ex["price"] or 0) != price_m:
                            diffs.append({"field": "سعر البيع", "old": _fmt_num_diff(round((ex["price"] or 0) / 100.0, 2)), "new": _fmt_num_diff(round(price_m / 100.0, 2))})
                        if int(ex["cost"] or 0) != cost_m:
                            diffs.append({"field": "التكلفة", "old": _fmt_num_diff(round((ex["cost"] or 0) / 100.0, 2)), "new": _fmt_num_diff(round(cost_m / 100.0, 2))})
                        if int(ex["qty"] or 0) != qty_v:
                            diffs.append({"field": "الكمية", "old": str(int(ex["qty"] or 0)), "new": str(qty_v)})
                        if int(ex["min_qty"] or 0) != min_v:
                            diffs.append({"field": "الحد الأدنى", "old": str(int(ex["min_qty"] or 0)), "new": str(min_v)})
                        if int(ex["tracked"] or 0) != trk_v:
                            diffs.append({"field": "سيريال", "old": str(int(ex["tracked"] or 0)), "new": str(trk_v)})
                        if (ex["notes"] or "") != notes_v:
                            diffs.append({"field": "ملاحظات", "old": ex["notes"] or "—", "new": notes_v or "—"})
                        if int(ex["active"] or 1) == 0:
                            diffs.append({"field": "الحالة", "old": "مؤرشف", "new": "نشط"})

                        status = "update" if diffs else "unchanged"
                        _add_row(idx, r_no, status, sku, name, cells, diffs=diffs, note=" | ".join(note_parts))
                    else:
                        _add_row(idx, r_no, "new", sku or "(تلقائي)", name, cells, note=" | ".join(note_parts) or "منتج جديد")

            elif key == "customers":
                i_name = col_idx(["اسم العميل", "العميل", "الاسم", "name", "customer"], 0)
                i_phone = col_idx(["رقم الهاتف", "الهاتف", "التليفون", "phone", "mobile"], 1)
                i_clim = col_idx(["حد الائتمان", "credit limit", "credit_limit"], 2)
                for idx, r in enumerate(data_rows):
                    r_no = idx + 2
                    cname = cell(r, i_name)
                    phone = cell(r, i_phone)
                    if not cname:
                        _add_row(idx, r_no, "error", "", "", ["", phone, 0, 0, 0], note="اسم العميل فارغ")
                        continue
                    try:
                        clim = max(0, _money(cell(r, i_clim, "0") or 0))
                    except Exception as ex_err:
                        _add_row(idx, r_no, "error", cname, cname, [cname, phone, cell(r, i_clim), 0, 0], note=str(ex_err))
                        continue
                    cells = [cname, phone, round(clim / 100.0, 2), 0, 0]
                    ex = conn.execute(
                        "SELECT id, COALESCE(credit_limit,0) cl, total_purchases, debt FROM customers WHERE name=? AND COALESCE(phone,'')=COALESCE(?, '')",
                        (cname, phone or None),
                    ).fetchone()
                    if ex:
                        cells[3] = round((ex["total_purchases"] or 0) / 100.0, 2)
                        cells[4] = round((ex["debt"] or 0) / 100.0, 2)
                        diffs = []
                        if int(ex["cl"] or 0) != clim:
                            diffs.append({"field": "حد الائتمان", "old": _fmt_num_diff(round((ex["cl"] or 0) / 100.0, 2)), "new": _fmt_num_diff(round(clim / 100.0, 2))})
                        _add_row(idx, r_no, "update" if diffs else "unchanged", phone or cname, cname, cells, diffs=diffs)
                    else:
                        _add_row(idx, r_no, "new", phone or cname, cname, cells, note="عميل جديد")

            elif key == "suppliers":
                i_name = col_idx(["اسم المورد", "المورد", "الاسم", "name", "supplier"], 0)
                i_comp = col_idx(["اسم الشركة", "الشركة", "company"], 1)
                i_phone = col_idx(["رقم الهاتف", "الهاتف", "phone"], 2)
                i_tax = col_idx(["الرقم الضريبي", "tax"], 3)
                i_terms = col_idx(["فترة الائتمان", "terms"], 4)
                i_addr = col_idx(["العنوان", "address"], 5)
                i_ob = col_idx(["الرصيد الافتتاحي", "opening"], 6)
                for idx, r in enumerate(data_rows):
                    r_no = idx + 2
                    sname = cell(r, i_name)
                    if not sname:
                        _add_row(idx, r_no, "error", "", "", ["", "", "", "", 30, "", 0], note="اسم المورد فارغ")
                        continue
                    try:
                        comp = cell(r, i_comp)
                        phone = cell(r, i_phone)
                        tax_no = cell(r, i_tax)
                        terms = max(0, int(float(cell(r, i_terms, "30") or 30)))
                        addr = cell(r, i_addr)
                        ob = max(0, _money(cell(r, i_ob, "0") or 0))
                    except Exception as ex_err:
                        _add_row(idx, r_no, "error", sname, sname, [sname, cell(r, i_comp), cell(r, i_phone), cell(r, i_tax), cell(r, i_terms), cell(r, i_addr), cell(r, i_ob)], note=str(ex_err))
                        continue
                    cells = [sname, comp, phone, tax_no, terms, addr, round(ob / 100.0, 2)]
                    ex = conn.execute(
                        "SELECT id, COALESCE(company,'') company, COALESCE(phone,'') phone, COALESCE(tax_reg_no,'') tax_reg, COALESCE(credit_terms_days,30) terms, COALESCE(address,'') addr FROM suppliers WHERE name=?",
                        (sname,),
                    ).fetchone()
                    if ex:
                        diffs = []
                        if ex["company"] != comp:
                            diffs.append({"field": "الشركة", "old": ex["company"] or "—", "new": comp or "—"})
                        if ex["phone"] != phone:
                            diffs.append({"field": "الهاتف", "old": ex["phone"] or "—", "new": phone or "—"})
                        if ex["tax_reg"] != tax_no:
                            diffs.append({"field": "الرقم الضريبي", "old": ex["tax_reg"] or "—", "new": tax_no or "—"})
                        if int(ex["terms"] or 0) != terms:
                            diffs.append({"field": "فترة الائتمان", "old": str(int(ex["terms"] or 0)), "new": str(terms)})
                        if ex["addr"] != addr:
                            diffs.append({"field": "العنوان", "old": ex["addr"] or "—", "new": addr or "—"})
                        _add_row(idx, r_no, "update" if diffs else "unchanged", sname, sname, cells, diffs=diffs)
                    else:
                        _add_row(idx, r_no, "new", sname, sname, cells, note="مورد جديد")

            elif key == "accounts":
                i_code = col_idx(["كود الحساب", "الكود", "code"], 0)
                i_name = col_idx(["اسم الحساب", "الاسم", "name"], 1)
                i_type = col_idx(["النوع", "type"], 2)
                i_parent = col_idx(["كود الحساب الأب", "كود الأب", "parent"], 3)
                i_grp = col_idx(["حساب رئيسي", "is_group", "group"], 4)
                valid_types = {"asset", "liability", "equity", "revenue", "expense"}
                by_id = {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM accounts").fetchall()}
                for idx, r in enumerate(data_rows):
                    r_no = idx + 2
                    code = cell(r, i_code)
                    name = cell(r, i_name)
                    atype = cell(r, i_type, "expense").lower()
                    pcode = cell(r, i_parent)
                    is_grp = 1 if cell(r, i_grp, "0") in ("1", "true", "نعم") else 0
                    cells = [code, name, atype, pcode, is_grp]
                    if not code or not name:
                        _add_row(idx, r_no, "error", code, name, cells, note="كود أو اسم الحساب فارغ")
                        continue
                    if atype not in valid_types:
                        _add_row(idx, r_no, "error", code, name, cells, note=f"نوع حساب غير صالح ({atype})")
                        continue
                    ex = conn.execute("SELECT id, name, parent_id, is_system FROM accounts WHERE code=?", (code,)).fetchone()
                    if ex:
                        if ex["is_system"]:
                            _add_row(idx, r_no, "unchanged", code, name, cells, note="حساب نظامي محمي (لن يُعدل)")
                        else:
                            diffs = []
                            old_p = by_id.get(ex["parent_id"], "")
                            if (ex["name"] or "") != name:
                                diffs.append({"field": "اسم الحساب", "old": ex["name"] or "", "new": name})
                            if old_p != pcode:
                                diffs.append({"field": "الحساب الأب", "old": old_p or "—", "new": pcode or "—"})
                            _add_row(idx, r_no, "update" if diffs else "unchanged", code, name, cells, diffs=diffs)
                    else:
                        _add_row(idx, r_no, "new", code, name, cells, note="حساب جديد")

            elif key == "translations":
                i_ar = col_idx(["النص العربي", "عربي", "ar_text", "arabic"], 0)
                i_en = col_idx(["الترجمة الإنجليزية", "إنجليزي", "en_text", "english"], 1)
                i_sec = col_idx(["القسم", "section"], 2)
                for idx, r in enumerate(data_rows):
                    r_no = idx + 2
                    ar = " ".join(cell(r, i_ar).split()).strip()
                    en = cell(r, i_en)
                    sec = cell(r, i_sec, "general") or "general"
                    cells = [ar, en, sec]
                    if not ar:
                        _add_row(idx, r_no, "error", "", "", cells, note="النص العربي فارغ")
                        continue
                    ex = conn.execute("SELECT en_text, section FROM translations WHERE ar_text=?", (ar,)).fetchone()
                    if ex:
                        diffs = []
                        if (ex["en_text"] or "") != en:
                            diffs.append({"field": "الترجمة الإنجليزية", "old": ex["en_text"] or "—", "new": en or "—"})
                        if (ex["section"] or "") != sec:
                            diffs.append({"field": "القسم", "old": ex["section"] or "", "new": sec})
                        _add_row(idx, r_no, "update" if diffs else "unchanged", ar, ar, cells, diffs=diffs)
                    else:
                        _add_row(idx, r_no, "new", ar, ar, cells, note="جملة جديدة")

            return {
                "entity": key,
                "title_ar": meta["title_ar"],
                "title_en": meta["title_en"],
                "filename": filename,
                "headers": meta["headers"],
                "summary": counts,
                "rows": preview_rows,
            }

    def excel_import(self, entity="products", file_base64="", filename="import.xlsx", selected_indices=None):
        """استيراد البيانات (الكل أو الصفوف المحددة من شاشة المعاينة) من ملف Excel (.xlsx) أو CSV لأي قسم قابل للاستيراد."""
        u = self._user()
        with db.connect() as conn:
            meta = self._entity_meta(conn, entity)
            if not meta.get("can_import") or not meta.get("perm_import"):
                raise ApiError(f"قسم «{meta['title_ar']}» يدعم التصدير فقط حفاظاً على سلامة القيود المالية")
            self._perm(meta["perm_import"])

            raw_rows = _parse_spreadsheet_payload(file_base64, filename)
            if len(raw_rows) < 2:
                raise ApiError("الملف فارغ أو لا يحتوي على صفوف بيانات بعد صف العناوين")

            selected_set = None
            if selected_indices is not None:
                if not isinstance(selected_indices, (list, tuple)):
                    raise ApiError("قائمة الصفوف المحددة غير صالحة")
                selected_set = {int(i) for i in selected_indices if str(i).lstrip("-").isdigit()}
                if not selected_set:
                    raise ApiError("يرجى تحديد عنصر واحد على الأقل للاستيراد")

            headers = [_norm_header(h) for h in raw_rows[0]]
            data_rows = raw_rows[1:]

            def col_idx(aliases: list[str], fallback: int | None = None) -> int | None:
                for al in aliases:
                    nal = _norm_header(al)
                    for i, h in enumerate(headers):
                        if h == nal or nal in h:
                            return i
                return fallback

            def cell(r: list[str], idx: int | None, default: str = "") -> str:
                if idx is None or idx < 0 or idx >= len(r):
                    return default
                return str(r[idx]).strip()

            inserted = updated = skipped = 0
            errors = []
            now_ts = db.now()
            key = meta["key"]

            if key == "categories":
                i_name = col_idx(["اسم التصنيف", "التصنيف", "الفئة", "اسم الفئة", "category", "name"], 0)
                for idx, r in enumerate(data_rows):
                    if selected_set is not None and idx not in selected_set:
                        skipped += 1
                        continue
                    cname = cell(r, i_name)
                    if not cname:
                        skipped += 1
                        continue
                    ex = conn.execute("SELECT id FROM categories WHERE name=?", (cname,)).fetchone()
                    if ex:
                        skipped += 1
                    else:
                        conn.execute("INSERT INTO categories(name) VALUES(?)", (cname,))
                        inserted += 1
                conn.execute("INSERT INTO settings(key, value) VALUES('hide_empty_categories','0') ON CONFLICT(key) DO UPDATE SET value='0'")
                self._settings_cache = None

            elif key == "products":
                i_sku = col_idx(["الكود / sku", "sku", "الكود", "الباركود", "barcode", "code", "internal reference"], 0)
                i_name = col_idx(["اسم المنتج", "المنتج", "الاسم", "name", "product"], 1)
                i_cat = col_idx(["التصنيف", "الفئة", "category"], 2)
                i_price = col_idx(["سعر البيع", "السعر", "sales price", "price"], 3)
                i_cost = col_idx(["التكلفة", "سعر الشراء", "cost"], 4)
                i_qty = col_idx(["الكمية", "الرصيد", "qty", "quantity", "stock"], 5)
                i_min = col_idx(["الحد الأدنى", "حد التنبيه", "min qty", "min_qty"], 6)
                i_trk = col_idx(["متتبع بالسيريال", "سيريال", "tracked"], 7)
                i_notes = col_idx(["ملاحظات", "notes", "description"], 8)

                for idx, r in enumerate(data_rows):
                    if selected_set is not None and idx not in selected_set:
                        skipped += 1
                        continue
                    r_no = idx + 2
                    sku = cell(r, i_sku)
                    name = cell(r, i_name)
                    if not name and not sku:
                        skipped += 1
                        continue
                    if not name:
                        errors.append(f"صف {r_no}: اسم المنتج مفقود")
                        continue
                    if not sku:
                        sku = f"IMP-{r_no}-{int(datetime.datetime.now().timestamp()) % 10000}"
                    try:
                        price_m = _money(cell(r, i_price, "0") or 0)
                        cost_m = _money(cell(r, i_cost, "0") or 0)
                        qty_v = max(0, int(float(cell(r, i_qty, "0") or 0)))
                        min_v = max(0, int(float(cell(r, i_min, "5") or 5)))
                        trk_v = 1 if cell(r, i_trk, "0").lower() in ("1", "true", "yes", "نعم") else 0
                        notes_v = cell(r, i_notes) or None
                        cat_name = cell(r, i_cat)
                        cat_id = None
                        if cat_name:
                            crow = conn.execute("SELECT id FROM categories WHERE name=?", (cat_name,)).fetchone()
                            if crow:
                                cat_id = crow["id"]
                            else:
                                cat_id = conn.execute("INSERT INTO categories(name) VALUES(?)", (cat_name,)).lastrowid

                        ex = conn.execute("SELECT id, qty FROM products WHERE sku=?", (sku,)).fetchone()
                        if ex:
                            pid = ex["id"]
                            old_qty = int(ex["qty"] or 0)
                            conn.execute(
                                """UPDATE products SET name=?, category_id=?, price=?, cost=?, qty=?, min_qty=?, tracked=?, notes=?, active=1
                                   WHERE id=?""",
                                (name, cat_id, price_m, cost_m, qty_v, min_v, trk_v, notes_v, pid),
                            )
                            if qty_v != old_qty:
                                conn.execute(
                                    "INSERT INTO stock_movements(created_at, user_id, product_id, qty_change, qty_after, reason, ref) VALUES(?,?,?,?,?,?,?)",
                                    (now_ts, u["id"], pid, qty_v - old_qty, qty_v, "استيراد Excel", filename),
                                )
                            updated += 1
                        else:
                            cur = conn.execute(
                                """INSERT INTO products(sku, name, category_id, price, cost, qty, min_qty, tracked, notes, created_at)
                                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                                (sku, name, cat_id, price_m, cost_m, qty_v, min_v, trk_v, notes_v, now_ts),
                            )
                            pid = cur.lastrowid
                            if qty_v > 0:
                                conn.execute(
                                    "INSERT INTO stock_movements(created_at, user_id, product_id, qty_change, qty_after, reason, ref) VALUES(?,?,?,?,?,?,?)",
                                    (now_ts, u["id"], pid, qty_v, qty_v, "رصيد افتتاحي — استيراد Excel", filename),
                                )
                            inserted += 1
                    except Exception as ex_err:
                        errors.append(f"صف {r_no} ({name}): {ex_err}")

            elif key == "customers":
                i_name = col_idx(["اسم العميل", "العميل", "الاسم", "name", "customer"], 0)
                i_phone = col_idx(["رقم الهاتف", "الهاتف", "التليفون", "phone", "mobile"], 1)
                i_clim = col_idx(["حد الائتمان", "credit limit", "credit_limit"], 2)
                for idx, r in enumerate(data_rows):
                    if selected_set is not None and idx not in selected_set:
                        skipped += 1
                        continue
                    r_no = idx + 2
                    cname = cell(r, i_name)
                    phone = cell(r, i_phone) or None
                    if not cname:
                        skipped += 1
                        continue
                    try:
                        clim = max(0, _money(cell(r, i_clim, "0") or 0))
                        ex = conn.execute(
                            "SELECT id FROM customers WHERE name=? AND COALESCE(phone,'')=COALESCE(?, '')",
                            (cname, phone),
                        ).fetchone()
                        if ex:
                            conn.execute("UPDATE customers SET credit_limit=? WHERE id=?", (clim, ex["id"]))
                            updated += 1
                        else:
                            conn.execute(
                                "INSERT INTO customers(name, phone, credit_limit, created_at) VALUES(?,?,?,?)",
                                (cname, phone, clim, now_ts),
                            )
                            inserted += 1
                    except Exception as ex_err:
                        errors.append(f"صف {r_no} ({cname}): {ex_err}")

            elif key == "suppliers":
                i_name = col_idx(["اسم المورد", "المورد", "الاسم", "name", "supplier"], 0)
                i_comp = col_idx(["اسم الشركة", "الشركة", "company"], 1)
                i_phone = col_idx(["رقم الهاتف", "الهاتف", "phone"], 2)
                i_tax = col_idx(["الرقم الضريبي", "tax"], 3)
                i_terms = col_idx(["فترة الائتمان", "terms"], 4)
                i_addr = col_idx(["العنوان", "address"], 5)
                i_ob = col_idx(["الرصيد الافتتاحي", "opening"], 6)
                for idx, r in enumerate(data_rows):
                    if selected_set is not None and idx not in selected_set:
                        skipped += 1
                        continue
                    r_no = idx + 2
                    sname = cell(r, i_name)
                    if not sname:
                        skipped += 1
                        continue
                    try:
                        comp = cell(r, i_comp) or None
                        phone = cell(r, i_phone) or None
                        tax_no = cell(r, i_tax) or None
                        terms = max(0, int(float(cell(r, i_terms, "30") or 30)))
                        addr = cell(r, i_addr) or None
                        ob = max(0, _money(cell(r, i_ob, "0") or 0))
                        ex = conn.execute("SELECT id FROM suppliers WHERE name=?", (sname,)).fetchone()
                        if ex:
                            conn.execute(
                                "UPDATE suppliers SET company=?, phone=?, tax_reg_no=?, credit_terms_days=?, address=?, active=1 WHERE id=?",
                                (comp, phone, tax_no, terms, addr, ex["id"]),
                            )
                            updated += 1
                        else:
                            conn.execute(
                                """INSERT INTO suppliers(name, company, phone, tax_reg_no, credit_terms_days, address, opening_balance, balance, active, created_at)
                                   VALUES(?,?,?,?,?,?,?,?,1,?)""",
                                (sname, comp, phone, tax_no, terms, addr, ob, ob, now_ts),
                            )
                            inserted += 1
                    except Exception as ex_err:
                        errors.append(f"صف {r_no} ({sname}): {ex_err}")

            elif key == "accounts":
                i_code = col_idx(["كود الحساب", "الكود", "code"], 0)
                i_name = col_idx(["اسم الحساب", "الاسم", "name"], 1)
                i_type = col_idx(["النوع", "type"], 2)
                i_parent = col_idx(["كود الحساب الأب", "كود الأب", "parent"], 3)
                i_grp = col_idx(["حساب رئيسي", "is_group", "group"], 4)
                valid_types = {"asset", "liability", "equity", "revenue", "expense"}
                normal_map = {"asset": "debit", "expense": "debit", "liability": "credit", "equity": "credit", "revenue": "credit"}
                for idx, r in enumerate(data_rows):
                    if selected_set is not None and idx not in selected_set:
                        skipped += 1
                        continue
                    r_no = idx + 2
                    code = cell(r, i_code)
                    name = cell(r, i_name)
                    atype = cell(r, i_type, "expense").lower()
                    if not code or not name:
                        skipped += 1
                        continue
                    if atype not in valid_types:
                        errors.append(f"صف {r_no}: نوع حساب غير صالح ({atype})")
                        continue
                    pcode = cell(r, i_parent)
                    prow = conn.execute("SELECT id FROM accounts WHERE code=?", (pcode,)).fetchone() if pcode else None
                    is_grp = 1 if cell(r, i_grp, "0") in ("1", "true", "نعم") else 0
                    ex = conn.execute("SELECT id, is_system FROM accounts WHERE code=?", (code,)).fetchone()
                    if ex:
                        if ex["is_system"]:
                            skipped += 1
                        else:
                            conn.execute("UPDATE accounts SET name=?, parent_id=? WHERE id=?", (name, prow["id"] if prow else None, ex["id"]))
                            updated += 1
                    else:
                        conn.execute(
                            """INSERT INTO accounts(code, name, type, normal_side, parent_id, is_group, is_system, active, created_at)
                               VALUES(?,?,?,?,?,?,0,1,?)""",
                            (code, name, atype, normal_map[atype], prow["id"] if prow else None, is_grp, now_ts),
                        )
                        inserted += 1

            elif key == "translations":
                i_ar = col_idx(["النص العربي", "عربي", "ar_text", "arabic"], 0)
                i_en = col_idx(["الترجمة الإنجليزية", "إنجليزي", "en_text", "english"], 1)
                i_sec = col_idx(["القسم", "section"], 2)
                for idx, r in enumerate(data_rows):
                    if selected_set is not None and idx not in selected_set:
                        skipped += 1
                        continue
                    ar = " ".join(cell(r, i_ar).split()).strip()
                    en = cell(r, i_en)
                    sec = cell(r, i_sec, "general") or "general"
                    if not ar:
                        skipped += 1
                        continue
                    ex = conn.execute("SELECT id FROM translations WHERE ar_text=?", (ar,)).fetchone()
                    conn.execute(
                        """INSERT INTO translations(ar_text, en_text, section, updated_at) VALUES(?,?,?,?)
                           ON CONFLICT(ar_text) DO UPDATE SET en_text=excluded.en_text, section=excluded.section, updated_at=excluded.updated_at""",
                        (ar, en, sec, now_ts),
                    )
                    if ex:
                        updated += 1
                    else:
                        inserted += 1

            self._log_activity(
                conn, "excel_import", key, filename,
                f"استيراد Excel لقسم «{meta['title_ar']}» (إضافة: {inserted}، تحديث: {updated}، تخطي: {skipped})",
                {"entity": key, "inserted": inserted, "updated": updated, "skipped": skipped, "errors_count": len(errors)},
                module_key=meta["module"],
            )
            return {
                "entity": key,
                "inserted": inserted,
                "updated": updated,
                "skipped": skipped,
                "errors": errors[:30],
                "total_rows": len(data_rows),
            }
