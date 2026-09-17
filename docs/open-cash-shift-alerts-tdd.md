# Evidencia TDD: alertas de turnos de caja sin cerrar

## Alcance y criterios

- Una caja no puede abrir un turno nuevo mientras conserve otro sin cierre, aunque sea de un día anterior.
- Otras cajas pueden operar de forma independiente.
- La interfaz muestra duración y severidad del turno, recalculadas en cada interacción o recarga.
- Un turno de más de 8 horas genera advertencia; uno de una fecha anterior genera alerta crítica.
- El cierre continúa siendo manual y auditable.
- El historial permite filtrar turnos sin cerrar y muestra su duración.

## Evidencia

| Garantía | Prueba | Resultado |
| --- | --- | --- |
| Un turno anterior bloquea una nueva apertura de la misma caja. | `test_previous_unclosed_shift_blocks_a_new_day_for_the_same_register` | PASS |
| La consulta de pendientes excluye turnos cerrados. | `test_unclosed_openings_include_only_shifts_without_a_close` | PASS |
| A las 8 horas cambia a advertencia y al cruzar de día cambia a vencido. | `tests.model.test_cash_shift_status` | PASS |
| Los flujos integrales de caja, ventas y devoluciones continúan funcionando. | `tests.model.repository.test_pos_end_to_end_qa` | 21 PASS |
| La interfaz principal conserva su arranque y navegación. | `tests.test_web_app_smoke` | 23 PASS |
| Una instancia anterior conservada por la recarga de Streamlit se reemplaza automáticamente. | `tests.model.repository.test_repository_factory_reload` | PASS |
| La lectura mantiene compatibilidad si un proceso local aún conserva el repositorio anterior. | `test_falls_back_when_hot_reloaded_repository_lacks_the_new_method` | PASS |

RED: las pruebas fallaron inicialmente porque el repositorio no consultaba turnos abiertos entre fechas y no existía el cálculo de duración.

GREEN: las pruebas específicas de caja pasaron 9 casos; la compilación de los módulos modificados también terminó correctamente.

## Recuperación de recarga en caliente

- Fallo capturado: `AttributeError` al ejecutar el fragmento temporizado.
- Causa: la fábrica conservaba en memoria un repositorio creado antes de incorporar `get_unclosed_opening`.
- Recuperación: la fábrica detecta la ausencia del método y crea una instancia actualizada usando la misma sesión.
- Contención adicional: la interfaz ya no usa un fragmento periódico y puede derivar el turno pendiente mediante la API anterior.
- Efecto secundario observado: `WinError 10054` fue producido por la interrupción del fragmento después del error principal.
