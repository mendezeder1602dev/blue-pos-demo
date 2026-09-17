# Evidencia TDD: tablero, seguridad y pytest

| Garantía | RED | GREEN |
|---|---|---|
| Resumen multicaaja clasifica pendientes y vencidos | `summarize_cash_fleet` no existía | Prueba parametrizada cubre 0, 1 y 2 turnos |
| Tablero permite elegir una caja pendiente y abrir su corte | Faltaba `Control de cajas` | Prueba estructural confirma métricas y acción |
| Vendedor no administra credenciales ajenas | No se lanzaba `PermissionError` | Repositorio exige `superuser` |
| Vendedor no descarga ni restaura SQLite | No se lanzaba `PermissionError` | Utilidades exigen `superuser` |
| pytest sólo recoge el POS | 440 pruebas mezcladas y 51 errores | 252 pruebas del POS recolectadas limpiamente |

Comandos ejecutados:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/model/repository/test_user_security.py tests/model/repository/test_business_extensions.py tests/model/test_cash_fleet_summary_pytest.py tests/test_cash_page_separation.py -q
```

Resultado final observado: **255 passed, 4 subtests passed**. El conjunto focalizado de tablero y seguridad también pasó completo.
