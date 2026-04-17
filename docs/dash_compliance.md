# Dash 3.x / 4.0 Compliance Guide

This document describes the Dash API changes relevant to all apps in this meta-repo, explains how to audit your code, and lists the patterns that have been updated across every registered application.

---

## Issue Summary (Audit Results — March 2026)

All issues below were found and fixed across the codebase to ensure consistent behaviour with the control panel's shared virtual environment (Dash ≥ 2.17.0, presently at 4.1.0).

| File | Issue | Fix Applied |
|---|---|---|
| `daily_use_aggregator/tabs/checklist_tab.py` | `callback_context as ctx` (deprecated alias) | `from dash import … ctx` |
| `daily_use_aggregator/tabs/email_tab.py` | `callback_context as ctx` (deprecated alias) | `from dash import … ctx` |
| `daily_use_aggregator/tabs/obsidian_tab.py` | `callback_context as ctx` (deprecated alias) | `from dash import … ctx` |
| `daily_use_aggregator/tabs/outline_tab.py` | `from dash import ctx` inside callback body | Moved to module-level import |
| `finance_tracker/admin_dashboard.py` | `from dash import ctx` inside two callbacks; `run_server()` | Moved to top-level; replaced with `run()` |
| `finance_tracker/sankey_demo.py` | `app.run_server()` | `app.run()` |
| `finance_tracker/finance_tracker_app.py` | 12 × `@app.callback` at module level | Standalone `@callback`; added to imports |
| `finance_tracker/invoice_tracker_app.py` tabs | `@app.callback` in tab modules | Standalone `@callback` |
| `finance_tracker/invoice-parser/src/invoice_parser.py` | 7 × `@app.callback` | Standalone `@callback`; added to imports |
| `finance_tracker/tabs/analytics_tab.py` | `@app.callback` (imported `callback` but unused) | `@callback` |
| `finance_tracker/tabs/invoice_manager_tab.py` | Same inconsistency | `@callback` |
| `finance_tracker/tabs/job_manager_tab.py` | Same inconsistency | `@callback` |
| `finance_tracker/tabs/qb_sync_tab.py` | Same inconsistency | `@callback` |
| `finance_tracker/tabs/historical_trends_tab.py` | `@app.callback`, missing `callback` import | Added import; `@callback` |
| `finance_tracker/tabs/sheet_viewer_tab.py` | Same | Same |
| `finance_tracker/tabs/spyder_agents_tab.py` | Same | Same |
| `finance_tracker/tabs/sankey_tab.py` | 7 × `@app.callback`, missing `callback` import | Added import; `@callback` |
| `finance_tracker/requirements.txt` | `dash>=2.0.0`, `dash-table>=5.0.0` (merged package) | `dash>=2.17.0`; removed `dash-table` pin |
| `daily_use_aggregator/requirements.txt` | `dash>=2.14` | `dash>=2.17.0` |
| `ollama_llm/requirements.txt` | `dash>=2.14.0` | `dash>=2.17.0` |
| `finance_tracker/invoice-parser/requirements.txt` | Unpinned `dash` | `dash>=2.17.0` |

---

## Important Dash API Changes (2.x → 3.x / 4.0)

| Category | Old Pattern | New Pattern | Notes |
|---|---|---|---|
| **App launch** | `app.run_server(debug=True)` | `app.run(debug=True)` | `run_server()` removed in Dash 4.0 |
| **Callback context** | `from dash import callback_context` or `callback_context as ctx` | `from dash import ctx` | `callback_context` deprecated since Dash 2.0 |
| **Callback decorator** | `@app.callback(...)` | `from dash import callback` → `@callback(...)` | Standalone decorator removes coupling to the app instance |
| **DataTable import** | `pip install dash-table` / `from dash_table import DataTable` | `from dash.dash_table import DataTable` | `dash-table` merged into `dash` since 2.x; no separate package needed |
| **Long callbacks** | `@app.long_callback(...)` / `dash.long_callback` | `@callback(..., background=True)` | `long_callback` module removed in Dash 3+ |
| **Patch helper** | —  | `from dash import Patch` | New in Dash 2.9+: efficient partial component updates |
| **Page registry** | Manual multi-page routing | `dash.register_page()` / `use_pages=True` | Use Dash Pages API for multi-page apps |
| **`ctx` attributes** | `ctx.triggered[0]["prop_id"]` string split | `ctx.triggered_id` (dict for pattern-match) | Cleaner API; `triggered_id` is a string or dict |
| **requirements.txt** | `dash-table>=5.0.0` | *(remove the line)* | Bundled in `dash` since 2.0; listing it separately causes pip conflicts |

---

## How to Check Your App for Compliance

Run the following command from the repo root to scan for deprecated patterns:

```bash
grep -rn \
  "run_server\|callback_context\|@app\.callback\|dash-table\|long_callback" \
  --include="*.py" --include="requirements*.txt" \
  --exclude-dir=archive
```

A clean, compliant app should produce **no output** from the above command.

---

## Recommended Import Block

Every Dash app in this repo should use this import structure:

```python
import dash
from dash import Dash, Input, Output, State, callback, ctx, dcc, html, no_update
import dash_bootstrap_components as dbc   # if using DBC theming
```

For apps that use DataTable:

```python
from dash.dash_table import DataTable     # ✅ correct
# from dash_table import DataTable        # ❌ old separate package — do not use
```

---

## Tab-Module Pattern

Tab modules that expose a `register_callbacks(app)` function should use **standalone `@callback`** inside, not `@app.callback`. The `app` argument can be retained for backward compatibility but is no longer used for callback registration:

```python
# tabs/my_tab.py
from dash import Input, Output, State, callback, ctx, dcc, html

def register_callbacks(app=None):   # app param kept for caller compatibility

    @callback(
        Output("my-output", "children"),
        Input("my-input", "value"),
    )
    def my_fn(value):
        return f"You entered: {value}"
```

---

## requirements.txt Standard

All apps in this repo should pin Dash to the same floor version as the control panel:

```
dash>=2.17.0
dash-bootstrap-components>=1.5.0
```

The control panel virtual environment (`/.venv`) is the single source of truth.  Apps launched via the control panel inherit that environment, so version mismatches between app-level `requirements.txt` pins and the installed packages will surface as import errors.
