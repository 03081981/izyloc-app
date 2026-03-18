from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                  TableStyle, Image, HRFlowable, PageBreak)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas as rl_canvas
from PIL import Image as PILImage
import io
import os
import base64
from datetime import datetime

# Cores izyLAUDO — Azul e Preto
PRIMARY = colors.HexColor('#1565E8')      # Azul principal
SECONDARY = colors.HexColor('#0D4FC4')    # Azul escuro
ACCENT = colors.HexColor('#3B82F6')       # Azul médio
LIGHT_GREEN = colors.HexColor('#EBF1FD')  # Azul bem claro (bg)
DARK_TEXT = colors.HexColor('#0A0A0A')    # Preto
GRAY = colors.HexColor('#6B7280')         # Cinza
LIGHT_GRAY = colors.HexColor('#F5F6FA')   # Cinza claro bg
WHITE = colors.white
RED_BAD = colors.HexColor('#DC2626')
ORANGE = colors.HexColor('#D97706')
YELLOW_OK = colors.HexColor('#16A34A')

CONDITION_COLORS = {
    'ótimo': colors.HexColor('#059669'),
    'bom': colors.HexColor('#10B981'),
    'regular': colors.HexColor('#D97706'),
    'ruim': colors.HexColor('#EF4444'),
    'péssimo': colors.HexColor('#DC2626'),
    'não avaliado': colors.HexColor('#6B7280'),
}

def get_styles():
    styles = getSampleStyleSheet()
    custom = {
        'Title': ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=22,
                                textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=4),
        'Subtitle': ParagraphStyle('Subtitle', fontName='Helvetica', fontSize=11,
                                   textColor=SECONDARY, alignment=TA_CENTER, spaceAfter=12),
        'SectionHeader': ParagraphStyle('SectionHeader', fontName='Helvetica-Bold', fontSize=13,
                                        textColor=WHITE, alignment=TA_LEFT, spaceAfter=4, spaceBefore=8),
        'FieldLabel': ParagraphStyle('FieldLabel', fontName='Helvetica-Bold', fontSize=8,
                                     textColor=GRAY, spaceAfter=1),
        'FieldValue': ParagraphStyle('FieldValue', fontName='Helvetica', fontSize=9,
                                     textColor=DARK_TEXT, spaceAfter=4),
        'RoomTitle': ParagraphStyle('RoomTitle', fontName='Helvetica-Bold', fontSize=12,
                                    textColor=PRIMARY, spaceAfter=4, spaceBefore=8),
        'ItemName': ParagraphStyle('ItemName', fontName='Helvetica-Bold', fontSize=9,
                                   textColor=DARK_TEXT, spaceAfter=2),
        'ItemDesc': ParagraphStyle('ItemDesc', fontName='Helvetica', fontSize=8,
                                   textColor=DARK_TEXT, spaceAfter=2, alignment=TA_JUSTIFY),
        'Small': ParagraphStyle('Small', fontName='Helvetica', fontSize=7, textColor=GRAY),
        'Footer': ParagraphStyle('Footer', fontName='Helvetica', fontSize=7,
                                 textColor=GRAY, alignment=TA_CENTER),
        'ObsText': ParagraphStyle('ObsText', fontName='Helvetica', fontSize=8,
                                  textColor=DARK_TEXT, alignment=TA_JUSTIFY),
    }
    return custom


def section_header(title, styles):
    table = Table([[Paragraph(f'  {title}', styles['SectionHeader'])]], colWidths=[17*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), PRIMARY),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    return table


def field_row(pairs, styles, col_widths=None):
    """Cria uma linha de campos label/valor"""
    cells = []
    for label, value in pairs:
        cell_content = [Paragraph(label.upper(), styles['FieldLabel']),
                        Paragraph(str(value) if value else '—', styles['FieldValue'])]
        cells.append(cell_content)
    if not col_widths:
        w = 17*cm / len(pairs)
        col_widths = [w] * len(pairs)
    table = Table([cells], colWidths=col_widths)
    table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_GRAY),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
    ]))
    return table


def condition_badge(condition):
    color = CONDITION_COLORS.get(condition.lower() if condition else '', GRAY)
    return color


def generate_pdf(inspection_data: dict, rooms_data: list, signatures_data: list,
                 output_path: str) -> bool:
    """
    Gera o laudo PDF completo da vistoria.
    """
    try:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2.5*cm, bottomMargin=2*cm,
            title=f"Laudo de Vistoria - izyLAUDO",
            author="izyLAUDO"
        )

        styles = get_styles()
        story = []
        inspection = inspection_data

        # ─── CABEÇALHO izyLAUDO ─────────────────────────────────────────────
        header_logo = Paragraph(
            '<font color="#1565E8">izy</font><font color="#0A0A0A">LAUDO</font>',
            ParagraphStyle('Logo', fontName='Helvetica-Bold', fontSize=30, textColor=PRIMARY))

        tipo_label = 'ENTRADA' if inspection.get('type') == 'entrada' else 'SAÍDA'
        header_right = Paragraph(
            f'<b>LAUDO DE VISTORIA</b><br/>'
            f'<font size="10" color="#6B7280">{tipo_label} DE IMÓVEL</font>',
            ParagraphStyle('HdrRight', fontName='Helvetica-Bold', fontSize=16,
                           textColor=DARK_TEXT, alignment=TA_RIGHT))

        header_table = Table([[header_logo, header_right]], colWidths=[8.5*cm, 8.5*cm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width='100%', thickness=2.5, color=PRIMARY, spaceBefore=0, spaceAfter=8))

        # Data e número do laudo
        story.append(Table([[
            Paragraph(f'<font color="#6B7280">Data da Vistoria: <b>{inspection.get("inspection_date", datetime.now().strftime("%d/%m/%Y"))}</b></font>',
                      ParagraphStyle('DateStyle', fontName='Helvetica', fontSize=9, textColor=GRAY)),
            Paragraph(f'<font color="#6B7280">Protocolo: <b>{inspection.get("id", "")[:8].upper()}</b></font>',
                      ParagraphStyle('ProtoStyle', fontName='Helvetica', fontSize=9,
                                     textColor=GRAY, alignment=TA_RIGHT))
        ]], colWidths=[8.5*cm, 8.5*cm]))
        story.append(Spacer(1, 8))

        # ─── IMOBILIÁRIA ────────────────────────────────────────────────────
        imob = inspection.get('imobiliaria_name', '')
        if imob:
            story.append(section_header('IMOBILIÁRIA', styles))
            story.append(Spacer(1, 4))
            story.append(field_row([
                ('Imobiliária', imob),
                ('CNPJ', inspection.get('imobiliaria_cnpj', '')),
                ('Telefone', inspection.get('imobiliaria_phone', '')),
            ], styles, [6*cm, 5*cm, 6*cm]))
            story.append(field_row([
                ('Endereço', inspection.get('imobiliaria_address', '')),
            ], styles, [17*cm]))
            story.append(Spacer(1, 6))

        # ─── DADOS DO IMÓVEL ────────────────────────────────────────────────
        story.append(section_header('DADOS DO IMÓVEL', styles))
        story.append(Spacer(1, 4))
        story.append(field_row([
            ('Endereço Completo', inspection.get('property_address', '')),
        ], styles, [17*cm]))
        story.append(field_row([
            ('Tipo do Imóvel', inspection.get('property_type', '')),
            ('Área', inspection.get('property_area', '') + (' m²' if inspection.get('property_area') else '')),
            ('Tipo de Vistoria', 'ENTRADA' if inspection.get('type') == 'entrada' else 'SAÍDA'),
        ], styles, [6*cm, 5*cm, 6*cm]))
        story.append(Spacer(1, 6))

        # ─── PARTES ENVOLVIDAS ──────────────────────────────────────────────
        story.append(section_header('PARTES ENVOLVIDAS', styles))
        story.append(Spacer(1, 4))

        # Locador
        if inspection.get('locador_name'):
            story.append(Paragraph('LOCADOR (Proprietário)', ParagraphStyle(
                'SubSec', fontName='Helvetica-Bold', fontSize=9, textColor=SECONDARY, spaceBefore=4, spaceAfter=2)))
            story.append(field_row([
                ('Nome Completo', inspection.get('locador_name', '')),
                ('CPF', inspection.get('locador_cpf', '')),
                ('RG', inspection.get('locador_rg', '')),
            ], styles, [7*cm, 5*cm, 5*cm]))
            story.append(field_row([
                ('Telefone', inspection.get('locador_phone', '')),
                ('E-mail', inspection.get('locador_email', '')),
            ], styles, [5*cm, 12*cm]))

        # Locatário
        if inspection.get('locatario_name'):
            story.append(Paragraph('LOCATÁRIO (Inquilino)', ParagraphStyle(
                'SubSec2', fontName='Helvetica-Bold', fontSize=9, textColor=SECONDARY, spaceBefore=6, spaceAfter=2)))
            story.append(field_row([
                ('Nome Completo', inspection.get('locatario_name', '')),
                ('CPF', inspection.get('locatario_cpf', '')),
                ('RG', inspection.get('locatario_rg', '')),
            ], styles, [7*cm, 5*cm, 5*cm]))
            story.append(field_row([
                ('Telefone', inspection.get('locatario_phone', '')),
                ('E-mail', inspection.get('locatario_email', '')),
            ], styles, [5*cm, 12*cm]))

        # Corretor
        if inspection.get('corretor_name'):
            story.append(Paragraph('CORRETOR / VISTORIADOR', ParagraphStyle(
                'SubSec3', fontName='Helvetica-Bold', fontSize=9, textColor=SECONDARY, spaceBefore=6, spaceAfter=2)))
            story.append(field_row([
                ('Nome', inspection.get('corretor_name', '')),
                ('CRECI', inspection.get('corretor_creci', '')),
                ('Telefone', inspection.get('corretor_phone', '')),
            ], styles, [7*cm, 5*cm, 5*cm]))

        story.append(Spacer(1, 8))

        # ─── VISTORIA POR AMBIENTE ──────────────────────────────────────────
        if rooms_data:
            story.append(section_header('VISTORIA DETALHADA POR AMBIENTE', styles))
            story.append(Spacer(1, 4))

            for room in rooms_data:
                # Título do ambiente
                story.append(Paragraph(f"🏠  {room.get('name', '').upper()}", styles['RoomTitle']))
                if room.get('general_condition'):
                    story.append(Paragraph(
                        f"Condição geral: <b>{room.get('general_condition')}</b>",
                        styles['Small']))

                items = room.get('items', [])
                if items:
                    for item in items:
                        item_desc = item.get('manual_description') or item.get('ai_description', '')
                        condition = item.get('condition', 'não avaliado')
                        cond_color = condition_badge(condition)

                        # Card do item
                        photo_path = item.get('photo_path', '')
                        has_photo = photo_path and os.path.exists(photo_path)

                        if has_photo:
                            try:
                                # Redimensiona a foto para o laudo
                                pil_img = PILImage.open(photo_path)
                                pil_img.thumbnail((300, 300))
                                img_buffer = io.BytesIO()
                                pil_img.save(img_buffer, format='JPEG', quality=75)
                                img_buffer.seek(0)
                                rl_img = Image(img_buffer, width=4.5*cm, height=4.5*cm)
                                rl_img.hAlign = 'CENTER'

                                desc_content = [
                                    [Paragraph(item.get('name', ''), styles['ItemName']),
                                     Paragraph(f'Estado: <b>{condition}</b>',
                                               ParagraphStyle('CondStyle', fontName='Helvetica',
                                                              fontSize=8, textColor=cond_color))],
                                    [Paragraph(item_desc, styles['ItemDesc']), '']
                                ]
                                text_table = Table(desc_content, colWidths=[9*cm, 3*cm])
                                text_table.setStyle(TableStyle([
                                    ('SPAN', (0, 1), (1, 1)),
                                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                                    ('TOPPADDING', (0,0), (-1,-1), 2),
                                    ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                                ]))

                                item_table = Table([[rl_img, text_table]], colWidths=[5*cm, 12*cm])
                                item_table.setStyle(TableStyle([
                                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                                    ('TOPPADDING', (0,0), (-1,-1), 6),
                                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                                    ('BACKGROUND', (0,0), (-1,-1), LIGHT_GRAY),
                                    ('LINEBELOW', (0,0), (-1,-1), 0.5, ACCENT),
                                    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                                ]))
                                story.append(item_table)
                                story.append(Spacer(1, 4))
                            except Exception:
                                pass
                        else:
                            item_row = [
                                [Paragraph(item.get('name', ''), styles['ItemName']),
                                 Paragraph(f'Estado: <b>{condition}</b>',
                                           ParagraphStyle('CondStyle2', fontName='Helvetica',
                                                          fontSize=8, textColor=cond_color)),
                                 Paragraph(item_desc, styles['ItemDesc'])]
                            ]
                            item_table = Table(item_row, colWidths=[3.5*cm, 3*cm, 10.5*cm])
                            item_table.setStyle(TableStyle([
                                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                                ('TOPPADDING', (0,0), (-1,-1), 5),
                                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                                ('LEFTPADDING', (0,0), (-1,-1), 6),
                                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                                ('BACKGROUND', (0,0), (-1,-1), LIGHT_GRAY),
                                ('LINEBELOW', (0,0), (-1,-1), 0.5, ACCENT),
                                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                            ]))
                            story.append(item_table)
                            story.append(Spacer(1, 3))

                if room.get('observations'):
                    story.append(Paragraph(f"<i>Observações: {room.get('observations')}</i>",
                                           styles['Small']))
                story.append(Spacer(1, 8))

        # ─── OBSERVAÇÕES GERAIS ─────────────────────────────────────────────
        if inspection.get('observations'):
            story.append(section_header('OBSERVAÇÕES GERAIS', styles))
            story.append(Spacer(1, 4))
            story.append(Paragraph(inspection.get('observations'), styles['ObsText']))
            story.append(Spacer(1, 8))

        # ─── DECLARAÇÃO ─────────────────────────────────────────────────────
        story.append(PageBreak())
        story.append(section_header('DECLARAÇÃO E ASSINATURAS', styles))
        story.append(Spacer(1, 8))

        tipo = 'entrada' if inspection.get('type') == 'entrada' else 'saída'
        decl_text = f"""As partes abaixo assinadas declaram estar de acordo com o presente Laudo de Vistoria de {tipo.upper()}
do imóvel situado em {inspection.get('property_address', '')}, datado de {inspection.get('inspection_date', datetime.now().strftime('%d/%m/%Y'))},
cujas condições foram verificadas, registradas e aceitas por todos."""
        story.append(Paragraph(decl_text, styles['ObsText']))
        story.append(Spacer(1, 16))

        # Campos de assinatura
        sig_parties = [
            ('locador', 'LOCADOR / PROPRIETÁRIO', inspection.get('locador_name', '')),
            ('locatario', 'LOCATÁRIO / INQUILINO', inspection.get('locatario_name', '')),
            ('corretor', 'CORRETOR / VISTORIADOR', inspection.get('corretor_name', '')),
        ]

        # Mapeia assinaturas coletadas
        sig_map = {s.get('party_type'): s for s in signatures_data}

        for party_type, party_label, party_name in sig_parties:
            sig = sig_map.get(party_type)
            story.append(Spacer(1, 8))

            if sig and sig.get('signature_data'):
                # Renderiza imagem da assinatura
                try:
                    sig_data = sig['signature_data']
                    if ',' in sig_data:
                        sig_data = sig_data.split(',')[1]
                    sig_bytes = base64.b64decode(sig_data)
                    sig_buf = io.BytesIO(sig_bytes)
                    sig_img = Image(sig_buf, width=6*cm, height=2*cm)
                    story.append(sig_img)
                except Exception:
                    story.append(Spacer(1, 2*cm))
            else:
                story.append(Spacer(1, 2*cm))

            story.append(HRFlowable(width='60%', thickness=1, color=PRIMARY))
            story.append(Paragraph(f'<b>{party_label}</b>', ParagraphStyle(
                'SigName', fontName='Helvetica-Bold', fontSize=9, textColor=PRIMARY)))
            if party_name:
                story.append(Paragraph(party_name, styles['Small']))
            if sig and sig.get('signed_at'):
                try:
                    dt = datetime.fromisoformat(sig['signed_at'])
                    story.append(Paragraph(f"Assinado em: {dt.strftime('%d/%m/%Y às %H:%M')}",
                                           styles['Small']))
                except Exception:
                    pass
            story.append(Spacer(1, 12))

        # ─── RODAPÉ FINAL ───────────────────────────────────────────────────
        story.append(Spacer(1, 16))
        story.append(HRFlowable(width='100%', thickness=1, color=ACCENT))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"izyLAUDO — Vistorias Imobiliarias | www.izylaudo.com.br | "
            f'Protocolo: {inspection.get("id", "")[:8].upper()} | '
            f'Gerado em: {datetime.now().strftime("%d/%m/%Y as %H:%M")}',
            styles['Footer']
        ))

        doc.build(story)
        return True

    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        import traceback
        traceback.print_exc()
        return False
