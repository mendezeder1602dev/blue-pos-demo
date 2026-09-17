# Revisión de seguridad local

## Alcance

Revisión estática de autenticación, autorización, respaldos, entradas, SQL, secretos y dependencias del POS local. No incluyó pruebas de penetración ni auditoría CVE externa.

## Controles comprobados

- Contraseñas con PBKDF2-SHA256, sal aleatoria y comparación constante.
- Bloqueo persistente después de intentos fallidos y revocación de sesiones al cambiar claves.
- Secretos iniciales mediante variables de entorno o secretos de Streamlit.
- `.env`, bases locales y `secrets.toml` excluidos de Git.
- Consultas SQLAlchemy parametrizadas; migraciones textuales limitan los identificadores a listas internas.
- Imágenes e importaciones validan contenido, tamaño y formato.
- Restauraciones SQLite validan firma e integridad antes de reemplazar datos.

## Hallazgos corregidos

### Alto: operaciones administrativas protegidas sólo por la interfaz

La gestión de vendedores y la descarga/restauración completa de SQLite no revalidaban el rol en su límite Python. Se agregó `require_role('superuser')` y pruebas que bloquean llamadas desde el contexto `seller`.

## Riesgos residuales

| Prioridad | Riesgo | Recomendación |
|---|---|---|
| Media | El servidor anuncia una URL de red local sin TLS | Si el uso es estrictamente local, enlazar Streamlit a `localhost`; si se comparte en LAN, colocarlo detrás de HTTPS y restringir firewall |
| Media | El archivo de respaldo contiene toda la información comercial | Guardarlo cifrado, limitar copias y no compartirlo por mensajería sin protección |
| Baja | No existe lockfile Python y varias dependencias usan rangos | Generar un archivo de versiones comprobadas para instalaciones reproducibles |
| Baja | `pip check` sólo valida compatibilidad, no vulnerabilidades conocidas | Incorporar `pip-audit` en una revisión periódica cuando haya acceso controlado a su base de vulnerabilidades |

## Evidencia

- `pip check`: dependencias instaladas compatibles.
- Suite final: 268 pruebas y 4 subpruebas aprobadas después del endurecimiento.
- Regresiones de autorización: vendedor rechazado al gestionar cuentas y respaldos.
