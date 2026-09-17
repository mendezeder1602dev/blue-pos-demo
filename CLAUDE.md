# Project Instructions

## Tech Stack

- Python 3.11+ application built with Streamlit.
- SQLAlchemy models and repositories back SQLite locally and PostgreSQL in production.
- Report generation uses Jinja2, xhtml2pdf, ReportLab, OpenPyXL, and pandas.

## Build And Run

- Install dependencies: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
- Run app: `.\.venv\Scripts\streamlit.exe run web\app.py`
- Run tests: `.\.venv\Scripts\python.exe runtests.py`
- Run pytest: `.\.venv\Scripts\python.exe -m pytest -q`

## Project Structure

- `web/app.py`: Streamlit UI, navigation, session state, and page orchestration.
- `model/entity/models.py`: SQLAlchemy tables and relationships.
- `model/repository/`: business rules, authorization checks, transactions, and persistence.
- `model/schema.py`: database creation and migrations for existing installations.
- `model/report/`: tickets, PDF, Excel, and report templates.
- `tests/`: unittest-based regression coverage for model, repositories, reports, and smoke checks.

## Conventions

- Keep visible copy in clear Spanish and money values in Mexican pesos.
- Put critical business and authorization rules in repositories, not only in the UI.
- Use `st.session_state` for per-user Streamlit state; avoid mutable module globals for user data.
- Use `enter_to_submit=False` for data-entry forms.
- Use parameterized SQLAlchemy queries and keep credentials in environment variables or Streamlit secrets.
- Before changing sales, inventory, cash, permissions, or migrations, run `.\.venv\Scripts\python.exe runtests.py`.
- Protect account management, backups, restores, cancellations, and financial writes with `require_role` in the Python data boundary; hiding a Streamlit control is not authorization.
- Keep operational dashboards actionable: every alert must name the condition and link to the page that resolves it.
