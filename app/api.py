"""Backend Api: موزع موحد لوحدات النظام + dispatcher للواجهة (window.pywebview.api.call)."""
import sys
import traceback

import db
from api_common import (  # noqa: F401
    ApiError,
    REPAIR_FLOW,
    _BaseApiMixin,
    _LOGIN_ATTEMPTS,
    _STATE,
    _customer_debt_summary,
    _customers_enriched_cte,
    _fmt_money,
    _format_doc_seq,
    _int,
    _money,
    _upsert_customer,
)
from api_accounting import AccountingMixin
from api_excel import ExcelMixin
from api_auth import AuthSettingsMixin
from api_customers import CustomersMixin
from api_installments import InstallmentsMixin
from api_inventory import InventoryMixin
from api_owner import OwnerMixin
from api_purchases import PurchasesMixin
from api_quotes import QuotesMixin
from api_reports import ReportsMixin
from api_sales import SalesMixin
from api_services import ServicesMixin
from modules_map import API_MODULE_MAP


class Api(
    AuthSettingsMixin,
    OwnerMixin,
    InventoryMixin,
    CustomersMixin,
    InstallmentsMixin,
    PurchasesMixin,
    AccountingMixin,
    ExcelMixin,
    SalesMixin,
    QuotesMixin,
    ServicesMixin,
    ReportsMixin,
    _BaseApiMixin,
):
    def __init__(self):
        with db.connect():
            pass  # إنشاء المخطط + الـ seed + ترحيل دفتر الأستاذ وشجرة الحسابات عند الإقلاع
        self._methods = {
            n for n in dir(self)
            if not n.startswith("_") and callable(getattr(self, n)) and n != "call"
        }

    # ---------------------------------------------------------------- جسر
    def call(self, name, payload=None):
        try:
            if name not in self._methods:
                raise ApiError("نداء غير معروف")
            mod = API_MODULE_MAP.get(name)
            if mod and not self._module_enabled(mod):
                raise ApiError("هذا القسم غير مُفعّل من مدير النظام الرئيسي")
            fn = getattr(self, name)
            if payload is None:
                data = fn()
            elif isinstance(payload, dict):
                data = fn(**payload)
            else:
                data = fn(payload)
            return {"ok": True, "data": data}
        except ApiError as e:
            return {"ok": False, "error": str(e)}
        except TypeError:
            return {"ok": False, "error": "معاملات غير صالحة للطلب"}
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return {"ok": False, "error": "حدث خطأ غير متوقع، راجع سجل البرنامج"}
