"""Blue POS Web: interfaz web (Streamlit) que reutiliza la capa model/ del escritorio.

Comparte la misma base de datos que la app de escritorio (PyQt5); ambas pueden
usarse en paralelo. Ejecutar con:

    .venv\\Scripts\\streamlit.exe run web/app.py
"""
import calendar
import os
import sys
from datetime import date, datetime, timedelta
from html import escape
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from model import economy, schema
from model.entity.models import CashClose, CashMovement, CashOpening, Expense, Product, Quote, QuoteItem, Sale
from model.repository.expense import ExpenseFilter
from model.repository.factory import RepositoryFactory
from model.repository.product import ProductFilter
from model.repository.sale import SaleFilter
from model.report.exports import business_as_dict, generate_excel_bytes, generate_pdf_bytes
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
    .st-key-product_grid {
        background:#E9EDF2; border:1px solid #D8DEE7; border-radius:12px;
        padding:10px; scrollbar-color:#73859A #E1E6EC; scrollbar-width:thin;
    }
    [class*="st-key-product_card_"] > div > [data-testid="stVerticalBlock"] {
        min-height:188px; padding:13px !important; gap:.38rem !important;
        background:linear-gradient(180deg,#FFFFFF 0%,#F8FAFC 100%);
        border:1px solid #D7DEE7; border-radius:11px;
        box-shadow:0 3px 9px rgba(20,35,55,.06);
    }
    [class*="st-key-product_card_"]:hover > div > [data-testid="stVerticalBlock"] {
        border-color:#7895B4; box-shadow:0 7px 18px rgba(18,59,109,.12);
    }
    .product-card-top { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }
    .product-card-icon { width:31px; height:31px; flex:0 0 31px; display:grid; place-items:center;
        background:#E7EEF6; color:#123B6D; border-radius:8px; font-weight:900; }
    .product-card-name { color:#101828; font-size:.92rem; font-weight:750; line-height:1.2;
        min-height:2.35em; overflow:hidden; }
    .product-card-price { color:#0B294E; font-size:1.25rem; font-weight:850; margin:.15rem 0; }
    .product-card-meta { color:#667085; font-size:.7rem; white-space:nowrap;
        overflow:hidden; text-overflow:ellipsis; }
    .product-card-stock { display:inline-block; border-radius:20px; padding:2px 8px;
        background:#E7F6EF; color:#087451; font-size:.67rem; font-weight:800; }
    .product-card-stock.low { background:#FFF2D8; color:#9A5B00; }
    [class*="st-key-product_card_"] button { min-height:34px !important; margin-top:2px; }
    .cart-summary-bar { display:flex; justify-content:space-between; align-items:center;
        background:#EAF0F7; border:1px solid #D6E0EA; border-radius:9px;
        padding:8px 11px; margin:2px 0 8px; }
    .cart-summary-bar strong { color:#0B294E !important; font-size:.82rem; }
    .cart-summary-bar span { color:#5F6873; font-size:.72rem; }
    .cart-item-head { display:flex; align-items:center; justify-content:space-between;
        gap:8px; margin-bottom:2px; }
    .cart-item-name { color:#101828; font-size:.88rem; font-weight:760;
        line-height:1.25; overflow:hidden; text-overflow:ellipsis; }
    .cart-quantity-badge { flex:0 0 auto; background:#123B6D; color:#FFFFFF;
        border-radius:20px; padding:3px 8px; font-size:.7rem; font-weight:850; }
    .cart-line-total { color:#101828; font-size:.93rem; font-weight:800; text-align:right; }
    .cart-unit-price { color:#667085; font-size:.68rem; text-align:right; }
    .st-key-checkout_cart [data-testid="stVerticalBlock"] { gap:.5rem; }
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
        .st-key-product_grid [data-testid="stHorizontalBlock"] {
            flex-direction:row !important;
        }
        .st-key-product_grid [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            width:33.333% !important; flex:1 1 33.333% !important;
        }
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
        .st-key-product_grid [data-testid="stHorizontalBlock"] { flex-direction:column !important; }
        .st-key-product_grid [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            width:100% !important; flex:1 1 100% !important;
        }
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
            with st.form('login_form', border=False, enter_to_submit=False):
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
            with st.form('recovery_form', border=False, enter_to_submit=False):
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
    return [product for product in products if not product.is_temporary and product.quantity > 0]


def _get_out_of_stock_products():
    return [product for product in RepositoryFactory.get_product_repository().get_all_products()
            if not product.is_temporary and product.quantity <= 0]


def _business_export_data():
    profile = RepositoryFactory.get_business_profile_repository().get_profile()
    return business_as_dict(profile)


def _inventory_export_rows(products):
    return [{
        'Producto': product.name,
        'Descripción': product.description or '',
        'Código': product.barcode or '',
        'Existencia': product.quantity,
        'Precio de venta': float(product.price.amount),
        'Costo': float(product.cost.amount),
    } for product in products]


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
        out_of_stock = _get_out_of_stock_products()
        if out_of_stock:
            st.error(f'{len(out_of_stock)} producto(s) agotado(s). Reabastece el inventario.',
                     icon=':material/error:')
            st.table(pd.DataFrame([{'Producto': p.name, 'Unidades': p.quantity}
                                   for p in out_of_stock]))
        if low_stock:
            st.warning('Estos productos están por agotarse, considera reabastecerlos pronto:')
            st.table(pd.DataFrame([{'Producto': p.name, 'Unidades': p.quantity}
                                   for p in low_stock]))
        if not low_stock and not out_of_stock:
            st.success(f'Todos los productos tienen más de {LOW_STOCK_THRESHOLD} unidades disponibles.')
        else:
            inventory_sections = [
                ('Productos por agotarse', _inventory_export_rows(low_stock)),
                ('Productos agotados', _inventory_export_rows(out_of_stock)),
            ]
            business = _business_export_data()
            alert_columns = st.columns(2)
            alert_columns[0].download_button(
                'Alertas en PDF',
                generate_pdf_bytes(business, 'Alertas de inventario',
                                   f'Corte al {date.today()}', inventory_sections),
                f'alertas-inventario-{date.today()}.pdf', 'application/pdf',
                icon=':material/picture_as_pdf:', width='stretch',
            )
            alert_columns[1].download_button(
                'Alertas en Excel',
                generate_excel_bytes(business, 'Alertas de inventario',
                                     f'Corte al {date.today()}', inventory_sections),
                f'alertas-inventario-{date.today()}.xlsx',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                icon=':material/table_view:', width='stretch',
            )


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
        st.metric('Total a pagar', f'${float(total):,.2f}')
        cash_key = f'{prefix}_cash_received'
        total_key = f'{prefix}_cash_total'
        if st.session_state.get(total_key) != float(total):
            st.session_state[cash_key] = float(total)
            st.session_state[total_key] = float(total)
        received = st.number_input(
            'Efectivo recibido', min_value=0.0, step=10.0,
            format='%.2f', key=cash_key,
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


def _set_cart_quantity(product_id, quantity):
    quantity = int(quantity)
    st.session_state.pos_cart[product_id] = quantity
    st.session_state[f'cart_qty_{product_id}'] = quantity


def _remove_from_cart(product_id):
    st.session_state.pos_cart.pop(product_id, None)
    st.session_state.pop(f'cart_qty_{product_id}', None)


def _clear_cart():
    for product_id in list(st.session_state.get('pos_cart', {})):
        st.session_state.pop(f'cart_qty_{product_id}', None)
    st.session_state.pos_cart = {}

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
            _remove_from_cart(product_id)
        else:
            adjusted_quantity = min(st.session_state.pos_cart[product_id], product.quantity)
            if adjusted_quantity != st.session_state.pos_cart[product_id]:
                _set_cart_quantity(product_id, adjusted_quantity)

    # La clave crea una clase CSS estable (st-key-pos_workspace) para que esta
    # pantalla pueda responder al ancho disponible sin afectar otros módulos.
    workspace = st.container(key='pos_workspace')
    catalog_column, checkout_column = workspace.columns((1.45, 1.3), gap='medium')

    with catalog_column:
        st.markdown('<div class="pos-section">CATÁLOGO</div>', unsafe_allow_html=True)
        search = st.text_input(
            'Buscar productos', placeholder='Buscar por nombre o código de barras',
            icon=':material/search:', label_visibility='collapsed', key='pos_search',
        ).strip().lower()
        filter_columns = st.columns(2)
        stock_filter = filter_columns[0].selectbox(
            'Mostrar', ('Todos', 'Stock suficiente', 'Por agotarse', 'En el carrito'),
            key='pos_stock_filter')
        sort_order = filter_columns[1].selectbox(
            'Ordenar', ('Nombre A–Z', 'Menor precio', 'Mayor precio', 'Menor existencia'),
            key='pos_sort_order')
        filtered = [
            product for product in available
            if not search or search in product.name.lower()
            or search in (product.barcode or '').lower()
            or search in (product.description or '').lower()
        ]
        if stock_filter == 'Stock suficiente':
            filtered = [product for product in filtered if product.quantity > LOW_STOCK_THRESHOLD]
        elif stock_filter == 'Por agotarse':
            filtered = [product for product in filtered if product.quantity <= LOW_STOCK_THRESHOLD]
        elif stock_filter == 'En el carrito':
            filtered = [product for product in filtered
                        if st.session_state.pos_cart.get(product.id, 0) > 0]
        if sort_order == 'Nombre A–Z':
            filtered.sort(key=lambda product: product.name.lower())
        elif sort_order == 'Menor precio':
            filtered.sort(key=lambda product: float(product.price.amount))
        elif sort_order == 'Mayor precio':
            filtered.sort(key=lambda product: float(product.price.amount), reverse=True)
        else:
            filtered.sort(key=lambda product: product.quantity)
        st.caption(f'{len(filtered)} productos encontrados · desplázate dentro del mosaico')

        if not available:
            st.info('No hay productos con existencias. Agrega inventario para comenzar.', icon=':material/inventory_2:')
        elif not filtered:
            st.warning('No encontramos productos con esa búsqueda.', icon=':material/search_off:')
        else:
            product_grid = st.container(height=520, border=False, key='product_grid')
            for row_start in range(0, len(filtered), 3):
                card_columns = product_grid.columns(3, gap='small')
                for column, product in zip(card_columns, filtered[row_start:row_start + 3]):
                    with column:
                        with st.container(border=False, key=f'product_card_{product.id}'):
                            in_cart = st.session_state.pos_cart.get(product.id, 0)
                            stock_class = ' low' if product.quantity <= LOW_STOCK_THRESHOLD else ''
                            barcode = escape(product.barcode or 'Sin código')
                            st.markdown(
                                '<div class="product-card-top">'
                                '<div><div class="product-card-name">'
                                f'{escape(product.name)}</div>'
                                f'<span class="product-card-stock{stock_class}">'
                                f'{product.quantity} disponibles</span></div>'
                                '<div class="product-card-icon">▦</div></div>'
                                f'<div class="product-card-price">${float(product.price.amount):,.2f}</div>'
                                f'<div class="product-card-meta">Código: {barcode}</div>',
                                unsafe_allow_html=True,
                            )
                            if in_cart:
                                st.caption(f'✓ {in_cart} en la venta actual')
                            else:
                                st.caption('Listo para agregar')
                            button_label = f'Agregar otra ({in_cart})' if in_cart else 'Agregar'
                            if st.button(
                                button_label, key=f'add_cart_{product.id}',
                                icon=':material/add_shopping_cart:', width='stretch',
                            ):
                                current = st.session_state.pos_cart.get(product.id, 0)
                                if current < product.quantity:
                                    _set_cart_quantity(product.id, current + 1)
                                    st.rerun()
                                else:
                                    st.toast('Ya agregaste todo el stock disponible.',
                                             icon=':material/warning:')

    with checkout_column:
        cart = st.session_state.pos_cart
        item_count = sum(cart.values())
        distinct_count = len(cart)
        st.markdown('<div class="pos-section">VENTA ACTUAL</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="cart-summary-bar">'
            f'<strong>{item_count} artículo{"s" if item_count != 1 else ""}</strong>'
            f'<span>{distinct_count} producto{"s" if distinct_count != 1 else ""} distinto'
            f'{"s" if distinct_count != 1 else ""}</span></div>',
            unsafe_allow_html=True)
        with st.container(border=True, key='checkout_cart'):
            if not cart:
                st.markdown('### Tu carrito está vacío')
                st.caption('Busca un producto y presiona Agregar para iniciar la venta.')
                st.button('Cobrar', disabled=True, width='stretch', icon=':material/payments:')
            else:
                total = 0.0
                cart_items = st.container(
                    height=270 if distinct_count > 2 else 'content',
                    border=False, key='cart_item_list')
                for product_id, current_quantity in list(cart.items()):
                    product = product_by_id[product_id]
                    line_total = float(product.price.amount) * current_quantity
                    total += line_total
                    with cart_items:
                        st.markdown(
                            '<div class="cart-item-head">'
                            f'<div class="cart-item-name">{escape(product.name)}</div>'
                            f'<span class="cart-quantity-badge">× {current_quantity}</span></div>',
                            unsafe_allow_html=True)
                        quantity_column, line_column, remove_column = st.columns(
                            (1.15, 1.25, .45), vertical_alignment='center'
                        )
                        quantity_key = f'cart_qty_{product_id}'
                        if quantity_key not in st.session_state:
                            st.session_state[quantity_key] = current_quantity
                        new_quantity = quantity_column.number_input(
                            f'Cantidad de {product.name}', min_value=1, max_value=product.quantity,
                            step=1, key=quantity_key,
                            label_visibility='collapsed',
                        )
                        if int(new_quantity) != current_quantity:
                            _set_cart_quantity(product_id, new_quantity)
                            st.rerun()
                        line_column.markdown(
                            f'<div class="cart-line-total">${line_total:,.2f}</div>'
                            f'<div class="cart-unit-price">${float(product.price.amount):,.2f} c/u</div>',
                            unsafe_allow_html=True)
                        if remove_column.button('', key=f'remove_cart_{product_id}',
                                                icon=':material/delete:'):
                            _remove_from_cart(product_id)
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
                    _clear_cart()
                    st.rerun()
                suspend_column.button('Venta en espera', width='stretch', icon=':material/pause_circle:', disabled=True,
                                      help='Disponible próximamente')

                if submitted:
                    if payment_error:
                        st.error(payment_error, icon=':material/error:')
                        return
                    try:
                        sale_repository = RepositoryFactory.get_sale_repository()
                        transaction_entries = []
                        for product_id, quantity in cart.items():
                            product = product_by_id[product_id]
                            sale = Sale(
                                product_id=product.id, price=product.price, cost=product.cost,
                                date=sale_date, payment_method=payment_method or 'Efectivo',
                                payment_details=payment_details,
                            )
                            transaction_entries.append((sale, int(quantity)))
                        sale_repository.insert_transaction(transaction_entries)
                        _clear_cart()
                        st.toast('Venta registrada correctamente.', icon=':material/check_circle:')
                        st.rerun()
                    except Exception as error:
                        st.error(f'No se pudo completar la venta: {error}')

        with st.expander('Movimientos recientes', icon=':material/receipt_long:'):
            recent_sales = sorted(
                RepositoryFactory.get_sale_repository().get_all_sales(),
                key=lambda sale: sale.id, reverse=True,
            )
            if not recent_sales:
                st.caption('Todavía no hay ventas registradas.')
            transactions = {}
            business = _business_export_data()
            for recent_sale in recent_sales:
                group_key = recent_sale.transaction_id or f'legacy-{recent_sale.id}'
                transactions.setdefault(group_key, []).append(recent_sale)
            for transaction_sales in list(transactions.values())[:8]:
                first_sale = transaction_sales[0]
                product_lines = {}
                for sale in transaction_sales:
                    product = product_by_id.get(sale.product_id) or sale.product
                    name = product.name if product else f'Producto #{sale.product_id}'
                    line = product_lines.setdefault(name, {'quantity': 0, 'total': 0.0})
                    line['quantity'] += 1
                    line['total'] += float(sale.price.amount)
                transaction_total = sum(line['total'] for line in product_lines.values())
                summary = ' · '.join(
                    f"{line['quantity']} × {name}" for name, line in product_lines.items()
                )
                st.markdown(f'**Venta #{first_sale.id} · ${transaction_total:,.2f}**')
                st.caption(f'{first_sale.date} · {first_sale.payment_method or "Sin método"} · {summary}')
                ticket_rows = [{
                    'Artículo': name, 'Cantidad': line['quantity'],
                    'Precio unitario': line['total'] / line['quantity'],
                    'Importe': line['total'],
                } for name, line in product_lines.items()]
                ticket_rows.append({
                    'Artículo': 'TOTAL', 'Cantidad': '', 'Precio unitario': '',
                    'Importe': transaction_total,
                })
                ticket_subtitle = (
                    f'Fecha: {first_sale.date} · Método: {first_sale.payment_method or "Sin método"}'
                    f' · {first_sale.payment_details or "Sin referencia"}'
                )
                ticket_actions = st.columns(3)
                ticket_actions[0].download_button(
                    'Ticket PDF',
                    generate_pdf_bytes(business, f'Ticket de venta #{first_sale.id}',
                                       ticket_subtitle, [('Productos', ticket_rows)]),
                    f'ticket-venta-{first_sale.id}.pdf', 'application/pdf',
                    key=f'ticket_pdf_{first_sale.id}', icon=':material/picture_as_pdf:',
                    width='stretch',
                )
                ticket_actions[1].download_button(
                    'Ticket Excel',
                    generate_excel_bytes(business, f'Ticket de venta #{first_sale.id}',
                                         ticket_subtitle, [('Productos', ticket_rows)]),
                    f'ticket-venta-{first_sale.id}.xlsx',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    key=f'ticket_excel_{first_sale.id}', icon=':material/table_view:',
                    width='stretch',
                )
                if ticket_actions[2].button('Anular', key=f'undo_sale_{first_sale.id}',
                                            width='stretch'):
                    RepositoryFactory.get_sale_repository().delete_sales(
                        [sale.id for sale in transaction_sales]
                    )
                    st.rerun()


# ---------------------------------------------------------------------------
# Inventario
# ---------------------------------------------------------------------------

def _render_inventory_downloads(products, key_prefix, include_cost):
    rows = []
    for product in products:
        status = ('Agotado' if product.quantity <= 0 else
                  'Por agotarse' if product.quantity <= LOW_STOCK_THRESHOLD else 'Disponible')
        row = {
            'Producto': product.name,
            'Descripción': product.description or '',
            'Código': product.barcode or '',
            'Existencia': product.quantity,
            'Precio de venta': float(product.price.amount),
            'Estado': status,
        }
        if include_cost:
            row['Costo'] = float(product.cost.amount)
            row['Valor del inventario'] = float(product.cost.amount) * product.quantity
        rows.append(row)
    summary = [{
        'Productos': len(products),
        'Unidades': sum(product.quantity for product in products),
        'Por agotarse': sum(0 < product.quantity <= LOW_STOCK_THRESHOLD for product in products),
        'Agotados': sum(product.quantity <= 0 for product in products),
    }]
    sections = [('Resumen', summary), ('Inventario', rows)]
    business = _business_export_data()
    subtitle = f'Inventario actualizado al {date.today()}'
    columns = st.columns(2)
    columns[0].download_button(
        'Descargar inventario PDF',
        generate_pdf_bytes(business, 'Reporte de inventario', subtitle, sections),
        f'inventario-{date.today()}.pdf', 'application/pdf',
        key=f'{key_prefix}_inventory_pdf', icon=':material/picture_as_pdf:',
        width='stretch')
    columns[1].download_button(
        'Descargar inventario Excel',
        generate_excel_bytes(business, 'Reporte de inventario', subtitle, sections),
        f'inventario-{date.today()}.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        key=f'{key_prefix}_inventory_excel', icon=':material/table_view:',
        width='stretch')


def _render_inventory():
    _hero('Inventario', 'Controla catálogo, precios y existencias con información lista para decidir.', 'GESTIÓN · CATÁLOGO')
    products = [product for product in RepositoryFactory.get_product_repository().get_all_products()
                if not product.is_temporary]

    with st.expander('Agregar producto'):
        with st.form('add_product_form', clear_on_submit=True, enter_to_submit=False):
            name = st.text_input('Nombre *')
            description = st.text_area(f'{DESCRIPTION_LABEL} *', height=68)
            price = st.number_input('Precio de venta', min_value=0.01, step=1.0, format='%.2f')
            cost = st.number_input('Precio de costo', min_value=0.0, step=1.0, format='%.2f')
            quantity = st.number_input('Cantidad disponible', min_value=0, step=1)
            barcode = st.text_input('Código de barras (opcional)')
            submitted = st.form_submit_button('Guardar producto')
        if submitted:
            clean_name = name.strip()
            clean_description = description.strip()
            if not clean_name or not clean_description:
                st.error('Completa los campos obligatorios: nombre y descripción.',
                         icon=':material/error:')
                return
            try:
                product = Product(name=clean_name, description=clean_description,
                                  price=CUPMoney(f'{price:.2f}'), cost=CUPMoney(f'{cost:.2f}'),
                                  quantity=int(quantity), barcode=barcode.strip())
                RepositoryFactory.get_product_repository().insert_product(product)
                st.success(f'Producto "{clean_name}" agregado.')
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
    _render_inventory_downloads(products, 'admin', include_cost=True)

    with st.expander('Editar o eliminar producto'):
        names = [p.name for p in products]
        selected_name = st.selectbox('Selecciona un producto', names, key='inventory_edit_select')
        product = next(p for p in products if p.name == selected_name)
        with st.form(f'edit_product_form_{product.id}', enter_to_submit=False):
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
            if not name.strip() or not description.strip():
                st.error('Completa los campos obligatorios: nombre y descripción.',
                         icon=':material/error:')
                return
            try:
                updated = Product(id=product.id, name=name.strip(), description=description.strip(),
                                  price=CUPMoney(f'{price:.2f}'), cost=CUPMoney(f'{cost:.2f}'),
                                  quantity=int(quantity), barcode=barcode.strip())
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
    products = [product for product in RepositoryFactory.get_product_repository().get_all_products()
                if not product.is_temporary]
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
    _render_inventory_downloads(visible, 'seller', include_cost=False)
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
    _hero('Cotizaciones', 'Prepara propuestas con información actual del inventario y envíalas a caja.',
          'VENDEDOR · PROPUESTAS')
    st.session_state.setdefault('quote_items', [])
    products = [product for product in RepositoryFactory.get_product_repository().get_all_products()
                if not product.is_temporary]
    product_by_id = {product.id: product for product in products}
    create_tab, history_tab = st.tabs(['Nueva cotización', 'Historial'])

    with create_tab:
        options = ['Artículo libre'] + [product.name for product in products]
        source = st.selectbox('Producto del inventario', options, key='quote_product_source')
        selected = next((product for product in products if product.name == source), None)
        if selected:
            information = st.columns(4)
            information[0].metric('Precio de venta', f'${float(selected.price.amount):,.2f}')
            information[1].metric('Existencia', f'{selected.quantity} unidades')
            information[2].metric('Costo', f'${float(selected.cost.amount):,.2f}')
            information[3].metric('Código', selected.barcode or 'Sin código')
            st.info(selected.description or 'Este producto no tiene descripción.',
                    icon=':material/inventory_2:')
        else:
            st.caption('El artículo libre no está vinculado al inventario y no puede enviarse a caja.')

        form_key = f"quote_add_item_{selected.id if selected else 'free'}"
        with st.form(form_key, border=False, clear_on_submit=True, enter_to_submit=False):
            row = st.columns((2, 1, 1), vertical_alignment='bottom')
            custom_name = row[0].text_input(
                'Descripción *', value=selected.description or selected.name if selected else '',
                disabled=selected is not None, placeholder='Producto o servicio',
            )
            quantity = row[1].number_input('Cantidad', min_value=1, value=1, step=1)
            price = row[2].number_input(
                'Precio unitario', min_value=0.01,
                value=float(selected.price.amount) if selected else 1.0,
                step=1.0, format='%.2f',
            )
            add_item = st.form_submit_button('Agregar a la cotización', icon=':material/add:')

        if add_item:
            description = (selected.name if selected else custom_name.strip())
            if not description:
                st.error('Escribe una descripción para el artículo.', icon=':material/error:')
            elif selected and int(quantity) > selected.quantity:
                st.error(f'Solo hay {selected.quantity} unidades disponibles de {selected.name}.',
                         icon=':material/error:')
            else:
                product_id = selected.id if selected else None
                matching_item = next((item for item in st.session_state.quote_items
                                      if item.get('product_id') == product_id
                                      and item['description'] == description
                                      and item['unit_price'] == float(price)), None)
                if matching_item:
                    matching_item['quantity'] += int(quantity)
                else:
                    st.session_state.quote_items.append({
                        'draft_id': datetime.now().strftime('%Y%m%d%H%M%S%f'),
                        'product_id': product_id, 'description': description,
                        'quantity': int(quantity), 'unit_price': float(price),
                    })
                st.rerun()

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

            st.markdown('#### Editar artículos')
            for index, item in enumerate(list(items)):
                draft_id = item.setdefault('draft_id', f'legacy_{index}')
                with st.container(border=True):
                    edit_columns = st.columns((2.2, .8, 1, .55, .55), vertical_alignment='bottom')
                    edited_description = edit_columns[0].text_input(
                        'Descripción', value=item['description'], key=f'quote_desc_{draft_id}')
                    edited_quantity = edit_columns[1].number_input(
                        'Cantidad', min_value=1, value=int(item['quantity']), step=1,
                        key=f'quote_qty_{draft_id}')
                    edited_price = edit_columns[2].number_input(
                        'Precio', min_value=0.01, value=float(item['unit_price']), step=1.0,
                        format='%.2f', key=f'quote_price_{draft_id}')
                    if edit_columns[3].button('', icon=':material/save:',
                                              key=f'quote_update_{draft_id}', help='Actualizar'):
                        if not edited_description.strip():
                            st.error('La descripción no puede quedar vacía.', icon=':material/error:')
                        else:
                            item['description'] = edited_description.strip()
                            item['quantity'] = int(edited_quantity)
                            item['unit_price'] = float(edited_price)
                            st.rerun()
                    if edit_columns[4].button('', icon=':material/delete:',
                                              key=f'quote_remove_{draft_id}', help='Eliminar'):
                        st.session_state.quote_items.pop(index)
                        st.rerun()

            with st.form('save_quote_form', clear_on_submit=True, enter_to_submit=False):
                customer = st.text_input('Cliente *', placeholder='Nombre del cliente')
                notes = st.text_area('Notas', height=70)
                save_quote = st.form_submit_button(
                    'Guardar cotización', type='primary', width='stretch', icon=':material/save:')
            if st.button('Vaciar borrador', icon=':material/delete_sweep:'):
                st.session_state.quote_items = []
                st.rerun()
            if save_quote:
                clean_customer = customer.strip()
                if not clean_customer:
                    st.error('Escribe el nombre del cliente antes de guardar la cotización.',
                             icon=':material/error:')
                    return
                quote = Quote(customer=clean_customer, notes=notes.strip())
                quote.items = [QuoteItem(
                    product_id=item.get('product_id'), description=item['description'],
                    quantity=item['quantity'], unit_price=CUPMoney(f"{item['unit_price']:.2f}"))
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
        business = _business_export_data()
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

                quote_rows = [{
                    'Artículo': item.description,
                    'Cantidad': item.quantity,
                    'Precio unitario': float(item.unit_price.amount),
                    'Importe': float(item.unit_price.amount) * item.quantity,
                } for item in quote.items]
                quote_rows.append({
                    'Artículo': 'TOTAL', 'Cantidad': '', 'Precio unitario': '',
                    'Importe': total,
                })
                quote_title = f'Cotización #{quote.id} · {quote.customer}'
                quote_subtitle = f'Fecha: {quote.date} · Estado: {quote.status} · {quote.notes or "Sin notas"}'
                export_columns = st.columns(2)
                export_columns[0].download_button(
                    'Descargar PDF',
                    generate_pdf_bytes(business, quote_title, quote_subtitle,
                                       [('Productos cotizados', quote_rows)]),
                    f'cotizacion-{quote.id}.pdf', 'application/pdf',
                    key=f'quote_pdf_{quote.id}', icon=':material/picture_as_pdf:',
                    width='stretch',
                )
                export_columns[1].download_button(
                    'Descargar Excel',
                    generate_excel_bytes(business, quote_title, quote_subtitle,
                                         [('Productos cotizados', quote_rows)]),
                    f'cotizacion-{quote.id}.xlsx',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    key=f'quote_excel_{quote.id}', icon=':material/table_view:',
                    width='stretch',
                )

                if quote.status == 'Pendiente' and st.button(
                        'Aceptar y enviar al carrito', type='primary',
                        key=f'accept_quote_{quote.id}', icon=':material/shopping_cart_checkout:'):
                    required = {}
                    free_items = []
                    for item in quote.items:
                        if item.product_id is None:
                            free_items.append(item.description)
                        else:
                            required[item.product_id] = required.get(item.product_id, 0) + item.quantity
                    unavailable = []
                    current_cart = st.session_state.setdefault('pos_cart', {})
                    for product_id, required_quantity in required.items():
                        product = product_by_id.get(product_id)
                        final_quantity = current_cart.get(product_id, 0) + required_quantity
                        if product is None:
                            unavailable.append(f'Producto #{product_id} ya no existe')
                        elif final_quantity > product.quantity:
                            unavailable.append(
                                f'{product.name}: se requieren {final_quantity} y hay {product.quantity}')
                    if free_items:
                        st.error('Primero agrega al inventario estos artículos libres: '
                                 + ', '.join(free_items), icon=':material/error:')
                    elif unavailable:
                        st.error('No se puede enviar a caja por falta de existencias: '
                                 + '; '.join(unavailable), icon=':material/error:')
                    else:
                        for product_id, required_quantity in required.items():
                            _set_cart_quantity(
                                product_id, current_cart.get(product_id, 0) + required_quantity)
                        RepositoryFactory.get_quote_repository().update_status(quote.id, 'Aceptada')
                        st.session_state['page'] = 'Nueva venta'
                        st.rerun()

                secondary_actions = st.columns(2)
                if quote.status == 'Pendiente' and secondary_actions[0].button(
                        'Marcar vencida', key=f'expire_quote_{quote.id}'):
                    RepositoryFactory.get_quote_repository().update_status(quote.id, 'Vencida')
                    st.rerun()
                if secondary_actions[1].button('Eliminar cotización', key=f'delete_quote_{quote.id}'):
                    RepositoryFactory.get_quote_repository().delete_quote(quote.id)
                    st.rerun()

# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def _render_expenses():
    _hero('Gastos operativos', 'Registra y consulta egresos para mantener visible la rentabilidad real.', 'FINANZAS · EGRESOS')
    with st.expander('Agregar gasto'):
        with st.form('add_expense_form', enter_to_submit=False):
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


def _cash_close_summary(close_date: date):
    result = _summary_for_range(close_date, close_date)
    totals = {'Efectivo': 0.0, 'Tarjeta': 0.0, 'Transferencia': 0.0, 'Otros': 0.0}
    operations = set()
    for sale in result['sales']:
        amount = float(sale.price.amount)
        method = (sale.payment_method or '').strip().lower()
        if method == 'efectivo' or method == 'cash':
            totals['Efectivo'] += amount
        elif method == 'tarjeta':
            totals['Tarjeta'] += amount
        elif method == 'transferencia':
            totals['Transferencia'] += amount
        else:
            totals['Otros'] += amount
        operations.add(sale.transaction_id or f'legacy-{sale.id}')
    return result, totals, len(operations)


def _cash_close_rows(cash_close):
    values = (
        ('Fecha', str(cash_close.date)),
        ('Responsable', cash_close.cashier),
        ('Operaciones', cash_close.operation_count),
        ('Ventas totales', float(cash_close.total_sales.amount)),
        ('Ventas en efectivo', float(cash_close.cash_sales.amount)),
        ('Ventas con tarjeta', float(cash_close.card_sales.amount)),
        ('Transferencias', float(cash_close.transfer_sales.amount)),
        ('Otros métodos', float(cash_close.other_sales.amount)),
        ('Gastos totales', float(cash_close.total_expenses.amount)),
        ('Gastos pagados desde caja', float(cash_close.cash_expenses.amount)),
        ('Fondo inicial', float(cash_close.opening_cash.amount)),
        ('Entradas adicionales', float(cash_close.cash_additions.amount)),
        ('Retiros de efectivo', float(cash_close.cash_withdrawals.amount)),
        ('Efectivo esperado', float(cash_close.expected_cash.amount)),
        ('Efectivo contado', float(cash_close.counted_cash.amount)),
        ('Diferencia', float(cash_close.difference.amount)),
        ('Observaciones', cash_close.notes or 'Sin observaciones'),
    )
    return [{'Concepto': concept, 'Valor': value} for concept, value in values]


def _render_cash_close():
    _hero('Corte de caja',
          'Concilia ventas, gastos y efectivo físico con un cierre claro y auditable.',
          'CAJA · CONTROL DIARIO')
    selected_date = st.date_input('Fecha del corte', value=date.today(), key='cash_close_date')
    result, payment_totals, operation_count = _cash_close_summary(selected_date)
    total_sales = sum(payment_totals.values())
    total_expenses = float(result['total_expense'].amount)
    user = st.session_state['user']
    is_admin = _is_administrator()
    repository = RepositoryFactory.get_cash_close_repository()
    control_repository = RepositoryFactory.get_cash_control_repository()
    existing_close = repository.get_by_date(selected_date)
    opening = control_repository.get_opening(selected_date)
    movements = control_repository.get_movements(selected_date)
    movement_totals = control_repository.totals_for_date(selected_date)

    st.markdown('#### Resumen del sistema')
    overview = st.columns(6)
    overview[0].metric('Operaciones', operation_count)
    overview[1].metric('Ventas totales', f'${total_sales:,.2f}')
    overview[2].metric('Efectivo', f"${payment_totals['Efectivo']:,.2f}")
    overview[3].metric('Tarjeta', f"${payment_totals['Tarjeta']:,.2f}")
    overview[4].metric('Transferencia', f"${payment_totals['Transferencia']:,.2f}")
    overview[5].metric('Gastos registrados', f'${total_expenses:,.2f}')

    st.markdown('#### Apertura y seguridad de efectivo')
    if opening is None:
        if is_admin and selected_date == date.today() and existing_close is None:
            st.warning('La caja todavía no ha sido abierta. Define el fondo de cambio antes de vender.',
                       icon=':material/lock_open:')
            opening_columns = st.columns(2)
            opening_amount = opening_columns[0].number_input(
                'Fondo inicial para cambio', min_value=0.0, value=0.0, step=100.0,
                format='%.2f', key=f'cash_opening_amount_{selected_date}')
            cash_limit = opening_columns[1].number_input(
                'Límite máximo recomendado en caja', min_value=100.0, value=3000.0,
                step=500.0, format='%.2f', key=f'cash_opening_limit_{selected_date}',
                help='Al superar este nivel, el sistema recomendará un retiro de seguridad.')
            opening_notes = st.text_input(
                'Nota de apertura', placeholder='Ej. Fondo entregado en billetes y monedas',
                key=f'cash_opening_notes_{selected_date}')
            if st.button('Abrir caja', type='primary', icon=':material/lock_open:',
                         width='stretch', key=f'cash_opening_submit_{selected_date}'):
                administrator = (getattr(user, 'display_name', '')
                                 or getattr(user, 'username', '') or 'Administrador')
                try:
                    control_repository.open_day(CashOpening(
                        date=selected_date, opening_amount=CUPMoney(f'{float(opening_amount):.2f}'),
                        cash_limit=CUPMoney(f'{float(cash_limit):.2f}'),
                        opened_by=administrator, notes=opening_notes.strip()), user.role)
                    st.success('Caja abierta correctamente.', icon=':material/check_circle:')
                    st.rerun()
                except Exception as error:
                    st.error(str(error), icon=':material/error:')
        elif existing_close is None:
            st.warning('El administrador debe abrir la caja y definir el fondo inicial antes del corte.',
                       icon=':material/admin_panel_settings:')
    else:
        estimated_drawer_cash = (float(opening.opening_amount.amount)
                                 + payment_totals['Efectivo']
                                 + movement_totals['Entrada'] - movement_totals['Retiro'])
        opening_metrics = st.columns(4)
        opening_metrics[0].metric('Fondo inicial', f'${float(opening.opening_amount.amount):,.2f}')
        opening_metrics[1].metric('Entradas autorizadas', f"${movement_totals['Entrada']:,.2f}")
        opening_metrics[2].metric('Retiros autorizados', f"${movement_totals['Retiro']:,.2f}")
        opening_metrics[3].metric('Efectivo estimado', f'${estimated_drawer_cash:,.2f}')
        st.caption(f'Caja abierta por {opening.opened_by} · Límite recomendado: '
                   f'${float(opening.cash_limit.amount):,.2f} · {opening.notes or "Sin nota"}')
        if estimated_drawer_cash > float(opening.cash_limit.amount) and existing_close is None:
            st.error(
                f'El efectivo estimado supera el límite por '
                f'${estimated_drawer_cash - float(opening.cash_limit.amount):,.2f}. '
                'Se recomienda que el administrador realice un retiro de seguridad.',
                icon=':material/security:')

        if is_admin and selected_date == date.today() and existing_close is None:
            with st.expander('Registrar entrada o retiro autorizado',
                             icon=':material/admin_panel_settings:'):
                movement_type = st.segmented_control(
                    'Tipo de movimiento', ('Retiro', 'Entrada'), default='Retiro',
                    selection_mode='single', key=f'cash_movement_type_{selected_date}') or 'Retiro'
                movement_columns = st.columns(2)
                movement_amount = movement_columns[0].number_input(
                    'Importe', min_value=0.01, value=100.0, step=100.0, format='%.2f',
                    key=f'cash_movement_amount_{selected_date}')
                reason_options = (
                    ('Retiro de seguridad', 'Pago autorizado', 'Depósito bancario', 'Otro')
                    if movement_type == 'Retiro'
                    else ('Cambio adicional', 'Reintegro', 'Entrada autorizada', 'Otro'))
                reason_category = movement_columns[1].selectbox(
                    'Motivo', reason_options, key=f'cash_movement_reason_category_{selected_date}')
                reason_detail = st.text_input(
                    'Detalle obligatorio', placeholder='Explica el destino u origen del efectivo',
                    key=f'cash_movement_reason_detail_{selected_date}')
                if st.button('Autorizar movimiento', type='primary',
                             icon=':material/currency_exchange:', width='stretch',
                             key=f'cash_movement_submit_{selected_date}'):
                    administrator = (getattr(user, 'display_name', '')
                                     or getattr(user, 'username', '') or 'Administrador')
                    reason = f'{reason_category}: {reason_detail.strip()}'
                    if not reason_detail.strip():
                        st.error('Escribe el detalle y destino u origen del dinero.',
                                 icon=':material/error:')
                    else:
                        try:
                            control_repository.add_movement(CashMovement(
                                date=selected_date, movement_type=movement_type,
                                amount=CUPMoney(f'{float(movement_amount):.2f}'),
                                reason=reason, authorized_by=administrator), user.role,
                                available_cash=max(0.0, estimated_drawer_cash))
                            st.success('Movimiento autorizado y registrado.',
                                       icon=':material/check_circle:')
                            st.rerun()
                        except Exception as error:
                            st.error(str(error), icon=':material/error:')

        if movements:
            st.markdown('##### Bitácora de movimientos')
            st.dataframe(pd.DataFrame([{
                'Hora': movement.created_at.strftime('%H:%M:%S'),
                'Tipo': movement.movement_type,
                'Importe': float(movement.amount.amount),
                'Motivo': movement.reason,
                'Autorizó': movement.authorized_by,
            } for movement in movements]), column_config={
                'Importe': st.column_config.NumberColumn(format='$ %.2f'),
            }, hide_index=True, width='stretch')

    if existing_close is not None:
        st.info(f'El corte de {selected_date} ya fue cerrado por {existing_close.cashier}. '
                'Se conserva bloqueado para proteger la auditoría.', icon=':material/lock:')
    elif opening is not None:
        responsible = st.text_input(
            'Responsable del corte *',
            value=getattr(user, 'display_name', '') or getattr(user, 'username', '') or 'Vendedor',
            key=f'cash_close_responsible_{selected_date}',
        )
        cash_expenses = st.number_input(
            'Gastos pagados desde caja', min_value=0.0, value=total_expenses, step=10.0,
            format='%.2f', key=f'cash_close_expenses_{selected_date}',
            help='Ajusta este importe si algún gasto se pagó por transferencia o tarjeta.')
        opening_cash = float(opening.opening_amount.amount)
        cash_additions = movement_totals['Entrada']
        cash_withdrawals = movement_totals['Retiro']
        expected_cash = (opening_cash + payment_totals['Efectivo']
                         + cash_additions - cash_withdrawals
                         - float(cash_expenses))

        use_denominations = st.toggle(
            'Conteo asistido por billetes y monedas', value=True,
            key=f'cash_close_use_denominations_{selected_date}')
        if use_denominations:
            denominations = (
                ('Billete $1,000', 1000.0), ('Billete $500', 500.0),
                ('Billete $200', 200.0), ('Billete $100', 100.0),
                ('Billete $50', 50.0), ('Billete $20', 20.0),
                ('Moneda $20', 20.0), ('Moneda $10', 10.0), ('Moneda $5', 5.0),
                ('Moneda $2', 2.0), ('Moneda $1', 1.0), ('Moneda $0.50', .5),
            )
            counted_cash = 0.0
            denomination_columns = st.columns(4)
            for index, (label, denomination) in enumerate(denominations):
                pieces = denomination_columns[index % 4].number_input(
                    label, min_value=0, value=0, step=1,
                    key=f'cash_close_denomination_{selected_date}_{index}')
                counted_cash += int(pieces) * denomination
            st.metric('Total contado por denominaciones', f'${counted_cash:,.2f}')
        else:
            counted_cash = st.number_input(
                'Efectivo contado', min_value=0.0, value=max(0.0, expected_cash),
                step=100.0, format='%.2f', key=f'cash_close_counted_{selected_date}')

        difference = float(counted_cash) - expected_cash
        reconciliation = st.columns(3)
        reconciliation[0].metric('Efectivo esperado', f'${expected_cash:,.2f}')
        reconciliation[1].metric('Efectivo contado', f'${float(counted_cash):,.2f}')
        reconciliation[2].metric(
            'Diferencia', f'${difference:,.2f}',
            delta='Cuadra' if abs(difference) < .005 else ('Sobrante' if difference > 0 else 'Faltante'),
            delta_color='normal' if difference >= 0 else 'inverse')
        if abs(difference) < .005:
            st.success('La caja cuadra correctamente.', icon=':material/check_circle:')
        elif difference < 0:
            st.error(f'Hay un faltante de ${abs(difference):,.2f}. Revisa el conteo y los movimientos.',
                     icon=':material/error:')
        else:
            st.warning(f'Hay un sobrante de ${difference:,.2f}. Registra una observación.',
                       icon=':material/warning:')

        notes = st.text_area(
            'Observaciones', placeholder='Incidencias, retiros, depósitos o explicación de diferencias',
            key=f'cash_close_notes_{selected_date}')
        confirmed = st.checkbox(
            'Confirmo que conté el efectivo y revisé los movimientos del día.',
            key=f'cash_close_confirmed_{selected_date}')
        if st.button('Cerrar caja', type='primary', icon=':material/point_of_sale:',
                     width='stretch', key=f'cash_close_submit_{selected_date}'):
            if not responsible.strip():
                st.error('Indica el responsable del corte.', icon=':material/error:')
            elif not confirmed:
                st.error('Confirma la revisión antes de cerrar la caja.', icon=':material/error:')
            elif abs(difference) >= .005 and not notes.strip():
                st.error('Explica el sobrante o faltante en Observaciones.', icon=':material/error:')
            else:
                cash_close = CashClose(
                    date=selected_date, cashier=responsible.strip(), operation_count=operation_count,
                    total_sales=CUPMoney(f'{total_sales:.2f}'),
                    cash_sales=CUPMoney(f"{payment_totals['Efectivo']:.2f}"),
                    card_sales=CUPMoney(f"{payment_totals['Tarjeta']:.2f}"),
                    transfer_sales=CUPMoney(f"{payment_totals['Transferencia']:.2f}"),
                    other_sales=CUPMoney(f"{payment_totals['Otros']:.2f}"),
                    total_expenses=CUPMoney(f'{total_expenses:.2f}'),
                    cash_expenses=CUPMoney(f'{float(cash_expenses):.2f}'),
                    opening_cash=CUPMoney(f'{float(opening_cash):.2f}'),
                    cash_additions=CUPMoney(f'{float(cash_additions):.2f}'),
                    cash_withdrawals=CUPMoney(f'{float(cash_withdrawals):.2f}'),
                    expected_cash=CUPMoney(f'{expected_cash:.2f}'),
                    counted_cash=CUPMoney(f'{float(counted_cash):.2f}'),
                    difference=CUPMoney(f'{difference:.2f}'), notes=notes.strip())
                try:
                    repository.insert(cash_close)
                    st.success(f'Corte #{cash_close.id} guardado correctamente.',
                               icon=':material/check_circle:')
                    st.rerun()
                except Exception as error:
                    st.error(f'No se pudo guardar el corte: {error}', icon=':material/error:')

    st.markdown('#### Historial de cortes')
    cash_closes = repository.get_all()
    if not cash_closes:
        st.caption('Todavía no hay cortes de caja guardados.')
        return
    business = _business_export_data()
    for cash_close in cash_closes[:30]:
        difference = float(cash_close.difference.amount)
        status = 'Cuadrado' if abs(difference) < .005 else ('Sobrante' if difference > 0 else 'Faltante')
        with st.expander(
                f'#{cash_close.id} · {cash_close.date} · {cash_close.cashier} · {status}',
                icon=':material/receipt_long:'):
            history_metrics = st.columns(4)
            history_metrics[0].metric('Ventas', f'${float(cash_close.total_sales.amount):,.2f}')
            history_metrics[1].metric('Esperado', f'${float(cash_close.expected_cash.amount):,.2f}')
            history_metrics[2].metric('Contado', f'${float(cash_close.counted_cash.amount):,.2f}')
            history_metrics[3].metric('Diferencia', f'${difference:,.2f}')
            st.caption(cash_close.notes or 'Sin observaciones')
            rows = _cash_close_rows(cash_close)
            export_columns = st.columns(2)
            export_columns[0].download_button(
                'Descargar PDF',
                generate_pdf_bytes(business, f'Corte de caja #{cash_close.id}',
                                   f'Fecha: {cash_close.date} · Responsable: {cash_close.cashier}',
                                   [('Conciliación', rows)]),
                f'corte-caja-{cash_close.date}.pdf', 'application/pdf',
                key=f'cash_close_pdf_{cash_close.id}', icon=':material/picture_as_pdf:',
                width='stretch')
            export_columns[1].download_button(
                'Descargar Excel',
                generate_excel_bytes(business, f'Corte de caja #{cash_close.id}',
                                     f'Fecha: {cash_close.date} · Responsable: {cash_close.cashier}',
                                     [('Conciliación', rows)]),
                f'corte-caja-{cash_close.date}.xlsx',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                key=f'cash_close_excel_{cash_close.id}', icon=':material/table_view:',
                width='stretch')


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
        'Folio': s.transaction_id or str(s.id), 'ID': s.id,
        'Producto': s.product.name if s.product else '—', 'Fecha': str(s.date),
        'Precio': float(s.price.amount), 'Método': s.payment_method or '',
    } for s in result['sales']])
    expenses_df = pd.DataFrame([{
        'ID': e.id, 'Nombre': e.name, 'Fecha': str(e.date),
        'Gastado': float(e.spent_money.amount),
    } for e in result['expenses']])
    low_stock = _get_low_stock_products()
    out_of_stock = _get_out_of_stock_products()
    low_stock_df = pd.DataFrame(_inventory_export_rows(low_stock))
    out_of_stock_df = pd.DataFrame(_inventory_export_rows(out_of_stock))

    summary_rows = [{
        'Periodo': f'{initial_date} al {final_date}',
        'Ventas': result['sale_quantity'],
        'Ingresos': float(result['acquired_money'].amount),
        'Ganancia bruta': float(result['total_profit'].amount),
        'Gastos': float(result['total_expense'].amount),
        'Ganancia neta': float(result['net_profit'].amount),
    }]
    report_sections = [
        ('Resumen', summary_rows),
        ('Ventas', sales_df.to_dict('records')),
        ('Gastos', expenses_df.to_dict('records')),
        ('Productos por agotarse', low_stock_df.to_dict('records')),
        ('Productos agotados', out_of_stock_df.to_dict('records')),
    ]
    business = _business_export_data()
    report_title = 'Reporte general de operación'
    report_subtitle = f'Periodo del {initial_date} al {final_date}'
    export_columns = st.columns(2)
    export_columns[0].download_button(
        'Descargar reporte PDF',
        generate_pdf_bytes(business, report_title, report_subtitle, report_sections),
        f'reporte-{initial_date}-{final_date}.pdf', 'application/pdf',
        icon=':material/picture_as_pdf:', width='stretch',
    )
    export_columns[1].download_button(
        'Descargar reporte Excel',
        generate_excel_bytes(business, report_title, report_subtitle, report_sections),
        f'reporte-{initial_date}-{final_date}.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        icon=':material/table_view:', width='stretch',
    )

    tab_sales, tab_expenses, tab_low, tab_out = st.tabs([
        'Ventas del periodo', 'Gastos del periodo', 'Por agotarse', 'Agotados'])
    with tab_sales:
        st.dataframe(sales_df, width='stretch', hide_index=True)
    with tab_expenses:
        st.dataframe(expenses_df, width='stretch', hide_index=True)
    with tab_low:
        if low_stock_df.empty:
            st.success('No hay productos por agotarse.')
        else:
            st.warning(f'{len(low_stock_df)} producto(s) requieren reabastecimiento.')
            st.dataframe(low_stock_df, width='stretch', hide_index=True)
    with tab_out:
        if out_of_stock_df.empty:
            st.success('No hay productos agotados.')
        else:
            st.error(f'{len(out_of_stock_df)} producto(s) están agotados.')
            st.dataframe(out_of_stock_df, width='stretch', hide_index=True)


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
    with st.form('business_profile_form', enter_to_submit=False):
        business_name = st.text_input('Nombre comercial', value=profile.business_name or '')
        owner_name = st.text_input('Responsable', value=profile.owner_name or '')
        phone = st.text_input('Teléfono', value=profile.phone or '')
        whatsapp = st.text_input('WhatsApp', value=profile.whatsapp or '')
        email = st.text_input('Correo', value=profile.email or '')
        address = st.text_input('Dirección', value=profile.address or '')
        tax_id = st.text_input('RFC o identificación fiscal', value=profile.tax_id or '')
        website = st.text_input('Sitio web', value=profile.website or '')
        submitted = st.form_submit_button('Guardar perfil')
    if submitted:
        repository.save_profile({
            'business_name': business_name, 'owner_name': owner_name, 'phone': phone,
            'whatsapp': whatsapp, 'email': email, 'address': address,
            'tax_id': tax_id, 'website': website,
        })
        st.success('Perfil actualizado.')


ADMIN_PAGES = {
    'Tablero': _render_dashboard, 'Ventas': _render_sales, 'Inventario': _render_inventory,
    'Corte de caja': _render_cash_close, 'Gastos': _render_expenses,
    'Reportes': _render_reports, 'Estadísticas': _render_statistics,
    'Mi negocio': _render_business_profile,
}
SELLER_PAGES = {
    'Nueva venta': _render_sales,
    'Cotizaciones': _render_quotes,
    'Inventario': _render_inventory_readonly,
    'Venta express': _render_express_sale,
    'Corte de caja': _render_cash_close,
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
        if token:
            user_repository = RepositoryFactory.get_user_repository()
            user = user_repository.authenticate_session(token)
            if user is not None:
                schema.activate_user_workspace(user)
                st.session_state['user'] = user
                st.session_state['page'] = 'Tablero'
            else:
                del st.query_params['session']
    if 'user' not in st.session_state:
        _render_login()
    else:
        _render_app()


main()
