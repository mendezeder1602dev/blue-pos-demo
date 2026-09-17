# Separación de apertura, corte e historial de caja

## Origen y recorrido de usuario

Los criterios se derivaron de la solicitud del usuario, sin un plan externo:

- Como operador, quiero abrir y administrar el turno activo sólo en **Apertura de caja**.
- Como operador, quiero conciliar y cerrar el turno actual sólo en **Corte de caja**.
- Como administrador, quiero consultar turnos y cortes anteriores sólo en **Historial de turnos y cortes**.

## Evidencia RED / GREEN

| Comportamiento | Prueba | RED | GREEN |
|---|---|---|---|
| Corte no lista cortes anteriores ni consulta `get_all()` | `tests.test_cash_page_separation` | Falló al encontrar `Historial de cortes` en `_render_cash_close` | Pasa tras retirar el mosaico histórico |
| Corte no contiene flujo de apertura | `tests.test_cash_page_separation` | El código inactivo contenía `Abrir caja` y `CashOpening` | Pasa tras eliminar el flujo duplicado |
| Apertura no presenta historial global | `tests.test_cash_page_separation` | Ya cumplía | Pasa |
| Historial conserva turnos, cortes, filtros y descargas | `tests.test_cash_page_separation` | Ya cumplía | Pasa |

## Validación

Comando ejecutado:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cash_page_separation tests.test_web_app_smoke
.\.venv\Scripts\python.exe -m py_compile web/app.py
```

Resultado: **26 pruebas aprobadas** y compilación de `web/app.py` correcta.

La suite no genera un reporte de cobertura configurado. La garantía específica se cubre mediante inspección AST de las tres funciones de página y la suite de humo de Streamlit.
