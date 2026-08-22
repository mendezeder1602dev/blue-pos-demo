"""Blue POS Web: interfaz web (Streamlit) que reutiliza la capa model/ del escritorio.

Comparte la misma base de datos que la app de escritorio (PyQt5); ambas pueden
usarse en paralelo. Ejecutar con:

    .venv\\Scripts\\streamlit.exe run web/app.py
"""
import calendar
import os
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from model import economy, schema
from model.entity.models import Expense, Product, Quote, QuoteItem, Sale
from model.repository.expense import ExpenseFilter
from model.repository.factory import RepositoryFactory
from model.repository.product import ProductFilter
from model.repository.sale import SaleFilter
from model.util.monetary_types import CUPMoney

LOW_STOCK_THRESHOLD = 5
PAYMENT_METHODS = ('Efectivo', 'Transferencia', 'Tarjeta')
DESCRIPTION_LABEL = 'Descripción'
NET_PROFIT_LABEL = 'Ganancias netas'

st.set_page_config(page_title='Blue POS Web', page_icon='🛒', layout='wide')


def _apply_brand_theme():
    """Sistema visual del POS: limpio, compacto y con alto contraste."""
    st.markdown('''
    <style>
    :root { --sidebar:#08111F; --primary:#123B6D; --primary-dark:#0B294E;
            --ink:#111820; --muted:#5F6873; --line:#D8DDE4; --canvas:#F1F3F6;
            --success:#12805C; --danger:#C73E4D; }
    html, body, .stApp { background:#F1F3F6 !important; color:#111418 !important; }
    [data-testid="stHeader"] {
        background:#FFFFFF !important; border-bottom:1px solid #D8DEE7 !important;
        opacity:1 !important;
    }
    [data-testid="stSidebar"] { background:var(--sidebar); border-right:1px solid #26374A; }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #EAF2F8; }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        border-radius:8px; padding:.52rem .7rem; transition:background .12s ease;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover { background:#111E2F; }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background:#172B43; border-left:3px solid #4D79A8; color:#FFFFFF;
    }
    [data-testid="stMainBlockContainer"] {
        max-width:1540px; padding-top:5.25rem !important; padding-bottom:2rem;
    }
    h1, h2, h3 { color: var(--ink); letter-spacing: -.025em; }
    h1 { font-size: 2rem !important; } h2 { font-size: 1.45rem !important; }
    [data-testid="stMainBlockContainer"] h1,
    [data-testid="stMainBlockContainer"] h2,
    [data-testid="stMainBlockContainer"] h3,
    [data-testid="stMainBlockContainer"] strong { color:#101828; }
    .eccos-hero { background:#FFFFFF !important; border:1px solid #D8DEE7;
        border-left:6px solid #123B6D; border-radius:12px; padding:20px 24px;
        margin:0 0 20px; box-shadow:0 5px 18px rgba(24,34,48,.07); opacity:1; }
    [data-testid="stMainBlockContainer"] .eccos-hero .eccos-eyebrow {
        color:#123B6D !important; font-size:.72rem; font-weight:800; letter-spacing:.11em;
    }
    [data-testid="stMainBlockContainer"] .eccos-hero .eccos-title {
        color:#101828 !important; font-size:1.65rem; font-weight:750; margin:.2rem 0;
        text-shadow:none;
    }
    [data-testid="stMainBlockContainer"] .eccos-hero .eccos-copy {
        color:#475467 !important; font-size:.94rem; font-weight:500; line-height:1.55; margin:0;
    }
    [data-testid="stMetric"] { background:white; border:1px solid var(--line); border-radius:12px;
        padding:14px 16px; box-shadow:0 3px 10px rgba(24,34,48,.04); }
    [data-testid="stMetricLabel"] { color:var(--muted); font-weight:700; }
    [data-testid="stMetricValue"] { color:var(--ink); font-weight:750; }
    [data-testid="stForm"], [data-testid="stExpander"], [data-testid="stDataFrame"] {
        background:#FFFFFF !important; border:1px solid #D8DEE7; border-radius:12px;
        box-shadow:0 3px 12px rgba(24,34,48,.04); opacity:1; }
    [data-testid="stForm"] { padding:16px; }
    [data-testid="stForm"] label, [data-testid="stExpander"] summary,
    [data-testid="stExpander"] p { color:var(--ink) !important; }
    [data-baseweb="input"] > div, [data-baseweb="textarea"] > div,
    [data-baseweb="select"] > div {
        background:#FFFFFF; color:var(--ink); border-color:#D1D6DF;
    }
    [data-baseweb="input"] input, [data-baseweb="textarea"] textarea,
    [data-baseweb="select"] span { color:var(--ink) !important; }
    [data-baseweb="popover"], [role="listbox"] { background:#FFFFFF !important; }
    [role="option"] { color:var(--ink) !important; background:#FFFFFF; }
    [role="option"]:hover, [aria-selected="true"] { background:#E8F1FB !important; }
    .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
        background:#FFFFFF; color:var(--ink); border-radius:9px; min-height:40px;
        font-weight:650; border:1px solid #D1D6DF; box-shadow:none; }
    .stButton > button p, .stDownloadButton > button p {
        color:#182230 !important; font-weight:650 !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background:#E9EEF4; color:var(--primary-dark); border-color:#4D79A8; }
    .stFormSubmitButton > button, button[kind="primary"] {
        background:var(--primary) !important; color:white !important; border-color:var(--primary) !important; }
    .stFormSubmitButton > button p, button[kind="primary"] p,
    .stFormSubmitButton > button span, button[kind="primary"] span {
        color:#FFFFFF !important; font-weight:750 !important;
    }
    .stFormSubmitButton > button:hover, button[kind="primary"]:hover {
        background:var(--primary-dark) !important; border-color:var(--primary-dark) !important; }
    [data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {
        border-color:var(--primary); box-shadow:0 0 0 2px rgba(18,59,109,.14); }
    [data-baseweb="tab-list"] { gap:.35rem; }
    [data-baseweb="tab"] { background:white; border-radius:8px 8px 0 0; padding:.6rem 1rem; }
    [data-baseweb="tab"][aria-selected="true"] { color:var(--primary); }
    .pos-section { color:var(--muted); font-size:.72rem; font-weight:800; letter-spacing:.09em; margin-bottom:4px; }
    .pos-total { background:#202636; border:1px solid #353D50; border-radius:12px;
        padding:18px 20px; color:#FFFFFF !important; margin:8px 0 12px; }
    .pos-total small { color:#D5DAE3 !important; font-weight:700; letter-spacing:.08em; }
    .pos-total strong { color:#FFFFFF !important; display:block; font-size:2rem; margin-top:3px; }
    .st-key-pos_workspace [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius:10px;
    }
    .st-key-pos_workspace [data-testid="stVerticalBlock"] { gap:.65rem; }
    .st-key-pos_workspace [data-testid="stWidgetLabel"] p { font-size:.86rem; }
    .st-key-pos_workspace [data-testid="stNumberInput"] input { min-width:0; }
    .st-key-login_shell { max-width:1120px; margin:1.5rem auto 0; }
    .st-key-login_shell > div > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
        gap:0 !important; align-items:stretch;
        border:1px solid #D8DEE7; border-radius:22px; overflow:hidden;
        box-shadow:0 24px 70px rgba(27,35,63,.14);
    }
    .st-key-login_shell [data-testid="stColumn"]:first-child {
        background:linear-gradient(145deg,#05080D 0%,#081A31 45%,#123B6D 100%);
        padding:clamp(2rem,4vw,4.25rem); min-height:590px;
    }
    .st-key-login_shell [data-testid="stColumn"]:last-child {
        background:#FFFFFF; padding:clamp(2rem,4vw,4rem); min-height:590px;
    }
    .login-brand { color:#FFFFFF; height:100%; display:flex; flex-direction:column; }
    .login-logo { display:flex; align-items:center; gap:12px; color:#FFFFFF; font-size:1.15rem;
        font-weight:800; letter-spacing:-.02em; margin-bottom:4.5rem; }
    .login-logo-mark { width:42px; height:42px; display:grid; place-items:center; border-radius:12px;
        background:linear-gradient(135deg,#4D79A8,#123B6D); box-shadow:0 10px 25px rgba(0,0,0,.28); }
    .login-kicker { color:#9DB9D5; font-size:.72rem; font-weight:800; letter-spacing:.14em; }
    .login-brand h1 { color:#FFFFFF !important; font-size:clamp(2rem,3.5vw,3.35rem) !important;
        line-height:1.05; letter-spacing:-.05em; margin:.7rem 0 1.1rem; }
    .login-brand-copy { color:#D9DBE8; font-size:1.02rem; line-height:1.65; max-width:470px; }
    .login-benefits { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:2.4rem; }
    .login-benefit { color:#F5F5FF; font-size:.78rem; font-weight:650; padding:12px 10px;
        border:1px solid rgba(255,255,255,.16); background:rgba(255,255,255,.07); border-radius:10px; }
    .login-benefit span { display:block; color:#82A9CE; font-size:1rem; margin-bottom:4px; }
    .login-form-head { margin-bottom:1.6rem; }
    .login-form-head small { color:#123B6D; font-weight:800; letter-spacing:.1em; }
    .login-form-head h2 { font-size:1.75rem !important; margin:.4rem 0 .45rem; }
    .login-form-head p { color:#667085; line-height:1.55; margin:0; }
    .st-key-login_shell [data-testid="stForm"] { box-shadow:none; border:0; padding:0; }
    .st-key-login_shell [data-testid="stButton"] button,
    .st-key-login_shell [data-testid="stFormSubmitButton"] button { min-height:48px; }
    .st-key-login_shell [data-testid="stSegmentedControl"] { margin-bottom:.8rem; }
    .login-trust { color:#7A8494; font-size:.76rem; text-align:center; margin-top:1rem; }
    .brand-legal { color:#8993A1; font-size:.7rem; line-height:1.5; margin-top:1.4rem; }
    .brand-legal strong { color:#D7E1EB !important; }
    .sidebar-legal { color:#9AA8B8; font-size:.68rem; line-height:1.5; margin-top:1rem; }
    .stock-ok { color:var(--success); font-weight:700; }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background:#FFFFFF !important; opacity:1 !important;
    }
    [data-testid="stAlert"] { opacity:1 !important; }
    @media (max-width: 900px) {
        [data-testid="stMainBlockContainer"] {
            padding-left:1rem; padding-right:1rem; padding-top:5.25rem !important;
        }
        .eccos-hero { padding:16px 18px; }
        .eccos-title { font-size:1.4rem !important; }
    }
    /* Streamlit apila columnas demasiado tarde para una caja POS. En pantallas
       medianas dejamos cada panel a ancho completo para evitar controles cortados. */
    @media (max-width: 1050px) {
        .st-key-pos_workspace > div > [data-testid="stVerticalBlock"] >
        [data-testid="stHorizontalBlock"] {
            flex-direction:column !important;
        }
        .st-key-pos_workspace > div > [data-testid="stVerticalBlock"] >
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            width:100% !important; flex:1 1 100% !important; min-width:0 !important;
        }
        .st-key-pos_workspace [data-testid="stForm"] { padding:12px; }
        .st-key-pos_workspace .pos-total { padding:13px 16px; }
        .st-key-pos_workspace .pos-total strong { font-size:1.65rem; }
        .st-key-login_shell { margin-top:0; }
        .st-key-login_shell > div > [data-testid="stVerticalBlock"] >
        [data-testid="stHorizontalBlock"] { flex-direction:column !important; }
        .st-key-login_shell [data-testid="stColumn"] { width:100% !important; flex:1 1 100% !important; }
        .st-key-login_shell [data-testid="stColumn"]:first-child { min-height:auto; padding:2rem; }
        .st-key-login_shell [data-testid="stColumn"]:last-child { min-height:auto; padding:2rem; }
        .login-logo { margin-bottom:2rem; }
        .login-benefits { margin-top:1.5rem; }
    }
    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"] { padding-left:.65rem; padding-right:.65rem; }
        .eccos-hero { padding:12px 14px; margin-bottom:12px; }
        .eccos-copy { display:none; }
        .st-key-pos_workspace button { min-height:38px; }
    }
    hr { border-color:var(--line); }
    </style>
    ''', unsafe_allow_html=True)


def _hero(title, subtitle, eyebrow='GRUPO ECCOS · PUNTO DE VENTA'):
    st.markdown(
        f'<section class="eccos-hero"><div class="eccos-eyebrow">{eyebrow}</div>'
        f'<div class="eccos-title">{title}</div><p class="eccos-copy">{subtitle}</p></section>',
        unsafe_allow_html=True,
    )


_apply_brand_theme()


# ---------------------------------------------------------------------------
# Autenticación (misma lógica y credenciales que la app de escritorio)
# ---------------------------------------------------------------------------

def _bootstrap_auth():
    if st.session_state.get('_auth_ready'):
        return
    # En hosting, las credenciales iniciales se configuran como secretos y no
    # se incluyen en el repositorio. Los valores locales conservan compatibilidad.
    try:
        secret_names = {
            'BLUE_POS_ADMIN_USER': 'BLUE_POS_ADMIN_USER',
            'BLUE_POS_ADMIN_PASSWORD': 'BLUE_POS_ADMIN_PASSWORD',
            'BLUE_POS_RECOVERY_CODE': 'BLUE_POS_RECOVERY_CODE',
        }
        for environment_name, secret_name in secret_names.items():
            if secret_name in st.secrets:
                os.environ[environment_name] = str(st.secrets[secret_name])
    except FileNotFoundError:
        pass
    schema.create_auth_database()
    st.session_state['_auth_ready'] = True


def _enter_seller():
    return SimpleNamespace(role='seller', display_name='Vendedor', workspace_key='primary')


def _render_login():
    _bootstrap_auth()
    login_shell = st.container(key='login_shell')
    brand_column, access_column = login_shell.columns((1.18, 1), gap=None)

    with brand_column:
        st.markdown('''
        <section class="login-brand">
          <div class="login-logo"><span class="login-logo-mark">◈</span> Blue POS</div>
          <div class="login-kicker">CONTROL INTELIGENTE PARA TU NEGOCIO</div>
          <h1>Vende mejor.<br>Decide con claridad.</h1>
          <p class="login-brand-copy">Todo lo que necesitas para cobrar, controlar tu inventario
          y conocer el resultado real de tu negocio, desde un solo lugar.</p>
          <div class="login-benefits">
            <div class="login-benefit"><span>✓</span>Ventas ágiles</div>
            <div class="login-benefit"><span>✓</span>Stock al día</div>
            <div class="login-benefit"><span>✓</span>Reportes claros</div>
          </div>
          <div class="brand-legal"><strong>Desarrollado por Grupo ECCOS</strong><br>
          © 2026 Grupo ECCOS · Licencia CC BY-NC 4.0</div>
        </section>
        ''', unsafe_allow_html=True)

    with access_column:
        st.markdown('''
        <div class="login-form-head">
          <small>ACCESO SEGURO</small>
          <h2>Bienvenido de nuevo</h2>
          <p>Selecciona tu perfil para comenzar tu jornada.</p>
        </div>
        ''', unsafe_allow_html=True)
        role_label = st.segmented_control(
            'Tipo de acceso', ('Administrador', 'Vendedor'), default='Administrador',
            selection_mode='single', width='stretch', key='login_role',
        )

        if role_label == 'Administrador':
            with st.form('login_form', border=False):
                username = st.text_input('Usuario', placeholder='Escribe tu usuario', icon=':material/person:')
                password = st.text_input(
                    'Contraseña', type='password', placeholder='Escribe tu contraseña',
                    icon=':material/lock:',
                )
                submitted = st.form_submit_button(
                    'Iniciar sesión', type='primary', width='stretch', icon=':material/login:'
                )
            if submitted:
                users = RepositoryFactory.get_user_repository()
                user = users.authenticate(username.strip(), password)
                if user is None:
                    st.error('Usuario o contraseña incorrectos.', icon=':material/error:')
                elif user.role != 'superuser':
                    st.error('Selecciona el perfil asociado a esta cuenta.', icon=':material/error:')
                else:
                    _log_in(user)
        else:
            st.caption('Acceso rápido para cobrar y consultar existencias, sin información financiera sensible.')
            if st.button(
                'Abrir punto de venta', type='primary', width='stretch', icon=':material/point_of_sale:'
            ):
                _log_in(_enter_seller())

        with st.expander('Recuperar acceso de administrador', icon=':material/key:'):
            with st.form('recovery_form', border=False):
                reset_username = st.text_input('Administrador')
                reset_code = st.text_input('Código de recuperación', type='password')
                new_password = st.text_input('Nueva contraseña (mínimo 8)', type='password')
                reset_submitted = st.form_submit_button('Actualizar contraseña', width='stretch')
            if reset_submitted:
                try:
                    RepositoryFactory.get_user_repository().reset_password(
                        reset_username, reset_code, new_password
                    )
                    st.success('Contraseña actualizada. Ya puedes iniciar sesión.')
                except ValueError as error:
                    st.error(str(error))
        st.markdown('<div class="login-trust">Tus datos permanecen protegidos en tu sistema.</div>',
                    unsafe_allow_html=True)


def _log_in(user, persist=True):
    schema.activate_user_workspace(user)
    st.session_state['user'] = user
    st.session_state['page'] = 'Tablero'
    if persist and getattr(user, 'id', None) is not None:
        token = RepositoryFactory.get_user_repository().create_session(user)
        st.query_params['session'] = token
    st.rerun()


def _log_out():
    token = st.query_params.get('session')
    if token:
        RepositoryFactory.get_user_repository().revoke_session(token)
        del st.query_params['session']
    st.session_state.pop('user', None)
    st.session_state.pop('page', None)
    st.rerun()


def _is_administrator():
    return getattr(st.session_state['user'], 'role', '') == 'superuser'


# ---------------------------------------------------------------------------
# Tablero
# ---------------------------------------------------------------------------

def _get_low_stock_products():
    product_filter = ProductFilter()
    product_filter.less_than_quantity = LOW_STOCK_THRESHOLD
    products = RepositoryFactory.get_product_repository().get_products_by_filter(product_filter)
    return [product for product in products if not product.is_temporary]


def _render_dashboard():
    _hero('Centro de operación', 'Ventas, inventario y resultados del negocio en una sola vista.')
    summary = RepositoryFactory.get_economic_summary_repository().get_economic_summary_on_day(date.today())
    product_quantity = len(RepositoryFactory.get_product_repository().get_all_products())
    columns = st.columns(5)
    columns[0].metric('Ventas de hoy', f'{summary.acquired_money.amount:,.2f} MXN')
    columns[1].metric('Operaciones', str(summary.sale_quantity or 0))
    columns[2].metric('Gastos de hoy', f'{summary.total_expense.amount:,.2f} MXN')
    columns[3].metric('Utilidad neta', f'{summary.net_profit.amount:,.2f} MXN')
    columns[4].metric('Productos', str(product_quantity))

    if _is_administrator():
        st.subheader('Alerta de inventario')
        low_stock = _get_low_stock_products()
        if not low_stock:
            st.success(f'Todos los productos tienen más de {LOW_STOCK_THRESHOLD} unidades disponibles.')
        else:
            st.warning('Estos productos están por agotarse, considera reabastecerlos pronto:')
            st.table(pd.DataFrame([{'Producto': p.name, 'Unidades': p.quantity} for p in low_stock]))


# ---------------------------------------------------------------------------
# Ventas
# ---------------------------------------------------------------------------

def _payment_controls(prefix, total):
    """Controles de cobro reutilizables y datos seguros para auditoría."""
    method = st.segmented_control(
        'Método de pago', PAYMENT_METHODS, default='Efectivo', selection_mode='single',
        width='stretch', key=f'{prefix}_payment_method',
    ) or 'Efectivo'
    details = []
    validation_error = ''

    if method == 'Tarjeta':
        st.caption('Registra solo datos de referencia. Nunca captures el número completo ni el CVV.')
        card_type = st.segmented_control(
            'Tipo de tarjeta', ('Débito', 'Crédito'), default='Débito',
            selection_mode='single', width='stretch', key=f'{prefix}_card_type',
        ) or 'Débito'
        card_columns = st.columns(2)
        last_four = card_columns[0].text_input(
            'Últimos 4 dígitos', max_chars=4, placeholder='0000', key=f'{prefix}_card_last4'
        ).strip()
        authorization = card_columns[1].text_input(
            'Autorización', placeholder='Folio del voucher', key=f'{prefix}_card_auth'
        ).strip()
        if len(last_four) != 4 or not last_four.isdigit():
            validation_error = 'Captura los 4 últimos dígitos de la tarjeta.'
        details.extend([f'Tarjeta: {card_type}', f'Terminación: {last_four}'])
        if authorization:
            details.append(f'Autorización: {authorization}')
    elif method == 'Transferencia':
        transfer_columns = st.columns(2)
        bank = transfer_columns[0].selectbox(
            'Banco receptor', ('BBVA', 'Banamex', 'Santander', 'Banorte', 'HSBC',
                               'Banco Azteca', 'Mercado Pago', 'Otro'),
            key=f'{prefix}_transfer_bank',
        )
        transfer_reference = transfer_columns[1].text_input(
            'Referencia', placeholder='Folio o clave de rastreo', key=f'{prefix}_transfer_reference'
        ).strip()
        if not transfer_reference:
            validation_error = 'Captura la referencia o clave de rastreo de la transferencia.'
        details.extend([f'Banco: {bank}', f'Referencia: {transfer_reference}'])
    else:
        received = st.number_input(
            'Efectivo recibido', min_value=0.0, value=float(total), step=10.0,
            format='%.2f', key=f'{prefix}_cash_received',
        )
        change = max(0.0, float(received) - float(total))
        if float(received) < float(total):
            validation_error = f'Faltan ${float(total) - float(received):,.2f} para completar el cobro.'
        st.metric('Cambio a entregar', f'${change:,.2f}')
        details.extend([f'Recibido: ${float(received):,.2f}', f'Cambio: ${change:,.2f}'])

    note = st.text_input(
        'Nota adicional', placeholder='Cliente, pedido u observación (opcional)', key=f'{prefix}_note'
    ).strip()
    if note:
        details.append(f'Nota: {note}')
    return method, ' | '.join(details), validation_error

def _render_sales():
    _hero('Punto de venta', 'Agrega productos al carrito y completa el cobro desde una sola pantalla.', 'CAJA · TURNO ACTIVO')
    st.session_state.setdefault('pos_cart', {})
    repository = RepositoryFactory.get_product_repository()
    products = [product for product in repository.get_all_products() if not product.is_temporary]
    available = [product for product in products if product.quantity > 0]
    product_by_id = {product.id: product for product in products}

    # Elimina del carrito referencias que ya no existen y ajusta cantidades al stock actual.
    for product_id in list(st.session_state.pos_cart):
        product = product_by_id.get(product_id)
        if product is None or product.quantity <= 0:
            st.session_state.pos_cart.pop(product_id, None)
        else:
            st.session_state.pos_cart[product_id] = min(
                st.session_state.pos_cart[product_id], product.quantity
            )

    # La clave crea una clase CSS estable (st-key-pos_workspace) para que esta
    # pantalla pueda responder al ancho disponible sin afectar otros módulos.
    workspace = st.container(key='pos_workspace')
    catalog_column, checkout_column = workspace.columns((1.8, 1.2), gap='medium')

    with catalog_column:
        st.markdown('<div class="pos-section">CATÁLOGO</div>', unsafe_allow_html=True)
        search = st.text_input(
            'Buscar productos', placeholder='Buscar por nombre o código de barras',
            icon=':material/search:', label_visibility='collapsed', key='pos_search',
        ).strip().lower()
        filtered = [
            product for product in available
            if not search or search in product.name.lower() or search in (product.barcode or '').lower()
        ]
        st.caption(f'{len(filtered)} productos disponibles')

        if not available:
            st.info('No hay productos con existencias. Agrega inventario para comenzar.', icon=':material/inventory_2:')
        elif not filtered:
            st.warning('No encontramos productos con esa búsqueda.', icon=':material/search_off:')
        else:
            for product in filtered[:16]:
                with st.container(border=True):
                    st.markdown(f'**{product.name}**')
                    barcode = f' · Código {product.barcode}' if product.barcode else ''
                    st.caption(f'{product.quantity} disponibles{barcode}')
                    st.markdown(f'### ${float(product.price.amount):,.2f}')
                    in_cart = st.session_state.pos_cart.get(product.id, 0)
                    if in_cart:
                        st.caption(f'En la venta actual: {in_cart} unidades')
                    button_label = f'Agregar otra · {in_cart} en venta' if in_cart else 'Agregar a la venta'
                    if st.button(
                        button_label, key=f'add_cart_{product.id}',
                        icon=':material/add_shopping_cart:', width='stretch',
                    ):
                        current = st.session_state.pos_cart.get(product.id, 0)
                        if current < product.quantity:
                            st.session_state.pos_cart[product.id] = current + 1
                            st.rerun()
                        else:
                            st.toast('Ya agregaste todo el stock disponible.', icon=':material/warning:')

    with checkout_column:
        cart = st.session_state.pos_cart
        item_count = sum(cart.values())
        st.markdown(f'<div class="pos-section">VENTA ACTUAL · {item_count} ARTÍCULOS</div>', unsafe_allow_html=True)
        with st.container(border=True):
            if not cart:
                st.markdown('### Tu carrito está vacío')
                st.caption('Busca un producto y presiona Agregar para iniciar la venta.')
                st.button('Cobrar', disabled=True, width='stretch', icon=':material/payments:')
            else:
                total = 0.0
                for product_id, current_quantity in list(cart.items()):
                    product = product_by_id[product_id]
                    line_total = float(product.price.amount) * current_quantity
                    total += line_total
                    st.markdown(f'**{product.name}** — **{current_quantity} unidades**')
                    quantity_column, line_column, remove_column = st.columns(
                        (1.15, 1.25, .45), vertical_alignment='center'
                    )
                    new_quantity = quantity_column.number_input(
                        f'Cantidad de {product.name}', min_value=1, max_value=product.quantity,
                        value=current_quantity, step=1, key=f'cart_qty_{product_id}',
                        label_visibility='collapsed',
                    )
                    if int(new_quantity) != current_quantity:
                        st.session_state.pos_cart[product_id] = int(new_quantity)
                        st.rerun()
                    line_column.markdown(f'**${line_total:,.2f}**')
                    line_column.caption(f'${float(product.price.amount):,.2f} c/u')
                    if remove_column.button('', key=f'remove_cart_{product_id}', icon=':material/delete:'):
                        st.session_state.pos_cart.pop(product_id, None)
                        st.rerun()

                st.markdown(
                    f'<div class="pos-total"><small>TOTAL A COBRAR</small>'
                    f'<strong>${total:,.2f} MXN</strong></div>', unsafe_allow_html=True,
                )
                payment_method, payment_details, payment_error = _payment_controls('checkout', total)
                sale_date = st.date_input('Fecha de venta', value=date.today(), key='checkout_date')
                submitted = st.button(
                    f'Cobrar ${total:,.2f}', type='primary', width='stretch',
                    icon=':material/payments:', key='checkout_submit',
                )

                clear_column, suspend_column = st.columns(2)
                if clear_column.button('Vaciar', width='stretch', icon=':material/delete_sweep:'):
                    st.session_state.pos_cart = {}
                    st.rerun()
                suspend_column.button('Venta en espera', width='stretch', icon=':material/pause_circle:', disabled=True,
                                      help='Disponible próximamente')

                if submitted:
                    if payment_error:
                        st.error(payment_error, icon=':material/error:')
                        return
                    try:
                        sale_repository = RepositoryFactory.get_sale_repository()
                        for product_id, quantity in cart.items():
                            product = product_by_id[product_id]
                            sale = Sale(
                                product_id=product.id, price=product.price, cost=product.cost,
                                date=sale_date, payment_method=payment_method or 'Efectivo',
                                payment_details=payment_details,
                            )
                            sale_repository.insert_sales(sale, int(quantity))
                        st.session_state.pos_cart = {}
                        st.toast('Venta registrada correctamente.', icon=':material/check_circle:')
                        st.rerun()
                    except Exception as error:
                        st.error(f'No se pudo completar la venta: {error}')

        with st.expander('Movimientos recientes', icon=':material/receipt_long:'):
            recent_sales = sorted(
                RepositoryFactory.get_sale_repository().get_all_sales(),
                key=lambda sale: sale.id, reverse=True,
            )[:8]
            if not recent_sales:
                st.caption('Todavía no hay ventas registradas.')
            for recent_sale in recent_sales:
                product = product_by_id.get(recent_sale.product_id)
                name = product.name if product else getattr(recent_sale.product, 'name', f'Producto #{recent_sale.product_id}')
                row, undo = st.columns((3, 1), vertical_alignment='center')
                row.markdown(f'**#{recent_sale.id} · {name}**')
                row.caption(f'{recent_sale.date} · {recent_sale.payment_method or "Sin método"} · {recent_sale.price}')
                if undo.button('Anular', key=f'undo_sale_{recent_sale.id}'):
                    RepositoryFactory.get_sale_repository().delete_sale(recent_sale)
                    st.rerun()


# ---------------------------------------------------------------------------
# Inventario
# ---------------------------------------------------------------------------

def _render_inventory():
    _hero('Inventario', 'Controla catálogo, precios y existencias con información lista para decidir.', 'GESTIÓN · CATÁLOGO')
    products = RepositoryFactory.get_product_repository().get_all_products()

    with st.expander('Agregar producto'):
        with st.form('add_product_form', clear_on_submit=True):
            name = st.text_input('Nombre')
            description = st.text_area(DESCRIPTION_LABEL, height=68)
            price = st.number_input('Precio de venta', min_value=0.01, step=1.0, format='%.2f')
            cost = st.number_input('Precio de costo', min_value=0.0, step=1.0, format='%.2f')
            quantity = st.number_input('Cantidad disponible', min_value=0, step=1)
            barcode = st.text_input('Código de barras (opcional)')
            submitted = st.form_submit_button('Guardar producto')
        if submitted:
            try:
                product = Product(name=name, description=description, price=CUPMoney(f'{price:.2f}'),
                                 cost=CUPMoney(f'{cost:.2f}'), quantity=int(quantity), barcode=barcode)
                RepositoryFactory.get_product_repository().insert_product(product)
                st.success(f'Producto "{name}" agregado.')
                st.rerun()
            except Exception as error:
                st.error(str(error))

    st.subheader('Catálogo')
    if not products:
        st.info('No hay productos registrados.')
        return
    st.dataframe(pd.DataFrame([{
        'ID': p.id, 'Nombre': p.name, 'Precio': str(p.price), 'Costo': str(p.cost),
        'Cantidad': p.quantity, 'Código de barras': p.barcode or '',
    } for p in products]), width='stretch', hide_index=True)

    with st.expander('Editar o eliminar producto'):
        names = [p.name for p in products]
        selected_name = st.selectbox('Selecciona un producto', names, key='inventory_edit_select')
        product = next(p for p in products if p.name == selected_name)
        with st.form(f'edit_product_form_{product.id}'):
            name = st.text_input('Nombre', value=product.name)
            description = st.text_area(DESCRIPTION_LABEL, value=product.description or '', height=68)
            price = st.number_input('Precio de venta', min_value=0.01, step=1.0, format='%.2f',
                                    value=float(product.price.amount))
            cost = st.number_input('Precio de costo', min_value=0.0, step=1.0, format='%.2f',
                                   value=float(product.cost.amount))
            quantity = st.number_input('Cantidad disponible', min_value=0, step=1, value=product.quantity)
            barcode = st.text_input('Código de barras', value=product.barcode or '')
            save_submitted = st.form_submit_button('Guardar cambios')
        if save_submitted:
            try:
                updated = Product(id=product.id, name=name, description=description,
                                  price=CUPMoney(f'{price:.2f}'), cost=CUPMoney(f'{cost:.2f}'),
                                  quantity=int(quantity), barcode=barcode)
                RepositoryFactory.get_product_repository().update_product(updated)
                st.success('Producto actualizado.')
                st.rerun()
            except Exception as error:
                st.error(str(error))
        if st.button('Eliminar producto', key=f'delete_product_{product.id}'):
            RepositoryFactory.get_product_repository().delete_product(product)
            st.success(f'Producto "{product.name}" eliminado.')
            st.rerun()


def _render_inventory_readonly():
    _hero('Consulta de inventario', 'Revisa precios y existencias sin modificar el catálogo.',
          'VENDEDOR · SOLO LECTURA')
    products = RepositoryFactory.get_product_repository().get_all_products()
    search = st.text_input('Buscar inventario', placeholder='Nombre o código de barras',
                           icon=':material/search:', label_visibility='collapsed').strip().lower()
    visible = [p for p in products if not search or search in p.name.lower()
               or search in (p.barcode or '').lower()]
    metrics = st.columns(3)
    metrics[0].metric('Productos', len(visible))
    metrics[1].metric('Unidades disponibles', sum(p.quantity for p in visible))
    metrics[2].metric('Por agotarse', sum(p.quantity <= LOW_STOCK_THRESHOLD for p in visible))
    if not visible:
        st.info('No hay productos que coincidan con la búsqueda.', icon=':material/inventory_2:')
        return
    st.dataframe(pd.DataFrame([{
        'Producto': p.name, 'Precio de venta': float(p.price.amount),
        'Disponibles': p.quantity, 'Código': p.barcode or '—',
    } for p in visible]), column_config={
        'Precio de venta': st.column_config.NumberColumn(format='$ %.2f'),
        'Disponibles': st.column_config.NumberColumn(format='%d'),
    }, width='stretch', hide_index=True)
    st.caption('Solo consulta: el vendedor no puede editar costos, precios ni existencias.')


def _render_express_sale():
    _hero('Venta express', 'Cobra un artículo que todavía no existe en el catálogo.',
          'VENDEDOR · COBRO RÁPIDO')
    st.info('La venta aparecerá en reportes. Solo se agregará al inventario si lo indicas.',
            icon=':material/bolt:')
    name = st.text_input('Artículo o servicio', placeholder='Ej. Entrega especial')
    columns = st.columns(3)
    quantity = columns[0].number_input('Cantidad', min_value=1, value=1, step=1)
    unit_price = columns[1].number_input('Precio unitario', min_value=0.01, value=1.0,
                                         step=1.0, format='%.2f')
    unit_cost = columns[2].number_input('Costo unitario', min_value=0.0, value=0.0,
                                        step=1.0, format='%.2f')
    add_to_inventory = st.toggle('Agregar este artículo al inventario')
    remaining_stock = st.number_input(
        'Unidades que quedarán disponibles después de esta venta', min_value=0,
        value=0, step=1, disabled=not add_to_inventory)
    total = int(quantity) * float(unit_price)
    st.markdown(f'<div class="pos-total"><small>TOTAL A COBRAR</small>'
                f'<strong>${total:,.2f} MXN</strong></div>', unsafe_allow_html=True)
    payment_method, payment_details, payment_error = _payment_controls('express', total)
    submitted = st.button(f'Cobrar ${total:,.2f}', type='primary', width='stretch',
                          icon=':material/bolt:', key='express_submit')
    if submitted:
        if payment_error:
            st.error(payment_error, icon=':material/error:')
            return
        clean_name = name.strip()
        if not clean_name:
            st.error('Escribe el nombre del artículo o servicio.', icon=':material/error:')
            return
        try:
            product_name = clean_name if add_to_inventory else \
                f'Express · {clean_name[:35]} · {datetime.now():%Y%m%d%H%M%S%f}'
            product = Product(
                name=product_name, description='Creado desde Venta express',
                price=CUPMoney(f'{unit_price:.2f}'), cost=CUPMoney(f'{unit_cost:.2f}'),
                quantity=int(quantity) + (int(remaining_stock) if add_to_inventory else 0),
                barcode='', is_temporary=not add_to_inventory)
            RepositoryFactory.get_product_repository().insert_product(product)
            sale = Sale(product_id=product.id, price=product.price, cost=product.cost,
                        date=date.today(), payment_method=payment_method or 'Efectivo',
                        payment_details=payment_details)
            RepositoryFactory.get_sale_repository().insert_sales(sale, int(quantity))
            message = 'Venta express registrada.'
            if add_to_inventory:
                message += f' {clean_name} quedó agregado al inventario.'
            st.success(message, icon=':material/check_circle:')
        except Exception as error:
            st.error(f'No se pudo registrar la venta express: {error}')


def _render_quotes():
    _hero('Cotizaciones', 'Prepara propuestas sin descontar existencias ni registrar una venta.',
          'VENDEDOR · PROPUESTAS')
    st.session_state.setdefault('quote_items', [])
    products = RepositoryFactory.get_product_repository().get_all_products()
    create_tab, history_tab = st.tabs(['Nueva cotización', 'Historial'])
    with create_tab:
        options = ['Artículo libre'] + [p.name for p in products]
        with st.form('quote_add_item', border=False, clear_on_submit=True):
            row = st.columns((2, 1, 1), vertical_alignment='bottom')
            source = row[0].selectbox('Artículo', options)
            quantity = row[1].number_input('Cantidad', min_value=1, value=1, step=1)
            selected = next((p for p in products if p.name == source), None)
            price = row[2].number_input('Precio unitario', min_value=0.01,
                                        value=float(selected.price.amount) if selected else 1.0,
                                        step=1.0, format='%.2f')
            custom_name = st.text_input('Descripción del artículo',
                                        disabled=source != 'Artículo libre',
                                        placeholder='Producto o servicio')
            add_item = st.form_submit_button('Agregar', icon=':material/add:')
        if add_item:
            description = custom_name.strip() if source == 'Artículo libre' else source
            if description:
                matching_item = next((item for item in st.session_state.quote_items
                                      if item['description'] == description
                                      and item['unit_price'] == float(price)), None)
                if matching_item:
                    matching_item['quantity'] += int(quantity)
                else:
                    st.session_state.quote_items.append({
                        'description': description, 'quantity': int(quantity),
                        'unit_price': float(price)})
                st.rerun()
            else:
                st.error('Escribe una descripción para el artículo.')
        items = st.session_state.quote_items
        if items:
            frame = pd.DataFrame([{
                'Artículo': item['description'], 'Cantidad': item['quantity'],
                'Precio unitario': item['unit_price'],
                'Importe': item['quantity'] * item['unit_price'],
            } for item in items])
            st.dataframe(frame, column_config={
                'Precio unitario': st.column_config.NumberColumn(format='$ %.2f'),
                'Importe': st.column_config.NumberColumn(format='$ %.2f'),
            }, hide_index=True, width='stretch')
            st.metric('Total cotizado', f"${frame['Importe'].sum():,.2f}")
            with st.form('save_quote_form', clear_on_submit=True):
                customer = st.text_input('Cliente', placeholder='Público general')
                notes = st.text_area('Notas', height=70)
                save_quote = st.form_submit_button('Guardar cotización', type='primary',
                                                    width='stretch', icon=':material/save:')
            if st.button('Vaciar borrador', icon=':material/delete_sweep:'):
                st.session_state.quote_items = []
                st.rerun()
            if save_quote:
                quote = Quote(customer=customer.strip() or 'Público general', notes=notes.strip())
                quote.items = [QuoteItem(description=item['description'], quantity=item['quantity'],
                                         unit_price=CUPMoney(f"{item['unit_price']:.2f}"))
                               for item in items]
                try:
                    RepositoryFactory.get_quote_repository().insert_quote(quote)
                    st.session_state.quote_items = []
                    st.success(f'Cotización #{quote.id} guardada.')
                    st.rerun()
                except Exception as error:
                    st.error(f'No se pudo guardar: {error}')
        else:
            st.caption('Agrega artículos para comenzar la cotización.')
    with history_tab:
        quotes = RepositoryFactory.get_quote_repository().get_all_quotes()
        if not quotes:
            st.info('Todavía no hay cotizaciones guardadas.', icon=':material/request_quote:')
        for quote in quotes:
            total = sum(float(item.unit_price.amount) * item.quantity for item in quote.items)
            with st.expander(f'#{quote.id} · {quote.customer} · ${total:,.2f} · {quote.status}',
                             icon=':material/request_quote:'):
                st.caption(f'{quote.date} · {quote.notes or "Sin notas"}')
                st.dataframe(pd.DataFrame([{
                    'Artículo': item.description, 'Cantidad': item.quantity,
                    'Precio': float(item.unit_price.amount),
                    'Importe': float(item.unit_price.amount) * item.quantity,
                } for item in quote.items]), hide_index=True, width='stretch')
                actions = st.columns(3)
                if actions[0].button('Aceptada', key=f'accept_quote_{quote.id}'):
                    RepositoryFactory.get_quote_repository().update_status(quote.id, 'Aceptada')
                    st.rerun()
                if actions[1].button('Vencida', key=f'expire_quote_{quote.id}'):
                    RepositoryFactory.get_quote_repository().update_status(quote.id, 'Vencida')
                    st.rerun()
                if actions[2].button('Eliminar', key=f'delete_quote_{quote.id}'):
                    RepositoryFactory.get_quote_repository().delete_quote(quote.id)
                    st.rerun()


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def _render_expenses():
    _hero('Gastos operativos', 'Registra y consulta egresos para mantener visible la rentabilidad real.', 'FINANZAS · EGRESOS')
    with st.expander('Agregar gasto'):
        with st.form('add_expense_form'):
            name = st.text_input('Nombre')
            description = st.text_area('Descripción', height=68)
            spent_money = st.number_input('Dinero gastado', min_value=0.01, step=1.0, format='%.2f')
            expense_date = st.date_input('Fecha', value=date.today())
            submitted = st.form_submit_button('Guardar gasto')
        if submitted:
            try:
                expense = Expense(name=name, description=description,
                                  spent_money=CUPMoney(f'{spent_money:.2f}'), date=expense_date)
                RepositoryFactory.get_expense_repository().insert_expense(expense)
                st.success(f'Gasto "{name}" registrado.')
                st.rerun()
            except Exception as error:
                st.error(str(error))

    st.subheader('Gastos registrados')
    expenses = RepositoryFactory.get_expense_repository().get_all_expenses()
    if not expenses:
        st.info('No hay gastos registrados.')
        return
    st.dataframe(pd.DataFrame([{
        'ID': e.id, 'Nombre': e.name, 'Descripción': e.description or '',
        'Gastado': str(e.spent_money), 'Fecha': str(e.date),
    } for e in expenses]), width='stretch', hide_index=True)

    with st.expander('Eliminar gasto'):
        options = {f'#{e.id} · {e.name} · {e.spent_money}': e.id for e in expenses}
        selected = st.selectbox('Selecciona un gasto', list(options.keys()))
        if st.button('Eliminar gasto seleccionado'):
            RepositoryFactory.get_expense_repository().delete_expenses([options[selected]])
            st.success('Gasto eliminado.')
            st.rerun()


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

def _summary_for_range(initial_date: date, final_date: date):
    sale_filter = SaleFilter()
    sale_filter.minimum_date = initial_date
    sale_filter.maximum_date = final_date
    sales = RepositoryFactory.get_sale_repository().get_sales_by_filter(sale_filter)

    expense_filter = ExpenseFilter()
    expense_filter.minimum_date = initial_date
    expense_filter.maximum_date = final_date
    expenses = RepositoryFactory.get_expense_repository().get_expenses_by_filter(expense_filter)

    acquired_money = economy.calculate_collected_money(sales)
    total_profit = economy.calculate_total_profit(sales)
    total_expense = CUPMoney('0')
    for an_expense in expenses:
        total_expense += an_expense.spent_money
    return {
        'sale_quantity': len(sales), 'acquired_money': acquired_money,
        'total_profit': total_profit, 'total_expense': total_expense,
        'net_profit': total_profit - total_expense, 'sales': sales, 'expenses': expenses,
    }


def _render_reports():
    _hero('Reportes', 'Convierte la operación diaria en información financiera clara y exportable.', 'INTELIGENCIA · RESULTADOS')
    period = st.selectbox('Periodo', ('Día', 'Semana', 'Mes', 'Año', 'Personalizado'))
    today = date.today()

    if period == 'Día':
        selected_day = st.date_input('Fecha', value=today)
        initial_date = final_date = selected_day
    elif period == 'Semana':
        any_day = st.date_input('Cualquier día de la semana a consultar', value=today)
        initial_date = any_day - timedelta(days=any_day.weekday())
        final_date = initial_date + timedelta(days=6)
    elif period == 'Mes':
        columns = st.columns(2)
        year = columns[0].number_input('Año', min_value=2000, max_value=2100, value=today.year, step=1)
        month = columns[1].number_input('Mes', min_value=1, max_value=12, value=today.month, step=1)
        initial_date = date(int(year), int(month), 1)
        final_date = date(int(year), int(month), calendar.monthrange(int(year), int(month))[1])
    elif period == 'Año':
        year = st.number_input('Año', min_value=2000, max_value=2100, value=today.year, step=1)
        initial_date = date(int(year), 1, 1)
        final_date = date(int(year), 12, 31)
    else:
        columns = st.columns(2)
        initial_date = columns[0].date_input('Fecha inicial', value=today - timedelta(days=30))
        final_date = columns[1].date_input('Fecha final', value=today)

    if initial_date > final_date:
        st.error('La fecha inicial no puede ser posterior a la final.')
        return

    result = _summary_for_range(initial_date, final_date)
    st.caption(f'Del {initial_date} al {final_date}')
    columns = st.columns(5)
    columns[0].metric('Ventas', str(result['sale_quantity']))
    columns[1].metric('Dinero obtenido', f"{result['acquired_money'].amount:,.2f} MXN")
    columns[2].metric('Ganancias', f"{result['total_profit'].amount:,.2f} MXN")
    columns[3].metric('Gastos', f"{result['total_expense'].amount:,.2f} MXN")
    columns[4].metric(NET_PROFIT_LABEL, f"{result['net_profit'].amount:,.2f} MXN")

    sales_df = pd.DataFrame([{
        'ID': s.id, 'Producto': s.product.name if s.product else '—', 'Fecha': str(s.date), 'Precio': str(s.price),
    } for s in result['sales']])
    expenses_df = pd.DataFrame([{
        'ID': e.id, 'Nombre': e.name, 'Fecha': str(e.date), 'Gastado': str(e.spent_money),
    } for e in result['expenses']])

    tab_sales, tab_expenses = st.tabs(['Ventas del periodo', 'Gastos del periodo'])
    with tab_sales:
        st.dataframe(sales_df, width='stretch', hide_index=True)
        if not sales_df.empty:
            st.download_button('Descargar ventas (CSV)', sales_df.to_csv(index=False), 'ventas.csv')
    with tab_expenses:
        st.dataframe(expenses_df, width='stretch', hide_index=True)
        if not expenses_df.empty:
            st.download_button('Descargar gastos (CSV)', expenses_df.to_csv(index=False), 'gastos.csv')


# ---------------------------------------------------------------------------
# Estadísticas
# ---------------------------------------------------------------------------

def _render_statistics():
    _hero('Estadísticas', 'Detecta tendencias y compara el desempeño mensual del negocio.', 'ANÁLISIS · TENDENCIAS')
    st.caption('Comportamiento mensual de los últimos 12 meses.')
    repository = RepositoryFactory.get_economic_summary_repository()
    today = date.today()
    rows = []
    for offset in range(11, -1, -1):
        year = today.year + (today.month - offset - 1) // 12
        month = (today.month - offset - 1) % 12 + 1
        summary = repository.get_economic_summary_on_month(date(year, month, 1))
        rows.append({
            'Mes': f'{year}-{month:02d}', 'Ventas': summary.sale_quantity or 0,
            NET_PROFIT_LABEL: float(summary.net_profit.amount), 'Gastos': float(summary.total_expense.amount),
        })
    dataframe = pd.DataFrame(rows).set_index('Mes')
    st.line_chart(dataframe[[NET_PROFIT_LABEL, 'Gastos']])
    st.bar_chart(dataframe[['Ventas']])


# ---------------------------------------------------------------------------
# Estructura principal
# ---------------------------------------------------------------------------

def _render_business_profile():
    _hero('Identidad del negocio', 'Mantén actualizados los datos que representan a tu empresa.', 'CONFIGURACIÓN · MARCA')
    repository = RepositoryFactory.get_business_profile_repository()
    profile = repository.get_profile()
    with st.form('business_profile_form'):
        business_name = st.text_input('Nombre comercial', value=profile.business_name or '')
        owner_name = st.text_input('Responsable', value=profile.owner_name or '')
        phone = st.text_input('Teléfono', value=profile.phone or '')
        whatsapp = st.text_input('WhatsApp', value=profile.whatsapp or '')
        email = st.text_input('Correo', value=profile.email or '')
        address = st.text_input('Dirección', value=profile.address or '')
        submitted = st.form_submit_button('Guardar perfil')
    if submitted:
        repository.save_profile({
            'business_name': business_name, 'owner_name': owner_name, 'phone': phone,
            'whatsapp': whatsapp, 'email': email, 'address': address,
        })
        st.success('Perfil actualizado.')


ADMIN_PAGES = {
    'Tablero': _render_dashboard, 'Ventas': _render_sales, 'Inventario': _render_inventory,
    'Gastos': _render_expenses, 'Reportes': _render_reports, 'Estadísticas': _render_statistics,
    'Mi negocio': _render_business_profile,
}
SELLER_PAGES = {
    'Canal de venta': _render_sales,
    'Cotizaciones': _render_quotes,
    'Inventario': _render_inventory_readonly,
    'Venta express': _render_express_sale,
}


def _render_app():
    user = st.session_state['user']
    pages = ADMIN_PAGES if _is_administrator() else SELLER_PAGES
    if st.session_state.get('page') not in pages:
        st.session_state['page'] = next(iter(pages))

    with st.sidebar:
        st.title('🛒 Blue POS')
        st.caption('Una solución de Grupo ECCOS')
        st.caption(f"{getattr(user, 'display_name', '') or user.role.title()} · {user.role.title()}")
        page = st.radio('Navegación', list(pages.keys()), key='page')
        st.divider()
        if st.button('Cerrar sesión'):
            _log_out()
        st.markdown(
            '<div class="sidebar-legal">© 2026 Grupo ECCOS<br>'
            'Desarrollado por Grupo ECCOS<br>CC BY-NC 4.0</div>',
            unsafe_allow_html=True,
        )

    pages[page]()


def main():
    _bootstrap_auth()
    if 'user' not in st.session_state:
        token = st.query_params.get('session')
        user = RepositoryFactory.get_user_repository().authenticate_session(token)
        if user is not None:
            schema.activate_user_workspace(user)
            st.session_state['user'] = user
            st.session_state['page'] = 'Tablero'
        elif token:
            del st.query_params['session']
    if 'user' not in st.session_state:
        _render_login()
    else:
        _render_app()


main()
