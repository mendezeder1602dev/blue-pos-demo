"""Exportaciones en memoria para la aplicación web."""

import base64
from io import BytesIO
from html import escape
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as ReportImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from model.color_safety import normalize_hex_color, readable_text_color


BRAND_BLUE = colors.HexColor('#123B6D')
BRAND_NAVY = colors.HexColor('#08111F')
LIGHT_GRAY = colors.HexColor('#E9EDF2')


def business_as_dict(profile) -> dict:
    fields = (
        'business_name', 'legal_name', 'business_type', 'slogan', 'owner_name',
        'phone', 'whatsapp', 'email', 'address', 'city', 'state', 'postal_code',
        'tax_id', 'tax_regime', 'website', 'receipt_header', 'receipt_footer',
        'return_policy', 'brand_color', 'app_background_color', 'app_surface_color',
        'app_text_color', 'document_primary_color', 'document_text_color',
        'logo_data', 'logo_mime',
    )
    return {field: getattr(profile, field, '') or '' for field in fields}


def _business_lines(business: dict) -> list[str]:
    contact = ' · '.join(value for value in (
        business.get('phone'), business.get('whatsapp'), business.get('email')) if value)
    location = ', '.join(value for value in (
        business.get('city'), business.get('state'), business.get('postal_code')) if value)
    return [value for value in (
        business.get('business_name') or 'Mi negocio', business.get('legal_name'),
        business.get('slogan'), business.get('receipt_header'), business.get('address'),
        location, contact,
        f"RFC: {business['tax_id']}" if business.get('tax_id') else '',
        business.get('tax_regime'),
        business.get('website'),
    ) if value]


def generate_pdf_bytes(business: dict, title: str, subtitle: str,
                       sections: Iterable[tuple[str, list[dict]]]) -> bytes:
    brand = normalize_hex_color(
        business.get('document_primary_color') or business.get('brand_color') or '#123B6D')
    header_text = readable_text_color(brand)
    document_text = normalize_hex_color(business.get('document_text_color') or '#111820')
    brand_blue = colors.HexColor(brand)
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=16 * mm,
                                 rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    centered = ParagraphStyle('Centered', parent=styles['Normal'], alignment=TA_CENTER,
                              textColor=colors.HexColor(document_text), leading=14)
    story = []
    business_lines = _business_lines(business)
    if business.get('logo_data'):
        try:
            story.append(ReportImage(
                BytesIO(base64.b64decode(business['logo_data'])),
                width=32 * mm, height=18 * mm, hAlign='CENTER'))
            story.append(Spacer(1, 4))
        except (ValueError, TypeError):
            pass
    story.append(Paragraph(f'<b>{business_lines[0]}</b>', styles['Title']))
    if len(business_lines) > 1:
        story.append(Paragraph('<br/>'.join(business_lines[1:]), centered))
    story.extend((Spacer(1, 8), Paragraph(f'<b>{title}</b>', styles['Heading1']),
                  Paragraph(subtitle, styles['Normal']),
                  Paragraph('Moneda: peso mexicano (MXN)', styles['Normal']),
                  Spacer(1, 10)))

    for section_title, rows in sections:
        story.append(Paragraph(f'<b>{section_title}</b>', styles['Heading2']))
        if not rows:
            story.append(Paragraph('Sin registros.', styles['Normal']))
            story.append(Spacer(1, 8))
            continue
        headers = list(rows[0].keys())
        cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontSize=7,
                                    leading=9, wordWrap='CJK')
        values = [[Paragraph(f'<b>{escape(str(header))}</b>', cell_style)
                   for header in headers]]
        values.extend([
            [Paragraph(escape(str(row.get(header, ''))), cell_style) for header in headers]
            for row in rows
        ])
        available_width = A4[0] - 32 * mm
        table = Table(values, repeatRows=1, hAlign='LEFT',
                      colWidths=[available_width / len(headers)] * len(headers))
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), brand_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(header_text)),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#B8C1CC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), (colors.white, LIGHT_GRAY)),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.extend((table, Spacer(1, 10)))
    # El agradecimiento pertenece al comprobante entregado al cliente. Los PDF
    # administrativos conservan identidad y políticas, pero no texto comercial.
    if business.get('return_policy'):
        story.append(Paragraph(f"Política: {escape(business['return_policy'])}", centered))
    document.build(story)
    return output.getvalue()


def generate_excel_bytes(business: dict, title: str, subtitle: str,
                         sections: Iterable[tuple[str, list[dict]]]) -> bytes:
    brand = normalize_hex_color(
        business.get('document_primary_color') or business.get('brand_color') or '#123B6D')
    brand_hex = brand.lstrip('#')
    header_text_hex = readable_text_color(brand).lstrip('#')
    document_text_hex = normalize_hex_color(business.get('document_text_color') or '#111820').lstrip('#')
    workbook = Workbook()
    information = workbook.active
    information.title = 'Información'
    information.append([business.get('business_name') or 'Mi negocio'])
    information.append([title])
    information.append([subtitle])
    information.append(['Moneda: peso mexicano (MXN)'])
    # El agradecimiento se reserva para tickets de venta y venta express.
    if business.get('return_policy'):
        information.append([f"Política: {business['return_policy']}"])
    for line in _business_lines(business)[1:]:
        information.append([line])
    information['A1'].font = Font(bold=True, size=16, color=brand_hex)
    information['A2'].font = Font(bold=True, size=13, color=document_text_hex)
    information.column_dimensions['A'].width = 70

    used_names = {'Información'}
    for section_title, rows in sections:
        base_name = section_title[:31] or 'Datos'
        sheet_name = base_name
        suffix = 2
        while sheet_name in used_names:
            sheet_name = f'{base_name[:27]} {suffix}'
            suffix += 1
        used_names.add(sheet_name)
        sheet = workbook.create_sheet(sheet_name)
        if not rows:
            sheet.append(['Sin registros'])
            continue
        headers = list(rows[0].keys())
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color=header_text_hex)
            cell.fill = PatternFill('solid', fgColor=brand_hex)
            cell.alignment = Alignment(horizontal='center')
        for row in rows:
            sheet.append([row.get(header, '') for header in headers])
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for column_cells in sheet.columns:
            width = min(45, max(len(str(cell.value or '')) for cell in column_cells) + 2)
            sheet.column_dimensions[column_cells[0].column_letter].width = width

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _html_table(section_title: str, rows: list[dict]) -> str:
    if not rows:
        return (
            f'<section class="report-section"><h2>{escape(section_title)}</h2>'
            '<p class="empty">Sin registros.</p></section>'
        )
    headers = list(rows[0].keys())
    header_html = ''.join(f'<th>{escape(str(header))}</th>' for header in headers)
    body_html = ''.join(
        '<tr>' + ''.join(
            f'<td>{escape(str(row.get(header, "")))}</td>' for header in headers
        ) + '</tr>'
        for row in rows
    )
    return (
        f'<section class="report-section"><h2>{escape(section_title)}</h2>'
        '<div class="table-wrap"><table>'
        f'<thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody>'
        '</table></div></section>'
    )


def generate_html_bytes(business: dict, title: str, subtitle: str,
                        sections: Iterable[tuple[str, list[dict]]]) -> bytes:
    """Genera un reporte HTML autosuficiente, legible en navegador y correo."""
    brand = escape(normalize_hex_color(
        business.get('document_primary_color') or business.get('brand_color') or '#123B6D'))
    on_brand = escape(readable_text_color(brand))
    document_text = escape(normalize_hex_color(business.get('document_text_color') or '#111820'))
    business_lines = _business_lines(business)
    details = ''.join(f'<p>{escape(line)}</p>' for line in business_lines[1:])
    logo = ''
    if business.get('logo_data'):
        logo_mime = escape(business.get('logo_mime') or 'image/png')
        logo_data = escape(business['logo_data'])
        logo = f'<img class="logo" src="data:{logo_mime};base64,{logo_data}" alt="Logo">'
    sections_html = ''.join(_html_table(section_title, rows)
                            for section_title, rows in sections)
    policy = (
        f'<p class="policy">Política: {escape(business["return_policy"])}</p>'
        if business.get('return_policy') else ''
    )
    html = f'''<!doctype html>
<html lang="es-MX">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ --brand: {brand}; --on-brand: {on_brand}; --ink: {document_text}; --muted: #5F6873; --line: #D8DDE4; }}
    body {{ margin: 0; background: #F1F3F6; color: var(--ink);
      font-family: Arial, Helvetica, sans-serif; }}
    main {{ max-width: 1120px; margin: 24px auto; padding: 0 18px 40px; }}
    .cover {{ background: #fff; border: 1px solid var(--line); border-radius: 18px;
      padding: 24px; box-shadow: 0 10px 28px rgba(7, 23, 42, .07); }}
    .brand {{ display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }}
    .logo {{ max-width: 140px; max-height: 72px; object-fit: contain; }}
    h1 {{ margin: 0; color: var(--brand); font-size: 1.8rem; }}
    h2 {{ margin: 28px 0 10px; color: var(--brand); }}
    p {{ margin: 4px 0; color: var(--muted); }}
    .subtitle {{ color: var(--ink); font-weight: 700; }}
    .report-section {{ background: #fff; border: 1px solid var(--line); border-radius: 16px;
      margin-top: 16px; padding: 18px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; min-width: 680px; }}
    th {{ background: var(--brand); color: var(--on-brand); text-align: left; }}
    th, td {{ border: 1px solid var(--line); padding: 8px 10px; font-size: .9rem; }}
    tr:nth-child(even) td {{ background: #F7F9FC; }}
    .empty, .policy {{ padding: 10px 0; }}
    @media print {{ body {{ background: #fff; }} main {{ margin: 0; max-width: none; }} }}
  </style>
</head>
<body>
  <main>
    <section class="cover">
      <div class="brand">{logo}<div>
        <h1>{escape(business_lines[0])}</h1>{details}
      </div></div>
      <p class="subtitle">{escape(title)}</p>
      <p>{escape(subtitle)}</p>
      <p>Moneda: peso mexicano (MXN)</p>
      {policy}
    </section>
    {sections_html}
  </main>
</body>
</html>'''
    return html.encode('utf-8')
