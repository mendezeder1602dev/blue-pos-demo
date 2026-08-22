# Publicar la demo de Blue POS

## Streamlit Community Cloud

1. Sube este proyecto a un repositorio de GitHub.
2. Entra a https://share.streamlit.io y conecta tu cuenta de GitHub.
3. Selecciona el repositorio, la rama `main` y el archivo `web/app.py`.
4. En **Advanced settings**, selecciona Python 3.12.
5. En **Secrets**, configura credenciales privadas distintas a las locales:

```toml
BLUE_POS_ADMIN_USER = "administrador_demo"
BLUE_POS_ADMIN_PASSWORD = "CAMBIA_ESTA_CLAVE_SEGURA"
BLUE_POS_RECOVERY_CODE = "CAMBIA_ESTE_CODIGO"
```

6. Pulsa **Deploy**.

## Limitación de la demo gratuita

La aplicación usa SQLite. Streamlit Community Cloud no garantiza que los
archivos locales sean permanentes, por lo que ventas, inventario, usuarios y
cotizaciones pueden reiniciarse. No uses esta instalación para operar una caja
real. Para producción se debe migrar la base de datos a un servicio persistente.
