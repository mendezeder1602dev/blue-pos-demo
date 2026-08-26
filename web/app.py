"""Interfaz web y orquestador principal de Puntos ECCOS.

Mapa rápido para mantenimiento:

* Las funciones ``_render_*`` representan páginas o bloques visuales.
* ``ADMIN_PAGES`` y ``SELLER_PAGES`` definen navegación y visibilidad por perfil.
* Los repositorios concentran persistencia y reglas críticas; la interfaz solamente
  coordina entradas, mensajes y navegación.
* Streamlit ejecuta este archivo completo en cada interacción. El estado que debe
  sobrevivir se guarda en ``st.session_state`` y no en variables globales mutables.
* Los documentos se generan de forma diferida para no bloquear el render normal.

Ejecutar localmente con:

    .venv\\Scripts\\streamlit.exe run web/app.py
"""
import calendar
import base64
import hashlib
import json
import os
import sys
import re
from datetime import date, datetime, timedelta
from html import escape
from types import SimpleNamespace
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st
from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing

# Los secretos de Streamlit deben exponerse antes de importar la fábrica de datos.
try:
    for _secret_name in ('BLUE_POS_DATABASE_URL', 'BLUE_POS_AUTH_DATABASE_URL'):
        if _secret_name in st.secrets:
            os.environ[_secret_name] = str(st.secrets[_secret_name])
except FileNotFoundError:
    pass

from model import economy, schema
from model.help_assistant import find_answer, topics_for_role
from model.inventory_excel import (
    ACTION_ADD, ACTION_CREATE, ACTION_REPLACE, ACTION_SKIP, IMPORT_ACTIONS,
    build_import_preview, generate_inventory_template, read_inventory_workbook,
    canonical_inventory_value, inventory_field_options, validate_import_rows,
)
from model.upload_security import validate_image_upload
from model.authorization import authorization_context
from model.repository.catalog import normalize_catalog_slug
from model.database_utilities import backup_database_bytes
from model.entity.models import CashClose, CashMovement, CashOpening, Expense, Product, Quote, QuoteItem, Sale
from model.repository.expense import ExpenseFilter
from model.repository.exc.product import UniqueProductBarcodeException, UniqueProductNameException
from model.repository.factory import RepositoryFactory
from model.repository.product import ProductFilter
from model.repository.sale import SaleFilter
from model.report.exports import (
    business_as_dict,
    generate_excel_bytes as _generate_excel_bytes,
    generate_pdf_bytes as _generate_pdf_bytes,
)
from model.report.ticket import generate_thermal_ticket_bytes as _generate_thermal_ticket_bytes
from model.util.monetary_types import CUPMoney
from model.timezone import mexico_now, mexico_today

LOW_STOCK_THRESHOLD = 5
PAYMENT_METHODS = ('Efectivo', 'Transferencia', 'Tarjeta')
MONTH_NAMES = ('', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')
DESCRIPTION_LABEL = 'Descripción'
NET_PROFIT_LABEL = 'Ganancias netas'
CURRENCY_CODE = 'MXN'
CASH_DENOMINATIONS = (
    ('bill_1000', 'Billete mexicano · 1,000 MXN', 1000.0),
    ('bill_500', 'Billete mexicano · 500 MXN', 500.0),
    ('bill_200', 'Billete mexicano · 200 MXN', 200.0),
    ('bill_100', 'Billete mexicano · 100 MXN', 100.0),
    ('bill_50', 'Billete mexicano · 50 MXN', 50.0),
    ('bill_20', 'Billete mexicano · 20 MXN', 20.0),
    ('coin_20', 'Moneda mexicana · 20 MXN', 20.0),
    ('coin_10', 'Moneda mexicana · 10 MXN', 10.0),
    ('coin_5', 'Moneda mexicana · 5 MXN', 5.0),
    ('coin_2', 'Moneda mexicana · 2 MXN', 2.0),
    ('coin_1', 'Moneda mexicana · 1 MXN', 1.0),
    ('coin_050', 'Moneda mexicana · 0.50 MXN', .5),
)
WORKSPACE_SCHEMA_VERSION = 4


@st.cache_data(ttl='10m', max_entries=48, show_spinner=False)
def _cached_pdf_bytes(business, title, subtitle, sections):
    """Conserva documentos ya solicitados sin permitir crecimiento ilimitado.

    El contenido completo forma parte de la clave. Por eso una venta, cambio de perfil
    o modificación de inventario produce automáticamente un documento diferente.
    """
    return _generate_pdf_bytes(business, title, subtitle, sections)


@st.cache_data(ttl='10m', max_entries=48, show_spinner=False)
def _cached_excel_bytes(business, title, subtitle, sections):
    return _generate_excel_bytes(business, title, subtitle, sections)


def generate_pdf_bytes(business, title, subtitle, sections):
    """Devuelve un callback: Streamlit construye el PDF únicamente al descargar."""
    return lambda: _cached_pdf_bytes(business, title, subtitle, sections)


def generate_excel_bytes(business, title, subtitle, sections):
    """Devuelve un callback: Streamlit construye Excel únicamente al descargar."""
    return lambda: _cached_excel_bytes(business, title, subtitle, sections)


@st.cache_data(ttl='10m', max_entries=96, show_spinner=False)
def _cached_thermal_ticket(business, folio, created_at, items, payment_method,
                           payment_details, customer, paper_width_mm, ticket_title):
    return _generate_thermal_ticket_bytes(
        business, folio, created_at, items, payment_method, payment_details,
        customer, paper_width_mm, ticket_title)


def _thermal_ticket_download(business, folio, created_at, items, payment_method,
                             payment_details='', customer='', paper_width_mm=80,
                             ticket_title='TICKET DE VENTA'):
    """Difere el ticket térmico hasta que el usuario pulsa Descargar."""
    return lambda: _cached_thermal_ticket(
        business, folio, created_at, items, payment_method, payment_details,
        customer, paper_width_mm, ticket_title)


def _mxn(value):
    """Formato monetario único para pesos mexicanos en interfaz y documentos."""
    return f'${float(value):,.2f} {CURRENCY_CODE}'


def _sale_folio(sale_id):
    """Folio comercial corto; el identificador interno nunca se muestra al cliente."""
    return f'V-{int(sale_id):06d}'

st.set_page_config(page_title='Puntos ECCOS', page_icon='🛒', layout='wide')

# Los traductores automáticos del navegador reemplazan nodos de texto directamente.
# React/Streamlit conserva referencias a esos nodos y, al navegar, puede intentar
# retirarlos por segunda vez (`removeChild: node is not a child`). La interfaz ya está
# localizada en español, por lo que indicamos explícitamente que no debe traducirse.
st.html('''
<meta name="google" content="notranslate">
<meta http-equiv="Content-Language" content="es-MX">
<style>body { translate: no; }</style>
''')


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
    .sidebar-user-card { margin:.75rem 0 .65rem; padding:.8rem .85rem;
        border:1px solid #263A52; border-radius:12px; background:#0E1B2D; }
    .sidebar-user-name { color:#F6F8FB; font-size:.88rem; font-weight:760;
        line-height:1.25; margin-bottom:.18rem; }
    .sidebar-user-role { color:#9FB0C3; font-size:.7rem; font-weight:650; }
    .sidebar-section-label { color:#7F95AB; font-size:.65rem; font-weight:850;
        letter-spacing:.11em; margin:.85rem 0 .28rem; text-transform:uppercase; }
    [class*="st-key-nav_"] button { min-height:38px !important; justify-content:flex-start;
        padding:.4rem .7rem !important; border-color:transparent !important; }
    [class*="st-key-nav_"] button[kind="secondary"] { background:transparent !important; }
    [class*="st-key-nav_"] button[kind="secondary"] p,
    [class*="st-key-nav_"] button[kind="secondary"] span { color:#DDE7F1 !important; }
    [class*="st-key-nav_"] button[kind="secondary"]:hover { background:#111E2F !important;
        border-color:#2C435D !important; }
    [class*="st-key-sidebar_utility_"] button { min-height:38px !important;
        padding:.35rem .5rem !important; }
    [data-testid="stSidebar"] [data-testid="stExpander"] { background:#0B1727 !important;
        border-color:#263A52 !important; box-shadow:none; }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary p {
        color:#DDE7F1 !important; font-size:.78rem; font-weight:720; }
    [data-testid="stMainBlockContainer"] {
        max-width:1680px; padding:4.35rem clamp(.85rem,2vw,2rem) 1.5rem !important;
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
        padding:12px 14px; min-height:112px; box-shadow:0 3px 10px rgba(24,34,48,.04); }
    [data-testid="stMetricLabel"] { color:var(--muted); font-weight:700; }
    [data-testid="stMetricLabel"] p { white-space:normal !important; overflow:visible !important;
        text-overflow:clip !important; line-height:1.2 !important; }
    [data-testid="stMetricValue"] { color:var(--ink); font-weight:750; }
    [data-testid="stMetricValue"] > div { font-size:clamp(1.45rem,2.25vw,2.15rem) !important;
        white-space:nowrap !important; overflow:visible !important; text-overflow:clip !important; }
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
    .stButton > button p, .stFormSubmitButton > button p,
    .stDownloadButton > button p {
        color:#182230 !important; font-weight:650 !important;
        word-break:normal !important; overflow-wrap:normal !important;
        hyphens:none !important;
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
            padding-left:.8rem !important; padding-right:.8rem !important;
            padding-top:4.2rem !important;
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
        [data-testid="stMainBlockContainer"] { padding-left:.55rem !important; padding-right:.55rem !important; }
        [data-testid="stMetric"] { min-height:100px; padding:10px 12px; }
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


def _queue_activity_notice(title, detail, tone='success', icon=':material/check_circle:'):
    """Keep action feedback visible after the rerun that refreshes a form."""
    actor = _actor_name() if st.session_state.get('user') is not None else 'Sistema'
    st.session_state['activity_notice'] = {
        'title': str(title), 'detail': str(detail), 'tone': tone, 'icon': icon,
        'actor': actor, 'created_at': mexico_now().strftime('%d/%m/%Y %H:%M'),
    }


def _form_version(scope):
    """Devuelve una versión para construir claves de una captura operativa."""
    return st.session_state.setdefault(f'_form_version_{scope}', 0)


def _reset_form(scope):
    """Presenta widgets nuevos y limpios después de guardar correctamente.

    Cambiar las claves evita modificar el estado de widgets ya renderizados, algo que
    Streamlit no permite. En errores de validación no se llama para conservar los datos.
    """
    state_key = f'_form_version_{scope}'
    st.session_state[state_key] = st.session_state.get(state_key, 0) + 1


def _render_activity_notice():
    notice = st.session_state.pop('activity_notice', None)
    if not notice:
        return
    title = notice['title']
    message = (
        f'**{title}**  \n{notice["detail"]}  \n'
        f'**Responsable:** {notice.get("actor", "Sistema")} · '
        f'**Fecha y hora:** {notice.get("created_at", "")}'
    )
    renderer = {
        'success': st.success,
        'warning': st.warning,
        'error': st.error,
        'info': st.info,
    }.get(notice.get('tone'), st.success)
    renderer(message, icon=notice.get('icon'))
    st.toast(title, icon=notice.get('icon'))


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
          <div class="login-logo"><span class="login-logo-mark">◈</span> Puntos ECCOS</div>
          <div class="login-kicker">CONTROL INTELIGENTE PARA TU NEGOCIO</div>
          <h1>Vende mejor.<br>Decide con claridad.</h1>
          <p class="login-brand-copy">Todo lo que necesitas para cobrar, controlar tu inventario
          y conocer el resultado real de tu negocio, desde un solo lugar.</p>
          <div class="login-benefits">
            <div class="login-benefit"><span>✓</span>Ventas ágiles</div>
            <div class="login-benefit"><span>✓</span>Stock al día</div>
            <div class="login-benefit"><span>✓</span>Reportes claros</div>
          </div>
          <div class="brand-legal"><strong>Creado y desarrollado en Tabasco, México, por Grupo ECCOS</strong><br>
          Con apoyo de tecnologías emergentes como Codex · Software propietario</div>
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
        role_label = st.radio(
            'Tipo de acceso', ('Administrador', 'Vendedor'), index=0,
            horizontal=True, key='login_role',
        )

        if role_label == 'Administrador':
            with st.form('login_form', border=False, enter_to_submit=False):
                username = st.text_input('Usuario', placeholder='Escribe tu usuario', icon=':material/person:')
                password = st.text_input(
                    'Contraseña', type='password', placeholder='Escribe tu contraseña',
                    icon=':material/lock:',
                )
                submitted = st.form_submit_button(
                    'Iniciar sesión', type='primary', width='stretch', icon=':material/login:',
                )
            if submitted:
                users = RepositoryFactory.get_user_repository()
                user = users.authenticate(username.strip(), password)
                if user is None:
                    blocked_seconds = users.login_block_seconds(username.strip())
                    if blocked_seconds:
                        remaining = max(1, blocked_seconds // 60 + 1)
                        st.error(
                            f'Acceso bloqueado temporalmente. Intenta nuevamente en '
                            f'{remaining} minuto(s).', icon=':material/timer:')
                    else:
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
    st.session_state['_workspace_schema_ready'] = True
    st.session_state['_workspace_schema_version'] = WORKSPACE_SCHEMA_VERSION
    st.session_state['user'] = user
    st.session_state['page'] = 'Tablero'
    # Nunca se coloca una credencial en la URL. El usuario vive únicamente en
    # el estado privado de esta sesión de Streamlit.
    st.query_params.pop('session', None)
    st.rerun()


def _log_out():
    st.query_params.pop('session', None)
    st.session_state.pop('user', None)
    st.session_state.pop('page', None)
    st.rerun()


def _is_administrator():
    return getattr(st.session_state['user'], 'role', '') == 'superuser'


# ---------------------------------------------------------------------------
# Tablero
# ---------------------------------------------------------------------------

def _get_low_stock_products():
    products = RepositoryFactory.get_product_repository().get_all_products()
    return [product for product in products if not product.is_temporary
            and 0 < product.quantity <= (product.minimum_stock or LOW_STOCK_THRESHOLD)]


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
        'Categoría': product.category or 'General',
        'Proveedor': product.supplier or '',
        'Existencia mínima': product.minimum_stock or LOW_STOCK_THRESHOLD,
    } for product in products]


def _render_dashboard():
    _hero('Centro de operación', 'Ventas, inventario y resultados del negocio en una sola vista.')
    summary = RepositoryFactory.get_economic_summary_repository().get_economic_summary_on_day(mexico_today())
    today_summary = _summary_for_range(mexico_today(), mexico_today())
    catalog_products = [
        product for product in RepositoryFactory.get_product_repository().get_all_products()
        if not product.is_temporary
    ]
    product_quantity = len(catalog_products)
    primary_metrics = st.columns(3)
    primary_metrics[0].metric('Ventas de hoy', _mxn(summary.acquired_money.amount))
    primary_metrics[1].metric('Operaciones', str(today_summary['sale_quantity']))
    primary_metrics[2].metric('Utilidad neta', _mxn(summary.net_profit.amount))
    secondary_metrics = st.columns(2)
    secondary_metrics[0].metric('Gastos de hoy', _mxn(summary.total_expense.amount))
    secondary_metrics[1].metric('Productos', str(product_quantity))

    if _is_administrator():
        st.subheader('Alerta de inventario')
        if not catalog_products:
            st.warning(
                'Inventario sin productos. Registra tu catálogo para comenzar a vender y '
                'recibir alertas reales de existencias.', icon=':material/inventory_2:')
            with st.container(border=True):
                st.markdown('### Prepara tu inventario')
                st.caption(
                    'Agrega nombre, descripción, precio, costo, existencia inicial y, si lo '
                    'utilizas, el código de barras de cada producto.')
                st.markdown('1. Registra tu primer producto.')
                st.markdown('2. Confirma sus existencias y precios.')
                st.markdown('3. Regresa a **Nueva venta** para comenzar a cobrar.')
                if st.button('Ir a Inventario y agregar producto', type='primary',
                             icon=':material/add_box:', width='stretch',
                             key='dashboard_go_inventory'):
                    st.session_state['page'] = 'Inventario'
                    st.rerun()
            return
        low_stock = [product for product in catalog_products
                     if 0 < product.quantity <= (product.minimum_stock
                                                  or LOW_STOCK_THRESHOLD)]
        out_of_stock = [product for product in catalog_products if product.quantity <= 0]
        low_margin = [product for product in catalog_products
                      if float(product.price.amount) > 0
                      and ((float(product.price.amount) - float(product.cost.amount))
                           / float(product.price.amount)) < .10]
        if out_of_stock:
            st.error(f'{len(out_of_stock)} producto(s) agotado(s). Reabastece el inventario.',
                     icon=':material/error:')
            st.table(pd.DataFrame([{'Producto': p.name, 'Unidades': p.quantity}
                                   for p in out_of_stock]))
        if low_stock:
            st.warning('Estos productos están por agotarse, considera reabastecerlos pronto:')
            st.table(pd.DataFrame([{'Producto': p.name, 'Unidades': p.quantity}
                                   for p in low_stock]))
        if low_margin:
            st.warning(
                f'{len(low_margin)} producto(s) tienen un margen menor al 10 %. '
                'Revisa costos y precios antes de vender.', icon=':material/price_check:')
            st.dataframe(pd.DataFrame([{
                'Producto': product.name,
                'Costo': float(product.cost.amount),
                'Precio': float(product.price.amount),
                'Margen': ((float(product.price.amount) - float(product.cost.amount))
                           / float(product.price.amount)),
            } for product in low_margin]), hide_index=True, width='stretch',
                column_config={
                    'Costo': st.column_config.NumberColumn(format='$ %.2f MXN'),
                    'Precio': st.column_config.NumberColumn(format='$ %.2f MXN'),
                    'Margen': st.column_config.NumberColumn(format='percent'),
                })
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
                                   f'Corte al {mexico_today()}', inventory_sections),
                f'alertas-inventario-{mexico_today()}.pdf', 'application/pdf',
                icon=':material/picture_as_pdf:', width='stretch',
            )
            alert_columns[1].download_button(
                'Alertas en Excel',
                generate_excel_bytes(business, 'Alertas de inventario',
                                     f'Corte al {mexico_today()}', inventory_sections),
                f'alertas-inventario-{mexico_today()}.xlsx',
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
        st.metric('Total a pagar', _mxn(total))
        cash_key = f'{prefix}_cash_received'
        total_key = f'{prefix}_cash_total'
        if st.session_state.get(total_key) != float(total):
            st.session_state[cash_key] = float(total)
            st.session_state[total_key] = float(total)
        received = st.number_input(
            'Efectivo recibido (MXN)', min_value=0.0, step=10.0,
            format='%.2f', key=cash_key,
        )
        change = max(0.0, float(received) - float(total))
        if float(received) < float(total):
            validation_error = f'Faltan {_mxn(float(total) - float(received))} para completar el cobro.'
        st.metric('Cambio a entregar', _mxn(change))
        details.extend([f'Recibido: {_mxn(received)}', f'Cambio: {_mxn(change)}'])

    note = st.text_input(
        'Nota adicional', placeholder='Cliente, pedido u observación (opcional)', key=f'{prefix}_note'
    ).strip()
    if note:
        details.append(f'Nota: {note}')
    return method, ' | '.join(details), validation_error


def _actor_name():
    user = st.session_state.get('user')
    if user is not None and not _is_administrator():
        try:
            opening = RepositoryFactory.get_cash_control_repository().get_opening(mexico_today())
            if opening and (opening.shift_responsible or '').strip():
                return opening.shift_responsible.strip()
        except Exception:
            pass
    return (getattr(user, 'display_name', '') or getattr(user, 'username', '')
            or ('Administrador' if _is_administrator() else 'Vendedor'))


def _set_cart_quantity(product_id, quantity, unit_price=None):
    quantity = int(quantity)
    st.session_state.pos_cart[product_id] = quantity
    st.session_state[f'cart_qty_{product_id}'] = quantity
    st.session_state.setdefault('pos_cart_prices', {})
    if unit_price is not None:
        st.session_state.pos_cart_prices[product_id] = float(unit_price)


def _remove_from_cart(product_id):
    st.session_state.pos_cart.pop(product_id, None)
    st.session_state.setdefault('pos_cart_prices', {}).pop(product_id, None)
    st.session_state.pop(f'cart_qty_{product_id}', None)


def _clear_cart():
    for product_id in list(st.session_state.get('pos_cart', {})):
        st.session_state.pop(f'cart_qty_{product_id}', None)
    st.session_state.pos_cart = {}
    st.session_state.pos_cart_prices = {}

def _render_sales():
    _hero('Punto de venta', 'Agrega productos al carrito y completa el cobro desde una sola pantalla.', 'CAJA · TURNO ACTIVO')
    if not _require_open_cash_for_sale():
        return
    st.session_state.setdefault('pos_cart', {})
    st.session_state.setdefault('pos_cart_prices', {})
    checkout_version = _form_version('checkout')
    repository = RepositoryFactory.get_product_repository()
    products = [product for product in repository.get_all_products() if not product.is_temporary]
    available = [product for product in products if product.quantity > 0]
    product_by_id = {product.id: product for product in products}

    held_sales = RepositoryFactory.get_operations_repository().get_held_sales()
    if held_sales:
        with st.expander(f'Ventas en espera ({len(held_sales)})', icon=':material/pause_circle:'):
            for held in held_sales:
                units = sum(item.quantity for item in held.items)
                amount = sum(float(item.unit_price.amount) * item.quantity for item in held.items)
                st.markdown(f'**{held.label} · {units} artículos · {_mxn(amount)}**')
                st.caption(f'{held.created_at:%d/%m/%Y %H:%M} · {held.created_by}')
                restore_column, discard_column = st.columns(2)
                if restore_column.button('Recuperar', key=f'restore_held_{held.id}',
                                         icon=':material/play_circle:', width='stretch'):
                    unavailable = [item for item in held.items
                                   if item.product_id not in product_by_id
                                   or product_by_id[item.product_id].quantity < item.quantity]
                    if unavailable:
                        st.error('No se puede recuperar: cambió la existencia de uno o más productos.')
                    else:
                        _clear_cart()
                        for item in held.items:
                            _set_cart_quantity(item.product_id, item.quantity,
                                               float(item.unit_price.amount))
                        RepositoryFactory.get_operations_repository().delete_held_sale(held.id)
                        RepositoryFactory.get_operations_repository().audit(
                            'venta_espera_recuperada', _actor_name(), 'held_sale', held.id,
                            f'{held.label} · {units} artículos devueltos al carrito')
                        _queue_activity_notice(
                            'Venta en espera recuperada',
                            f'Se devolvieron {units} artículo(s) al carrito y se retiró '
                            f'la espera “{held.label}”.', icon=':material/play_circle:')
                        st.rerun()
                if discard_column.button('Descartar', key=f'discard_held_{held.id}',
                                          icon=':material/delete:', width='stretch'):
                    RepositoryFactory.get_operations_repository().delete_held_sale(held.id)
                    RepositoryFactory.get_operations_repository().audit(
                        'venta_espera_descartada', _actor_name(), 'held_sale', held.id,
                        f'{held.label} · {units} artículos')
                    _queue_activity_notice(
                        'Venta en espera descartada',
                        f'Se eliminó “{held.label}”. No se registró ninguna venta.',
                        tone='warning', icon=':material/delete:')
                    st.rerun()

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
            icon=':material/search:', label_visibility='collapsed',
            key=f'pos_search_{checkout_version}',
        ).strip().lower()
        exact_barcode = next((product for product in available
                              if search and (product.barcode or '').lower() == search), None)
        if exact_barcode is not None:
            current_scanned = st.session_state.pos_cart.get(exact_barcode.id, 0)
            st.success(
                f'Código reconocido: {exact_barcode.name} · {_mxn(exact_barcode.price.amount)}',
                icon=':material/barcode_scanner:')
            if st.button('Agregar producto escaneado', type='primary', width='stretch',
                         icon=':material/add_shopping_cart:',
                         key=f'add_exact_barcode_{checkout_version}'):
                if current_scanned < exact_barcode.quantity:
                    _set_cart_quantity(
                        exact_barcode.id, current_scanned + 1,
                        st.session_state.pos_cart_prices.get(
                            exact_barcode.id, float(exact_barcode.price.amount)))
                    st.rerun()
                else:
                    st.error('Ya agregaste todas las existencias disponibles.')
        filter_columns = st.columns(2)
        stock_filter = filter_columns[0].selectbox(
            'Mostrar', ('Todos', 'Stock suficiente', 'Por agotarse', 'En el carrito'),
            key=f'pos_stock_filter_{checkout_version}')
        sort_order = filter_columns[1].selectbox(
            'Ordenar', ('Nombre A–Z', 'Menor precio', 'Mayor precio', 'Menor existencia'),
            key=f'pos_sort_order_{checkout_version}')
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
                                f'<div class="product-card-price">{_mxn(product.price.amount)}</div>'
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
                                    _set_cart_quantity(
                                        product.id, current + 1,
                                        st.session_state.pos_cart_prices.get(
                                            product.id, float(product.price.amount)))
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
                    unit_price = st.session_state.pos_cart_prices.get(
                        product_id, float(product.price.amount))
                    line_total = unit_price * current_quantity
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
                            f'<div class="cart-line-total">{_mxn(line_total)}</div>'
                            f'<div class="cart-unit-price">{_mxn(unit_price)} c/u</div>',
                            unsafe_allow_html=True)
                        if remove_column.button('', key=f'remove_cart_{product_id}',
                                                icon=':material/delete:'):
                            _remove_from_cart(product_id)
                            st.rerun()

                st.markdown(
                    f'<div class="pos-total"><small>TOTAL A COBRAR</small>'
                    f'<strong>{_mxn(total)}</strong></div>', unsafe_allow_html=True,
                )
                customers = RepositoryFactory.get_operations_repository().get_customers()
                customer_options = ['Público general'] + [customer.name for customer in customers]
                sale_customer = st.selectbox(
                    'Cliente', customer_options,
                    key=f'checkout_customer_{checkout_version}',
                    help='Opcional. Administración puede registrar clientes desde el menú Clientes.')
                payment_method, payment_details, payment_error = _payment_controls(
                    f'checkout_{checkout_version}', total)
                sale_date = mexico_today()
                st.caption(f'Fecha y jornada de venta: {sale_date}')
                submitted = st.button(
                    f'Cobrar {_mxn(total)}', type='primary', width='stretch',
                    icon=':material/payments:', key=f'checkout_submit_{checkout_version}',
                )

                clear_column, suspend_column = st.columns(2)
                if clear_column.button('Vaciar', width='stretch', icon=':material/delete_sweep:'):
                    _clear_cart()
                    st.rerun()
                if suspend_column.button('Venta en espera', width='stretch',
                                         icon=':material/pause_circle:'):
                    label = f'Espera {mexico_now():%H:%M} · {item_count} artículos'
                    RepositoryFactory.get_operations_repository().hold_sale(
                        label, '', _actor_name(), cart, {
                            product_id: st.session_state.pos_cart_prices.get(
                                product_id, float(product_by_id[product_id].price.amount))
                            for product_id in cart
                        })
                    _clear_cart()
                    _queue_activity_notice(
                        'Venta guardada en espera',
                        f'El carrito con {item_count} artículo(s) quedó reservado para '
                        'continuarlo después.', icon=':material/pause_circle:')
                    _reset_form('checkout')
                    st.rerun()

                if submitted:
                    if payment_error:
                        st.error(payment_error, icon=':material/error:')
                        return
                    try:
                        sale_repository = RepositoryFactory.get_sale_repository()
                        transaction_entries = []
                        for product_id, quantity in cart.items():
                            product = product_by_id[product_id]
                            unit_price = st.session_state.pos_cart_prices.get(
                                product_id, float(product.price.amount))
                            sale = Sale(
                                product_id=product.id, product_name=product.name,
                                price=CUPMoney(f'{unit_price:.2f}'), cost=product.cost,
                                date=sale_date, payment_method=payment_method or 'Efectivo',
                                payment_details=payment_details, cashier=_actor_name(),
                                customer=sale_customer,
                            )
                            transaction_entries.append((sale, int(quantity)))
                        inserted = sale_repository.insert_transaction(transaction_entries)
                        RepositoryFactory.get_operations_repository().audit(
                            'venta_registrada', _actor_name(), 'sale', inserted[0].transaction_id,
                            f'{item_count} artículos · {_mxn(total)} · {payment_method}')
                        _clear_cart()
                        _queue_activity_notice(
                            'Venta registrada correctamente',
                            f'Folio {_sale_folio(inserted[0].id)} · {item_count} '
                            f'artículo(s) · {_mxn(total)} · {payment_method}.',
                            icon=':material/receipt_long:')
                        _reset_form('checkout')
                        st.rerun()
                    except Exception as error:
                        st.error(f'No se pudo completar la venta: {error}')

        with st.expander('Movimientos recientes', icon=':material/receipt_long:'):
            history_limit = st.selectbox(
                'Mostrar operaciones', (8, 20, 50), key='sales_history_limit')
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
            for transaction_sales in list(transactions.values())[:history_limit]:
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
                commercial_folio = _sale_folio(min(sale.id for sale in transaction_sales))
                st.markdown(f'**Venta {commercial_folio} · {_mxn(transaction_total)}**')
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
                    f' · Cliente: {first_sale.customer or "Público general"}'
                    f' · {first_sale.payment_details or "Sin referencia"}'
                )
                thermal_items = tuple({
                    'name': name, 'quantity': line['quantity'],
                    'unit_price': line['total'] / line['quantity'],
                } for name, line in product_lines.items())
                ticket_actions = st.columns(2)
                ticket_actions[0].download_button(
                    'Ticket térmico 58 mm',
                    _thermal_ticket_download(
                        business, commercial_folio, first_sale.created_at or first_sale.date,
                        thermal_items, first_sale.payment_method or 'Sin método',
                        first_sale.payment_details or '',
                        first_sale.customer or 'Público general', 58),
                    f'ticket-{commercial_folio}-58mm.pdf', 'application/pdf',
                    key=f'ticket_58_{first_sale.id}', icon=':material/receipt_long:',
                    width='stretch',
                )
                ticket_actions[1].download_button(
                    'Ticket térmico 80 mm',
                    _thermal_ticket_download(
                        business, commercial_folio, first_sale.created_at or first_sale.date,
                        thermal_items, first_sale.payment_method or 'Sin método',
                        first_sale.payment_details or '',
                        first_sale.customer or 'Público general', 80),
                    f'ticket-{commercial_folio}-80mm.pdf', 'application/pdf',
                    key=f'ticket_80_{first_sale.id}', icon=':material/receipt_long:',
                    width='stretch',
                )
                if _is_administrator():
                    reversal_reason = st.text_input(
                        'Motivo de anulación', key=f'undo_reason_{first_sale.id}',
                        placeholder='Obligatorio para conservar la auditoría')
                    if st.button(
                        'Anular venta', key=f'undo_sale_{first_sale.id}',
                        icon=':material/cancel:', width='stretch',
                    ):
                        try:
                            RepositoryFactory.get_sale_repository().reverse_transaction(
                                first_sale.transaction_id, reversal_reason, _actor_name())
                            RepositoryFactory.get_operations_repository().audit(
                                'venta_anulada', _actor_name(), 'sale', first_sale.transaction_id,
                                reversal_reason)
                            _queue_activity_notice(
                                'Venta anulada',
                                f'La venta {commercial_folio} fue anulada y sus '
                                'existencias fueron restituidas. La evidencia se conserva.',
                                tone='warning', icon=':material/cancel:')
                            st.rerun()
                        except Exception as error:
                            st.error(str(error))
                else:
                    st.button(
                        'Anulación requiere administrador', disabled=True,
                        key=f'undo_sale_disabled_{first_sale.id}',
                        icon=':material/lock:', width='stretch')


# ---------------------------------------------------------------------------
# Inventario
# ---------------------------------------------------------------------------

def _render_inventory_excel_import(products):
    import_version = st.session_state.setdefault('inventory_import_version', 0)
    with st.expander('Importar inventario desde Excel', icon=':material/upload_file:'):
        st.markdown('#### Migra tu inventario en tres pasos')
        st.caption(
            'Descarga la plantilla, captura tus productos y revisa cada fila antes de guardar. '
            'Nada se incorpora al inventario hasta confirmar la importación.')
        st.download_button(
            'Descargar plantilla Excel', generate_inventory_template(),
            'plantilla-inventario-puntos-eccos.xlsx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            icon=':material/download:', key=f'inventory_template_{import_version}')
        uploaded = st.file_uploader(
            'Selecciona tu archivo Excel', type=('xlsx',),
            help='Máximo 5 MB y 2,000 productos. Utiliza la plantilla para evitar errores.',
            key=f'inventory_excel_upload_{import_version}')
        if uploaded is None:
            st.info(
                'Columnas obligatorias: nombre, descripción, costo, precio de venta, '
                'cantidad disponible y categoría.', icon=':material/info:')
            return

        try:
            content = uploaded.getvalue()
            source_rows = read_inventory_workbook(content)
            preview_rows = build_import_preview(source_rows, products)
        except ValueError as error:
            st.error(str(error), icon=':material/error:')
            return

        file_digest = hashlib.sha256(content).hexdigest()[:12]
        st.success(
            f'Archivo leído correctamente: {len(preview_rows):,} producto(s). '
            'Corrige celdas o elimina filas antes de continuar.',
            icon=':material/check_circle:')
        edited = st.data_editor(
            pd.DataFrame(preview_rows), hide_index=True, num_rows='dynamic', width='stretch',
            key=f'inventory_excel_editor_{file_digest}', disabled=('Estado',),
            column_config={
                'Acción': st.column_config.SelectboxColumn(
                    'Acción', options=IMPORT_ACTIONS, required=True),
                'Precio de costo': st.column_config.NumberColumn(
                    'Costo', min_value=0.01, format='$ %.2f'),
                'Precio de venta': st.column_config.NumberColumn(
                    'Precio de venta', min_value=0.01, format='$ %.2f'),
                'Cantidad disponible': st.column_config.NumberColumn(
                    'Cantidad', min_value=0, step=1, format='%d'),
                'Existencia mínima': st.column_config.NumberColumn(
                    'Mínimo', min_value=0, step=1, format='%d'),
            })
        plans, errors = validate_import_rows(edited.to_dict('records'), products)
        create_count = sum(plan['action'] == ACTION_CREATE for plan in plans)
        add_count = sum(plan['action'] == ACTION_ADD for plan in plans)
        replace_count = sum(plan['action'] == ACTION_REPLACE for plan in plans)
        omitted_count = sum(str(row.get('Acción')) == ACTION_SKIP
                            for row in edited.to_dict('records'))
        summary = st.columns(4)
        summary[0].metric('Nuevos', create_count)
        summary[1].metric('Sumar stock', add_count)
        summary[2].metric('Reemplazar stock', replace_count)
        summary[3].metric('Omitidos', omitted_count)

        if errors:
            st.error(
                f'Corrige {len(errors)} problema(s) antes de importar.',
                icon=':material/error:')
            for message in errors[:20]:
                st.caption(f'• {message}')
            if len(errors) > 20:
                st.caption(f'… y {len(errors) - 20} problema(s) adicionales.')

        confirm = st.checkbox(
            'Confirmo que revisé precios, cantidades y acciones del archivo.',
            key=f'inventory_excel_confirm_{file_digest}')
        if st.button(
                'Importar productos al inventario', type='primary',
                icon=':material/publish:', width='stretch',
                disabled=bool(errors) or not confirm or not plans,
                key=f'inventory_excel_apply_{file_digest}'):
            try:
                result = RepositoryFactory.get_product_repository().import_inventory(
                    plans, _actor_name())
                st.session_state.inventory_import_version += 1
                _queue_activity_notice(
                    'Importación completada',
                    f'Se crearon {result["created"]} producto(s), se actualizaron '
                    f'{result["updated"]} y la existencia cambió en '
                    f'{result["unit_delta"]:+d} unidad(es).',
                    icon=':material/upload_file:')
                st.rerun()
            except Exception as error:
                st.error(
                    f'No se guardó ninguna fila. Revisa el archivo: {error}',
                    icon=':material/error:')

@st.fragment
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
    subtitle = f'Inventario actualizado al {mexico_today()}'
    columns = st.columns(2)
    columns[0].download_button(
        'Descargar inventario PDF',
        generate_pdf_bytes(business, 'Reporte de inventario', subtitle, sections),
        f'inventario-{mexico_today()}.pdf', 'application/pdf',
        key=f'{key_prefix}_inventory_pdf', icon=':material/picture_as_pdf:',
        width='stretch')
    columns[1].download_button(
        'Descargar inventario Excel',
        generate_excel_bytes(business, 'Reporte de inventario', subtitle, sections),
        f'inventario-{mexico_today()}.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        key=f'{key_prefix}_inventory_excel', icon=':material/table_view:',
        width='stretch')


def _render_inventory():
    _hero('Inventario', 'Controla catálogo, precios y existencias con información lista para decidir.', 'GESTIÓN · CATÁLOGO')
    products = [product for product in RepositoryFactory.get_product_repository().get_all_products()
                if not product.is_temporary]
    category_options = inventory_field_options(products, 'category')
    supplier_options = inventory_field_options(products, 'supplier')

    _render_inventory_excel_import(products)

    inventory_form_version = st.session_state.setdefault('inventory_form_version', 0)
    with st.expander('Agregar producto'):
        with st.form(f'add_product_form_{inventory_form_version}', enter_to_submit=False):
            name = st.text_input('Nombre *')
            description = st.text_area(f'{DESCRIPTION_LABEL} *', height=68)
            price = st.number_input(
                'Precio de venta (MXN) *', min_value=0.01, value=None, step=1.0,
                format='%.2f', placeholder='Captura el precio de venta')
            cost = st.number_input(
                'Precio de costo (MXN) *', min_value=0.01, value=None, step=1.0,
                format='%.2f', placeholder='Captura cuánto costó el producto')
            quantity = st.number_input(
                'Cantidad disponible *', min_value=0, value=None, step=1,
                placeholder='Captura las unidades disponibles')
            barcode = st.text_input('Código de barras (opcional)')
            category = st.selectbox(
                'Categoría *', category_options, index=None,
                placeholder='Selecciona o escribe una categoría',
                accept_new_options=True,
                help='Reutiliza una categoría registrada o escribe una nueva.',
                key=f'add_product_category_{inventory_form_version}')
            supplier = st.selectbox(
                'Proveedor (opcional)', supplier_options, index=None,
                placeholder='Selecciona o escribe un proveedor',
                accept_new_options=True,
                help='Reutiliza un proveedor registrado o escribe uno nuevo.',
                key=f'add_product_supplier_{inventory_form_version}')
            minimum_stock = st.number_input('Existencia mínima', min_value=0, value=5, step=1)
            st.caption('Los campos marcados con * son obligatorios.')
            submitted = st.form_submit_button(
                'Guardar producto', type='primary', icon=':material/save:')
        if submitted:
            clean_name = name.strip()
            clean_description = description.strip()
            clean_category = canonical_inventory_value(category, category_options)
            clean_supplier = canonical_inventory_value(supplier, supplier_options)
            required_fields = {
                'nombre': clean_name,
                'descripción': clean_description,
                'precio de venta': price,
                'precio de costo': cost,
                'cantidad disponible': quantity,
                'categoría': clean_category,
            }
            missing_fields = [label for label, value in required_fields.items()
                              if value is None or (isinstance(value, str) and not value)]
            if missing_fields:
                st.error(
                    'No se guardó el producto. Completa: '
                    f'{", ".join(missing_fields)}.',
                         icon=':material/error:')
                return
            try:
                product = Product(name=clean_name, description=clean_description,
                                  price=CUPMoney(f'{price:.2f}'), cost=CUPMoney(f'{cost:.2f}'),
                                  quantity=int(quantity), barcode=barcode.strip(),
                                  category=clean_category, supplier=clean_supplier,
                                  minimum_stock=int(minimum_stock))
                RepositoryFactory.get_product_repository().insert_product(product)
                RepositoryFactory.get_operations_repository().audit(
                    'producto_creado', _actor_name(), 'product', product.id,
                    f'{clean_name} · existencia inicial {int(quantity)}')
                st.session_state.inventory_form_version += 1
                _queue_activity_notice(
                    'Producto agregado correctamente',
                    f'“{clean_name}” ya está disponible en {clean_category} con '
                    f'{int(quantity)} unidad(es) iniciales.',
                    icon=':material/add_box:')
                st.rerun()
            except (UniqueProductNameException, UniqueProductBarcodeException) as error:
                st.warning(str(error), icon=':material/content_copy:')
            except Exception as error:
                st.error(str(error), icon=':material/error:')

    st.subheader('Catálogo')
    if not products:
        st.info('No hay productos registrados.')
        return
    st.dataframe(pd.DataFrame([{
        'ID': p.id, 'Nombre': p.name, 'Precio': str(p.price), 'Costo': str(p.cost),
        'Cantidad': p.quantity, 'Mínimo': p.minimum_stock, 'Categoría': p.category,
        'Proveedor': p.supplier or '', 'Código de barras': p.barcode or '',
    } for p in products]), width='stretch', hide_index=True)
    _render_inventory_downloads(products, 'admin', include_cost=True)

    with st.expander('Editar o dar de baja un producto'):
        inventory_admin_version = _form_version('inventory_admin')
        names = [p.name for p in products]
        selected_name = st.selectbox(
            'Selecciona un producto', names, index=None,
            placeholder='Elige el producto que deseas administrar',
            key=f'inventory_edit_select_{inventory_admin_version}')
        if selected_name is None:
            st.caption('Selecciona un producto para editarlo o darlo de baja.')
            return
        product = next(p for p in products if p.name == selected_name)
        with st.form(f'edit_product_form_{product.id}', enter_to_submit=False):
            name = st.text_input('Nombre', value=product.name)
            description = st.text_area(DESCRIPTION_LABEL, value=product.description or '', height=68)
            price = st.number_input('Precio de venta (MXN)', min_value=0.01, step=1.0, format='%.2f',
                                    value=float(product.price.amount))
            cost = st.number_input('Precio de costo (MXN)', min_value=0.0, step=1.0, format='%.2f',
                                   value=float(product.cost.amount))
            barcode = st.text_input('Código de barras', value=product.barcode or '')
            current_category = canonical_inventory_value(
                product.category or 'General', category_options)
            edit_category_options = tuple(dict.fromkeys((*category_options, current_category)))
            category = st.selectbox(
                'Categoría', edit_category_options,
                index=edit_category_options.index(current_category),
                accept_new_options=True,
                placeholder='Selecciona o escribe una categoría',
                help='Reutiliza una categoría registrada o escribe una nueva.',
                key=f'edit_product_category_{product.id}')
            current_supplier = canonical_inventory_value(product.supplier, supplier_options)
            edit_supplier_options = tuple(dict.fromkeys(
                (*supplier_options, *((current_supplier,) if current_supplier else ()))))
            supplier = st.selectbox(
                'Proveedor', edit_supplier_options,
                index=(edit_supplier_options.index(current_supplier)
                       if current_supplier else None),
                accept_new_options=True,
                placeholder='Selecciona o escribe un proveedor',
                help='Reutiliza un proveedor registrado o escribe uno nuevo.',
                key=f'edit_product_supplier_{product.id}')
            minimum_stock = st.number_input('Existencia mínima', min_value=0, step=1,
                                            value=product.minimum_stock or 0)
            save_submitted = st.form_submit_button('Guardar cambios')
        if save_submitted:
            clean_category = canonical_inventory_value(category, category_options)
            clean_supplier = canonical_inventory_value(supplier, supplier_options)
            if not name.strip() or not description.strip() or not clean_category:
                st.error('Completa los campos obligatorios: nombre, descripción y categoría.',
                         icon=':material/error:')
                return
            try:
                updated = Product(id=product.id, name=name.strip(), description=description.strip(),
                                  price=CUPMoney(f'{price:.2f}'), cost=CUPMoney(f'{cost:.2f}'),
                                  quantity=product.quantity, barcode=barcode.strip(),
                                  category=clean_category, supplier=clean_supplier,
                                  minimum_stock=int(minimum_stock), is_active=True)
                RepositoryFactory.get_product_repository().update_product(updated)
                RepositoryFactory.get_operations_repository().audit(
                    'producto_editado', _actor_name(), 'product', product.id, name.strip())
                _queue_activity_notice(
                    'Cambios guardados',
                    f'Se actualizó “{name.strip()}”. Categoría: {clean_category}; '
                    f'proveedor: {clean_supplier or "sin proveedor"}.',
                    icon=':material/edit_square:')
                _reset_form('inventory_admin')
                st.rerun()
            except (UniqueProductNameException, UniqueProductBarcodeException) as error:
                st.warning(str(error), icon=':material/content_copy:')
            except Exception as error:
                st.error(str(error), icon=':material/error:')
        st.divider()
        st.markdown('#### Dar de baja del inventario')
        st.warning(
            f'Esta acción quitará **{product.name}** de ventas, inventario y catálogo público. '
            'Sus tickets, movimientos y reportes anteriores se conservarán para mantener la '
            'auditoría del negocio.',
            icon=':material/warning:')
        confirm_removal = st.checkbox(
            f'Confirmo que deseo dar de baja “{product.name}”',
            key=f'confirm_delete_product_{product.id}')
        if st.button(
                'Eliminar del inventario', key=f'delete_product_{product.id}',
                type='primary', icon=':material/delete:', disabled=not confirm_removal):
            try:
                RepositoryFactory.get_product_repository().archive_product(product)
                RepositoryFactory.get_operations_repository().audit(
                    'producto_archivado', _actor_name(), 'product', product.id,
                    f'{product.name} · baja segura; historial conservado')
                _queue_activity_notice(
                    'Producto retirado del inventario',
                    f'“{product.name}” ya no aparece en ventas ni en el catálogo. '
                    'Su historial permanece disponible para auditoría.',
                    tone='warning', icon=':material/inventory_2:')
                _reset_form('inventory_admin')
                st.rerun()
            except Exception as error:
                st.error(f'No fue posible dar de baja el producto: {error}',
                         icon=':material/error:')

def _movement_product_selector(products, prefix, only_out_of_stock=False):
    search = st.text_input(
        'Buscar producto', key=f'{prefix}_search',
        placeholder='Nombre, código de barras, categoría o proveedor',
        icon=':material/search:')
    normalized_search = search.strip().lower()
    visible = [product for product in products
               if (not only_out_of_stock or product.quantity <= 0)
               and (not normalized_search
                    or normalized_search in product.name.lower()
                    or normalized_search in (product.barcode or '').lower()
                    or normalized_search in (product.category or '').lower()
                    or normalized_search in (product.supplier or '').lower())]
    if not visible:
        st.info(
            'No hay productos que coincidan con el filtro. Cambia la búsqueda o '
            'muestra todos los productos.', icon=':material/search_off:')
        return None
    selected_name = st.selectbox(
        'Producto', [product.name for product in visible], key=f'{prefix}_product',
        help='Selecciona el artículo cuya existencia deseas modificar.')
    return next(product for product in visible if product.name == selected_name)


def _render_inventory_movements():
    _hero(
        'Entradas y mermas',
        'Registra mercancía recibida, pérdidas y correcciones con trazabilidad completa.',
        'INVENTARIO · MOVIMIENTOS')
    products = [product for product in
                RepositoryFactory.get_product_repository().get_all_products()
                if not product.is_temporary]
    if not products:
        st.warning(
            'Primero registra productos en Inventario. Después podrás recibir mercancía '
            'o documentar mermas desde aquí.', icon=':material/inventory_2:')
        if st.button('Ir a Inventario', type='primary', icon=':material/arrow_forward:'):
            _navigate_to_page('Inventario')
            st.rerun()
        return

    stock_units = sum(product.quantity for product in products)
    out_of_stock = sum(product.quantity <= 0 for product in products)
    low_stock = sum(0 < product.quantity <= (product.minimum_stock or LOW_STOCK_THRESHOLD)
                    for product in products)
    summary = st.columns(3)
    summary[0].metric('Unidades disponibles', f'{stock_units:,}')
    summary[1].metric('Productos agotados', out_of_stock)
    summary[2].metric('Por reabastecer', low_stock)

    entry_tab, loss_tab, count_tab, history_tab = st.tabs(
        ('Entradas', 'Mermas y salidas', 'Conteo físico', 'Historial'))
    entry_version = _form_version('inventory_entry')
    loss_version = _form_version('inventory_loss')
    count_version = _form_version('inventory_count')

    with entry_tab:
        st.markdown('### :material/add_box: Registrar entrada')
        st.caption(
            'Recibe una compra, una devolución o una corrección positiva. '
            'La existencia solo cambia al presionar Registrar entrada.')
        only_out = st.toggle(
            'Mostrar solamente productos agotados', value=out_of_stock > 0,
            key=f'entry_only_out_of_stock_{entry_version}')
        selected = _movement_product_selector(
            products, f'entry_{entry_version}', only_out)
        if selected is not None:
            current_cost = float(selected.cost.amount)
            with st.container(border=True):
                product_metrics = st.columns(3)
                product_metrics[0].metric('Existencia actual', f'{selected.quantity} unidades')
                product_metrics[1].metric('Costo registrado', _mxn(current_cost))
                product_metrics[2].metric(
                    'Proveedor', selected.supplier or 'Sin proveedor')

                entry_type = st.selectbox(
                    'Tipo de entrada',
                    ('Compra a proveedor', 'Devolución de cliente', 'Corrección positiva'),
                    key=f'entry_type_{entry_version}')
                quantity = st.number_input(
                    'Unidades recibidas *', min_value=1, value=1, step=1,
                    key=f'entry_quantity_{entry_version}')
                purchase_cost = None
                update_average = False
                if entry_type == 'Compra a proveedor':
                    purchase_cost = st.number_input(
                        'Costo unitario de esta compra (MXN) *', min_value=0.01,
                        value=max(0.01, current_cost), step=1.0, format='%.2f',
                        key=f'entry_unit_cost_{entry_version}')
                    cost_policy = st.segmented_control(
                        'Tratamiento del costo',
                        ('Actualizar costo promedio', 'Conservar costo registrado'),
                        default='Actualizar costo promedio',
                        key=f'entry_cost_policy_{entry_version}',
                        help='El costo promedio pondera las existencias actuales y la nueva compra.')
                    update_average = cost_policy == 'Actualizar costo promedio'
                    st.metric('Importe de la compra', _mxn(float(purchase_cost) * int(quantity)))
                resulting_stock = selected.quantity + int(quantity)
                st.info(
                    f'Existencia después del movimiento: **{resulting_stock} unidades**.',
                    icon=':material/trending_up:')
                movement_date = st.date_input(
                    'Fecha del movimiento', value=mexico_today(), max_value=mexico_today(),
                    key=f'entry_date_{entry_version}')
                reference = st.text_input(
                    'Factura, remisión o referencia',
                    key=f'entry_reference_{entry_version}',
                    placeholder='Ejemplo: FAC-1025')
                reason = st.text_area(
                    'Observaciones *', key=f'entry_reason_{entry_version}',
                    placeholder='Describe la recepción o el motivo de la corrección')
                if st.button(
                        'Registrar entrada', type='primary', icon=':material/add_box:',
                        width='stretch', key=f'submit_inventory_entry_{entry_version}'):
                    if len(reason.strip()) < 5:
                        st.error(
                            'Escribe una observación de al menos 5 caracteres.',
                            icon=':material/error:')
                    else:
                        try:
                            updated = RepositoryFactory.get_operations_repository().adjust_stock(
                                selected.id, int(quantity), entry_type,
                                f'{reason.strip()} Fecha efectiva: {movement_date}.',
                                _actor_name(), reference.strip(), unit_cost=purchase_cost,
                                update_average_cost=update_average)
                            _queue_activity_notice(
                                'Entrada registrada correctamente',
                                f'Se agregaron {int(quantity)} unidad(es) de “{selected.name}”. '
                                f'Nueva existencia: {updated.quantity} unidades.',
                                icon=':material/add_box:')
                            _reset_form('inventory_entry')
                            st.rerun()
                        except Exception as error:
                            st.error(f'No se registró la entrada: {error}',
                                     icon=':material/error:')

    with loss_tab:
        st.markdown('### :material/production_quantity_limits: Registrar merma')
        st.caption(
            'Documenta productos dañados, caducados, perdidos o utilizados internamente. '
            'Nunca se permiten existencias negativas.')
        available = [product for product in products if product.quantity > 0]
        selected = _movement_product_selector(
            available, f'loss_{loss_version}') if available else None
        if not available:
            st.info('No hay productos con existencia disponible para registrar una merma.',
                    icon=':material/info:')
        elif selected is not None:
            with st.container(border=True):
                loss_metrics = st.columns(2)
                loss_metrics[0].metric('Existencia actual', f'{selected.quantity} unidades')
                loss_metrics[1].metric(
                    'Valor al costo', _mxn(float(selected.cost.amount) * selected.quantity))
                quantity = st.number_input(
                    'Unidades a descontar *', min_value=1, max_value=selected.quantity,
                    value=1, step=1, key=f'loss_quantity_{loss_version}')
                resulting_stock = selected.quantity - int(quantity)
                st.warning(
                    f'Existencia después de la merma: **{resulting_stock} unidades**.',
                    icon=':material/trending_down:')
                loss_reason = st.selectbox(
                    'Motivo de la merma *',
                    ('Daño', 'Caducidad', 'Pérdida', 'Robo', 'Consumo interno',
                     'Devolución a proveedor', 'Error de inventario'),
                    key=f'loss_type_{loss_version}')
                movement_date = st.date_input(
                    'Fecha del movimiento', value=mexico_today(), max_value=mexico_today(),
                    key=f'loss_date_{loss_version}')
                reference = st.text_input(
                    'Referencia o evidencia', key=f'loss_reference_{loss_version}',
                    placeholder='Ejemplo: ACTA-004')
                notes = st.text_area(
                    'Explicación *', key=f'loss_notes_{loss_version}',
                    placeholder='Explica qué ocurrió y quién lo verificó')
                confirm = st.checkbox(
                    f'Confirmo el descuento de {int(quantity)} unidad(es)',
                    key=f'loss_confirm_{loss_version}')
                if st.button(
                        'Registrar merma', type='primary',
                        icon=':material/production_quantity_limits:', width='stretch',
                        disabled=not confirm,
                        key=f'submit_inventory_loss_{loss_version}'):
                    if len(notes.strip()) < 5:
                        st.error(
                            'Escribe una explicación de al menos 5 caracteres.',
                            icon=':material/error:')
                    else:
                        try:
                            updated = RepositoryFactory.get_operations_repository().adjust_stock(
                                selected.id, -int(quantity), f'Merma · {loss_reason}',
                                f'{notes.strip()} Fecha efectiva: {movement_date}.',
                                _actor_name(), reference.strip())
                            _queue_activity_notice(
                                'Merma registrada',
                                f'Se descontaron {int(quantity)} unidad(es) de '
                                f'“{selected.name}”. Nueva existencia: '
                                f'{updated.quantity} unidades.',
                                tone='warning',
                                icon=':material/production_quantity_limits:')
                            _reset_form('inventory_loss')
                            st.rerun()
                        except Exception as error:
                            st.error(f'No se registró la merma: {error}',
                                     icon=':material/error:')

    with count_tab:
        st.markdown('### :material/fact_check: Conciliar existencia')
        st.caption('Captura lo contado físicamente. El sistema registrará solamente la diferencia.')
        selected = _movement_product_selector(
            products, f'physical_count_{count_version}')
        if selected is not None:
            counted = st.number_input(
                'Unidades contadas *', min_value=0, value=int(selected.quantity), step=1,
                key=f'physical_count_quantity_{count_version}')
            difference = int(counted) - selected.quantity
            metrics = st.columns(3)
            metrics[0].metric('En sistema', selected.quantity)
            metrics[1].metric('Conteo físico', int(counted))
            metrics[2].metric('Diferencia', f'{difference:+d}')
            count_reason = st.text_area(
                'Explicación del ajuste *',
                placeholder='Conteo cíclico, inventario general o corrección verificada',
                key=f'physical_count_reason_{count_version}')
            confirm_count = st.checkbox(
                'Confirmo que realicé el conteo físico.',
                key=f'physical_count_confirm_{count_version}')
            if st.button(
                    'Conciliar existencia', type='primary', icon=':material/fact_check:',
                    width='stretch', disabled=not confirm_count or difference == 0,
                    key=f'physical_count_submit_{count_version}'):
                if len(count_reason.strip()) < 5:
                    st.error('Explica el ajuste con al menos 5 caracteres.', icon=':material/error:')
                else:
                    try:
                        previous_count = selected.quantity
                        updated = RepositoryFactory.get_operations_repository().adjust_stock(
                            selected.id, difference, 'Conteo físico', count_reason.strip(),
                            _actor_name(), f'CONTEO-{mexico_today()}')
                        _queue_activity_notice(
                            'Existencia conciliada',
                            f'“{selected.name}” pasó de {previous_count} a '
                            f'{updated.quantity} unidad(es).', icon=':material/fact_check:')
                        _reset_form('inventory_count')
                        st.rerun()
                    except Exception as error:
                        st.error(f'No se pudo conciliar: {error}', icon=':material/error:')

    with history_tab:
        st.markdown('### :material/history: Historial de movimientos')
        movements = RepositoryFactory.get_operations_repository().get_stock_movements()
        if not movements:
            st.info('El historial comenzará a llenarse con la primera entrada o merma.')
        else:
            product_names = {product.id: product.name for product in products}
            movement_types = sorted({movement.movement_type for movement in movements})
            type_filter = st.multiselect(
                'Filtrar por tipo', movement_types, key='movement_history_types')
            visible_movements = [movement for movement in movements
                                 if not type_filter or movement.movement_type in type_filter]
            st.dataframe(pd.DataFrame([{
                'Fecha y hora': movement.created_at,
                'Producto': product_names.get(
                    movement.product_id, f'Producto #{movement.product_id}'),
                'Movimiento': movement.movement_type,
                'Cambio': movement.quantity,
                'Antes': movement.previous_stock,
                'Después': movement.resulting_stock,
                'Referencia': movement.reference or '',
                'Motivo': movement.reason,
                'Responsable': movement.performed_by,
            } for movement in visible_movements]), hide_index=True, width='stretch',
                column_config={
                    'Fecha y hora': st.column_config.DatetimeColumn(format='DD/MM/YYYY HH:mm'),
                    'Cambio': st.column_config.NumberColumn(format='%+d'),
                })


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
    metrics[2].metric('Por agotarse', sum(
        p.quantity <= (p.minimum_stock or LOW_STOCK_THRESHOLD) for p in visible))
    if not visible:
        st.info('No hay productos que coincidan con la búsqueda.', icon=':material/inventory_2:')
        return
    st.dataframe(pd.DataFrame([{
        'Producto': p.name, 'Precio de venta': float(p.price.amount),
        'Disponibles': p.quantity, 'Código': p.barcode or '—',
    } for p in visible]), column_config={
        'Precio de venta': st.column_config.NumberColumn(format='$ %.2f MXN'),
        'Disponibles': st.column_config.NumberColumn(format='%d'),
    }, width='stretch', hide_index=True)
    _render_inventory_downloads(visible, 'seller', include_cost=False)
    st.caption('Solo consulta: el vendedor no puede editar costos, precios ni existencias.')


def _render_express_sale():
    _hero('Venta express', 'Cobra un artículo que todavía no existe en el catálogo.',
          'VENDEDOR · COBRO RÁPIDO')
    if not _require_open_cash_for_sale():
        return
    express_version = _form_version('express_sale')
    st.info('La venta aparecerá en reportes. Solo se agregará al inventario si lo indicas.',
            icon=':material/bolt:')

    last_ticket = st.session_state.get('express_last_ticket')
    if last_ticket:
        with st.container(border=True):
            st.subheader('Ticket de venta', icon=':material/receipt_long:')
            st.caption(
                f"Folio {last_ticket['folio']} · {last_ticket['created_at']} · "
                f"{last_ticket['payment_method']}"
            )
            ticket_summary = st.columns(3)
            ticket_summary[0].metric('Cantidad', last_ticket['quantity'])
            ticket_summary[1].metric('Precio unitario', _mxn(last_ticket['unit_price']))
            ticket_summary[2].metric('Total pagado', _mxn(last_ticket['total']))
            st.markdown(f"**{last_ticket['name']}**")
            if last_ticket['payment_details']:
                st.caption(last_ticket['payment_details'])

            ticket_rows = [{
                'Artículo': last_ticket['name'],
                'Cantidad': last_ticket['quantity'],
                'Precio unitario': last_ticket['unit_price'],
                'Importe': last_ticket['total'],
            }, {
                'Artículo': 'TOTAL', 'Cantidad': '', 'Precio unitario': '',
                'Importe': last_ticket['total'],
            }]
            ticket_subtitle = (
                f"Fecha: {last_ticket['created_at']} · "
                f"Método: {last_ticket['payment_method']} · "
                f"{last_ticket['payment_details'] or 'Sin referencia'}"
            )
            business = _business_export_data()
            thermal_items = ({
                'name': last_ticket['name'],
                'quantity': last_ticket['quantity'],
                'unit_price': last_ticket['unit_price'],
            },)
            ticket_actions = st.columns(2)
            ticket_actions[0].download_button(
                'Ticket térmico 58 mm',
                _thermal_ticket_download(
                    business, last_ticket['folio'], last_ticket['created_at'],
                    thermal_items, last_ticket['payment_method'],
                    last_ticket['payment_details'], '', 58, 'TICKET DE VENTA EXPRÉS'),
                f"ticket-express-{last_ticket['folio']}-58mm.pdf",
                'application/pdf', key='express_ticket_pdf',
                icon=':material/receipt_long:', width='stretch',
            )
            ticket_actions[1].download_button(
                'Ticket térmico 80 mm',
                _thermal_ticket_download(
                    business, last_ticket['folio'], last_ticket['created_at'],
                    thermal_items, last_ticket['payment_method'],
                    last_ticket['payment_details'], '', 80, 'TICKET DE VENTA EXPRÉS'),
                f"ticket-express-{last_ticket['folio']}-80mm.pdf",
                'application/pdf', key='express_ticket_excel',
                icon=':material/receipt_long:', width='stretch',
            )
    name = st.text_input(
        'Artículo o servicio', placeholder='Ej. Entrega especial',
        key=f'express_name_{express_version}')
    columns = st.columns(3)
    quantity = columns[0].number_input(
        'Cantidad', min_value=1, value=1, step=1,
        key=f'express_quantity_{express_version}')
    unit_price = columns[1].number_input('Precio unitario (MXN)', min_value=0.01, value=1.0,
                                         step=1.0, format='%.2f',
                                         key=f'express_price_{express_version}')
    unit_cost = columns[2].number_input('Costo unitario (MXN)', min_value=0.0, value=0.0,
                                        step=1.0, format='%.2f',
                                        key=f'express_cost_{express_version}')
    add_to_inventory = st.toggle(
        'Agregar este artículo al inventario',
        key=f'express_add_inventory_{express_version}')
    remaining_stock = st.number_input(
        'Unidades que quedarán disponibles después de esta venta', min_value=0,
        value=0, step=1, disabled=not add_to_inventory,
        key=f'express_remaining_{express_version}')
    total = int(quantity) * float(unit_price)
    st.markdown(f'<div class="pos-total"><small>TOTAL A COBRAR</small>'
                f'<strong>{_mxn(total)}</strong></div>', unsafe_allow_html=True)
    payment_method, payment_details, payment_error = _payment_controls(
        f'express_{express_version}', total)
    submitted = st.button(f'Cobrar {_mxn(total)}', type='primary', width='stretch',
                          icon=':material/bolt:', key=f'express_submit_{express_version}')
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
                f'Express · {clean_name[:35]} · {mexico_now():%Y%m%d%H%M%S%f}'
            product = Product(
                name=product_name, description='Creado desde Venta express',
                price=CUPMoney(f'{unit_price:.2f}'), cost=CUPMoney(f'{unit_cost:.2f}'),
                quantity=int(quantity) + (int(remaining_stock) if add_to_inventory else 0),
                barcode='', is_temporary=not add_to_inventory)
            RepositoryFactory.get_product_repository().insert_product(product)
            sale = Sale(product_id=product.id, price=product.price, cost=product.cost,
                        date=mexico_today(), payment_method=payment_method or 'Efectivo',
                        payment_details=payment_details)
            inserted_sales = RepositoryFactory.get_sale_repository().insert_sales(
                sale, int(quantity))
            first_sale = inserted_sales[0]
            st.session_state.express_last_ticket = {
                'folio': _sale_folio(first_sale.id),
                'created_at': mexico_now().strftime('%d/%m/%Y %H:%M'),
                'name': clean_name,
                'quantity': int(quantity),
                'unit_price': float(unit_price),
                'total': total,
                'payment_method': payment_method or 'Efectivo',
                'payment_details': payment_details or '',
            }
            message = 'Venta express registrada.'
            if add_to_inventory:
                message += f' {clean_name} quedó agregado al inventario.'
            RepositoryFactory.get_operations_repository().audit(
                'venta_express_registrada', _actor_name(), 'sale',
                first_sale.transaction_id or first_sale.id,
                f'{clean_name} · {int(quantity)} artículo(s) · {_mxn(total)} · '
                f'{payment_method or "Efectivo"}')
            _queue_activity_notice(
                'Venta express registrada',
                f'{message} Total cobrado: {_mxn(total)} mediante '
                f'{payment_method or "Efectivo"}.', icon=':material/bolt:')
            _reset_form('express_sale')
            st.rerun()
        except (UniqueProductNameException, UniqueProductBarcodeException) as error:
            st.warning(str(error), icon=':material/content_copy:')
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
        quote_item_version = _form_version('quote_item')
        options = ['Artículo libre'] + [product.name for product in products]
        source = st.selectbox(
            'Producto del inventario', options,
            key=f'quote_product_source_{quote_item_version}')
        selected = next((product for product in products if product.name == source), None)
        if selected:
            information = st.columns(4)
            information[0].metric('Precio de venta', _mxn(selected.price.amount))
            information[1].metric('Existencia', f'{selected.quantity} unidades')
            information[2].metric('Costo', _mxn(selected.cost.amount))
            information[3].metric('Código', selected.barcode or 'Sin código')
            st.info(selected.description or 'Este producto no tiene descripción.',
                    icon=':material/inventory_2:')
        else:
            st.caption('El artículo libre no está vinculado al inventario y no puede enviarse a caja.')

        form_key = (
            f"quote_add_item_{selected.id if selected else 'free'}_{quote_item_version}")
        with st.form(form_key, border=False, clear_on_submit=True, enter_to_submit=False):
            row = st.columns((2, 1, 1), vertical_alignment='bottom')
            custom_name = row[0].text_input(
                'Descripción *', value=selected.description or selected.name if selected else '',
                disabled=selected is not None, placeholder='Producto o servicio',
            )
            quantity = row[1].number_input('Cantidad', min_value=1, value=1, step=1)
            price = row[2].number_input(
                'Precio unitario (MXN)', min_value=0.01,
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
                    notice_title = 'Cantidad actualizada en la cotización'
                else:
                    st.session_state.quote_items.append({
                        'draft_id': mexico_now().strftime('%Y%m%d%H%M%S%f'),
                        'product_id': product_id, 'description': description,
                        'quantity': int(quantity), 'unit_price': float(price),
                    })
                    notice_title = 'Producto agregado a la cotización'
                _queue_activity_notice(
                    notice_title,
                    f'“{description}” quedó en el borrador. La cotización todavía '
                    'no ha sido guardada.', tone='info', icon=':material/request_quote:')
                _reset_form('quote_item')
                st.rerun()

        items = st.session_state.quote_items
        if items:
            frame = pd.DataFrame([{
                'Artículo': item['description'], 'Cantidad': item['quantity'],
                'Precio unitario': item['unit_price'],
                'Importe': item['quantity'] * item['unit_price'],
            } for item in items])
            st.dataframe(frame, column_config={
                'Precio unitario': st.column_config.NumberColumn(format='$ %.2f MXN'),
                'Importe': st.column_config.NumberColumn(format='$ %.2f MXN'),
            }, hide_index=True, width='stretch')
            st.metric('Total cotizado', _mxn(frame['Importe'].sum()))

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
                            _queue_activity_notice(
                                'Renglón de cotización actualizado',
                                f'Se guardaron los cambios de “{edited_description.strip()}” '
                                'en el borrador.', tone='info', icon=':material/edit:')
                            st.rerun()
                    if edit_columns[4].button('', icon=':material/delete:',
                                              key=f'quote_remove_{draft_id}', help='Eliminar'):
                        st.session_state.quote_items.pop(index)
                        _queue_activity_notice(
                            'Producto retirado del borrador',
                            f'Se quitó “{item["description"]}” de la cotización.',
                            tone='warning', icon=':material/delete:')
                        st.rerun()

            with st.form('save_quote_form', clear_on_submit=True, enter_to_submit=False):
                customer = st.text_input('Cliente *', placeholder='Nombre del cliente')
                notes = st.text_area('Notas', height=70)
                save_quote = st.form_submit_button(
                    'Guardar cotización', type='primary', width='stretch', icon=':material/save:')
            if st.button('Vaciar borrador', icon=':material/delete_sweep:'):
                removed_items = len(st.session_state.quote_items)
                st.session_state.quote_items = []
                _queue_activity_notice(
                    'Borrador vaciado',
                    f'Se retiraron {removed_items} renglón(es). No se eliminó ninguna '
                    'cotización previamente guardada.', tone='warning',
                    icon=':material/delete_sweep:')
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
                    RepositoryFactory.get_operations_repository().audit(
                        'cotizacion_creada', _actor_name(), 'quote', quote.id,
                        f'{clean_customer} · {len(quote.items)} renglones')
                    _queue_activity_notice(
                        'Cotización guardada',
                        f'Cotización #{quote.id} para {clean_customer} con '
                        f'{len(quote.items)} renglón(es).', icon=':material/request_quote:')
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
            with st.expander(f'#{quote.id} · {quote.customer} · {_mxn(total)} · {quote.status}',
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
                            quoted_item = next(
                                item for item in quote.items if item.product_id == product_id)
                            _set_cart_quantity(
                                product_id, current_cart.get(product_id, 0) + required_quantity,
                                float(quoted_item.unit_price.amount))
                        RepositoryFactory.get_quote_repository().update_status(quote.id, 'Aceptada')
                        RepositoryFactory.get_operations_repository().audit(
                            'cotizacion_aceptada', _actor_name(), 'quote', quote.id,
                            f'{quote.customer} · enviada a Nueva venta')
                        _queue_activity_notice(
                            'Cotización enviada a venta',
                            f'La cotización #{quote.id} fue aceptada y sus productos '
                            'quedaron cargados en el carrito.', icon=':material/shopping_cart:')
                        st.session_state['page'] = 'Nueva venta'
                        st.rerun()

                secondary_actions = st.columns(2)
                if quote.status == 'Pendiente' and secondary_actions[0].button(
                        'Marcar vencida', key=f'expire_quote_{quote.id}'):
                    RepositoryFactory.get_quote_repository().update_status(quote.id, 'Vencida')
                    RepositoryFactory.get_operations_repository().audit(
                        'cotizacion_vencida', _actor_name(), 'quote', quote.id, quote.customer)
                    _queue_activity_notice(
                        'Cotización marcada como vencida',
                        f'La cotización #{quote.id} ya no está pendiente.',
                        tone='warning', icon=':material/event_busy:')
                    st.rerun()
                if secondary_actions[1].button('Eliminar cotización', key=f'delete_quote_{quote.id}'):
                    quote_detail = f'#{quote.id} · {quote.customer}'
                    RepositoryFactory.get_quote_repository().delete_quote(quote.id)
                    RepositoryFactory.get_operations_repository().audit(
                        'cotizacion_eliminada', _actor_name(), 'quote', quote.id, quote_detail)
                    _queue_activity_notice(
                        'Cotización eliminada',
                        f'Se eliminó la cotización {quote_detail}.',
                        tone='warning', icon=':material/delete:')
                    st.rerun()

# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def _render_expenses():
    _hero('Gastos operativos', 'Registra y consulta egresos para mantener visible la rentabilidad real.', 'FINANZAS · EGRESOS')
    if not _is_administrator():
        st.error('Solo el administrador puede registrar, editar o anular gastos.',
                 icon=':material/admin_panel_settings:')
        return
    expense_version = _form_version('expense_new')
    with st.expander('Agregar gasto'):
        with st.form(f'add_expense_form_{expense_version}', enter_to_submit=False):
            name = st.text_input('Nombre', key=f'expense_new_name_{expense_version}')
            description = st.text_area(
                'Descripción', height=68, key=f'expense_new_description_{expense_version}')
            spent_money = st.number_input(
                'Dinero gastado (MXN)', min_value=0.01, step=1.0, format='%.2f',
                key=f'expense_new_amount_{expense_version}')
            detail_columns = st.columns(2)
            category = detail_columns[0].selectbox(
                'Categoría', ('Operación', 'Servicios', 'Renta', 'Nómina', 'Compra',
                              'Transporte', 'Mantenimiento', 'Impuestos', 'Otro'))
            payment_method = detail_columns[1].segmented_control(
                'Método de pago', ('Efectivo', 'Tarjeta', 'Transferencia'),
                default='Efectivo') or 'Efectivo'
            beneficiary = st.text_input('Proveedor o beneficiario')
            reference = st.text_input('Folio o referencia (opcional)')
            affects_cash = st.checkbox(
                'Descontar este gasto del efectivo de caja', value=payment_method == 'Efectivo',
                help='Actívalo solo cuando el dinero salió físicamente de la caja.')
            expense_date = st.date_input(
                'Fecha', value=mexico_today(), key=f'expense_new_date_{expense_version}')
            submitted = st.form_submit_button(
                'Guardar gasto', type='primary', icon=':material/save:', width='stretch')
        if submitted:
            try:
                expense = Expense(name=name, description=description,
                                  spent_money=CUPMoney(f'{spent_money:.2f}'), date=expense_date,
                                  payment_method=payment_method, category=category,
                                  beneficiary=beneficiary.strip(), reference=reference.strip(),
                                  affects_cash=bool(affects_cash))
                RepositoryFactory.get_expense_repository().insert_expense(expense)
                RepositoryFactory.get_operations_repository().audit(
                    'gasto_registrado', _actor_name(), 'expense', expense.id,
                    f'{name} · {_mxn(spent_money)} · {payment_method} · {category}')
                _queue_activity_notice(
                    'Gasto registrado',
                    f'“{name.strip()}” por {_mxn(spent_money)} quedó incluido en '
                    'reportes y auditoría.', icon=':material/payments:')
                _reset_form('expense_new')
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
        'Categoría': e.category, 'Método': e.payment_method,
        'Beneficiario': e.beneficiary or '', 'Referencia': e.reference or '',
        'Sale de caja': 'Sí' if e.affects_cash else 'No',
        'Gastado': float(e.spent_money.amount), 'Fecha': e.date,
    } for e in expenses]), column_config={
        'Gastado': st.column_config.NumberColumn(format='$ %.2f MXN'),
        'Fecha': st.column_config.DateColumn(format='DD/MM/YYYY'),
    }, width='stretch', hide_index=True)

    with st.expander('Administrar gastos', icon=':material/edit_note:'):
        expense_admin_version = _form_version('expense_admin')
        options = {
            f'#{expense.id} · {expense.name} · {_mxn(expense.spent_money.amount)}': expense
            for expense in expenses
        }
        selected_label = st.selectbox(
            'Selecciona un gasto', list(options), index=None,
            placeholder='Elige el gasto que deseas administrar',
            key=f'expense_admin_selection_{expense_admin_version}')
        if selected_label is None:
            st.caption('Selecciona un gasto para editarlo o anularlo.')
            return
        selected_expense = options[selected_label]
        action = st.segmented_control(
            'Acción', ('Editar', 'Anular'), default='Editar',
            key=f'expense_admin_action_{expense_admin_version}') or 'Editar'

        if action == 'Editar':
            with st.form(f'edit_expense_form_{selected_expense.id}', enter_to_submit=False):
                edited_name = st.text_input('Nombre', value=selected_expense.name)
                edited_description = st.text_area(
                    'Descripción', value=selected_expense.description or '', height=68)
                edited_amount = st.number_input(
                    'Dinero gastado (MXN)', min_value=0.01,
                    value=float(selected_expense.spent_money.amount), step=1.0, format='%.2f')
                edited_date = st.date_input('Fecha', value=selected_expense.date)
                edited_details = st.columns(2)
                expense_categories = ('Operación', 'Servicios', 'Renta', 'Nómina', 'Compra',
                                      'Transporte', 'Mantenimiento', 'Impuestos', 'Otro')
                edited_category = edited_details[0].selectbox(
                    'Categoría', expense_categories,
                    index=expense_categories.index(selected_expense.category)
                    if selected_expense.category in expense_categories else 0)
                payment_methods = ('Efectivo', 'Tarjeta', 'Transferencia')
                edited_payment = edited_details[1].selectbox(
                    'Método de pago', payment_methods,
                    index=payment_methods.index(selected_expense.payment_method)
                    if selected_expense.payment_method in payment_methods else 0)
                edited_beneficiary = st.text_input(
                    'Proveedor o beneficiario', value=selected_expense.beneficiary or '')
                edited_reference = st.text_input(
                    'Folio o referencia', value=selected_expense.reference or '')
                edited_affects_cash = st.checkbox(
                    'Descontar este gasto del efectivo de caja',
                    value=bool(selected_expense.affects_cash))
                update_submitted = st.form_submit_button(
                    'Guardar cambios', type='primary', icon=':material/save:', width='stretch')
            if update_submitted:
                old_detail = (f'{selected_expense.name} · '
                              f'{_mxn(selected_expense.spent_money.amount)} · '
                              f'{selected_expense.date}')
                try:
                    RepositoryFactory.get_expense_repository().update_expense(Expense(
                        id=selected_expense.id, name=edited_name.strip(),
                        description=edited_description.strip(),
                        spent_money=CUPMoney(f'{float(edited_amount):.2f}'),
                        date=edited_date, payment_method=edited_payment,
                        category=edited_category, beneficiary=edited_beneficiary.strip(),
                        reference=edited_reference.strip(),
                        affects_cash=bool(edited_affects_cash)))
                    RepositoryFactory.get_operations_repository().audit(
                        'gasto_editado', _actor_name(), 'expense', selected_expense.id,
                        f'Antes: {old_detail} · Ahora: {edited_name.strip()} · '
                        f'{_mxn(edited_amount)} · {edited_date}')
                    _queue_activity_notice(
                        'Gasto actualizado',
                        f'El gasto #{selected_expense.id} ahora corresponde a '
                        f'“{edited_name.strip()}” por {_mxn(edited_amount)}.',
                        icon=':material/edit_square:')
                    _reset_form('expense_admin')
                    st.rerun()
                except Exception as error:
                    st.error(str(error), icon=':material/error:')
        else:
            st.warning(
                'La anulación lo retirará de reportes activos, pero conservará la evidencia '
                'para auditoría.', icon=':material/warning:')
            confirmed = st.checkbox(
                f'Confirmo que deseo anular el gasto #{selected_expense.id}.',
                key=f'expense_delete_confirm_{selected_expense.id}')
            if st.button('Anular gasto', type='primary', icon=':material/delete:',
                         width='stretch', disabled=not confirmed,
                         key=f'expense_delete_{selected_expense.id}'):
                RepositoryFactory.get_expense_repository().archive_expenses(
                    [selected_expense.id])
                RepositoryFactory.get_operations_repository().audit(
                    'gasto_anulado', _actor_name(), 'expense', selected_expense.id,
                    f'{selected_expense.name} · {_mxn(selected_expense.spent_money.amount)} · '
                    'Archivado; se conserva evidencia.')
                _queue_activity_notice(
                    'Gasto anulado',
                    f'El gasto #{selected_expense.id} “{selected_expense.name}” fue '
                    'retirado de los registros activos; la evidencia se conserva.',
                    tone='warning', icon=':material/delete:')
                _reset_form('expense_admin')
                st.rerun()


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

def _summary_for_range(initial_date: date, final_date: date):
    """Devuelve el resumen financiero y sus registros para un intervalo inclusivo.

    Se usa cuando la página también necesita el detalle de ventas y gastos. Las
    gráficas de tendencia usan agregaciones SQL para no llamar esta función por día.
    """
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
    total_cost = acquired_money - total_profit
    total_expense = CUPMoney('0')
    for an_expense in expenses:
        total_expense += an_expense.spent_money
    return {
        'sale_quantity': len({sale.transaction_id or f'legacy-{sale.id}' for sale in sales}),
        'unit_quantity': len(sales), 'acquired_money': acquired_money,
        'total_cost': total_cost, 'total_profit': total_profit,
        'total_expense': total_expense,
        'net_profit': total_profit - total_expense, 'sales': sales, 'expenses': expenses,
    }


def _cash_close_summary(close_date: date, opening=None, closed_at=None):
    """Resume el día completo o exclusivamente el intervalo de un turno."""
    result = _summary_for_range(close_date, close_date)
    if opening is not None:
        start_at = opening.created_at

        def belongs_to_shift(record):
            created_at = getattr(record, 'created_at', None)
            if created_at is None:
                return True  # Compatibilidad con registros históricos sin hora.
            return created_at >= start_at and (closed_at is None or created_at <= closed_at)

        sales = [sale for sale in result['sales'] if belongs_to_shift(sale)]
        expenses = [expense for expense in result['expenses'] if belongs_to_shift(expense)]
        acquired_money = economy.calculate_collected_money(sales)
        total_profit = economy.calculate_total_profit(sales)
        total_expense = CUPMoney('0')
        for expense in expenses:
            total_expense += expense.spent_money
        result.update({
            'sale_quantity': len({sale.transaction_id or f'legacy-{sale.id}' for sale in sales}),
            'unit_quantity': len(sales), 'acquired_money': acquired_money,
            'total_cost': acquired_money - total_profit, 'total_profit': total_profit,
            'total_expense': total_expense, 'net_profit': total_profit - total_expense,
            'sales': sales, 'expenses': expenses,
        })
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
    denomination_counts = _cash_denomination_details(cash_close.denomination_details)
    denomination_summary = ', '.join(
        f'{label}: {denomination_counts.get(code, 0)}'
        for code, label, _ in CASH_DENOMINATIONS
        if denomination_counts.get(code, 0)
    ) or 'Conteo manual'
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
        ('Detalle de denominaciones', denomination_summary),
        ('Observaciones', cash_close.notes or 'Sin observaciones'),
    )
    money_concepts = {
        'Ventas totales', 'Ventas en efectivo', 'Ventas con tarjeta', 'Transferencias',
        'Otros métodos', 'Gastos totales', 'Gastos pagados desde caja', 'Fondo inicial',
        'Entradas adicionales', 'Retiros de efectivo', 'Efectivo esperado',
        'Efectivo contado', 'Diferencia',
    }
    return [{'Concepto': concept, 'Valor': _mxn(value) if concept in money_concepts else value}
            for concept, value in values]


def _cash_denomination_details(raw_details):
    try:
        details = json.loads(raw_details or '{}')
        return {str(key): max(0, int(value)) for key, value in details.items()}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _render_cash_denominations(key_prefix, defaults=None):
    """Captura piezas por denominación y devuelve total y detalle auditable."""
    defaults = defaults or {}
    st.caption('Denominaciones en pesos mexicanos (MXN).')
    details = {}
    total = 0.0
    denomination_columns = st.columns(3)
    for index, (code, label, denomination) in enumerate(CASH_DENOMINATIONS):
        pieces = denomination_columns[index % 3].number_input(
            label, min_value=0, value=int(defaults.get(code, 0)), step=1,
            key=f'{key_prefix}_{code}')
        details[code] = int(pieces)
        total += int(pieces) * denomination
    with st.container(border=True):
        st.caption('Total contado')
        st.markdown(f'### {_mxn(total)}')
    return total, details


def _render_cash_summary_cards(items):
    """Muestra indicadores de caja con una estructura DOM simple y estable.

    Se evita ``st.metric`` en estas vistas porque el navegador observado modifica sus
    nodos monetarios y React falla al reconciliarlos durante la navegación.
    """
    with st.container(horizontal=True, gap='small'):
        for label, value in items:
            with st.container(border=True, width='stretch'):
                st.caption(label)
                st.markdown(f'### {value}')


def _require_open_cash_for_sale():
    control_repository = RepositoryFactory.get_cash_control_repository()
    opening = control_repository.get_opening(mexico_today())
    if opening is None:
        st.warning('La caja aún no está abierta. Ve a Apertura de caja antes de registrar ventas.',
                   icon=':material/lock:')
        return False
    return True


def _render_cash_opening():
    _hero('Apertura de caja',
          'Verifica el fondo de cambio y habilita la jornada con un conteo auditable.',
          'CAJA · INICIO DE JORNADA')
    selected_date = st.date_input('Fecha de apertura', value=mexico_today(),
                                  key='cash_opening_date')
    user = st.session_state['user']
    is_admin = _is_administrator()
    control_repository = RepositoryFactory.get_cash_control_repository()
    close_repository = RepositoryFactory.get_cash_close_repository()
    opening = control_repository.get_opening(selected_date)
    openings_today = control_repository.get_openings(selected_date)
    existing_close = close_repository.get_for_opening(opening.id) if opening else None
    previous_close = close_repository.get_latest()
    result, payment_totals, _ = _cash_close_summary(selected_date, opening)
    movements = control_repository.get_movements(
        selected_date, opening.id if opening else None)
    movement_totals = control_repository.totals_for_date(
        selected_date, opening.id if opening else None)
    form_key = f'{selected_date}_turno_{len(openings_today) + 1}'

    if opening is None:
        if selected_date != mexico_today():
            st.info('No existe una apertura registrada para esta fecha.',
                    icon=':material/history:')
            return
        if not is_admin:
            st.warning('La caja está cerrada. Solicita al administrador que confirme la apertura.',
                       icon=':material/admin_panel_settings:')
            return
        suggested_amount = 0.0
        suggested_details = {}
        source_close_id = None
        if previous_close is not None:
            suggested_amount = float(previous_close.counted_cash.amount)
            suggested_details = _cash_denomination_details(
                previous_close.denomination_details)
            source_close_id = previous_close.id
            st.info(
                f'El cierre #{previous_close.id} del {previous_close.date} terminó con '
                f'{_mxn(suggested_amount)}. Se usa como propuesta; vuelve a contar el efectivo '
                'antes de confirmar la apertura.', icon=':material/sync_alt:')
        else:
            st.info('Es la primera apertura registrada. Cuenta el fondo que entregarás al vendedor.',
                    icon=':material/point_of_sale:')

        default_mode = 'Por denominaciones' if suggested_details else 'Importe manual'
        count_mode = st.segmented_control(
            'Forma de captura', ('Por denominaciones', 'Importe manual'),
            default=default_mode, key=f'opening_count_mode_{form_key}')
        if count_mode == 'Por denominaciones':
            opening_amount, denomination_details = _render_cash_denominations(
                f'opening_denomination_{form_key}', suggested_details)
        else:
            opening_amount = st.number_input(
                'Fondo inicial para cambio (MXN)', min_value=0.0, value=suggested_amount,
                step=100.0, format='%.2f', key=f'cash_opening_amount_{form_key}')
            denomination_details = {}

        if previous_close is not None:
            carry_difference = float(opening_amount) - suggested_amount
            carry_status = ('Sin diferencia' if abs(carry_difference) < .005 else
                            'Efectivo agregado' if carry_difference > 0 else
                            'Efectivo retirado')
            _render_cash_summary_cards(((
                f'Diferencia contra el cierre anterior · {carry_status}',
                _mxn(carry_difference)),))
        opening_columns = st.columns(2)
        shift_responsible = opening_columns[0].text_input(
            'Responsable del turno *', placeholder='Nombre de quien operará la caja',
            key=f'cash_shift_responsible_{form_key}')
        cash_limit = opening_columns[1].number_input(
            'Límite máximo recomendado en caja (MXN)', min_value=100.0, value=3000.0,
            step=500.0, format='%.2f', key=f'cash_opening_limit_{form_key}',
            help='Al superar este nivel, el sistema recomendará un retiro de seguridad.')
        opening_notes = st.text_input(
            'Nota de apertura', placeholder='Entrega, retiro previo o incidencia',
            key=f'cash_opening_notes_{form_key}')
        confirmed = st.checkbox(
            'Confirmo que el efectivo fue contado físicamente y entregado a caja.',
            key=f'cash_opening_confirmed_{form_key}')
        if st.button('Confirmar apertura', type='primary', icon=':material/lock_open:',
                     width='stretch', key=f'cash_opening_submit_{form_key}'):
            if not shift_responsible.strip():
                st.error('Indica el responsable del turno.', icon=':material/error:')
            elif not confirmed:
                st.error('Confirma el conteo físico antes de abrir la caja.',
                         icon=':material/error:')
            elif (previous_close is not None and abs(carry_difference) >= .005
                  and not opening_notes.strip()):
                st.error('Explica en la nota por qué la apertura difiere del cierre anterior.',
                         icon=':material/error:')
            else:
                administrator = (getattr(user, 'display_name', '')
                                 or getattr(user, 'username', '') or 'Administrador')
                try:
                    control_repository.open_day(CashOpening(
                        date=selected_date,
                        opening_amount=CUPMoney(f'{float(opening_amount):.2f}'),
                        cash_limit=CUPMoney(f'{float(cash_limit):.2f}'),
                        opened_by=administrator, notes=opening_notes.strip(),
                        shift_responsible=shift_responsible.strip(),
                        denomination_details=json.dumps(denomination_details),
                        source_close_id=source_close_id), user.role)
                    RepositoryFactory.get_operations_repository().audit(
                        'caja_abierta', administrator, 'cash_opening', selected_date,
                        f'Fondo {_mxn(opening_amount)} · cierre origen '
                        f'#{source_close_id or "ninguno"} · límite {_mxn(cash_limit)} '
                        f'· turno {shift_responsible.strip()}')
                    _queue_activity_notice(
                        f'Turno {len(openings_today) + 1} abierto correctamente',
                        f'Caja del {selected_date} iniciada con fondo de '
                        f'{_mxn(opening_amount)}, límite de {_mxn(cash_limit)} y '
                        f'responsable {shift_responsible.strip()}.',
                        icon=':material/lock_open:')
                    st.rerun()
                except Exception as error:
                    st.error(str(error), icon=':material/error:')
        return

    estimated_cash = (float(opening.opening_amount.amount) + payment_totals['Efectivo']
                      + movement_totals['Entrada'] - movement_totals['Retiro'])
    st.success(
        f'Caja abierta por {opening.opened_by} · turno de {opening.shift_responsible}.',
        icon=':material/lock_open:')
    _render_cash_summary_cards((
        ('Fondo inicial', _mxn(opening.opening_amount.amount)),
        ('Ventas en efectivo', _mxn(payment_totals['Efectivo'])),
        ('Entradas autorizadas', _mxn(movement_totals['Entrada'])),
        ('Retiros autorizados', _mxn(movement_totals['Retiro'])),
        ('Efectivo estimado', _mxn(estimated_cash)),
    ))
    source_text = (f'Cierre de origen: #{opening.source_close_id}'
                   if opening.source_close_id else 'Apertura sin cierre anterior vinculado')
    st.caption(f'{source_text} · Límite: {_mxn(opening.cash_limit.amount)} · '
               f'{opening.notes or "Sin nota"}')

    if estimated_cash > float(opening.cash_limit.amount) and existing_close is None:
        st.error(f'La caja supera el límite recomendado por '
                 f'{_mxn(estimated_cash - float(opening.cash_limit.amount))}. '
                 'Conviene realizar un retiro de seguridad.', icon=':material/security:')

    if is_admin and selected_date == mexico_today() and existing_close is None:
        movement_scope = f'cash_movement_{opening.id}'
        movement_version = _form_version(movement_scope)
        with st.expander('Registrar entrada o retiro autorizado',
                         icon=':material/currency_exchange:'):
            movement_type = st.segmented_control(
                'Tipo de movimiento', ('Retiro', 'Entrada'), default='Retiro',
                key=f'cash_movement_type_{opening.id}_{movement_version}') or 'Retiro'
            movement_columns = st.columns(2)
            movement_amount = movement_columns[0].number_input(
                'Importe (MXN)', min_value=0.01, value=100.0, step=100.0, format='%.2f',
                key=f'cash_movement_amount_{opening.id}_{movement_version}')
            options = (('Retiro de seguridad', 'Pago autorizado', 'Depósito bancario', 'Otro')
                       if movement_type == 'Retiro' else
                       ('Cambio adicional', 'Reintegro', 'Entrada autorizada', 'Otro'))
            category = movement_columns[1].selectbox(
                'Motivo', options,
                key=f'cash_movement_reason_category_{opening.id}_{movement_version}')
            detail = st.text_input(
                'Detalle obligatorio', placeholder='Explica el destino u origen del efectivo',
                key=f'cash_movement_reason_detail_{opening.id}_{movement_version}')
            if st.button('Autorizar movimiento', type='primary',
                         icon=':material/currency_exchange:', width='stretch',
                         key=f'cash_movement_submit_{opening.id}_{movement_version}'):
                if not detail.strip():
                    st.error('Escribe el detalle y destino u origen del dinero.',
                             icon=':material/error:')
                else:
                    administrator = (getattr(user, 'display_name', '')
                                     or getattr(user, 'username', '') or 'Administrador')
                    reason = f'{category}: {detail.strip()}'
                    try:
                        control_repository.add_movement(CashMovement(
                            date=selected_date, movement_type=movement_type,
                            amount=CUPMoney(f'{float(movement_amount):.2f}'),
                            reason=reason, authorized_by=administrator), user.role,
                            available_cash=max(0.0, estimated_cash))
                        RepositoryFactory.get_operations_repository().audit(
                            'movimiento_caja', administrator, 'cash_movement', selected_date,
                            f'{movement_type} {_mxn(movement_amount)} · {reason}')
                        _queue_activity_notice(
                            'Movimiento de caja registrado',
                            f'{movement_type} por {_mxn(movement_amount)}. Motivo: {reason}.',
                            tone='warning' if movement_type == 'Retiro' else 'success',
                            icon=':material/account_balance_wallet:')
                        _reset_form(movement_scope)
                        st.rerun()
                    except Exception as error:
                        st.error(str(error), icon=':material/error:')

    if movements:
        st.markdown('#### Bitácora de movimientos')
        st.dataframe(pd.DataFrame([{
            'Hora': movement.created_at.strftime('%H:%M:%S'),
            'Tipo': movement.movement_type, 'Importe': float(movement.amount.amount),
            'Motivo': movement.reason, 'Autorizó': movement.authorized_by,
        } for movement in movements]), column_config={
            'Importe': st.column_config.NumberColumn(format='$ %.2f MXN'),
        }, hide_index=True, width='stretch')


def _render_cash_close():
    _hero('Corte de caja',
          'Concilia ventas, gastos y efectivo físico con un cierre claro y auditable.',
          'CAJA · CONTROL DIARIO')
    selected_date = st.date_input('Fecha del corte', value=mexico_today(), key='cash_close_date')
    user = st.session_state['user']
    is_admin = _is_administrator()
    repository = RepositoryFactory.get_cash_close_repository()
    control_repository = RepositoryFactory.get_cash_control_repository()
    opening = control_repository.get_opening(selected_date)
    existing_close = repository.get_for_opening(opening.id) if opening else None
    result, payment_totals, operation_count = _cash_close_summary(selected_date, opening)
    total_sales = sum(payment_totals.values())
    total_expenses = float(result['total_expense'].amount)
    cash_expense_total = sum(
        float(expense.spent_money.amount) for expense in result['expenses']
        if bool(getattr(expense, 'affects_cash', False)))
    movements = control_repository.get_movements(
        selected_date, opening.id if opening else None)
    movement_totals = control_repository.totals_for_date(
        selected_date, opening.id if opening else None)

    st.markdown('#### Resumen del sistema')
    _render_cash_summary_cards((
        ('Operaciones', str(operation_count)),
        ('Ventas totales', _mxn(total_sales)),
        ('Gastos registrados', _mxn(total_expenses)),
        ('Efectivo', _mxn(payment_totals['Efectivo'])),
        ('Tarjeta', _mxn(payment_totals['Tarjeta'])),
        ('Transferencia', _mxn(payment_totals['Transferencia'])),
    ))

    st.markdown('#### Estado de la jornada')
    if opening is None:
        if False and is_admin and selected_date == mexico_today() and existing_close is None:
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
                    RepositoryFactory.get_operations_repository().audit(
                        'caja_abierta', administrator, 'cash_opening', selected_date,
                        f'Fondo {_mxn(opening_amount)} · límite {_mxn(cash_limit)}')
                    _queue_activity_notice(
                        'Caja abierta correctamente',
                        f'Jornada {selected_date} iniciada con fondo de '
                        f'{_mxn(opening_amount)} y límite de {_mxn(cash_limit)}.',
                        icon=':material/lock_open:')
                    st.rerun()
                except Exception as error:
                    st.error(str(error), icon=':material/error:')
        elif existing_close is None:
            closes_today = repository.get_for_date(selected_date)
            if closes_today and selected_date == mexico_today():
                st.success(
                    f'No hay un turno activo. Hoy se han cerrado {len(closes_today)} '
                    f'{"turno" if len(closes_today) == 1 else "turnos"}. '
                    'Puedes iniciar otro desde Apertura de caja.',
                    icon=':material/check_circle:')
            else:
                st.warning(
                    'Primero registra la Apertura de caja desde su opción independiente del menú.',
                    icon=':material/lock_open:')
    else:
        estimated_drawer_cash = (float(opening.opening_amount.amount)
                                 + payment_totals['Efectivo']
                                 + movement_totals['Entrada'] - movement_totals['Retiro'])
        _render_cash_summary_cards((
            ('Fondo inicial', _mxn(opening.opening_amount.amount)),
            ('Entradas autorizadas', _mxn(movement_totals['Entrada'])),
            ('Retiros autorizados', _mxn(movement_totals['Retiro'])),
            ('Efectivo estimado', _mxn(estimated_drawer_cash)),
        ))
        st.caption(f'Caja abierta por {opening.opened_by} · Límite recomendado: '
                   f'{_mxn(opening.cash_limit.amount)} · {opening.notes or "Sin nota"}')
        if estimated_drawer_cash > float(opening.cash_limit.amount) and existing_close is None:
            st.error(
                f'El efectivo estimado supera el límite por '
                f'{_mxn(estimated_drawer_cash - float(opening.cash_limit.amount))}. '
                'Se recomienda que el administrador realice un retiro de seguridad.',
                icon=':material/security:')

        if False and is_admin and selected_date == mexico_today() and existing_close is None:
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
                            RepositoryFactory.get_operations_repository().audit(
                                'movimiento_caja', administrator, 'cash_movement', selected_date,
                                f'{movement_type} {_mxn(movement_amount)} · {reason}')
                            _queue_activity_notice(
                                'Movimiento de caja autorizado',
                                f'{movement_type} por {_mxn(movement_amount)}. Motivo: {reason}.',
                                tone='warning' if movement_type == 'Retiro' else 'success',
                                icon=':material/account_balance_wallet:')
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
                'Importe': st.column_config.NumberColumn(format='$ %.2f MXN'),
            }, hide_index=True, width='stretch')

    if existing_close is not None:
        st.info(f'El corte de {selected_date} ya fue cerrado por {existing_close.cashier}. '
                'Se conserva bloqueado para proteger la auditoría.', icon=':material/lock:')
    elif opening is not None and selected_date == mexico_today():
        responsible = st.text_input(
            'Responsable del corte *',
            value=(opening.shift_responsible or getattr(user, 'display_name', '')
                   or getattr(user, 'username', '') or 'Vendedor'),
            disabled=not is_admin,
            key=f'cash_close_responsible_{opening.id}',
        )
        cash_expenses = st.number_input(
            'Gastos pagados desde caja (MXN)', min_value=0.0,
            value=float(cash_expense_total), step=10.0,
            format='%.2f', key=f'cash_close_expenses_{opening.id}',
            disabled=not is_admin,
            help='Se calcula con los gastos marcados como salida de efectivo. Solo administración puede corregirlo.')
        opening_cash = float(opening.opening_amount.amount)
        cash_additions = movement_totals['Entrada']
        cash_withdrawals = movement_totals['Retiro']
        expected_cash = (opening_cash + payment_totals['Efectivo']
                         + cash_additions - cash_withdrawals
                         - float(cash_expenses))

        use_denominations = st.toggle(
            'Conteo asistido por billetes y monedas', value=True,
            key=f'cash_close_use_denominations_{opening.id}')
        if use_denominations:
            counted_cash, denomination_details = _render_cash_denominations(
                f'cash_close_denomination_{opening.id}')
        else:
            counted_cash = st.number_input(
                'Efectivo contado (MXN)', min_value=0.0, value=max(0.0, expected_cash),
                step=100.0, format='%.2f', key=f'cash_close_counted_{opening.id}')
            denomination_details = {}

        difference = float(counted_cash) - expected_cash
        difference_status = ('Cuadra' if abs(difference) < .005 else
                             'Sobrante' if difference > 0 else 'Faltante')
        _render_cash_summary_cards((
            ('Efectivo esperado', _mxn(expected_cash)),
            ('Efectivo contado', _mxn(counted_cash)),
            (f'Diferencia · {difference_status}', _mxn(difference)),
        ))
        if abs(difference) < .005:
            st.success('La caja cuadra correctamente.', icon=':material/check_circle:')
        elif difference < 0:
            st.error(f'Hay un faltante de {_mxn(abs(difference))}. Revisa el conteo y los movimientos.',
                     icon=':material/error:')
        else:
            st.warning(f'Hay un sobrante de {_mxn(difference)}. Registra una observación.',
                       icon=':material/warning:')

        notes = st.text_area(
            'Observaciones', placeholder='Incidencias, retiros, depósitos o explicación de diferencias',
            key=f'cash_close_notes_{opening.id}')
        confirmed = st.checkbox(
            'Confirmo que conté el efectivo y revisé los movimientos del día.',
            key=f'cash_close_confirmed_{opening.id}')
        if st.button('Cerrar caja', type='primary', icon=':material/point_of_sale:',
                     width='stretch', key=f'cash_close_submit_{opening.id}'):
            if not responsible.strip():
                st.error('Indica el responsable del corte.', icon=':material/error:')
            elif not confirmed:
                st.error('Confirma la revisión antes de cerrar la caja.', icon=':material/error:')
            elif abs(difference) >= .005 and not notes.strip():
                st.error('Explica el sobrante o faltante en Observaciones.', icon=':material/error:')
            else:
                cash_close = CashClose(
                    date=selected_date, opening_id=opening.id,
                    cashier=responsible.strip(), operation_count=operation_count,
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
                    difference=CUPMoney(f'{difference:.2f}'), notes=notes.strip(),
                    denomination_details=json.dumps(denomination_details))
                try:
                    repository.insert(cash_close)
                    RepositoryFactory.get_operations_repository().audit(
                        'caja_cerrada', responsible.strip(), 'cash_close', cash_close.id,
                        f'Esperado {_mxn(expected_cash)} · contado {_mxn(counted_cash)} '
                        f'· diferencia {_mxn(difference)}')
                    close_tone = 'success' if abs(difference) < .005 else 'warning'
                    _queue_activity_notice(
                        'Cierre de caja guardado',
                        f'Corte #{cash_close.id} · esperado {_mxn(expected_cash)} · '
                        f'contado {_mxn(counted_cash)} · diferencia {_mxn(difference)}.',
                        tone=close_tone, icon=':material/lock:')
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
            _render_cash_summary_cards((
                ('Ventas', _mxn(cash_close.total_sales.amount)),
                ('Esperado', _mxn(cash_close.expected_cash.amount)),
                ('Contado', _mxn(cash_close.counted_cash.amount)),
                ('Diferencia', _mxn(difference)),
            ))
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
    today = mexico_today()

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
    report_primary = st.columns(3)
    report_primary[0].metric('Tickets', str(result['sale_quantity']))
    report_primary[1].metric('Ventas brutas', _mxn(result['acquired_money'].amount))
    report_primary[2].metric('Costo de mercancía vendida', _mxn(result['total_cost'].amount))
    report_secondary = st.columns(3)
    report_secondary[0].metric('Utilidad bruta', _mxn(result['total_profit'].amount))
    report_secondary[1].metric('Gastos operativos', _mxn(result['total_expense'].amount))
    report_secondary[2].metric('Utilidad neta · ganancia real', _mxn(result['net_profit'].amount))
    units_label = 'unidad vendida' if result['unit_quantity'] == 1 else 'unidades vendidas'
    operations_label = 'operación' if result['sale_quantity'] == 1 else 'operaciones'
    st.caption(
        f"{result['unit_quantity']} {units_label} en "
        f"{result['sale_quantity']} {operations_label}.")

    transaction_folios = {}
    for report_sale in result['sales']:
        transaction_key = report_sale.transaction_id or f'legacy-{report_sale.id}'
        transaction_folios[transaction_key] = min(
            transaction_folios.get(transaction_key, report_sale.id), report_sale.id)
    grouped_report_sales = {}
    for report_sale in result['sales']:
        transaction_key = report_sale.transaction_id or f'legacy-{report_sale.id}'
        product_name = (report_sale.product_name
                        or (report_sale.product.name if report_sale.product else '—'))
        row_key = (transaction_key, report_sale.product_id,
                   float(report_sale.price.amount), product_name)
        row = grouped_report_sales.setdefault(row_key, {
            'Folio': _sale_folio(transaction_folios[transaction_key]),
            'Producto': product_name, 'Cantidad': 0,
            'Precio unitario': float(report_sale.price.amount), 'Importe': 0.0,
            'Fecha': str(report_sale.date), 'Método': report_sale.payment_method or '',
            'Cliente': report_sale.customer or 'Público general',
            'Responsable': report_sale.cashier or 'Vendedor',
        })
        row['Cantidad'] += 1
        row['Importe'] += float(report_sale.price.amount)
    sales_df = pd.DataFrame(grouped_report_sales.values())
    expenses_df = pd.DataFrame([{
        'ID': e.id, 'Nombre': e.name, 'Fecha': str(e.date),
        'Gastado': float(e.spent_money.amount),
    } for e in result['expenses']])
    inventory_snapshot = RepositoryFactory.get_product_repository().get_all_products()
    low_stock = [product for product in inventory_snapshot
                 if not product.is_temporary and 0 < product.quantity <=
                 (product.minimum_stock or LOW_STOCK_THRESHOLD)]
    out_of_stock = [product for product in inventory_snapshot
                    if not product.is_temporary and product.quantity <= 0]
    low_stock_df = pd.DataFrame(_inventory_export_rows(low_stock))
    out_of_stock_df = pd.DataFrame(_inventory_export_rows(out_of_stock))

    summary_rows = [{
        'Periodo': f'{initial_date} al {final_date}',
        'Tickets': result['sale_quantity'],
        'Unidades vendidas': result['unit_quantity'],
        'Ventas brutas': float(result['acquired_money'].amount),
        'Costo de mercancía vendida': float(result['total_cost'].amount),
        'Utilidad bruta': float(result['total_profit'].amount),
        'Gastos operativos': float(result['total_expense'].amount),
        'Utilidad neta / ganancia real': float(result['net_profit'].amount),
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
        'Ventas del periodo', 'Gastos del periodo', 'Por agotarse', 'Agotados'],
        on_change='rerun')
    if tab_sales.open:
      with tab_sales:
        st.dataframe(sales_df, width='stretch', hide_index=True, column_config={
            'Folio': st.column_config.TextColumn('Folio de venta', width='small'),
            'Cantidad': st.column_config.NumberColumn('Cantidad', format='%d'),
            'Precio unitario': st.column_config.NumberColumn(format='$ %.2f MXN'),
            'Importe': st.column_config.NumberColumn(format='$ %.2f MXN'),
        })
    if tab_expenses.open:
      with tab_expenses:
        st.dataframe(expenses_df, width='stretch', hide_index=True)
    if tab_low.open:
      with tab_low:
        if low_stock_df.empty:
            st.success('No hay productos por agotarse.')
        else:
            st.warning(f'{len(low_stock_df)} producto(s) requieren reabastecimiento.')
            st.dataframe(low_stock_df, width='stretch', hide_index=True)
    if tab_out.open:
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
    """Presenta rentabilidad por día, mes o año con una tendencia agregada en SQL."""
    _hero('Estadísticas', 'Analiza ventas, utilidad y resultado real por día, mes o año.',
          'ANÁLISIS · RENTABILIDAD')
    today = mexico_today()
    period = st.segmented_control(
        'Periodo de análisis', ('Día', 'Mes', 'Año'), default='Mes',
        selection_mode='single', width='stretch', key='statistics_period') or 'Mes'

    trend_rows = []
    if period == 'Día':
        selected_day = st.date_input('Día a consultar', value=today, key='statistics_day')
        initial_date = final_date = selected_day
        period_label = selected_day.strftime('%d/%m/%Y')
    elif period == 'Mes':
        selector_columns = st.columns(2)
        selected_year = int(selector_columns[0].number_input(
            'Año', min_value=2000, max_value=2100, value=today.year,
            step=1, key='statistics_month_year'))
        selected_month = int(selector_columns[1].selectbox(
            'Mes', tuple(range(1, 13)), index=today.month - 1,
            format_func=lambda value: MONTH_NAMES[value],
            key='statistics_month'))
        initial_date = date(selected_year, selected_month, 1)
        final_date = date(selected_year, selected_month,
                          calendar.monthrange(selected_year, selected_month)[1])
        period_label = f'{MONTH_NAMES[selected_month]} {selected_year}'
        daily_trend = RepositoryFactory.get_economic_summary_repository().get_daily_trend(
            initial_date, final_date)
        for day_number in range(1, final_date.day + 1):
            current_day = date(selected_year, selected_month, day_number)
            day_result = daily_trend.get(current_day, {
                'sales': 0.0, 'cost': 0.0, 'expenses': 0.0,
                'tickets': 0, 'units': 0,
            })
            trend_rows.append({
                'Periodo': f'{day_number:02d}',
                'Ventas brutas': day_result['sales'],
                'Utilidad bruta': day_result['sales'] - day_result['cost'],
                'Utilidad neta': (day_result['sales'] - day_result['cost']
                                  - day_result['expenses']),
                'Tickets': day_result['tickets'], 'Unidades': day_result['units'],
            })
    else:
        selected_year = int(st.number_input(
            'Año a consultar', min_value=2000, max_value=2100, value=today.year,
            step=1, key='statistics_year'))
        initial_date, final_date = date(selected_year, 1, 1), date(selected_year, 12, 31)
        period_label = str(selected_year)
        daily_trend = RepositoryFactory.get_economic_summary_repository().get_daily_trend(
            initial_date, final_date)
        for month_number in range(1, 13):
            month_initial = date(selected_year, month_number, 1)
            month_final = date(selected_year, month_number,
                               calendar.monthrange(selected_year, month_number)[1])
            month_days = [values for day, values in daily_trend.items()
                          if month_initial <= day <= month_final]
            month_result = {
                key: sum(values[key] for values in month_days)
                for key in ('sales', 'cost', 'expenses', 'tickets', 'units')
            }
            trend_rows.append({
                'Periodo': MONTH_NAMES[month_number][:3],
                'Ventas brutas': month_result['sales'],
                'Utilidad bruta': month_result['sales'] - month_result['cost'],
                'Utilidad neta': (month_result['sales'] - month_result['cost']
                                  - month_result['expenses']),
                'Tickets': month_result['tickets'], 'Unidades': month_result['units'],
            })

    result = _summary_for_range(initial_date, final_date)
    gross_sales = float(result['acquired_money'].amount)
    cost_of_goods = float(result['total_cost'].amount)
    gross_profit = float(result['total_profit'].amount)
    expenses = float(result['total_expense'].amount)
    net_profit = float(result['net_profit'].amount)
    cash_difference = RepositoryFactory.get_cash_close_repository().get_difference_between(
        initial_date, final_date)

    st.caption(f'Resultados de {period_label} · {initial_date} al {final_date}')
    main_metrics = st.columns(3)
    main_metrics[0].metric('Ventas brutas', _mxn(gross_sales))
    main_metrics[1].metric('Costo de mercancía vendida', _mxn(cost_of_goods))
    main_metrics[2].metric('Utilidad bruta', _mxn(gross_profit))
    detail_metrics = st.columns(3)
    detail_metrics[0].metric('Gastos operativos', _mxn(expenses))
    detail_metrics[1].metric('Utilidad neta · ganancia real', _mxn(net_profit))
    detail_metrics[2].metric('Diferencia de caja', _mxn(cash_difference),
                             delta='Sobrante' if cash_difference > 0 else
                             'Faltante' if cash_difference < 0 else 'Caja conciliada',
                             delta_color='normal' if cash_difference >= 0 else 'inverse')
    st.caption(f'Actividad del periodo: {result["sale_quantity"]} tickets · '
               f'{result["unit_quantity"]} unidades vendidas.')

    with st.expander('Cómo se calculan las ganancias', icon=':material/calculate:'):
        st.markdown(
            '- **Ventas brutas:** total cobrado por las ventas, antes de descontar costos o gastos.\n'
            '- **Costo de mercancía vendida:** lo que costaron los productos que se vendieron.\n'
            '- **Utilidad bruta:** ventas brutas menos costo de mercancía vendida.\n'
            '- **Utilidad neta o ganancia real:** utilidad bruta menos gastos operativos.\n'
            '- **Diferencia de caja:** sobrante o faltante del arqueo; se muestra por separado '
            'porque no representa una ganancia comercial.')

    if period == 'Día':
        payment_totals = {'Efectivo': 0.0, 'Tarjeta': 0.0, 'Transferencia': 0.0, 'Otros': 0.0}
        for sale in result['sales']:
            method = (sale.payment_method or '').strip().lower()
            key = ('Efectivo' if method in ('efectivo', 'cash') else
                   'Tarjeta' if method == 'tarjeta' else
                   'Transferencia' if method == 'transferencia' else 'Otros')
            payment_totals[key] += float(sale.price.amount)
        st.subheader('Ventas por método de pago')
        st.bar_chart(pd.DataFrame({
            'Método': list(payment_totals), 'Importe (MXN)': list(payment_totals.values())
        }).set_index('Método'))
    else:
        trend_dataframe = pd.DataFrame(trend_rows).set_index('Periodo')
        st.subheader('Evolución de rentabilidad')
        st.line_chart(trend_dataframe[
            ['Ventas brutas', 'Utilidad bruta', 'Utilidad neta']])
        st.subheader('Actividad comercial')
        st.bar_chart(trend_dataframe[['Tickets', 'Unidades']])


# ---------------------------------------------------------------------------
# Estructura principal
# ---------------------------------------------------------------------------

def _render_customers():
    _hero('Clientes', 'Conserva datos básicos para atención, cotizaciones y seguimiento comercial.',
          'RELACIÓN · SERVICIO')
    operations = RepositoryFactory.get_operations_repository()
    customer_version = _form_version('customer_new')
    with st.expander('Registrar cliente', icon=':material/person_add:'):
        with st.form(f'customer_form_{customer_version}', enter_to_submit=False):
            name = st.text_input('Nombre *')
            columns = st.columns(2)
            phone = columns[0].text_input('Teléfono')
            email = columns[1].text_input('Correo electrónico')
            tax_id = st.text_input('RFC o identificación fiscal')
            notes = st.text_area('Notas')
            submitted = st.form_submit_button('Guardar cliente', type='primary')
        if submitted:
            try:
                customer = operations.add_customer(name, phone, email, tax_id, notes)
                operations.audit('cliente_creado', _actor_name(), 'customer', customer.id, customer.name)
                _queue_activity_notice(
                    'Cliente registrado',
                    f'“{customer.name}” quedó disponible para futuras ventas y '
                    'cotizaciones.', icon=':material/person_add:')
                _reset_form('customer_new')
                st.rerun()
            except Exception as error:
                st.error(str(error))
    customers = operations.get_customers()
    if not customers:
        st.info('No hay clientes registrados. Las ventas pueden continuar como Público general.')
        return
    search = st.text_input('Buscar cliente', placeholder='Nombre, teléfono, correo o RFC',
                           icon=':material/search:').strip().lower()
    visible = [customer for customer in customers if not search or search in ' '.join((
        customer.name, customer.phone or '', customer.email or '', customer.tax_id or '')).lower()]
    st.dataframe(pd.DataFrame([{
        'Nombre': customer.name, 'Teléfono': customer.phone, 'Correo': customer.email,
        'RFC': customer.tax_id, 'Notas': customer.notes,
    } for customer in visible]), hide_index=True, width='stretch')
    with st.expander('Archivar cliente'):
        customer_admin_version = _form_version('customer_admin')
        selected = st.selectbox(
            'Cliente', [customer.name for customer in customers], index=None,
            placeholder='Selecciona el cliente que deseas archivar',
            key=f'archive_customer_select_{customer_admin_version}')
        if selected is None:
            st.caption('Selecciona un cliente para continuar.')
            return
        customer = next(customer for customer in customers if customer.name == selected)
        if st.button('Archivar', key='archive_customer_button'):
            operations.archive_customer(customer.id)
            operations.audit('cliente_archivado', _actor_name(), 'customer', customer.id, customer.name)
            _queue_activity_notice(
                'Cliente archivado',
                f'“{customer.name}” fue retirado del directorio activo; sus operaciones '
                'anteriores se conservan.', tone='warning', icon=':material/person_remove:')
            _reset_form('customer_admin')
            st.rerun()


def _render_supply():
    _hero('Abastecimiento', 'Prepara una lista de compra editable y lista para entregar.',
          'COMPRAS · PLANEACIÓN')
    products = RepositoryFactory.get_product_repository().get_all_products()
    candidates = [product for product in products
                  if product.quantity <= (product.minimum_stock or LOW_STOCK_THRESHOLD)]
    if not candidates:
        st.success('No hay productos que requieran reposición.', icon=':material/check_circle:')
        return
    rows = []
    for product in candidates:
        minimum = product.minimum_stock or LOW_STOCK_THRESHOLD
        suggested = max(1, minimum * 2 - product.quantity)
        rows.append({
            'Incluir': True,
            'Producto': product.name, 'Proveedor': product.supplier or 'Sin proveedor',
            'Existencia': product.quantity, 'Mínimo': minimum,
            'Cantidad a comprar': suggested,
            'Costo unitario': float(product.cost.amount),
            'Indicaciones': '',
        })

    st.info(
        'Las cantidades son una recomendación. Puedes ajustarlas, excluir renglones y '
        'agregar instrucciones antes de descargar la lista. Esto no modifica el inventario.',
        icon=':material/edit_note:')
    editor_version = st.session_state.setdefault('supply_editor_version', 0)
    heading = st.container(horizontal=True, vertical_alignment='center')
    with heading:
        st.markdown('### Lista de compra')
        if st.button('Restablecer sugerencias', icon=':material/refresh:',
                     key='reset_supply_suggestions'):
            st.session_state.supply_editor_version += 1
            st.rerun()

    edited = st.data_editor(
        pd.DataFrame(rows), hide_index=True, width='stretch', num_rows='fixed',
        key=f'supply_editor_{editor_version}',
        disabled=('Producto', 'Existencia', 'Mínimo'),
        column_config={
            'Incluir': st.column_config.CheckboxColumn(
                'Comprar', help='Desmarca un producto para excluirlo del documento.'),
            'Producto': st.column_config.TextColumn('Producto', pinned=True),
            'Proveedor': st.column_config.TextColumn(
                'Proveedor', help='Puedes cambiarlo solamente para esta lista.'),
            'Existencia': st.column_config.NumberColumn(format='%d'),
            'Mínimo': st.column_config.NumberColumn(format='%d'),
            'Cantidad a comprar': st.column_config.NumberColumn(
                'Comprar', min_value=0, step=1, format='%d', required=True),
            'Costo unitario': st.column_config.NumberColumn(
                'Costo unitario', min_value=0.0, step=1.0,
                format='$ %.2f MXN', required=True),
            'Indicaciones': st.column_config.TextColumn(
                'Indicaciones', help='Marca, presentación, lugar de compra u otra nota.'),
        })

    selected_rows, validation_errors = [], []
    for row_number, item in enumerate(edited.to_dict('records'), start=1):
        if not bool(item.get('Incluir')):
            continue
        try:
            quantity = float(item.get('Cantidad a comprar'))
            unit_cost = float(item.get('Costo unitario'))
            if quantity < 0 or quantity != int(quantity):
                raise ValueError('la cantidad debe ser un entero de cero o más')
            if unit_cost < 0:
                raise ValueError('el costo no puede ser negativo')
            if int(quantity) == 0:
                continue
            selected_rows.append({
                'Estado': 'Pendiente',
                'Producto': str(item.get('Producto') or '').strip(),
                'Proveedor': str(item.get('Proveedor') or '').strip() or 'Sin proveedor',
                'Existencia actual': int(item.get('Existencia') or 0),
                'Existencia mínima': int(item.get('Mínimo') or 0),
                'Cantidad a comprar': int(quantity),
                'Costo unitario': unit_cost,
                'Costo estimado': int(quantity) * unit_cost,
                'Indicaciones': str(item.get('Indicaciones') or '').strip(),
            })
        except (TypeError, ValueError) as error:
            validation_errors.append(f'Renglón {row_number}: {error}.')

    total_units = sum(row['Cantidad a comprar'] for row in selected_rows)
    total_cost = sum(row['Costo estimado'] for row in selected_rows)
    metrics = st.columns(3)
    metrics[0].metric('Productos incluidos', len(selected_rows))
    metrics[1].metric('Unidades a comprar', total_units)
    metrics[2].metric('Presupuesto estimado', _mxn(total_cost))

    if validation_errors:
        st.error('Corrige la lista antes de descargarla.', icon=':material/error:')
        for error in validation_errors:
            st.caption(f'• {error}')
    elif not selected_rows:
        st.warning(
            'Selecciona al menos un producto con una cantidad mayor que cero.',
            icon=':material/shopping_cart:')

    with st.container(border=True):
        st.markdown('#### Datos para entregar la lista')
        document_columns = st.columns(2)
        assigned_to = document_columns[0].text_input(
            'Responsable de la compra', placeholder='Nombre del trabajador')
        purchase_date = document_columns[1].date_input(
            'Fecha prevista de compra', value=mexico_today(), min_value=mexico_today())
        general_notes = st.text_area(
            'Indicaciones generales',
            placeholder='Presupuesto autorizado, establecimientos sugeridos o condiciones')

    business = _business_export_data()
    assigned_name = assigned_to.strip() or 'Por asignar'
    document_summary = [{
        'Preparado por': _actor_name(),
        'Responsable de compra': assigned_name,
        'Fecha prevista': str(purchase_date),
        'Productos': len(selected_rows),
        'Unidades': total_units,
        'Presupuesto estimado': total_cost,
        'Indicaciones generales': general_notes.strip() or 'Sin indicaciones adicionales',
    }]
    sections = [('Datos de la compra', document_summary),
                ('Lista de abastecimiento', selected_rows)]
    subtitle = f'Lista preparada el {mexico_today()} · Responsable: {assigned_name}'
    downloads_disabled = bool(validation_errors) or not selected_rows
    export_columns = st.columns(2)
    export_columns[0].download_button(
        'Descargar lista PDF', generate_pdf_bytes(
            business, 'Lista de compra y abastecimiento', subtitle, sections),
        f'lista-compra-{mexico_today()}.pdf', 'application/pdf',
        icon=':material/picture_as_pdf:', width='stretch',
        disabled=downloads_disabled)
    export_columns[1].download_button(
        'Descargar lista Excel', generate_excel_bytes(
            business, 'Lista de compra y abastecimiento', subtitle, sections),
        f'lista-compra-{mexico_today()}.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        icon=':material/table_view:', width='stretch', disabled=downloads_disabled)
    st.info(
        'Cuando recibas mercancía, regístrala en Entradas y mermas para actualizar '
        'existencias, costos y Kardex.', icon=':material/info:')
    if st.button('Registrar mercancía recibida', type='primary',
                 icon=':material/add_box:', width='stretch'):
        _navigate_to_page('Movimientos')
        st.rerun()


def _render_audit():
    _hero('Auditoría', 'Rastrea ventas, anulaciones y movimientos sensibles sin borrar evidencia.',
          'CONTROL · TRAZABILIDAD')
    operations = RepositoryFactory.get_operations_repository()
    audit_logs = operations.get_audit_logs()
    stock_movements = operations.get_stock_movements()
    audit_tab, stock_tab, continuity_tab = st.tabs(
        ('Bitácora operativa', 'Kardex de inventario', 'Continuidad y respaldos'))
    with audit_tab:
        if not audit_logs:
            st.info('La bitácora comenzará a llenarse con las nuevas operaciones.')
        else:
            event_filter = st.multiselect(
                'Filtrar eventos', sorted({log.event_type for log in audit_logs}))
            visible = [log for log in audit_logs if not event_filter or log.event_type in event_filter]
            st.dataframe(pd.DataFrame([{
                'Fecha y hora': log.created_at, 'Evento': log.event_type,
                'Responsable': log.actor, 'Entidad': log.entity_type,
                'Folio': log.entity_id, 'Detalle': log.detail,
            } for log in visible]), hide_index=True, width='stretch')
    with stock_tab:
        products = {product.id: product.name for product in
                    RepositoryFactory.get_product_repository().get_all_products()}
        if not stock_movements:
            st.info('Aún no existen movimientos manuales de inventario.')
        else:
            st.dataframe(pd.DataFrame([{
                'Fecha y hora': movement.created_at,
                'Producto': products.get(movement.product_id, f'Producto #{movement.product_id}'),
                'Tipo': movement.movement_type, 'Cambio': movement.quantity,
                'Anterior': movement.previous_stock, 'Resultado': movement.resulting_stock,
                'Motivo': movement.reason, 'Referencia': movement.reference,
                'Responsable': movement.performed_by,
            } for movement in stock_movements]), hide_index=True, width='stretch')
    with continuity_tab:
        using_external_database = bool(os.environ.get('BLUE_POS_DATABASE_URL'))
        if using_external_database:
            st.success('La aplicación está conectada a una base de datos persistente externa.',
                       icon=':material/cloud_done:')
        else:
            st.warning(
                'Esta instalación usa SQLite local. Es adecuada para pruebas, pero en Streamlit Cloud '
                'los archivos pueden perderse al reiniciar el servicio.', icon=':material/cloud_alert:')
            st.markdown(
                'Configura el secreto `BLUE_POS_DATABASE_URL` con una conexión PostgreSQL administrada '
                'antes de capturar operación real.')
            try:
                backup_bytes = backup_database_bytes(RepositoryFactory.active_database_url())
                st.download_button(
                    'Descargar respaldo completo SQLite', backup_bytes,
                    f'puntos-eccos-respaldo-{mexico_today()}.db', 'application/octet-stream',
                    icon=':material/database:', width='stretch')
            except Exception as error:
                st.error(f'No fue posible preparar el respaldo: {error}')
        st.caption('Los reportes PDF y Excel son exportaciones operativas; no sustituyen un respaldo completo.')


def _render_business_profile():
    _hero('Mi perfil',
          'Personaliza cómo se presenta tu negocio en el sistema, tickets y reportes.',
          'CONFIGURACIÓN · IDENTIDAD')
    repository = RepositoryFactory.get_business_profile_repository()
    profile = repository.get_profile()

    preview, progress = st.columns((2, 1), vertical_alignment='center')
    with preview.container(border=True):
        if profile.logo_data:
            try:
                st.image(base64.b64decode(profile.logo_data), width=120)
            except (ValueError, TypeError):
                st.caption('El logotipo guardado no pudo mostrarse.')
        st.subheader(profile.business_name or 'Nombre de tu negocio')
        st.caption(profile.slogan or 'Agrega una frase que identifique tu negocio.')
        contact_preview = ' · '.join(value for value in (
            profile.phone, profile.whatsapp, profile.email) if value)
        if contact_preview:
            st.write(contact_preview)
        st.caption(profile.address or 'Agrega la ubicación del establecimiento.')

    profile_values = (
        profile.business_name, profile.owner_name, profile.phone, profile.email,
        profile.address, profile.city, profile.state, profile.tax_id,
        profile.receipt_footer,
    )
    completion = round(100 * sum(bool(value) for value in profile_values) / len(profile_values))
    progress.metric('Perfil completado', f'{completion}%')
    progress.progress(completion, text='Información que aparecerá en documentos')

    with st.form('business_profile_form', enter_to_submit=False):
        identity_tab, contact_tab, receipt_tab = st.tabs(
            ('Identidad', 'Contacto y ubicación', 'Tickets'))
        with identity_tab:
            identity_columns = st.columns(2)
            business_name = identity_columns[0].text_input(
                'Nombre comercial *', value=profile.business_name or '',
                help='Es el nombre principal que verán clientes y vendedores.')
            legal_name = identity_columns[1].text_input(
                'Razón social', value=profile.legal_name or '')
            business_type = identity_columns[0].selectbox(
                'Tipo de negocio',
                ('Comercio minorista', 'Abarrotes', 'Ropa y accesorios',
                 'Farmacia y salud', 'Restaurante o alimentos', 'Servicios',
                 'Ferretería', 'Tecnología', 'Otro'),
                index=(('Comercio minorista', 'Abarrotes', 'Ropa y accesorios',
                        'Farmacia y salud', 'Restaurante o alimentos', 'Servicios',
                        'Ferretería', 'Tecnología', 'Otro').index(profile.business_type)
                       if profile.business_type in ('Comercio minorista', 'Abarrotes',
                          'Ropa y accesorios', 'Farmacia y salud', 'Restaurante o alimentos',
                          'Servicios', 'Ferretería', 'Tecnología', 'Otro') else 8))
            owner_name = identity_columns[1].text_input(
                'Responsable o propietario', value=profile.owner_name or '')
            slogan = st.text_input(
                'Frase de marca', value=profile.slogan or '', max_chars=180,
                placeholder='Ej. Calidad y servicio cerca de ti')
            brand_color = st.color_picker(
                'Color principal de documentos', value=profile.brand_color or '#123B6D')
            logo = st.file_uploader(
                'Logotipo', type=('png', 'jpg', 'jpeg'),
                help='PNG o JPG, máximo 2 MB. Recomendado: fondo transparente y al menos 400 px.')
            remove_logo = st.checkbox(
                'Eliminar el logotipo actual', value=False, disabled=not bool(profile.logo_data))

        with contact_tab:
            contact_columns = st.columns(2)
            phone = contact_columns[0].text_input('Teléfono', value=profile.phone or '')
            whatsapp = contact_columns[1].text_input('WhatsApp', value=profile.whatsapp or '')
            email = contact_columns[0].text_input('Correo electrónico', value=profile.email or '')
            website = contact_columns[1].text_input('Sitio web', value=profile.website or '')
            address = st.text_input(
                'Calle, número y colonia', value=profile.address or '')
            location_columns = st.columns(3)
            city = location_columns[0].text_input('Municipio o ciudad', value=profile.city or '')
            state = location_columns[1].text_input('Estado', value=profile.state or '')
            postal_code = location_columns[2].text_input(
                'Código postal', value=profile.postal_code or '', max_chars=12)
            tax_columns = st.columns(2)
            tax_id = tax_columns[0].text_input(
                'RFC', value=profile.tax_id or '', max_chars=13)
            tax_regime = tax_columns[1].text_input(
                'Régimen fiscal', value=profile.tax_regime or '')

        with receipt_tab:
            st.caption(
                'El encabezado identifica al negocio en sus documentos. El agradecimiento '
                'se imprime únicamente en tickets de Nueva venta y Venta express.')
            receipt_header = st.text_area(
                'Encabezado del ticket', value=profile.receipt_header or '', height=80,
                max_chars=300, placeholder='Promoción, sucursal o mensaje destacado')
            receipt_footer = st.text_area(
                'Mensaje de agradecimiento del ticket',
                value=profile.receipt_footer or 'Gracias por su compra.', height=80,
                max_chars=500)
            return_policy = st.text_area(
                'Política de cambios o devoluciones', value=profile.return_policy or '',
                height=100, max_chars=500,
                placeholder='Ej. Cambios dentro de 15 días presentando este ticket.')

        submitted = st.form_submit_button(
            'Guardar y aplicar perfil', type='primary', icon=':material/save:',
            width='stretch')
    if submitted:
        clean_name = business_name.strip()
        clean_email = email.strip()
        if not clean_name:
            st.error('Escribe el nombre comercial del negocio.', icon=':material/error:')
            return
        if clean_email and ('@' not in clean_email or '.' not in clean_email.split('@')[-1]):
            st.error('Revisa el formato del correo electrónico.', icon=':material/error:')
            return
        logo_data = profile.logo_data or ''
        logo_mime = profile.logo_mime or ''
        if remove_logo:
            logo_data, logo_mime = '', ''
        elif logo is not None:
            try:
                logo_bytes, logo_mime = validate_image_upload(
                    logo.getvalue(), 2 * 1024 * 1024, {'PNG', 'JPEG'})
            except ValueError as error:
                st.error(str(error), icon=':material/error:')
                return
            logo_data = base64.b64encode(logo_bytes).decode('ascii')
        repository.save_profile({
            'business_name': clean_name, 'legal_name': legal_name.strip(),
            'business_type': business_type, 'slogan': slogan.strip(),
            'owner_name': owner_name.strip(), 'phone': phone.strip(),
            'whatsapp': whatsapp.strip(), 'email': clean_email,
            'website': website.strip(), 'address': address.strip(),
            'city': city.strip(), 'state': state.strip(),
            'postal_code': postal_code.strip(), 'tax_id': tax_id.strip().upper(),
            'tax_regime': tax_regime.strip(), 'receipt_header': receipt_header.strip(),
            'receipt_footer': receipt_footer.strip(), 'return_policy': return_policy.strip(),
            'brand_color': brand_color, 'logo_data': logo_data, 'logo_mime': logo_mime,
        })
        RepositoryFactory.get_operations_repository().audit(
            'perfil_actualizado', _actor_name(), 'business_profile', profile.id,
            f'{clean_name} · identidad, contacto y documentos actualizados')
        _queue_activity_notice(
            'Perfil del negocio actualizado',
            f'La identidad y los datos de “{clean_name}” ya se aplican al sistema, '
            'tickets y documentos.', icon=':material/store:')
        st.rerun()


def _public_catalog_url(slug):
    configured = os.environ.get('BLUE_POS_PUBLIC_URL', '').strip().rstrip('/')
    if configured:
        base_url = configured
    else:
        headers = st.context.headers
        host = headers.get('Host', 'localhost:8501')
        if not re.fullmatch(r'[A-Za-z0-9.-]+(?::\d+)?', host):
            host = 'localhost:8501'
        protocol = headers.get('X-Forwarded-Proto', 'http' if host.startswith('localhost') else 'https')
        base_url = f'{protocol}://{host}'
    return f'{base_url}/?catalogo={normalize_catalog_slug(slug)}'


def _catalog_whatsapp_url(number, product_name=None):
    digits = re.sub(r'\D', '', number or '')
    if not digits:
        return ''
    if len(digits) == 10:
        digits = '52' + digits
    message = ('Hola, vi su catálogo en Puntos ECCOS y quisiera más información.' if not product_name else
               f'Hola, vi “{product_name}” en su catálogo y quisiera confirmar disponibilidad.')
    return f'https://wa.me/{digits}?text={quote(message)}'


def _catalog_qr_svg(url):
    widget = QrCodeWidget(url)
    x0, y0, x1, y1 = widget.getBounds()
    size = 180
    drawing = Drawing(size, size, transform=[
        size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(widget)
    return renderSVG.drawToString(drawing)


def _render_catalog_storefront(settings, profile, products, preview=False):
    """Escaparate público de solo lectura; nunca expone costo ni stock exacto."""
    accent = profile.brand_color if re.fullmatch(r'#[0-9A-Fa-f]{6}', profile.brand_color or '') else '#123B6D'
    st.markdown(f'''<style>
      .catalog-hero {{background:linear-gradient(135deg,{accent},#08111f);color:white;
        border-radius:22px;padding:34px 38px;margin-bottom:22px;}}
      .catalog-hero h1 {{color:white!important;margin:0 0 8px;font-size:clamp(2rem,5vw,3.5rem);}}
      .catalog-hero p {{color:#edf4ff!important;font-size:1.08rem;max-width:760px;}}
      .catalog-brand {{font-weight:800;letter-spacing:.12em;font-size:.76rem;opacity:.85;}}
      [data-testid="stImage"] img {{border-radius:14px;object-fit:cover;}}
    </style>''', unsafe_allow_html=True)
    header_columns = st.columns((1, 4), vertical_alignment='center')
    with header_columns[0]:
        if profile.logo_data:
            try:
                st.image(base64.b64decode(profile.logo_data), width=110)
            except (ValueError, TypeError):
                st.markdown(':material/storefront:')
    with header_columns[1]:
        st.markdown(f'''<section class="catalog-hero">
          <div class="catalog-brand">CATÁLOGO OFICIAL</div>
          <h1>{escape(profile.business_name or 'Nuestro catálogo')}</h1>
          <p>{escape(settings.headline or profile.slogan or 'Productos seleccionados para ti.')}</p>
        </section>''', unsafe_allow_html=True)

    if settings.about:
        st.markdown(f'### Conoce nuestro negocio\n{settings.about}')
    contact = settings.whatsapp or profile.whatsapp or profile.phone
    with st.container(horizontal=True, vertical_alignment='center'):
        if contact:
            st.link_button('Hablar por WhatsApp', _catalog_whatsapp_url(contact),
                           icon=':material/chat:', type='primary')
        if profile.address:
            st.caption(f':material/location_on: {profile.address}')
        if settings.business_hours:
            st.caption(f':material/schedule: {settings.business_hours}')
    if settings.service_message:
        st.info(settings.service_message, icon=':material/local_shipping:')

    visible_products = [product for product in products
                        if settings.show_out_of_stock or product.quantity > 0]
    st.markdown('## Explora nuestros productos')
    if not visible_products:
        st.info('Estamos preparando nuestro catálogo. Vuelve pronto.', icon=':material/inventory_2:')
    else:
        controls = st.columns((2, 1))
        search = controls[0].text_input(
            'Buscar productos', placeholder='¿Qué estás buscando?',
            icon=':material/search:', key=f'catalog_search_{"preview" if preview else "public"}')
        categories = ('Todas', *sorted({product.category or 'General' for product in visible_products}))
        category = controls[1].selectbox(
            'Categoría', categories, key=f'catalog_category_{"preview" if preview else "public"}')
        normalized_search = search.strip().casefold()
        filtered = [product for product in visible_products
                    if (category == 'Todas' or (product.category or 'General') == category)
                    and (not normalized_search or normalized_search in product.name.casefold()
                         or normalized_search in (product.catalog_description or product.description or '').casefold())]
        if not filtered:
            st.warning('No encontramos productos con esos filtros.', icon=':material/search_off:')
        for row_start in range(0, len(filtered), 3):
            columns = st.columns(3)
            for column, product in zip(columns, filtered[row_start:row_start + 3]):
                with column.container(border=True, height='stretch'):
                    if product.catalog_image_data:
                        try:
                            st.image(base64.b64decode(product.catalog_image_data), width='stretch')
                        except (ValueError, TypeError):
                            st.markdown('### :material/inventory_2:')
                    else:
                        st.markdown('### :material/inventory_2:')
                        st.caption('Imagen próximamente')
                    if product.catalog_featured:
                        st.badge('Destacado', icon=':material/star:', color='blue')
                    st.markdown(f'### {escape(product.name)}')
                    st.write(product.catalog_description or product.description or 'Consulta detalles con nosotros.')
                    st.markdown(f'## {_mxn(product.price.amount)}')
                    if product.quantity <= 0:
                        st.badge('Agotado', icon=':material/block:', color='red')
                    elif product.quantity <= (product.minimum_stock or 0):
                        st.badge('Pocas unidades', icon=':material/bolt:', color='orange')
                    else:
                        st.badge('Disponible', icon=':material/check_circle:', color='green')
                    whatsapp_url = _catalog_whatsapp_url(contact, product.name)
                    if whatsapp_url and product.quantity > 0:
                        st.link_button('Consultar por WhatsApp', whatsapp_url,
                                       icon=':material/chat:', width='stretch')
    st.caption(f'© {mexico_today().year} {profile.business_name or "Negocio"} · Catálogo impulsado por Puntos ECCOS')


def _render_public_catalog(slug):
    workspace_url = RepositoryFactory.workspace_url('primary')
    RepositoryFactory.activate_workspace(workspace_url)
    schema.create_database(workspace_url)
    catalog_repository = RepositoryFactory.get_catalog_repository()
    settings = catalog_repository.get_published_by_slug(slug)
    if settings is None:
        st.error('Este catálogo no está disponible.', icon=':material/storefront:')
        st.caption('Verifica el enlace o solicita al negocio que active su catálogo.')
        return
    profile = RepositoryFactory.get_business_profile_repository().get_profile()
    _render_catalog_storefront(
        settings, profile, catalog_repository.get_catalog_products(), preview=False)


def _render_catalog_manager():
    _hero('Mi página web',
          'Convierte tu inventario en un catálogo profesional para compartir con clientes.',
          'CATÁLOGO DIGITAL · VENTA POR WHATSAPP')
    catalog_repository = RepositoryFactory.get_catalog_repository()
    profile = RepositoryFactory.get_business_profile_repository().get_profile()
    products = [product for product in RepositoryFactory.get_product_repository().get_all_products()
                if not product.is_temporary]
    settings = catalog_repository.get_settings()
    published_products = [product for product in products if product.catalog_visible]
    contact = settings.whatsapp or profile.whatsapp or profile.phone
    requirements = {
        'Identidad del negocio': bool((profile.business_name or '').strip()),
        'Descripción o eslogan': bool((settings.headline or profile.slogan or '').strip()),
        'WhatsApp o teléfono': bool((contact or '').strip()),
        'Producto publicado': bool(published_products),
    }
    completion = round(sum(requirements.values()) / len(requirements) * 100)

    status_columns = st.columns((2, 1, 1))
    status_columns[0].progress(completion / 100, text=f'Preparación del catálogo · {completion}%')
    status_columns[1].metric('Productos públicos', len(published_products))
    status_columns[2].metric('Estado', 'Publicado' if settings.is_published else 'Borrador')
    missing = [label for label, complete in requirements.items() if not complete]
    if missing:
        st.warning('Para publicar completa: ' + ', '.join(missing) + '.', icon=':material/checklist:')

    configuration_tab, products_tab, preview_tab = st.tabs(
        ('1. Configuración', '2. Productos', '3. Vista previa'))
    with configuration_tab:
        with st.form('catalog_settings_form', enter_to_submit=False):
            st.subheader('Identidad y contacto')
            slug = st.text_input(
                'Dirección de tu catálogo', value=settings.slug or 'mi-negocio',
                help='Usa letras minúsculas, números y guiones. Ejemplo: papeleria-eder.')
            headline = st.text_input(
                'Mensaje principal', value=settings.headline or profile.slogan or '',
                placeholder='Todo lo que necesitas, cerca de ti')
            about = st.text_area(
                'Acerca del negocio', value=settings.about or '', height=110,
                placeholder='Cuenta qué te hace diferente y por qué deberían elegirte.')
            whatsapp = st.text_input(
                'WhatsApp comercial', value=settings.whatsapp or profile.whatsapp or '',
                placeholder='Ejemplo: 5215551234567',
                help='Incluye lada y código de país para que el botón funcione fuera de México.')
            contact_columns = st.columns(2)
            business_hours = contact_columns[0].text_area(
                'Horarios', value=settings.business_hours or '', height=90,
                placeholder='Lun–Vie 9:00–18:00 · Sáb 9:00–14:00')
            service_message = contact_columns[1].text_area(
                'Entrega o atención', value=settings.service_message or '', height=90,
                placeholder='Recoge en tienda o consulta entregas disponibles.')
            show_out_of_stock = st.toggle(
                'Mostrar productos agotados', value=settings.show_out_of_stock,
                help='Se mostrarán como agotados, sin botón de consulta.')
            publish_requested = st.toggle(
                'Publicar catálogo', value=settings.is_published,
                help='Al activarlo, cualquier persona con el enlace podrá verlo.')
            save_settings = st.form_submit_button(
                'Guardar y aplicar', type='primary', icon=':material/publish:')
        if save_settings:
            clean_slug = normalize_catalog_slug(slug)
            can_publish = (bool((profile.business_name or '').strip()) and
                           bool((headline or profile.slogan or '').strip()) and
                           bool((whatsapp or profile.phone or '').strip()) and
                           bool([product for product in products if product.catalog_visible]))
            catalog_repository.save_settings({
                'slug': clean_slug, 'headline': headline.strip(), 'about': about.strip(),
                'whatsapp': whatsapp.strip(), 'business_hours': business_hours.strip(),
                'service_message': service_message.strip(),
                'show_out_of_stock': bool(show_out_of_stock),
                'is_published': bool(publish_requested and can_publish),
            })
            if publish_requested and not can_publish:
                _queue_activity_notice(
                    'Borrador del catálogo guardado',
                    'Los cambios se conservaron, pero el catálogo no se publicó porque '
                    'faltan requisitos indicados en esta pantalla.', tone='warning',
                    icon=':material/draft:')
            else:
                RepositoryFactory.get_operations_repository().audit(
                    'catalogo_actualizado', _actor_name(), 'catalog', '', clean_slug)
                catalog_state = 'publicado' if publish_requested else 'guardado como privado'
                _queue_activity_notice(
                    'Catálogo actualizado',
                    f'El catálogo “{clean_slug}” quedó {catalog_state}.',
                    icon=':material/language:')
            st.rerun()
        if settings.slug:
            public_url = _public_catalog_url(settings.slug)
            st.text_input('Enlace para compartir', value=public_url, disabled=True)
            if settings.is_published:
                st.link_button('Abrir página pública', public_url,
                               icon=':material/open_in_new:', type='primary')
                with st.expander('Código QR para clientes', icon=':material/qr_code_2:'):
                    qr_svg = _catalog_qr_svg(public_url)
                    qr_columns = st.columns((1, 2), vertical_alignment='center')
                    qr_columns[0].image(qr_svg, width=180)
                    with qr_columns[1]:
                        st.write('Colócalo en mostrador, tickets o redes sociales para abrir el catálogo.')
                        st.download_button(
                            'Descargar QR', qr_svg.encode('utf-8'),
                            f'qr-catalogo-{settings.slug}.svg', 'image/svg+xml',
                            icon=':material/download:')

    with products_tab:
        if not products:
            st.info('Primero agrega productos desde Inventario.', icon=':material/inventory_2:')
        else:
            st.caption('Publica solamente productos con información clara. El costo, proveedor, código y cantidad exacta nunca serán visibles.')
            editor = st.data_editor(
                pd.DataFrame([{
                    'ID': product.id, 'Publicar': bool(product.catalog_visible),
                    'Destacado': bool(product.catalog_featured), 'Producto': product.name,
                    'Descripción pública': product.catalog_description or product.description or '',
                } for product in products]),
                disabled=('ID', 'Producto'), hide_index=True, width='stretch',
                column_config={
                    'ID': st.column_config.NumberColumn(width='small'),
                    'Publicar': st.column_config.CheckboxColumn(width='small'),
                    'Destacado': st.column_config.CheckboxColumn(width='small'),
                    'Descripción pública': st.column_config.TextColumn(max_chars=500, width='large'),
                }, key='catalog_products_editor')
            if st.button('Guardar selección de productos', type='primary',
                         icon=':material/save:'):
                for row in editor.to_dict('records'):
                    catalog_repository.save_product_presentation(row['ID'], {
                        'catalog_visible': bool(row['Publicar']),
                        'catalog_featured': bool(row['Destacado']),
                        'catalog_description': str(row['Descripción pública'] or '').strip(),
                    })
                RepositoryFactory.get_operations_repository().audit(
                    'productos_catalogo_actualizados', _actor_name(), 'catalog', '',
                    f'{len(editor)} productos revisados')
                _queue_activity_notice(
                    'Productos del catálogo actualizados',
                    f'Se guardó la visibilidad y presentación de {len(editor)} producto(s).',
                    icon=':material/inventory_2:')
                st.rerun()
            with st.expander('Fotografía de producto', icon=':material/add_photo_alternate:'):
                selected_name = st.selectbox(
                    'Producto', [product.name for product in products], key='catalog_photo_product')
                selected_product = next(product for product in products if product.name == selected_name)
                if selected_product.catalog_image_data:
                    try:
                        st.image(base64.b64decode(selected_product.catalog_image_data), width=240)
                    except (ValueError, TypeError):
                        pass
                photo_scope = f'catalog_photo_{selected_product.id}'
                photo_version = _form_version(photo_scope)
                image_file = st.file_uploader(
                    'Subir fotografía', type=('png', 'jpg', 'jpeg', 'webp'),
                    key=f'catalog_photo_{selected_product.id}_{photo_version}',
                    help='Máximo 700 KB. Usa una foto cuadrada, limpia y bien iluminada.')
                image_buttons = st.columns(2)
                if image_buttons[0].button('Guardar fotografía', type='primary',
                                           disabled=image_file is None):
                    try:
                        image_bytes, image_mime = validate_image_upload(
                            image_file.getvalue(), 700 * 1024, {'PNG', 'JPEG', 'WEBP'})
                        catalog_repository.save_product_presentation(selected_product.id, {
                            'catalog_image_data': base64.b64encode(image_bytes).decode('ascii'),
                            'catalog_image_mime': image_mime,
                        })
                        RepositoryFactory.get_operations_repository().audit(
                            'foto_producto_actualizada', _actor_name(), 'product',
                            selected_product.id, selected_product.name)
                        _queue_activity_notice(
                            'Fotografía guardada',
                            f'La nueva imagen de “{selected_product.name}” ya se utiliza '
                            'en el catálogo.', icon=':material/add_photo_alternate:')
                        _reset_form(photo_scope)
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error), icon=':material/error:')
                if image_buttons[1].button('Quitar fotografía',
                                           disabled=not bool(selected_product.catalog_image_data)):
                    catalog_repository.save_product_presentation(selected_product.id, {
                        'catalog_image_data': '', 'catalog_image_mime': '',
                    })
                    RepositoryFactory.get_operations_repository().audit(
                        'foto_producto_eliminada', _actor_name(), 'product',
                        selected_product.id, selected_product.name)
                    _queue_activity_notice(
                        'Fotografía retirada',
                        f'Se eliminó la imagen de “{selected_product.name}” del catálogo.',
                        tone='warning', icon=':material/hide_image:')
                    _reset_form(photo_scope)
                    st.rerun()

    with preview_tab:
        preview_products = catalog_repository.get_catalog_products()
        if not preview_products:
            st.info('Selecciona al menos un producto para generar la vista previa.')
        else:
            st.caption('Así verán tu página los clientes. Los controles de búsqueda también funcionan aquí.')
            _render_catalog_storefront(settings, profile, preview_products, preview=True)


def _render_returns():
    _hero('Devoluciones y reembolsos',
          'Devuelve artículos completos o parciales y define su destino con trazabilidad.',
          'VENTAS · POSVENTA')
    if not _is_administrator():
        st.error('Solo administración puede autorizar una devolución.',
                 icon=':material/admin_panel_settings:')
        return
    sales = RepositoryFactory.get_sale_repository().get_all_sales()
    transactions = {}
    for sale in sales:
        transactions.setdefault(sale.transaction_id or f'legacy-{sale.id}', []).append(sale)
    transactions = {
        transaction_id: [line for line in lines if line.status == 'Completada']
        for transaction_id, lines in transactions.items()
        if any(line.status == 'Completada' for line in lines)
    }
    if not transactions:
        st.info(
            'No hay artículos vendidos pendientes de devolución. Las unidades anuladas o '
            'devueltas ya no requieren otra acción.', icon=':material/receipt_long:')
        return
    st.info(
        '**Proceso:** 1. Elige el ticket · 2. Edita cantidades y quita lo que el cliente '
        'conserva · 3. Decide si cada producto vuelve al stock o se da de baja · '
        '4. Guarda la selección y autoriza.',
        icon=':material/info:')
    labels = {}
    for transaction_id, lines in transactions.items():
        total = sum(float(line.price.amount) for line in lines)
        labels[f'Venta {_sale_folio(min(line.id for line in lines))} · '
               f'{lines[0].date} · {_mxn(total)}'] = transaction_id
    return_version = _form_version('return_transaction')
    selected_label = st.selectbox(
        '1. Ticket original', list(labels), key=f'return_ticket_{return_version}',
        help='También aparecen tickets con algunas unidades devueltas; sólo podrás elegir las pendientes.')
    selected_id = labels[selected_label]
    selected_sales = transactions[selected_id]
    original_method = selected_sales[0].payment_method or 'Efectivo'

    grouped = {}
    for sale in sorted(selected_sales, key=lambda item: item.id):
        group_key = (sale.product_id, sale.product_name, float(sale.price.amount))
        grouped.setdefault(group_key, []).append(sale)
    rows = []
    group_sale_ids = {}
    for row_number, ((product_id, product_name, unit_price), lines) in enumerate(grouped.items()):
        group_sale_ids[row_number] = [line.id for line in lines]
        rows.append({
            'Devolver': True,
            'Producto': product_name or f'Producto #{product_id}',
            'Disponibles': len(lines),
            'Cantidad': len(lines),
            'Destino': 'Reintegrar a inventario',
            'Precio unitario': unit_price,
        })
    st.caption('Desmarca **Devolver** para quitar un producto o cambia la cantidad.')
    edited = st.data_editor(
        pd.DataFrame(rows), hide_index=True, width='stretch', num_rows='fixed',
        key=f'return_items_editor_{selected_id}_{return_version}',
        disabled=('Producto', 'Disponibles', 'Precio unitario'),
        column_config={
            'Devolver': st.column_config.CheckboxColumn('Devolver', width='small'),
            'Producto': st.column_config.TextColumn('Producto', width='large'),
            'Disponibles': st.column_config.NumberColumn('Máximo', width='small'),
            'Cantidad': st.column_config.NumberColumn(
                'Cantidad', min_value=0, step=1, width='small', required=True),
            'Destino': st.column_config.SelectboxColumn(
                'Destino del producto',
                options=('Reintegrar a inventario', 'Dar de baja'), required=True,
                help='Reintegra sólo artículos aptos para volver a venderse.'),
            'Precio unitario': st.column_config.NumberColumn(
                'Precio unitario', format='$ %.2f MXN'),
        })
    st.warning(
        '**Antes de guardar:** reintegra únicamente mercancía completa y vendible. '
        'Usa **Dar de baja** para productos dañados, incompletos o no aptos; éstos no '
        'aumentarán la existencia disponible.', icon=':material/inventory:')

    editor_signature = tuple(
        (bool(row['Devolver']), str(row['Cantidad']), str(row['Destino']))
        for _, row in edited.iterrows()
    )

    if st.button('Guardar selección de devolución', type='primary',
                 icon=':material/save:', width='stretch',
                 key=f'save_return_selection_{return_version}'):
        plan = []
        errors = []
        for row_number, row in edited.iterrows():
            if not bool(row['Devolver']):
                continue
            raw_quantity = row['Cantidad']
            quantity = int(raw_quantity) if pd.notna(raw_quantity) else 0
            maximum = int(row['Disponibles'])
            if quantity != raw_quantity or quantity < 1 or quantity > maximum:
                errors.append(
                    f"{row['Producto']}: la cantidad debe ser un número entero entre 1 y {maximum}.")
                continue
            plan.append({
                'sale_ids': group_sale_ids[row_number][:quantity],
                'disposition': row['Destino'],
                'product_name': row['Producto'],
                'unit_price': float(row['Precio unitario']),
            })
        if errors:
            for error in errors:
                st.error(error, icon=':material/error:')
        elif not plan:
            st.error('Selecciona al menos un artículo para devolver.', icon=':material/checklist:')
        else:
            st.session_state['return_draft'] = {
                'transaction_id': selected_id, 'plan': plan,
                'editor_signature': editor_signature,
            }
            st.success(
                'Selección guardada. Revisa el resumen y autoriza la devolución.',
                icon=':material/task_alt:')

    draft = st.session_state.get('return_draft')
    if (not draft or draft.get('transaction_id') != selected_id
            or draft.get('editor_signature') != editor_signature):
        if draft and draft.get('transaction_id') == selected_id:
            st.warning(
                'Hay cambios pendientes. Vuelve a guardar la selección para actualizar '
                'la autorización final.', icon=':material/edit:')
        st.caption('Guarda la selección para habilitar la autorización final.')
        return
    return_plan = draft['plan']
    selected_ids = {sale_id for group in return_plan for sale_id in group['sale_ids']}
    sales_by_id = {sale.id: sale for sale in selected_sales}
    return_total = sum(float(sales_by_id[sale_id].price.amount) for sale_id in selected_ids)
    restock_count = sum(len(group['sale_ids']) for group in return_plan
                        if group['disposition'] == 'Reintegrar a inventario')
    writeoff_count = len(selected_ids) - restock_count
    _render_cash_summary_cards((
        ('Unidades a devolver', str(len(selected_ids))),
        ('Total a reembolsar', _mxn(return_total)),
        ('Regresan al stock', str(restock_count)),
        ('Se dan de baja', str(writeoff_count)),
    ))
    st.subheader('Autorización final')
    with st.form(f'return_transaction_form_{return_version}', enter_to_submit=False):
        refund_options = ('Efectivo', 'Tarjeta', 'Transferencia', 'Vale')
        suggested_refund = original_method if original_method in refund_options else 'Efectivo'
        refund_method = st.segmented_control(
            'Forma de reembolso', refund_options,
            default=suggested_refund,
            help='Por control financiero se recomienda usar el mismo método del cobro original.',
        ) or suggested_refund
        reason = st.text_area(
            'Motivo de devolución *',
            placeholder='Ejemplo: producto defectuoso confirmado por el encargado',
            help='Escribe al menos 5 caracteres; este texto quedará en la auditoría.')
        confirmed = st.checkbox(
            'Confirmo cantidades, estado físico, destino de mercancía e importe del reembolso.')
        st.caption(
            'Esta acción sólo afectará las unidades seleccionadas y conservará el resto del ticket.')
        submitted = st.form_submit_button(
            'Autorizar devolución', type='primary', icon=':material/assignment_return:',
            width='stretch')
    if submitted:
        clean_reason = reason.strip()
        if not confirmed:
            st.error(
                'Marca la confirmación del paso 3 para autorizar la devolución.',
                icon=':material/check_box:')
        elif len(clean_reason) < 5:
            st.error(
                'Escribe un motivo de devolución de al menos 5 caracteres.',
                icon=':material/edit_note:')
        else:
            try:
                returned = RepositoryFactory.get_sale_repository().return_items(
                    selected_id, return_plan, clean_reason, refund_method, _actor_name())
                amount = sum(float(sale.price.amount) for sale in returned)
                RepositoryFactory.get_operations_repository().audit(
                    'venta_devuelta', _actor_name(), 'sale', selected_id,
                    f'{len(returned)} artículos · {_mxn(amount)} · {refund_method} · '
                    f'{restock_count} a stock · {writeoff_count} de baja · {clean_reason}')
                _queue_activity_notice(
                    'Devolución registrada',
                    f'Reembolso de {_mxn(amount)} mediante {refund_method}. '
                    f'{restock_count} unidad(es) regresaron al stock y '
                    f'{writeoff_count} quedaron dadas de baja.',
                    tone='warning', icon=':material/assignment_return:')
                st.session_state.pop('return_draft', None)
                _reset_form('return_transaction')
                st.rerun()
            except Exception as error:
                st.error(
                    f'No se pudo completar la devolución: {error}',
                    icon=':material/error:')


def _navigate_to_page(target):
    """Callback de navegación; se ejecuta antes de crear el widget del menú."""
    st.session_state['page'] = target


def _sidebar_nav_button(page_name, label, icon, key):
    """Navegación compacta con estado activo visible y sin una lista de radios."""
    st.button(
        label, icon=icon, key=key, width='stretch',
        type='primary' if st.session_state.get('page') == page_name else 'secondary',
        on_click=_navigate_to_page, args=(page_name,))


def _render_sidebar_navigation(is_admin):
    if is_admin:
        primary_groups = (
            ('Operación diaria', (
                ('Tablero', 'Tablero', ':material/dashboard:'),
                ('Ventas', 'Nueva venta', ':material/point_of_sale:'),
                ('Inventario', 'Inventario', ':material/inventory_2:'),
                ('Movimientos', 'Entradas y mermas', ':material/sync_alt:'),
            )),
            ('Caja', (
                ('Apertura de caja', 'Apertura de caja', ':material/lock_open:'),
                ('Corte de caja', 'Cierre de caja', ':material/lock:'),
            )),
        )
        secondary_groups = (
            ('Gestión del negocio', ':material/store:', (
                ('Gastos', 'Gastos', ':material/payments:'),
                ('Devoluciones', 'Devoluciones', ':material/assignment_return:'),
                ('Clientes', 'Clientes', ':material/groups:'),
                ('Abastecimiento', 'Abastecimiento', ':material/local_shipping:'),
                ('Auditoría', 'Actividad y auditoría', ':material/history:'),
            )),
            ('Análisis y crecimiento', ':material/monitoring:', (
                ('Reportes', 'Reportes', ':material/description:'),
                ('Estadísticas', 'Estadísticas', ':material/query_stats:'),
                ('Mi página web', 'Catálogo web', ':material/language:'),
            )),
        )
    else:
        primary_groups = (
            ('Ventas', (
                ('Nueva venta', 'Nueva venta', ':material/point_of_sale:'),
                ('Cotizaciones', 'Cotizaciones', ':material/request_quote:'),
                ('Inventario', 'Consultar inventario', ':material/inventory_2:'),
                ('Venta express', 'Venta express', ':material/bolt:'),
            )),
            ('Caja', (
                ('Apertura de caja', 'Apertura de caja', ':material/lock_open:'),
                ('Corte de caja', 'Cierre de caja', ':material/lock:'),
            )),
        )
        secondary_groups = ()

    for group_index, (group_label, items) in enumerate(primary_groups):
        st.markdown(f'<div class="sidebar-section-label">{group_label}</div>',
                    unsafe_allow_html=True)
        for page_name, label, icon in items:
            _sidebar_nav_button(
                page_name, label, icon,
                f'nav_primary_{group_index}_{page_name.lower().replace(" ", "_")}')

    current_page = st.session_state.get('page')
    for group_index, (group_label, group_icon, items) in enumerate(secondary_groups):
        with st.expander(
                group_label, icon=group_icon,
                expanded=current_page in {item[0] for item in items}):
            for page_name, label, icon in items:
                _sidebar_nav_button(
                    page_name, label, icon,
                    f'nav_secondary_{group_index}_{page_name.lower().replace(" ", "_")}')


def _render_help_assistant():
    """Ayuda operativa local: no consulta APIs ni modifica información."""
    _hero('Asistente ECCOS',
          'Resuelve dudas del punto de venta con instrucciones claras y seguras.',
          'AYUDA DEL SISTEMA · SIN COSTO')
    role = 'admin' if _is_administrator() else 'seller'
    topics = topics_for_role(role)
    state_key = f'assistant_messages_{role}'
    st.session_state.setdefault(state_key, [])

    with st.container(border=True):
        st.markdown('#### ¿En qué necesitas ayuda?')
        category = st.selectbox(
            'Tema', ('Todos', *sorted({topic.category for topic in topics})),
            key=f'assistant_category_{role}')
        visible_topics = topics if category == 'Todos' else tuple(
            topic for topic in topics if topic.category == category)
        selected_question = st.selectbox(
            'Preguntas frecuentes',
            ('Selecciona una pregunta…', *(topic.question for topic in visible_topics)),
            key=f'assistant_question_{role}')
        if st.button('Ver solución', type='primary', icon=':material/help:',
                     disabled=selected_question.startswith('Selecciona')):
            selected_topic = next(
                topic for topic in visible_topics if topic.question == selected_question)
            st.session_state[state_key].extend((
                {'role': 'user', 'content': selected_topic.question},
                {'role': 'assistant', 'content': selected_topic.answer,
                 'page': selected_topic.page},
            ))
            st.rerun()

    if not st.session_state[state_key]:
        st.info('Selecciona una pregunta o escribe tu duda. El asistente funciona sin internet y no comparte los datos de tu negocio.')

    for index, message in enumerate(st.session_state[state_key]):
        avatar = ':material/support_agent:' if message['role'] == 'assistant' else ':material/person:'
        with st.chat_message(message['role'], avatar=avatar):
            st.markdown(message['content'])
            target = message.get('page')
            available_pages = ADMIN_PAGES if _is_administrator() else SELLER_PAGES
            if _is_administrator() and target == 'Nueva venta':
                target = 'Ventas'
            if target in available_pages:
                st.button(f'Ir a {target}', key=f'assistant_go_{role}_{index}',
                          icon=':material/arrow_forward:',
                          on_click=_navigate_to_page, args=(target,))

    if prompt := st.chat_input('Escribe una duda sobre Puntos ECCOS…',
                               key=f'assistant_input_{role}'):
        topic = find_answer(prompt, role)
        if topic is None:
            answer = ('No encontré una solución suficientemente segura para esa pregunta. '
                      'Prueba con otras palabras o selecciona una pregunta frecuente. '
                      'Este asistente evita inventar procedimientos que podrían afectar tu operación.')
            target = None
        else:
            answer, target = topic.answer, topic.page
        st.session_state[state_key].extend((
            {'role': 'user', 'content': prompt},
            {'role': 'assistant', 'content': answer, 'page': target},
        ))
        st.rerun()

    if st.session_state[state_key] and st.button(
            'Limpiar conversación', icon=':material/delete_sweep:'):
        st.session_state[state_key] = []
        st.rerun()


ADMIN_PAGES = {
    'Tablero': _render_dashboard, 'Ventas': _render_sales, 'Inventario': _render_inventory,
    'Movimientos': _render_inventory_movements,
    'Apertura de caja': _render_cash_opening, 'Corte de caja': _render_cash_close,
    'Gastos': _render_expenses, 'Devoluciones': _render_returns,
    'Clientes': _render_customers, 'Abastecimiento': _render_supply, 'Auditoría': _render_audit,
    'Reportes': _render_reports, 'Estadísticas': _render_statistics,
    'Mi perfil': _render_business_profile, 'Mi página web': _render_catalog_manager,
    'Asistente ECCOS': _render_help_assistant,
}
SELLER_PAGES = {
    'Nueva venta': _render_sales,
    'Cotizaciones': _render_quotes,
    'Inventario': _render_inventory_readonly,
    'Venta express': _render_express_sale,
    'Apertura de caja': _render_cash_opening,
    'Corte de caja': _render_cash_close,
    'Asistente ECCOS': _render_help_assistant,
}


def _render_app():
    """Construye la sesión autenticada y ejecuta solamente la página seleccionada.

    La autorización del repositorio permanece activa durante el render. Esto protege
    operaciones sensibles incluso si en el futuro un botón se muestra por error.
    """
    user = st.session_state['user']
    if st.session_state.get('_workspace_schema_version') != WORKSPACE_SCHEMA_VERSION:
        schema.activate_user_workspace(user)
        st.session_state['_workspace_schema_ready'] = True
        st.session_state['_workspace_schema_version'] = WORKSPACE_SCHEMA_VERSION
    pages = ADMIN_PAGES if _is_administrator() else SELLER_PAGES
    business_profile = RepositoryFactory.get_business_profile_repository().get_profile()
    brand_color = (business_profile.brand_color or '#123B6D')
    st.markdown(
        f'<style>:root{{--primary:{brand_color};}}'
        f'[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked)'
        f'{{border-left-color:{brand_color} !important;}}'
        f'button[kind="primary"]{{background:{brand_color} !important;}}</style>',
        unsafe_allow_html=True)
    if st.session_state.get('page') not in pages:
        st.session_state['page'] = next(iter(pages))

    with st.sidebar:
        if business_profile.logo_data:
            try:
                st.image(base64.b64decode(business_profile.logo_data), width=110)
            except (ValueError, TypeError):
                pass
        st.title(business_profile.business_name or 'Puntos ECCOS')
        st.caption(business_profile.slogan or 'Puntos ECCOS · Tecnología tabasqueña de Grupo ECCOS')
        display_name = getattr(user, 'display_name', '') or user.role.title()
        role_label = 'Administrador' if _is_administrator() else 'Vendedor'
        st.markdown(
            f'<div class="sidebar-user-card">'
            f'<div class="sidebar-user-name">{escape(display_name)}</div>'
            f'<div class="sidebar-user-role">Sesión activa · {role_label}</div>'
            f'</div>', unsafe_allow_html=True)

        utility_columns = st.columns(2, gap='small')
        if _is_administrator():
            utility_columns[0].button(
                'Mi perfil', icon=':material/account_circle:', width='stretch',
                type='primary' if st.session_state.get('page') == 'Mi perfil' else 'secondary',
                key='sidebar_utility_profile', on_click=_navigate_to_page,
                args=('Mi perfil',))
        else:
            utility_columns[0].button(
                'Mi jornada', icon=':material/badge:', width='stretch', disabled=True,
                key='sidebar_utility_shift')
        utility_columns[1].button(
            'Ayuda', icon=':material/support_agent:', width='stretch',
            type='primary' if st.session_state.get('page') == 'Asistente ECCOS' else 'secondary',
            key='sidebar_utility_help', on_click=_navigate_to_page,
            args=('Asistente ECCOS',))

        _render_sidebar_navigation(_is_administrator())

        st.space('small')
        if st.button('Cerrar sesión', icon=':material/logout:', width='stretch'):
            _log_out()
        st.markdown(
            f'<div class="sidebar-legal">© {mexico_today().year} Grupo ECCOS<br>'
            'Creado y desarrollado en Tabasco, México<br>'
            'Con apoyo tecnológico de Codex<br>Software propietario</div>',
            unsafe_allow_html=True,
        )

    _render_activity_notice()
    with authorization_context(getattr(user, 'role', '')):
        pages[st.session_state['page']]()


def main():
    """Punto de entrada de cada rerun: catálogo, acceso o aplicación autenticada."""
    catalog_slug = st.query_params.get('catalogo')
    if catalog_slug:
        _render_public_catalog(catalog_slug)
        return
    _bootstrap_auth()
    # Elimina enlaces antiguos con token sin intentar autenticarlos.
    st.query_params.pop('session', None)
    if 'user' not in st.session_state:
        _render_login()
    else:
        _render_app()


main()
