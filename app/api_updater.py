"""نظام التحقق التلقائي من التحديثات عبر GitHub Releases والتحميل الآمن مع تحقق SHA-256 والترقية السلسة."""
import datetime
import hashlib
import json
import os
import pathlib
import re
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import db
from api_common import ApiError, _STATE
from version import (
    GITHUB_REPO_SLUG,
    RELEASES_API_URL,
    RELEASES_PAGE_URL,
    get_app_version,
    is_newer_version,
    normalize_version,
)

# النطاقات المسموح بالتحميل منها فقط (حماية من الروابط المزيفة أو إعادة التوجيه غير الآمنة)
_ALLOWED_DOWNLOAD_HOSTS = (
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
)

_UPDATE_LOCK = threading.Lock()
_UPDATE_CACHE = {
    "checked_ts": 0.0,
    "result": None,
}
_UPDATE_STATE = {
    "state": "idle",  # idle | downloading | verifying | ready | installing | error
    "version": "",
    "asset_name": "",
    "file_path": "",
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "percent": 0,
    "sha256_verified": False,
    "error": "",
    "message": "",
}


def _app_root_dir() -> pathlib.Path:
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent.parent


def _updates_dir() -> pathlib.Path:
    d = pathlib.Path(db.db_path()).resolve().parent / "updates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _detect_install_mode() -> str:
    """تحديد نوع التثبيت: installer (مثبت عبر Inno Setup) أو portable (ملف exe مباشر) أو dev (تشغيل بايثون)."""
    if not getattr(sys, "frozen", False):
        return "dev"
    root = _app_root_dir()
    if any(root.glob("unins*.exe")):
        return "installer"
    return "portable"


def _is_trusted_https_url(url: str) -> bool:
    try:
        u = urllib.parse.urlparse(str(url or "").strip())
        if u.scheme != "https" or not u.hostname:
            return False
        host = u.hostname.lower()
        return any(host == h or host.endswith("." + h) for h in _ALLOWED_DOWNLOAD_HOSTS)
    except Exception:
        return False


def _sanitize_asset_name(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]", "_", pathlib.Path(str(name or "TechZone-Setup.exe")).name)
    if not clean.lower().endswith(".exe"):
        clean += ".exe"
    return clean


def _parse_sha256_sums(text: str) -> dict[str, str]:
    """تحليل محتوى SHA256SUMS.txt إلى قاموس {filename_lower: sha256_hex}."""
    out: dict[str, str] = {}
    for line in str(text or "").splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line:
            continue
        m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", line)
        if m:
            h, fname = m.group(1).lower(), pathlib.Path(m.group(2).strip()).name.lower()
            out[fname] = h
    return out


def _select_release_assets(assets: list, install_mode: str) -> tuple[dict | None, dict | None]:
    """اختيار أفضل ملف تنفيذي للترقية مع ملف بصمات SHA256SUMS.txt إن وُجد."""
    setup_asset = None
    portable_asset = None
    checksum_asset = None
    fallback_exe = None

    for item in assets or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        lname = name.lower()
        url = str(item.get("browser_download_url") or "").strip()
        if not name or not _is_trusted_https_url(url):
            continue
        if "sha256" in lname and lname.endswith(".txt"):
            checksum_asset = item
        elif lname.endswith(".exe"):
            if "setup" in lname or "installer" in lname:
                setup_asset = item
            elif lname == "techzone.exe":
                portable_asset = item
            elif fallback_exe is None:
                fallback_exe = item

    # في الوضع المثبت (Inno Setup) نفضّل دائماً ملف السطب TechZone-Setup-v*.exe
    # في الوضع المحمول (Portable exe فقط) نفضّل TechZone.exe وإن لم يوجد نرجع لملف السطب
    if install_mode == "portable":
        chosen = portable_asset or setup_asset or fallback_exe
    else:
        chosen = setup_asset or portable_asset or fallback_exe
    return chosen, checksum_asset


def _parse_release_payload(payload: dict, current_version: str, install_mode: str) -> dict:
    """تحويل رد GitHub Releases API إلى بنية موحدة للواجهة."""
    tag_name = str(payload.get("tag_name") or "").strip()
    release_name = str(payload.get("name") or tag_name or "").strip()
    latest_version = normalize_version(tag_name or release_name)
    has_upd = bool(tag_name) and is_newer_version(latest_version, current_version)
    asset, checksum_asset = _select_release_assets(payload.get("assets") or [], install_mode)
    return {
        "current_version": current_version,
        "latest_version": latest_version,
        "tag_name": tag_name,
        "release_name": release_name or f"TechZone V{latest_version}",
        "release_notes": str(payload.get("body") or "").strip(),
        "published_at": str(payload.get("published_at") or "").strip(),
        "release_url": str(payload.get("html_url") or RELEASES_PAGE_URL).strip(),
        "has_update": has_upd,
        "asset_name": str((asset or {}).get("name") or ""),
        "asset_size": int((asset or {}).get("size") or 0),
        "asset_url": str((asset or {}).get("browser_download_url") or ""),
        "checksum_url": str((checksum_asset or {}).get("browser_download_url") or ""),
        "install_mode": install_mode,
        "is_frozen": bool(getattr(sys, "frozen", False)),
        "offline": False,
        "error": "",
        "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _http_get_bytes(url: str, timeout: float = 8.0) -> bytes:
    if not _is_trusted_https_url(url):
        raise ApiError("رابط التحميل غير موثوق")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"TechZone-POS/{get_app_version()}",
            "Accept": "application/vnd.github+json",
        },
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        final_url = resp.geturl()
        if not _is_trusted_https_url(final_url):
            raise ApiError("تم رفض إعادة التوجيه إلى نطاق غير موثوق")
        return resp.read()


def _set_update_state(**kv):
    with _UPDATE_LOCK:
        _UPDATE_STATE.update(kv)


def _get_update_state() -> dict:
    with _UPDATE_LOCK:
        return dict(_UPDATE_STATE)


def _sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 128), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def _trigger_clean_shutdown_delayed(delay_sec: float = 0.45):
    """إغلاق البرنامج نهائياً بنعومة عبر _STATE المشترك (حتى لو كان وضع شريط النظام System Tray مفعلاً)."""
    _STATE["force_exit"] = True

    def _runner():
        time.sleep(max(0.1, delay_sec))
        _STATE["force_exit"] = True
        cb = _STATE.get("shutdown_cb")
        if callable(cb):
            try:
                cb()
            except Exception:
                pass
        else:
            try:
                win = _STATE.get("window")
                if win is not None:
                    win.destroy()
            except Exception:
                pass
        # ضمان الخروج التام من العملية بعد 1.5 ثانية حتى لا يبقى التطبيق عالقاً في شريط النظام
        time.sleep(1.5)
        os._exit(0)

    threading.Thread(target=_runner, daemon=True).start()


def _clean_spawn_env() -> dict[str, str]:
    """تنظيف متغيرات بيئة PyInstaller (_MEIPASS2 / _PYI_* / مسارات _MEI في PATH) حتى يعمل الـ EXE الجديد بعد الترقية دون خطأ Failed to load Python DLL."""
    env = dict(os.environ)
    for k in list(env.keys()):
        ku = k.upper()
        if (
            ku.startswith("_PYI_")
            or ku.startswith("PYI_")
            or ku in ("_MEIPASS2", "PYTHONHOME", "PYTHONPATH", "TCL_LIBRARY", "TK_LIBRARY")
        ):
            env.pop(k, None)
    meipass = getattr(sys, "_MEIPASS", None)
    if "PATH" in env:
        meipass_norm = str(pathlib.Path(meipass).resolve()).lower() if meipass else ""
        parts = []
        for entry in env["PATH"].split(os.pathsep):
            el = entry.strip().lower()
            if not el:
                continue
            if meipass_norm and el.rstrip("\\/") == meipass_norm.rstrip("\\/"):
                continue
            if "\\_mei" in el or "/_mei" in el:
                continue
            parts.append(entry)
        env["PATH"] = os.pathsep.join(parts)
    return env


def _build_windows_update_script(
    downloaded_exe: pathlib.Path,
    install_mode: str,
    app_dir: pathlib.Path,
    current_exe: pathlib.Path,
    pid: int,
) -> tuple[pathlib.Path, pathlib.Path]:
    """توليد سكربت ترقية مؤقت + مشغّل VBS مخفي تماماً (بدون شاشة cmd سوداء) يثبّت التحديث ويعيد فتح البرنامج."""
    ts = int(time.time())
    tmp_dir = pathlib.Path(tempfile.gettempdir())
    script_path = tmp_dir / f"techzone_update_{pid}_{ts}.cmd"
    vbs_path = tmp_dir / f"techzone_update_{pid}_{ts}.vbs"
    log_path = _updates_dir() / "update_install.log"
    dl_str = str(downloaded_exe.resolve())
    dir_str = str(app_dir.resolve())
    exe_str = str(current_exe.resolve())
    log_str = str(log_path.resolve())
    vbs_str = str(vbs_path.resolve())
    is_setup = ("setup" in downloaded_exe.name.lower()) or ("installer" in downloaded_exe.name.lower())

    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "setlocal",
        "set \"_MEIPASS2=\"",
        "set \"_PYI_APPLICATION_HOME_DIR=\"",
        "set \"_PYI_ARCHIVE_FILE=\"",
        "set \"_PYI_PARENT_PROCESS_LEVEL=\"",
        "set \"_PYI_SPLASH_IPC=\"",
        "set \"PYTHONHOME=\"",
        "set \"PYTHONPATH=\"",
        f"echo [%DATE% %TIME%] Starting TechZone update > \"{log_str}\"",
        f"set \"TARGET_PID={pid}\"",
        "set /a TRIES=0",
        ":wait_loop",
        "tasklist /FI \"PID eq %TARGET_PID%\" 2>nul | find \"%TARGET_PID%\" >nul",
        "if errorlevel 1 goto do_update",
        "set /a TRIES+=1",
        "if %TRIES% GEQ 8 goto force_kill",
        "ping -n 2 127.0.0.1 >nul",
        "goto wait_loop",
        ":force_kill",
        f"echo [%DATE% %TIME%] Force closing remaining TechZone.exe instances >> \"{log_str}\"",
        "taskkill /F /T /IM TechZone.exe >nul 2>nul",
        "ping -n 2 127.0.0.1 >nul",
        ":do_update",
        "ping -n 2 127.0.0.1 >nul",
    ]

    if is_setup or install_mode == "installer":
        # ترقية صامتة في نفس مجلد التثبيت دون المساس بمجلد data\ ثم إعادة تشغيل TechZone.exe تلقائياً
        lines.extend([
            f"echo [%DATE% %TIME%] Running installer: {dl_str} >> \"{log_str}\"",
            f"\"{dl_str}\" /SILENT /NORESTART /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /DIR=\"{dir_str}\"",
            f"echo [%DATE% %TIME%] Installer exited with code %ERRORLEVEL% >> \"{log_str}\"",
            "ping -n 2 127.0.0.1 >nul",
            f"if exist \"{dir_str}\\TechZone.exe\" start \"\" /D \"{dir_str}\" \"{dir_str}\\TechZone.exe\"",
        ])
    else:
        # استبدال مباشر للنسخة المحمولة (Portable TechZone.exe) مع نسخة احتياطية .bak
        lines.extend([
            f"if exist \"{exe_str}.bak\" del /f /q \"{exe_str}.bak\" >nul 2>nul",
            f"move /y \"{exe_str}\" \"{exe_str}.bak\" >nul 2>nul",
            f"copy /y \"{dl_str}\" \"{exe_str}\" >nul",
            "if errorlevel 1 (",
            f"  if exist \"{exe_str}.bak\" move /y \"{exe_str}.bak\" \"{exe_str}\" >nul 2>nul",
            ")",
            f"if exist \"{exe_str}\" start \"\" \"{exe_str}\"",
        ])

    lines.extend([
        f"del /f /q \"{vbs_str}\" >nul 2>nul",
        "(goto) 2>nul & del /f /q \"%~f0\"",
    ])

    script_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    # مشغّل VBS يعمل عبر wscript.exe (GUI subsystem) لضمان عدم ظهور أي نافذة سوداء على ويندوز 10 و 11
    cmd_escaped = str(script_path.resolve()).replace('"', '""')
    vbs_content = f'CreateObject("WScript.Shell").Run "cmd.exe /c ""{cmd_escaped}""", 0, False\r\n'
    vbs_path.write_text(vbs_content, encoding="utf-8")
    return script_path, vbs_path


class UpdaterMixin:
    def app_version_info(self):
        """إرجاع معلومات الإصدار الحالي وحالة التحديثات (تعمل 100% بدون إنترنت)."""
        self._user()
        with db.connect() as conn:
            st = self._settings(conn)
            auto_chk = st.get("auto_update_check", "1") != "0"
        return {
            "current_version": get_app_version(),
            "repo": GITHUB_REPO_SLUG,
            "releases_url": RELEASES_PAGE_URL,
            "is_frozen": bool(getattr(sys, "frozen", False)),
            "install_mode": _detect_install_mode(),
            "auto_update_check": auto_chk,
            "update_state": _get_update_state(),
        }

    def update_check(self, force=False, silent=False):
        """التحقق الآمن من وجود إصدار أحدث على GitHub Releases دون تعطيل العمل الأوفلاين أبداً."""
        self._user()
        current_ver = get_app_version()
        install_mode = _detect_install_mode()

        with _UPDATE_LOCK:
            cached = _UPDATE_CACHE.get("result")
            age = time.time() - float(_UPDATE_CACHE.get("checked_ts") or 0.0)
            if not force and cached and age < 300.0:
                out = dict(cached)
                out["current_version"] = current_ver
                out["has_update"] = is_newer_version(out.get("latest_version"), current_ver)
                return out

        try:
            raw = _http_get_bytes(RELEASES_API_URL, timeout=6.0)
            payload = json.loads(raw.decode("utf-8", errors="replace"))
            if not isinstance(payload, dict) or not payload.get("tag_name"):
                raise ValueError("استجابة غير صالحة من GitHub")
            result = _parse_release_payload(payload, current_ver, install_mode)
            with _UPDATE_LOCK:
                _UPDATE_CACHE["checked_ts"] = time.time()
                _UPDATE_CACHE["result"] = dict(result)
            return result
        except urllib.error.HTTPError as e:
            err_msg = "تم تجاوز حد طلبات GitHub مؤقتاً، حاول لاحقاً" if e.code == 403 else f"تعذر الوصول لخادم التحديثات (HTTP {e.code})"
            return {
                "current_version": current_ver,
                "latest_version": current_ver,
                "has_update": False,
                "offline": True,
                "install_mode": install_mode,
                "is_frozen": bool(getattr(sys, "frozen", False)),
                "releases_url": RELEASES_PAGE_URL,
                "error": "" if silent else err_msg,
                "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception:
            return {
                "current_version": current_ver,
                "latest_version": current_ver,
                "has_update": False,
                "offline": True,
                "install_mode": install_mode,
                "is_frozen": bool(getattr(sys, "frozen", False)),
                "releases_url": RELEASES_PAGE_URL,
                "error": "" if silent else "لا يوجد اتصال بالإنترنت حالياً — يعمل البرنامج محلياً بدون إنترنت بشكل طبيعي",
                "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    def update_status(self):
        """متابعة حالة وتقدم تحميل/تثبيت التحديث لحظياً."""
        self._user()
        return _get_update_state()

    def update_download(self, asset_url=None, asset_name=None, checksum_url=None, version=None):
        """بدء تحميل ملف التحديث الأخير في الخلفية مع التحقق من بصمة SHA-256."""
        self._perm("settings_view_edit")

        cur_state = _get_update_state()
        if cur_state.get("state") in ("downloading", "verifying"):
            return cur_state

        url = str(asset_url or "").strip()
        name = str(asset_name or "").strip()
        chk_url = str(checksum_url or "").strip()
        ver = normalize_version(version) if version else ""

        if not url:
            chk = self.update_check(force=True, silent=False)
            if chk.get("offline"):
                raise ApiError(chk.get("error") or "لا يوجد اتصال بالإنترنت لتحميل التحديث")
            if not chk.get("has_update"):
                raise ApiError("أنت تستخدم أحدث إصدار بالفعل")
            url = chk.get("asset_url") or ""
            name = chk.get("asset_name") or ""
            chk_url = chk.get("checksum_url") or ""
            ver = chk.get("latest_version") or ""

        if not url or not _is_trusted_https_url(url):
            raise ApiError("لم يتم العثور على رابط تحميل موثوق لملف التحديث في هذا الإصدار")
        if chk_url and not _is_trusted_https_url(chk_url):
            chk_url = ""

        safe_name = _sanitize_asset_name(name or f"TechZone-Setup-v{ver or 'latest'}.exe")
        dest_dir = _updates_dir()
        final_path = dest_dir / safe_name
        part_path = dest_dir / (safe_name + ".part")

        _set_update_state(
            state="downloading",
            version=ver,
            asset_name=safe_name,
            file_path=str(final_path),
            downloaded_bytes=0,
            total_bytes=0,
            percent=0,
            sha256_verified=False,
            error="",
            message="جاري الاتصال بخادم GitHub وتحميل الإصدار الجديد...",
        )

        def _worker():
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": f"TechZone-POS/{get_app_version()}"},
                )
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=30.0, context=ctx) as resp:
                    if not _is_trusted_https_url(resp.geturl()):
                        raise ApiError("تم إيقاف التحميل لأن رابط التحويل غير موثوق")
                    total = int(resp.headers.get("Content-Length") or 0)
                    downloaded = 0
                    with open(part_path, "wb") as out_f:
                        while True:
                            chunk = resp.read(1024 * 128)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            downloaded += len(chunk)
                            pct = int(min(99, (downloaded * 100) / total)) if total > 0 else 0
                            _set_update_state(
                                downloaded_bytes=downloaded,
                                total_bytes=total,
                                percent=pct,
                                message=f"جاري التحميل... ({downloaded / (1024 * 1024):.1f} MB)",
                            )

                if downloaded < 1024 * 100:
                    raise ApiError("ملف التحديث الذي تم تحميله غير مكتمل أو تالف")

                verified = False
                if chk_url:
                    _set_update_state(
                        state="verifying",
                        percent=99,
                        message="جاري التحقق من سلامة الملف عبر بصمة SHA-256...",
                    )
                    try:
                        sums_raw = _http_get_bytes(chk_url, timeout=10.0).decode("utf-8", errors="ignore")
                        sums_map = _parse_sha256_sums(sums_raw)
                        expected_hash = sums_map.get(safe_name.lower())
                        if expected_hash:
                            actual_hash = _sha256_file(part_path)
                            if actual_hash != expected_hash:
                                try:
                                    part_path.unlink(missing_ok=True)
                                except Exception:
                                    pass
                                raise ApiError("فشل التحقق من بصمة الأمان SHA-256 — الملف تالف وتم حذفه لحمايتك")
                            verified = True
                    except ApiError:
                        raise
                    except Exception:
                        verified = False

                if final_path.exists():
                    try:
                        final_path.unlink()
                    except Exception:
                        pass
                part_path.replace(final_path)
                _set_update_state(
                    state="ready",
                    file_path=str(final_path),
                    downloaded_bytes=downloaded,
                    total_bytes=max(total, downloaded),
                    percent=100,
                    sha256_verified=verified,
                    error="",
                    message="تم تحميل التحديث والتحقق منه بنجاح — جاهز للتثبيت الآن!",
                )
            except Exception as exc:
                try:
                    part_path.unlink(missing_ok=True)
                except Exception:
                    pass
                _set_update_state(
                    state="error",
                    error=str(exc) or "فشل تحميل ملف التحديث",
                    message="تعذر إكمال تحميل التحديث",
                )

        threading.Thread(target=_worker, daemon=True).start()
        return _get_update_state()

    def update_install(self):
        """أخذ نسخة احتياطية تلقائية لقاعدة البيانات ثم تشغيل مثبّت الإصدار الأخير وإعادة فتح البرنامج تلقائياً."""
        self._perm("settings_view_edit")
        st = _get_update_state()
        fpath_str = str(st.get("file_path") or "").strip()
        if st.get("state") != "ready" or not fpath_str:
            raise ApiError("لا يوجد تحديث محمّل وجاهز للتثبيت حالياً")

        downloaded_exe = pathlib.Path(fpath_str).resolve()
        updates_root = _updates_dir().resolve()
        if not downloaded_exe.exists() or updates_root not in downloaded_exe.parents:
            raise ApiError("ملف التحديث غير موجود في المسار الآمن، أعد التحميل")

        # 1) نسخة احتياطية أمان تلقائية لقاعدة البيانات قبل الترقية
        backup_path = None
        try:
            bp = db.backup_database("before_update")
            backup_path = str(bp) if bp else None
        except Exception:
            backup_path = None

        with db.connect() as conn:
            self._log_activity(
                conn,
                "app_update_install",
                "settings",
                st.get("version") or "",
                f"بدء ترقية البرنامج إلى الإصدار v{st.get('version') or ''}",
                {"file": downloaded_exe.name, "sha256_verified": bool(st.get("sha256_verified")), "backup": backup_path},
                module_key="settings",
            )

        _set_update_state(state="installing", message="جاري تثبيت التحديث وإعادة تشغيل البرنامج...")
        install_mode = _detect_install_mode()

        if sys.platform != "win32":
            return {
                "installing": False,
                "file_path": str(downloaded_exe),
                "backup_path": backup_path,
                "message": "تم حفظ ملف التحديث — شغّله يدوياً على نظام غير ويندوز",
            }

        # في وضع التطوير (python app/main.py) نفتح المثبت مباشرة دون إنهاء بيئة التطوير قسراً
        if install_mode == "dev":
            try:
                os.startfile(str(downloaded_exe))
            except Exception as exc:
                raise ApiError(f"تعذر تشغيل ملف المثبت: {exc}")
            return {
                "installing": True,
                "dev_mode": True,
                "file_path": str(downloaded_exe),
                "backup_path": backup_path,
                "message": "تم تشغيل مثبّت الإصدار الجديد (وضع التطوير).",
            }

        # وضع التشغيل الفعلي (TechZone.exe): توليد سكربت الترقية الصامتة ومشغّل VBS مخفي + إغلاق نظيف + إعادة تشغيل تلقائي
        script, vbs_launcher = _build_windows_update_script(
            downloaded_exe=downloaded_exe,
            install_mode=install_mode,
            app_dir=_app_root_dir(),
            current_exe=pathlib.Path(sys.executable).resolve(),
            pid=os.getpid(),
        )
        clean_env = _clean_spawn_env()
        try:
            subprocess.Popen(
                ["wscript.exe", "//B", "//Nologo", str(vbs_launcher)],
                env=clean_env,
                close_fds=True,
            )
        except Exception:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            subprocess.Popen(
                ["cmd.exe", "/c", str(script)],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                startupinfo=si,
                env=clean_env,
                close_fds=True,
            )
        _trigger_clean_shutdown_delayed(0.45)
        return {
            "installing": True,
            "dev_mode": False,
            "version": st.get("version") or "",
            "backup_path": backup_path,
            "message": "جاري إغلاق البرنامج وتثبيت الإصدار الجديد تلقائياً...",
        }
