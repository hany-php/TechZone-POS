"""مصدر الحقيقة الوحيد لإصدار التطبيق ومعلومات مستودع GitHub للتحديثات التلقائية."""
import pathlib
import re
import sys

APP_NAME = "TechZone POS"
GITHUB_OWNER = "hany-php"
GITHUB_REPO = "TechZone-POS"
GITHUB_REPO_SLUG = f"{GITHUB_OWNER}/{GITHUB_REPO}"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO_SLUG}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPO_SLUG}/releases"

# يتم تحديث هذا الرقم تلقائياً أثناء البناء على GitHub Actions ليطابق إصدار الـ Release تماماً
FALLBACK_VERSION = "1.0.0"

_SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?")


def normalize_version(raw: str | None) -> str:
    """استخراج رقم الإصدار النظيف مثل 1.0.1 من أي نص مثل v1.0.1 أو TechZone V1.0.1."""
    if not raw:
        return FALLBACK_VERSION
    m = _SEMVER_RE.search(str(raw).strip())
    if not m:
        return FALLBACK_VERSION
    parts = [p for p in m.groups() if p is not None]
    return ".".join(str(int(p)) for p in parts)


def parse_semver(raw: str | None) -> tuple[int, ...]:
    """تحويل رقم الإصدار إلى Tuple رقمي للمقارنة الدقيقة بين الإصدارات."""
    norm = normalize_version(raw)
    try:
        nums = tuple(int(p) for p in norm.split("."))
        return nums + (0,) * max(0, 4 - len(nums))
    except Exception:
        return (0, 0, 0, 0)


def is_newer_version(latest: str | None, current: str | None) -> bool:
    """إرجاع True فقط إذا كان الإصدار الأحدث أكبر فعلياً من الإصدار الحالي."""
    if not latest:
        return False
    return parse_semver(latest) > parse_semver(current)


def _version_file_candidates() -> list[pathlib.Path]:
    cands: list[pathlib.Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cands.append(pathlib.Path(meipass) / "version.txt")
        cands.append(pathlib.Path(sys.executable).resolve().parent / "version.txt")
    else:
        cands.append(pathlib.Path(__file__).resolve().parent.parent / "version.txt")
    return cands


def get_app_version() -> str:
    """قراءة رقم الإصدار المثبت حالياً من version.txt المدمج أو القيمة الاحتياطية."""
    for p in _version_file_candidates():
        try:
            if p.exists():
                txt = p.read_text(encoding="utf-8", errors="ignore").strip()
                if txt and _SEMVER_RE.search(txt):
                    return normalize_version(txt)
        except Exception:
            continue
    return normalize_version(FALLBACK_VERSION)


APP_VERSION = get_app_version()
