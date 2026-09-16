# Evidencia TDD: clientes y ventas a crédito

## Alcance

Los recorridos se derivaron de la solicitud del usuario. No se utilizó un plan externo.

- El crédito requiere un cliente activo con nombre, teléfono y dirección.
- El cajero puede buscar, registrar o actualizar al cliente sin abandonar la venta.
- Los datos deben confirmarse antes de cobrar.
- El enganche se registra como abono inicial y deja un saldo pendiente.
- Administrador y vendedor pueden abrir el directorio; las acciones administrativas
  conservan su restricción de rol.

## Evidencia RED/GREEN

| Garantía | Prueba | Tipo | Resultado |
| --- | --- | --- | --- |
| Teléfono y dirección son obligatorios | `test_credit_customer_requires_phone_and_address` | Unidad | PASS |
| Los límites de almacenamiento se validan | `test_customer_fields_reject_values_longer_than_storage_limits` | Unidad/seguridad | PASS |
| La búsqueda coincide por contacto y dirección | `test_customer_search_matches_contact_and_address_fields` | Integración SQLite | PASS |
| El vendedor puede actualizar la ficha | `test_seller_can_update_customer_contact_before_credit` | Integración SQLite | PASS |
| Una ficha incompleta revierte la venta | `test_credit_sale_rejects_customer_with_incomplete_contact_data` | Integración transaccional | PASS |
| El enganche reduce el saldo y crea el abono | `test_credit_sale_records_initial_payment_and_remaining_balance` | Integración transaccional | PASS |
| La interfaz exige confirmación y transmite `customer_id` | `test_credit_checkout_requires_confirmed_complete_customer_profile` | Contrato UI | PASS |
| El vendedor dispone del menú Clientes | `test_seller_navigation_includes_customer_directory` | Contrato UI | PASS |

RED verificado: las pruebas fallaron inicialmente por ausencia de `address`, búsqueda,
actualización, validación de ficha y navegación. GREEN verificado con:

```powershell
.\.venv\Scripts\python.exe -m unittest <9 pruebas de cliente/crédito>
.\.venv\Scripts\python.exe -m unittest <2 contratos UI>
```

Resultado: 11/11 pruebas específicas aprobadas. El smoke test autenticado de Streamlit
también aprobó. `coverage.py` no está instalado, por lo que no se generó porcentaje de
cobertura. No se crearon commits de checkpoint porque el árbol ya contenía cambios locales
del usuario que deben conservarse sin mezclarse.
