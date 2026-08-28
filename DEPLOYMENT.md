# Publicar una demostración de Puntos ECCOS

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

### Soporte técnico en línea opcional

El Asistente ECCOS funciona localmente sin esta configuración. Para permitir
consultas generales por internet cuando la guía local no tenga respuesta, crea
una clave del nivel gratuito en `https://console.groq.com/keys` y agrega:

```toml
GROQ_API_KEY = "TU_CLAVE_PRIVADA"
GROQ_SUPPORT_MODEL = "openai/gpt-oss-20b"
```

No escribas la clave dentro de `web/app.py` ni la publiques en Git. La interfaz
oculta identificadores comunes antes de enviar una pregunta y nunca transmite
bases de datos, ventas, inventarios o historiales. Los límites gratuitos pueden
cambiar; si se agotan, el asistente continúa trabajando en modo local.

6. Pulsa **Deploy**.

## Limitación de la demo gratuita

La aplicación usa SQLite. Streamlit Community Cloud no garantiza que los
archivos locales sean permanentes, por lo que ventas, inventario, usuarios y
cotizaciones pueden reiniciarse. No uses esta instalación para operar una caja
real. Para producción se debe migrar la base de datos a un servicio persistente.
