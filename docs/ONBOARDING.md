# Onboarding de Puntos ECCOS

## Panorama

Puntos ECCOS es un POS local en Python para ventas, inventario, clientes, crédito y control multicaaja. La interfaz Streamlit coordina casos de uso; las reglas críticas y transacciones viven en repositorios SQLAlchemy.

## Tecnologías

| Capa | Tecnología |
|---|---|
| Interfaz | Streamlit 1.62 |
| Lenguaje | Python 3.11+ |
| Persistencia | SQLAlchemy 1.4; SQLite local o PostgreSQL |
| Reportes | pandas, ReportLab, xhtml2pdf y OpenPyXL |
| Pruebas | unittest, pytest y `streamlit.testing.AppTest` |

## Arquitectura

```text
Navegador -> web/app.py -> model/repository/* -> model/entity/models.py -> SQLite/PostgreSQL
                            |                         |
                            +-> authorization.py      +-> schema.py/migraciones
                            +-> report/*
```

## Puntos de entrada

- `web/app.py`: `main()`, autenticación, navegación y páginas.
- `model/repository/factory.py`: sesiones y construcción de repositorios.
- `model/entity/models.py`: modelo relacional.
- `model/schema.py`: creación y migraciones compatibles con instalaciones existentes.
- `model/authorization.py`: contexto de rol y protección de operaciones sensibles.
- `runtests.py` y `pytest.ini`: ejecución de pruebas del POS.

## Flujo representativo: corte de caja

1. Streamlit obtiene la caja seleccionada desde `st.session_state`.
2. `CashControlRepository` localiza su apertura sin cerrar.
3. La interfaz calcula ventas, movimientos y efectivo esperado.
4. `CashCloseRepository.insert()` vuelve a validar el rol y guarda el corte.
5. El historial relaciona apertura y corte sin mezclar la operación con la consulta histórica.

## Convenciones

- Textos visibles en español y montos en MXN.
- Clases en `PascalCase`; funciones, archivos y pruebas en `snake_case`.
- La UI puede orientar, pero los permisos y reglas financieras deben repetirse en repositorios.
- Las consultas se construyen con SQLAlchemy; el SQL textual usa parámetros para valores.
- Las eliminaciones con valor de auditoría se sustituyen por archivo, anulación o movimientos compensatorios.

## Comandos habituales

```powershell
.\.venv\Scripts\streamlit.exe run web\app.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe runtests.py
.\.venv\Scripts\python.exe -m pip check
```

## Dónde modificar

| Necesidad | Ubicación |
|---|---|
| Nueva página o widget | `web/app.py` |
| Regla de ventas/inventario/caja | `model/repository/` |
| Tabla o migración | `model/entity/models.py` y `model/schema.py` |
| PDF, Excel o ticket | `model/report/` |
| Regresión | `tests/model/` o `tests/test_web_app_smoke.py` |
