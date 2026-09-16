# Evidencia TDD: mosaico de acciones rápidas

## Alcance

La historia se derivó de la solicitud del usuario: el mosaico de acciones rápidas
debe mostrarse de forma fija únicamente en `Tablero` y no ocupar espacio dentro de
Ventas, Clientes, Inventario u otros formularios.

## Evidencia RED/GREEN

| Garantía | Prueba | Tipo | Resultado |
| --- | --- | --- | --- |
| Las acciones rápidas se condicionan a `Tablero` | `test_quick_actions_render_as_a_dashboard_only_mosaic` | Contrato UI/AST | PASS |
| El mosaico distribuye las acciones en tres columnas | `test_quick_actions_render_as_a_dashboard_only_mosaic` | Contrato UI/AST | PASS |
| El arranque, la navegación y las vistas existentes siguen funcionando | `tests/test_web_app_smoke.py` | Integración Streamlit | PASS |

RED verificado antes de modificar la implementación:

```text
AssertionError: "if current_page == 'Tablero':" not found
1 failed
```

GREEN verificado después de implementar el mosaico:

```text
1 passed in 0.86s
18 passed in 16.63s
```

Comandos ejecutados:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_app_smoke.py::TestWebAppSmoke::test_quick_actions_render_as_a_dashboard_only_mosaic -q
.\.venv\Scripts\python.exe -m pytest tests\test_web_app_smoke.py -q
.\.venv\Scripts\python.exe -m py_compile web\app.py
```

## Cobertura y límites conocidos

`coverage.py` no está instalado en el entorno, por lo que no se generó un
porcentaje. La garantía está cubierta por un contrato estructural específico y
por la prueba integrada de todas las vistas autenticadas de Streamlit.

## Puntos de control

- RED: `14eabb3 test(ui): exige acciones rapidas solo en tablero`
- GREEN: `6e36884 feat(ui): fija mosaico de acciones en tablero`
