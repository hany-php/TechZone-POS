# Code Quality Audit Report — TechZone (تك زون للإلكترونيات)

**Date:** 2026-10-17  
**Scope:** `app/` (Python backend), `web/` (HTML/CSS/JS frontend), `app/db.py`, `app/selfcheck.py`  
**Methodology:** Static review of source + 4 parallel sub-agent audits (maintainability, clean architecture, code quality, security, performance). No code changes were made.

---

## 1. Overall Scores

| Dimension | Score (0–10) | Weight | Weighted |
|---|---:|---:|---:|
| 1. Maintainability | 4.0 | 20% | 0.80 |
| 2. Clean Architecture | 3.0 | 20% | 0.60 |
| 3. Code Quality | 5.5 | 20% | 1.10 |
| 4. Security | 6.5 | 20% | 1.30 |
| 5. Performance | 5.0 | 20% | 1.00 |
| **Overall (weighted)** | | **100%** | **4.80 / 10** |

**Verdict:** A feature-complete, functional offline POS/desktop app with reasonable security baselines, but it is a monolithic, single-layer application. Architecture and maintainability are the weakest areas; security and performance are acceptable for a small shop but will not scale.

---

## 2. Dimension 1 — Maintainability (4.0 / 10)

**Justification:** The project ships with an excellent `AGENTS.md` and a 104-check `selfcheck.py`, and the DB migration is non-destructive. However, modularity is poor: `app/api.py` is 3,384 lines containing ~90 methods in one god class `Api`, `web/app.js` is 1,414 lines mixing bridge/permissions/rendering/PDF, and large HTML pages (e.g. `desktop.html` 1,852 lines, `pos.html` 1,415, `sales_quotes.html` 1,441) embed inline JS. Code-level documentation is minimal (only 30 comment lines in `api.py`, 10 in `db.py`); no docstrings on most methods.

**Files / sections needing attention:**
- `app/api.py:368` — god class `Api` (~90 methods).
- `app/api.py:1576` `sale_create` (127 lines), `:1786` `sale_modify_from_cart` (145), `:2506` `quotation_save` (196), `:2380` `_convert_quote_to_sale_in_tx` (125).
- `app/db.py` — mixes schema, migrations, seeding, connection management.
- `web/app.js` — bridge + permissions + invoice rendering + WhatsApp delivery.
- `web/desktop.html`, `web/pos.html`, `web/sales_quotes.html`, `web/settings.html` — monolithic pages with inline scripts.

**Recommended fixes:**
1. Split `api.py` into per-aggregate modules (sales, customers, inventory, repairs, reports, settings).
2. Extract DB access into repository helpers (`get_user`, `get_product`, `get_sale`).
3. Add docstrings/type hints to public methods; enforce `ruff`/`black` + ESLint/Prettier.
4. Move inline page scripts into separate `.js` files.

---

## 3. Dimension 2 — Clean Architecture (3.0 / 10)

**Justification:** Essentially a single-layer monolith. `Api` simultaneously acts as transport adapter, application service, domain logic, data access, PDF generator, and OS-integration layer. Dependency direction is inverted (use cases depend on `sqlite3`, `ctypes.windll`, `os.startfile`). No abstractions/repositories; no Unit of Work; permission checks sprinkled inside methods; global mutable session state.

**Files / sections needing attention:**
- `app/api.py:15` — global `_STATE = {"user": None}`.
- `app/api.py:59-110` — Win32 clipboard integration in backend module.
- `app/api.py:216` — PDF generator in backend module.
- `app/api.py:368` — god class; `:377-396` — reflection dispatcher with no validation.
- `app/api.py:398-425` — procedural permission helpers tied to global state.
- `app/api.py:426-427` — raw settings access.
- `app/main.py:24-33` — DB query in entry point (`store_title`).
- `web/app.js:155,175,702,927,1193,1224` — bridge + permissions + rendering mixed.

**Recommended fixes:**
1. Layer into `domain/` (entities, repo interfaces, permission policy), `application/` (use cases), `infrastructure/` (SQLite repos, PDF, Win32 gateway), `interface/` (pywebview adapter + DTO validation).
2. Replace global `_STATE` with an explicit session/auth context passed to use cases.
3. Introduce transaction boundaries (Unit of Work) for multi-write operations.
4. Move PDF/OS integration out of use cases; backend returns data, infrastructure handles delivery.
5. Move `store_title()` DB access out of `main.py` into a settings service.

---

## 4. Dimension 3 — Code Quality (5.5 / 10)

**Justification:** Functional (104/104 selfchecks pass), SQL is parameterized, `esc()` used consistently. Weakened by a monolithic 3,155-line `api.py`, long methods, duplicated SQL/PDF logic, global mutable state, leaked DB connections, a 38KB base64 logo embedded in `db.py`, broad swallowed exceptions, and heavy `innerHTML` templating.

**Files / sections needing attention:**
- Duplicated SQL lookups: `SELECT * FROM users WHERE id=?` ×6 (`app/api.py:551,585,645,712,734,784`); `SELECT qty FROM products WHERE id=?` ×7; `SELECT * FROM sales WHERE id=?` ×3.
- Duplicated WhatsApp/PDF export: `whatsapp_send_invoice` (`app/api.py:1998`, 102 lines) and `whatsapp_send_quote` (`app/api.py:2850`, 98 lines).
- `_customer_debt_summary` reused in 6+ places via `_upsert_customer` (`app/api.py:290`).
- Dead code: `payment_methods_get` (`app/api.py:864`) unused; `_FALLBACK_JPEG` test fallback in production (`app/api.py:53`).
- Broad `except Exception` in 14 places in `app/api.py`; empty `catch (e) {}` in `web/app.js` (lines 22,27,81,83,92,100,115,262…).
- Connection leak: `db.connect()` returns a connection; 74 call sites use `with db.connect()` but sqlite3 context managers do not close connections; `api.py` has 0 `.close()` calls.
- Embedded asset: `DEFAULT_TAQNIA_LOGO` ~38KB base64 in `app/db.py:32`.
- XSS surface: extensive `innerHTML` templating (`web/staff.html:234,259,287,298,333`; `web/inventory.html:250`); `document.write` in `web/receipt.html:171`.
- Dynamic SQL via `' AND '.join(where)` (`app/api.py:2149,2172,2192,2776,3022,3083`); `col_prefix` interpolation latent injection point.
- Magic numbers: card size `110..360` (`app/api.py:510,838`), `950 * 1024` (`app/api.py:523`), PBKDF2 `200_000` (`app/db.py:385`).

**Recommended fixes:**
1. Make `db.connect()` a real closing context manager; add `try/finally` + `.close()`.
2. Extract shared WhatsApp/PDF sender and shared SQL repositories.
3. Move `DEFAULT_TAQNIA_LOGO` to a file asset.
4. Remove dead `payment_methods_get`; replace swallowed catches with logged warnings.
5. Add linting/formatting; reduce `innerHTML` usage; centralize SQL builders with allow-listed column prefixes.
6. Split large methods into transaction helpers; introduce named constants.

---

## 5. Dimension 4 — Security (6.5 / 10)

**Justification:** Solid baselines: SQL is parameterized, PINs use PBKDF2-HMAC-SHA256 with 16-byte salt and 200k iterations, authorization enforced server-side via `_perm()`/`_has_perm()` for most mutating endpoints, money/numeric inputs validated, `esc()` used consistently. Reduced by default hardcoded credentials, no brute-force protection, path-traversal in PDF filename, several endpoints requiring only authentication (not permission), weak validation of `data:image/` uploads, and unbounded string inputs.

**Files / sections needing attention:**
- Default seeded credentials: `admin`/`1234`, `cashier`/`1111` (`app/db.py:596-601`).
- No brute-force protection: `login` (`app/api.py:748-773`) iterates all users comparing hashes; no rate limiting/lockout.
- PIN hashing: `app/db.py:385-387` (`hashlib.pbkdf2_hmac("sha256", ..., 200_000)`), no pepper.
- Global in-memory session, no expiry/token: `app/api.py:15`, `app/api.py:791-793`.
- Endpoints requiring only `_user()` (auth) not permission: `sale(id)` (`app/api.py:1704-1705`), `quotation(id)` (`app/api.py:2721`), `repair(id)` (`app/api.py:3092`), `customer(id)` (`app/api.py:1229`), `used()` (`app/api.py:3014`), `shift_summary()` (`app/api.py:1442-1444`).
- Repair mutations require `repair_view` instead of `repair_edit`: `repair_set_status` (`app/api.py:3106-3107`), `repair_update` (`app/api.py:3153-3154`), `repair_delete` (`app/api.py:3193-3194`).
- `settings()` requires login but not `settings_manage` (`app/api.py:796-799`).
- Path traversal: invoice number used directly in path `app/api.py:2051` (`receipts_dir / f"{d['invoice_no']}.pdf"`), `app/api.py:2055` (`.txt`); quote path sanitized inconsistently (`app/api.py:2904` `safe_name`).
- Upload validation prefix-only: `custom_bg` (`app/api.py:516-525`, 950KB), `avatar` (`app/api.py:615-624`, 450KB), `receipt_logo` (`app/api.py:841-845`, 200KB), `company_logo` (`app/api.py:943-949`, 500KB) — no magic-byte checks.
- Full tracebacks to stderr (`app/api.py:394`); default PINs in seed (`app/db.py:596`).
- No DB encryption at rest; no input length limits on many free-text fields.

**Recommended fixes:**
1. Remove/rotate default credentials; seed random PINs or force first-run password change.
2. Add per-account attempt counters with lockout/backoff in `login`; constant-time comparison.
3. Apply `safe_name` allowlist to `invoice_no` before writing PDF/TXT.
4. Tighten authorization: replace `_user()` with `_perm(...)` on `sale`, `quotation`, `repair`, `customer`, `used`, `shift_summary`; repair mutations require `repair_edit`.
5. Validate uploads: decode base64 and verify magic bytes + exact MIME; reject SVG/HTML masquerading as images.
6. Reduce logging; bound text inputs; add idle session timeout.
7. Document/enable at-rest protection for `data/shop.db`.

---

## 6. Dimension 5 — Performance (5.0 / 10)

**Justification:** Acceptable for a small single-user local SQLite workload, but clear N+1 queries, unbounded `SELECT *`/`fetchall()` with in-Python slicing/sorting, missing FK indexes, repeated settings/template fetches, and large base64 payloads/canvas rendering will degrade as data grows.

**Files / sections needing attention:**
- N+1: `shift_summary` (`app/api.py:1481`) runs a payments query per sale row; `customers_list` (`app/api.py:1285-1291`) and `customers_search` (`app/api.py:1219-1225`) call `_customer_debt_summary` per customer; `sale()` (`app/api.py:1721-1727`) sums return items per item; `quotations()` (`app/api.py:2786-2801`) runs 3 queries per converted quote; `_customer_debt_summary` (`app/api.py:314-324`) 3 correlated subqueries per sale.
- Unbounded/in-Python pagination: `sales()` (`app/api.py:2155,2176,2196`) fetches all rows then slices; `out.sort(...)` (`app/api.py:2202`); `customers_list` (`app/api.py:1282`) no limit.
- Missing FK indexes: `app/db.py:293-296,337,449` define few; missing `sale_items(sale_id)`, `sale_items(product_id)`, `payments(sale_id)`, `sale_returns(sale_id)`, `sale_return_items(sale_item_id)`, `quotation_items(quote_id)`, `serials(product_id)`, `repairs(customer_name/phone)`, `stock_movements(created_at)`, `shifts(user_id)`, `customer_payments(shift_id)`.
- Repeated work/no caching: `_settings` (`app/api.py:426-427`) runs `SELECT key, value FROM settings` on nearly every call; `_load_templates`/`_load_payment_methods` reloaded per operation; `pageInit` (`web/app.js:370`) fetches settings on every page.
- Memory/large payloads: product images/custom backgrounds as base64 up to 600KB/950KB stored in SQLite and returned in list queries (`app/api.py:1084-1089`, `app/api.py:517-524`); canvas rendering 720×~1200 and 1240×1754 with `toDataURL('image/jpeg', 0.92)` creates multi-MB strings (`web/app.js:394-403`, `web/app.js:963-967`).
- UI-thread heavy work: `renderA4DocumentToJpeg` (`web/app.js:963-1191`) synchronous canvas drawing.
- JS rendering inefficiencies: rebinds via `querySelectorAll(...).forEach(addEventListener)` on each render (e.g. `web/pos.html:593,759,775,788,793`; `web/sales_quotes.html:1284-1337`); `setInterval(updateClocks, 1000)` never cleared (`web/desktop.html:1697`); theme/accent propagation scans all iframes on every toggle (`web/app.js:16-23`, `web/app.js:78-82`).
- File I/O: writes both `.pdf` and `.txt` on every WhatsApp send; `receipts_dir.mkdir(..., exist_ok=True)` each call (`app/api.py:2049-2056`).

**Recommended fixes:**
1. Add FK indexes in `app/db.py`.
2. Eliminate N+1 in `customers_list`, `shift_summary`, `sale()`, `quotations()`.
3. Convert `sales()` to bounded SQL (or bound each source + global pagination).
4. Cache `_settings`/templates in Python with invalidation on save.
5. Move base64 images to disk + thumbnails.
6. Use event delegation in HTML render loops.

---

## 7. Top 5 Critical Issues (Ranked by Priority)

### #1 — Default hardcoded credentials (Security, P1)
- **Evidence:** `app/db.py:596-601` seeds `admin`/`1234` and `cashier`/`1111`.
- **Impact:** Trivial account takeover on any deployment that keeps seed data.
- **Fix:** Seed random PINs or force a first-run password change; remove default PINs from seed.

### #2 — Authorization gaps on read/mutation endpoints (Security, P1)
- **Evidence:** `app/api.py:1704-1705`, `:2721`, `:3092`, `:1229`, `:3014`, `:1442-1444` require only `_user()`; repair mutations use `repair_view` instead of `repair_edit` (`app/api.py:3106-3107`, `:3153-3154`, `:3193-3194`).
- **Impact:** Any logged-in cashier can read sensitive sales/customers/repairs/shifts and mutate repairs.
- **Fix:** Replace `_user()` with the appropriate `_perm(...)`; repair mutations require `repair_edit`.

### #3 — Path traversal in PDF filename (Security, P2)
- **Evidence:** `app/api.py:2051` (`receipts_dir / f"{d['invoice_no']}.pdf"`), `app/api.py:2055` (`.txt`); quote path sanitized inconsistently at `app/api.py:2904`.
- **Impact:** A compromised/malicious admin prefix or invoice number can write outside `receipts/`.
- **Fix:** Apply the `safe_name` allowlist to `invoice_no` before any filesystem write.

### #4 — DB connection leak (Performance/Reliability, P2)
- **Evidence:** `app/db.py:408-421` `connect()` returns a connection; 74 `with db.connect()` sites; `api.py` has 0 `.close()` calls.
- **Impact:** Connection/file-handle accumulation under load; potential "database is locked" errors.
- **Fix:** Make `connect()` a real closing context manager (close in `__exit__`) or add `try/finally` + `.close()` at all call sites.

### #5 — Monolithic architecture / god class (Maintainability/Architecture, P3)
- **Evidence:** `app/api.py` 3,384 lines / ~90 methods in `Api` (`app/api.py:368`); `web/app.js` 1,414 lines; no layers, repositories, or abstractions.
- **Impact:** High cost of change, hard to test, high regression risk.
- **Fix:** Split backend into domain/application/infrastructure/interface layers; split frontend into API client, state/permissions, and rendering modules.

---

## 8. Strengths (why scores are not lower)

- 104/104 selfchecks pass (`app/selfcheck.py`).
- SQL is parameterized; no `eval`/`exec`; `esc()` present and used.
- Schema migration is non-destructive (`_ensure_schema_columns`, `_migrate_customers`).
- PIN hashing uses PBKDF2-HMAC-SHA256 with 16-byte salt and 200k iterations.
- Authorization enforced server-side for most mutating endpoints.
- Offline-first design; local fonts (no network at runtime).
- Detailed `AGENTS.md` as a single source of truth.

---

## 9. Appendix — Key File Metrics

| File | Lines | Notes |
|---|---:|---|
| `app/api.py` | 3,384 | God class `Api`, ~90 methods, 30 comment lines |
| `app/db.py` | 637 | Schema + migrations + seed + connection |
| `app/main.py` | 49 | Entry point; contains DB query (`store_title`) |
| `app/selfcheck.py` | 582 | 104 checks |
| `web/app.js` | 1,414 | Bridge + permissions + rendering + PDF |
| `web/desktop.html` | 1,852 | OS shell + inline JS |
| `web/pos.html` | 1,415 | POS + inline JS |
| `web/sales_quotes.html` | 1,441 | Sales/quotes + inline JS |
| `web/settings.html` | 1,078 | Settings + invoice studio |
| `web/history.html` | 773 | History + filters |

**Recommended next step:** Address issues #1–#4 first (security + reliability), then plan the architectural refactor (#5) incrementally behind the existing `selfcheck.py` regression suite.
