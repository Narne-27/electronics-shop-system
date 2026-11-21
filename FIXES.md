# Electrodesk – bug-fix release

Templates, CSS/JS and the visual design are **unchanged**. Only Python, SQL and docs were edited.
Drop these files over your project folder (same names) and run `python test_app.py`.

| File | What changed |
| :--- | :--- |
| `app.py` | Checkout, returns, dues, quotations, products/CSV, inventory, settings/backup/restore, daily closing, GST, users, auth (details below) |
| `db.py` | Real `transaction()`; no silent MySQL→SQLite switch; Decimal→float; MySQL-safe `%`; `upsert_setting()` |
| `init_db.py` | MySQL schema script now actually creates tables; start-up initialises the active engine; calendar-accurate seed warranties |
| `schema_mysql.sql` | Added missing `SALE.cgst_amount` / `SALE.sgst_amount` |
| `config.py` | No hard-coded secret; debug off; localhost bind; configurable PIN & approval thresholds |
| `test_app.py` (new) | 35 regression tests |
| `requirements.txt` | Removed unused `reportlab` |
| `README.md`, `PROJECT_NOTES.md` | Corrected table count, test file, date notes; added config/security section |
| `.gitignore` (new) | Keeps `.secret_key` and the DB out of git |

## Behaviour changes worth knowing
* Credit / partial-payment sales **must have a customer** (otherwise the balance can't be chased).
* Exchange value above 50% of the bill needs the Owner PIN (`config.EXCHANGE_APPROVAL_PCT`).
* Converting a quotation creates a **Pending** invoice (shows in Customer Dues) instead of pretending it was paid by UPI; expired quotes can't be converted.
* A sale can be returned once; refund ≤ amount paid. Returns still restock the whole invoice (the return form has no per-item selection).
* Restore replaces everything with the backup (all-or-nothing). Reset-demo and restore sign you out.
* CSV import: missing stock = 0 (was 10); unknown category skips the row (was silently category 1); exported files can be re-imported.
* Daily closing "expected" values are computed on the server; staff can't overwrite a finalised closing.
* Admin accounts can no longer create/edit/delete Shop Owner accounts, deactivate themselves, or remove the last admin/owner.
* Cross-site POSTs are rejected (Origin/Referer check) without needing template changes.

## Not changed (needs template/design work or is out of scope)
* No CSRF *tokens* in forms (Origin check used instead); demo credentials still shown on the login page.
* Returns are whole-invoice only; the product edit form can still overwrite stock with a stale value (now audited).
* Reports/P&L pages other than GST were not reworked; MySQL path is fixed but was **not** tested against a live MySQL server.

## Second-pass audit (independent review of the first release)
Found by attacking the delivered code, each now fixed and covered by a test that fails on the previous version:
1. **0% GST products were taxed at 18%** (a falsy `0` fell back to the default rate) - checkout and quotations.
2. **A serial/IMEI could never be sold again after its invoice was returned** - duplicate check now ignores refunded sales.
3. **Restoring an older backup wiped the audit log** - restore now only replaces tables that are present in the file.
4. **Fractional quantities were silently truncated** (`1.9` became `1`, `true` became 1) - now rejected.
5. **Owner-approval threshold could trigger at exactly 10%** because of float rounding - now compared in rupees with a 1-paisa tolerance.
6. The generic bad-input handler now logs unexpected `ValueError`s instead of hiding real bugs.

Verified clean: 65 routes x 4 roles fuzzed with empty input (no 500s, no lost sessions), no unauthenticated pages, 6 threads racing for the last unit (exactly one wins), no undefined names.

Known limits: MySQL not tested on a live server; `pos.js`, `main.js` and 20 templates were not available to review; behind an HTTPS reverse proxy the Origin check needs the proxy to pass the original Host header.
