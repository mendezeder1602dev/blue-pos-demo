# Regresión de estado del tablero y fecha de corte

## Garantías

| Comportamiento | Evidencia RED | Evidencia GREEN |
|---|---|---|
| El tablero funciona sin apertura actual y con un turno anterior sin cerrar | La prueba no encontró inicialización de `estimated_cash` y el error reportado mostró `UnboundLocalError` | Los importes se inicializan antes de calcular la salud operativa y se excluyen turnos vencidos del control de límite |
| Corte carga el turno pendiente sin mezclar fechas históricas | La prueba encontró escritura directa en `cash_close_date` y un selector que ocultaba el formulario para turnos anteriores | La página obtiene el turno sin cerrar de la caja activa y usa directamente su fecha |
| Un turno anterior siempre puede cerrarse | El formulario exigía `selected_date == mexico_today()` | El formulario muestra ID, fecha, duración y el botón **Realizar corte y cerrar caja** para cualquier turno pendiente |

## Validación local

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cash_page_separation tests.test_web_app_smoke
.\.venv\Scripts\python.exe -m py_compile web/app.py
```

Resultado: **29 pruebas aprobadas** y compilación correcta.
