# Puntos ECCOS

**Puntos ECCOS** es un sistema web comercial de punto de venta para pequeños y
medianos negocios. Fue creado y desarrollado en Tabasco, México, por
**Grupo ECCOS**, con apoyo de tecnologías emergentes como Codex. Centraliza
ventas, inventario, caja, gastos,
clientes, abastecimiento, reportes, estadísticas y catálogo comercial desde el
navegador.

El proyecto funciona exclusivamente como aplicación web con Streamlit. Es
software propietario y no se distribuye gratuitamente. La
interfaz de escritorio basada en PyQt fue retirada y ya no forma parte del
producto.

## Funciones principales

- Venta normal y venta exprés con ticket.
- Inventario, entradas, mermas, ajustes y alertas de existencias.
- Importación de inventario desde Excel y exportación a Excel/PDF.
- Apertura y cierre de caja en pesos mexicanos.
- Gastos, clientes, proveedores y abastecimiento sugerido.
- Cotizaciones, reportes, estadísticas y auditoría.
- Catálogo web configurable con los datos del negocio.
- Perfiles de administrador y vendedor.

## Ejecutar localmente en Windows

Requiere Python 3.11 o superior.

```powershell
cd "C:\Users\HP\Desktop\blue-pos-master"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run web\app.py
```

Después abre `http://localhost:8501` en el navegador.

Las credenciales y códigos privados deben configurarse mediante variables de
entorno o secretos de Streamlit; no deben guardarse en el repositorio.

## Ejecutar pruebas

```powershell
.\.venv\Scripts\python.exe runtests.py
```

## Publicación

Las instrucciones de Streamlit Community Cloud están en
[`DEPLOYMENT.md`](DEPLOYMENT.md). El archivo principal de la aplicación es
`web/app.py`.

## Autoría y contacto

Creado y desarrollado en Tabasco, México, por **Grupo ECCOS**.

Desarrollo asistido con tecnologías emergentes como **Codex**. Esta mención no
implica patrocinio, asociación ni propiedad del producto por parte del proveedor
de dicha tecnología.

Contacto: [mendezeder@gmail.com](mailto:mendezeder@gmail.com)

© 2026 Grupo ECCOS. Todos los derechos reservados.

Condiciones de uso: consulta [`LICENSE`](LICENSE).
