# ============================================================
import base64
# izyLAUDO â PDF SERVICE
# Gera laudos em PDF usando os templates oficiais.
# ============================================================
# MantÃ©m a assinatura: generate_pdf(inspection_data, rooms_data,
#                                    signatures_data, output_path) -> bool
# ============================================================

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 HRFlowable, Table, TableStyle, Image)
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
import io
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# âââ CORES ââââââââââââââââââââââââââââââââââââââââââââââââââ
AZUL  = HexColor('#2d7dd2')
PRETO = HexColor('#1a1a1a')
CINZA = HexColor('#666666')
FUNDO = HexColor('#f0f0f0')

W, H = A4
ML, MR, MT, MB = 3*cm, 2*cm, 3*cm, 2*cm
TW = W - ML - MR

# âââ ESTILOS ââââââââââââââââââââââââââââââââââââââââââââââââ
def mk_styles():
    return {
        'normal': ParagraphStyle('normal',
            fontName='Helvetica', fontSize=11, textColor=PRETO,
            leading=18, alignment=TA_JUSTIFY, spaceAfter=6),
        'item': ParagraphStyle('item',
            fontName='Helvetica', fontSize=11, textColor=PRETO,
            leading=18, alignment=TA_JUSTIFY,
            leftIndent=20, spaceAfter=3),
        'clausula_titulo': ParagraphStyle('clausula_titulo',
            fontName='Helvetica-Bold', fontSize=11, textColor=PRETO,
            leading=16, spaceBefore=14, spaceAfter=5),
        'campo_label': ParagraphStyle('campo_label',
            fontName='Helvetica', fontSize=9, textColor=CINZA,
            leading=12, spaceAfter=1),
        'campo_valor': ParagraphStyle('campo_valor',
            fontName='Helvetica-Bold', fontSize=11, textColor=PRETO,
            leading=14, spaceAfter=8),
        'secao': ParagraphStyle('secao',
            fontName='Helvetica-Bold', fontSize=11, textColor=PRETO,
            leading=16, spaceBefore=10, spaceAfter=6),
        'parte': ParagraphStyle('parte',
            fontName='Helvetica-Bold', fontSize=10, textColor=CINZA,
            leading=14, spaceBefore=12, spaceAfter=4),
        'destaque': ParagraphStyle('destaque',
            fontName='Helvetica-Bold', fontSize=11, textColor=PRETO,
            leading=18, alignment=TA_JUSTIFY,
            leftIndent=10, rightIndent=10,
            spaceBefore=4, spaceAfter=6,
            backColor=FUNDO, borderPad=6),
        'assinatura': ParagraphStyle('assinatura',
            fontName='Helvetica', fontSize=10, textColor=CINZA,
            leading=14, spaceAfter=20),
        'rodape': ParagraphStyle('rodape',
            fontName='Helvetica', fontSize=8, textColor=CINZA,
            leading=12, alignment=TA_CENTER),
        'foto_num': ParagraphStyle('foto_num',
            fontName='Helvetica-Bold', fontSize=9, textColor=CINZA,
            leading=12, spaceAfter=2),
        'foto_desc': ParagraphStyle('foto_desc',
            fontName='Helvetica', fontSize=10, textColor=PRETO,
            leading=14, spaceAfter=4, alignment=TA_JUSTIFY),
        'ia_label': ParagraphStyle('ia_label',
            fontName='Helvetica-Bold', fontSize=9, textColor=AZUL,
            leading=12, spaceAfter=2),
        'ambiente_titulo': ParagraphStyle('ambiente_titulo',
            fontName='Helvetica-Bold', fontSize=12, textColor=PRETO,
            leading=16, spaceBefore=14, spaceAfter=6),
        'verif_label': ParagraphStyle('verif_label',
            fontName='Helvetica', fontSize=10, textColor=CINZA,
            leading=14),
        'obs': ParagraphStyle('obs',
            fontName='Helvetica', fontSize=10, textColor=PRETO,
            leading=14, spaceAfter=4, alignment=TA_JUSTIFY),
        'vistoria_box': ParagraphStyle('vistoria_box',
            fontName='Helvetica', fontSize=10, textColor=CINZA,
            leading=14, alignment=TA_CENTER, spaceAfter=8),
        'data': ParagraphStyle('data',
            fontName='Helvetica', fontSize=10, textColor=CINZA,
            leading=14, spaceAfter=10),
    }

def hr(sa=4, sd=4, t=0.5, c=CINZA):
    return HRFlowable(width='100%', thickness=t, color=c,
                      spaceBefore=sa, spaceAfter=sd)

def maiusculo(v):
    """Converte para CAIXA ALTA exceto e-mails e URLs."""
    return v if ('@' in v or 'http' in v) else v.upper()

# âââ COMPONENTES ââââââââââââââââââââââââââââââââââââââââââââ

def add_cabecalho(story, s, titulo_doc, numero_doc):
    logo = Paragraph(
        '<font face="Helvetica" size="17" color="#2d7dd2">izy</font>'
        '<font face="Helvetica-Bold" size="17">LAUDO</font>',
        ParagraphStyle('logo', fontName='Helvetica', fontSize=17,
                       textColor=PRETO, leading=20))
    sub = Paragraph(u'VISTORIAS IMOBILI\u00c1RIAS',
        ParagraphStyle('sub', fontName='Helvetica', fontSize=8,
                       textColor=CINZA, leading=11))
    titulo = Paragraph(titulo_doc,
        ParagraphStyle('td', fontName='Helvetica-Bold', fontSize=12,
                       textColor=PRETO, alignment=TA_RIGHT, leading=16))
    numero = Paragraph(numero_doc,
        ParagraphStyle('nd', fontName='Helvetica', fontSize=10,
                       textColor=CINZA, alignment=TA_RIGHT, leading=14))
    t = Table([[logo, titulo], [sub, numero]],
              colWidths=[TW*0.45, TW*0.55])
    t.setStyle(TableStyle([
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',        (1,0), (1,-1),  'RIGHT'),
        ('TOPPADDING',   (0,0), (-1,-1), 2),
        ('BOTTOMPADDING',(0,0), (-1,-1), 2),
        ('LEFTPADDING',  (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t)
    story.append(hr(6, 12, 1.5, PRETO))

def add_parte(story, s, texto):
    story.append(hr(0, 4, 0.5))
    story.append(Paragraph(texto.upper(), s['parte']))
    story.append(hr(0, 8, 0.5))

def add_campo(story, s, label, valor):
    story.append(Paragraph(label.upper(), s['campo_label']))
    story.append(Paragraph(maiusculo(valor), s['campo_valor']))

def add_foto_item(story, s, item, numero_inicio=1):
    """Renderiza um item com fotos, descri\u00e7\u00e3o IA e estado."""
    story.append(Paragraph(
        f'<b>{item["nome"]}</b> &nbsp;&nbsp; Estado: <b>{item["estado"]}</b>',
        ParagraphStyle('item_hdr', fontName='Helvetica-Bold', fontSize=10,
                       textColor=PRETO, leading=14,
                       spaceBefore=10, spaceAfter=4,
                       backColor=FUNDO, leftIndent=4, borderPad=4)))

    fotos = item.get('fotos', [])
    for i, foto_bytes in enumerate(fotos):
        n = numero_inicio + i
        story.append(Paragraph(f'Foto {n}', s['foto_num']))
        try:
            img = Image(io.BytesIO(foto_bytes), width=TW*0.8, height=TW*0.48)
            img.hAlign = 'LEFT'
            story.append(img)
        except Exception:
            story.append(Paragraph(f'[Foto {n} \u2014 imagem n\u00e3o dispon\u00edvel]',
                                   s['foto_desc']))

    desc = item.get('descricao_ia', '')
    if desc:
        story.append(Paragraph(u'\u2726 IA izyLAUDO', s['ia_label']))
        story.append(Paragraph(desc, s['foto_desc']))

    obs = item.get('observacao', '')
    if obs:
        story.append(Paragraph(f'Observa\u00e7\u00e3o: {obs}', s['obs']))

    story.append(hr(4, 4, 0.3))

def add_ambientes(story, s, ambientes):
    add_parte(story, s, u'Parte 2 \u2014 Vistoria dos Ambientes')

    if not ambientes:
        story.append(Paragraph(
            '[ Ambientes, fotos numeradas, descri\u00e7\u00f5es geradas pela IA izyLAUDO '
            'e verifica\u00e7\u00f5es t\u00e9cnicas inseridos automaticamente pelo sistema ]',
            s['vistoria_box']))
        return

    foto_global = 1
    for amb in ambientes:
        story.append(Paragraph(amb['nome'].upper(), s['ambiente_titulo']))
        story.append(hr(0, 6, 0.8, PRETO))

        for item in amb.get('itens', []):
            add_foto_item(story, s, item, foto_global)
            foto_global += len(item.get('fotos', [])) or 1

        verif = amb.get('verificacoes', {})
        if verif:
            story.append(Paragraph(u'Verifica\u00e7\u00f5es t\u00e9cnicas', s['secao']))
            linhas = []
            mapa = {
                'iluminacao'    : u'Ilumina\u00e7\u00e3o',
                'tomadas'       : 'Tomadas',
                'agua'          : u'\u00c1gua / Encanamento',
                'ar_condicionado': 'Ar-condicionado',
                'portas'        : 'Portas / Fechaduras',
            }
            for k, label in mapa.items():
                if k in verif:
                    linhas.append([
                        Paragraph(label, s['verif_label']),
                        Paragraph(f'<b>{verif[k]}</b>', s['verif_label']),
                    ])
            if linhas:
                t = Table(linhas, colWidths=[TW*0.5, TW*0.5])
                t.setStyle(TableStyle([
                    ('FONTSIZE',    (0,0), (-1,-1), 10),
                    ('TOPPADDING',  (0,0), (-1,-1), 3),
                    ('BOTTOMPADDING',(0,0),(-1,-1), 3),
                    ('LINEBELOW',   (0,0), (-1,-2), 0.3, CINZA),
                ]))
                story.append(t)

        obs_g = amb.get('observacoes_gerais', '')
        if obs_g:
            story.append(Paragraph(f'Observa\u00e7\u00f5es gerais: {obs_g}', s['obs']))

        story.append(Spacer(1, 8))

def add_clausulas_entrada(story, s, email_contestacao, is_imobiliaria=False, creci=''):
    add_parte(story, s, u'Parte 3 \u2014 Cl\u00e1usulas')

    story.append(Paragraph(u'Cl\u00e1usula 1 \u2014 Identifica\u00e7\u00e3o e Finalidade', s['clausula_titulo']))
    story.append(Paragraph(
        u'O presente Laudo de Vistoria de Entrada tem por finalidade registrar, de forma '
        u'detalhada e imparcial, o estado de conserva\u00e7\u00e3o do im\u00f3vel descrito neste documento '
        u'na data de realiza\u00e7\u00e3o da vistoria, servindo como instrumento de prova e refer\u00eancia '
        u'para compara\u00e7\u00e3o ao t\u00e9rmino do contrato de loca\u00e7\u00e3o, nos termos do art. 22, inciso V, '
        u'e art. 23, inciso III, da Lei n\u00ba 8.245/91.', s['normal']))
    if is_imobiliaria:
        story.append(Paragraph(
            u'Este laudo foi elaborado por vistoriador habilitado, com registro no CRECI n\u00ba '
            + _safe(creci) +
            u', utilizando recursos fotogr\u00e1ficos e tecnol\u00f3gicos, constituindo documento '
            u'de valor jur\u00eddico entre as partes.', s['normal']))
    else:
        story.append(Paragraph(
            u'Esta vistoria foi realizada diretamente pelo propriet\u00e1rio do im\u00f3vel, utilizando '
            u'recursos fotogr\u00e1ficos e tecnol\u00f3gicos disponibilizados pelo sistema izyLAUDO, '
            u'constituindo documento de valor jur\u00eddico entre as partes.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 2 \u2014 Metodologia da Vistoria', s['clausula_titulo']))
    story.append(Paragraph(
        u'<b>2.1</b> A vistoria foi realizada de forma presencial, com inspe\u00e7\u00e3o visual '
        u'detalhada de todos os ambientes do im\u00f3vel, incluindo paredes, pisos, tetos, '
        u'esquadrias, instala\u00e7\u00f5es el\u00e9tricas, hidr\u00e1ulicas e demais elementos construtivos '
        u'e de acabamento.', s['normal']))
    story.append(Paragraph(
        u'<b>2.2</b> Cada ambiente foi fotografado individualmente, com registro fotogr\u00e1fico '
        u'numerado. As descri\u00e7\u00f5es foram geradas com aux\u00edlio de intelig\u00eancia artificial '
        u'(IA izyLAUDO) e revisadas pelo ' + (u'vistoriador respons\u00e1vel' if is_imobiliaria else u'pr\u00f3prio propriet\u00e1rio') + u', sendo de sua inteira '
        u'responsabilidade o conte\u00fado final deste documento.', s['normal']))
    story.append(Paragraph(u'<b>2.3</b> Os itens foram classificados segundo os seguintes estados de conserva\u00e7\u00e3o:', s['normal']))
    story.append(Paragraph(u'\u2022 <b>Bom:</b> item em perfeito estado, sem danos, desgastes ou necessidade de reparos;', s['item']))
    story.append(Paragraph(u'\u2022 <b>Regular:</b> item com desgaste natural ou pequenas imperfei\u00e7\u00f5es que n\u00e3o comprometem o uso;', s['item']))
    story.append(Paragraph(u'\u2022 <b>Ruim:</b> item com danos, defeitos ou deteriora\u00e7\u00e3o que comprometem o uso ou a est\u00e9tica.', s['item']))

    story.append(Paragraph(u'Cl\u00e1usula 3 \u2014 Estado Geral do Im\u00f3vel na Entrada', s['clausula_titulo']))
    story.append(Paragraph(u'<b>3.1</b> O estado detalhado de cada ambiente est\u00e1 registrado na Parte 2 deste laudo, acompanhado do respectivo registro fotogr\u00e1fico numerado.', s['normal']))
    story.append(Paragraph(u'<b>3.2</b> Todos os itens n\u00e3o mencionados neste laudo s\u00e3o presumidos como inexistentes ou em estado satisfat\u00f3rio de conserva\u00e7\u00e3o na data da realiza\u00e7\u00e3o da vistoria.', s['normal']))
    story.append(Paragraph(u'<b>3.3</b> Itens classificados como "Regular", decorrentes de desgaste natural, n\u00e3o poder\u00e3o ser cobrados do locat\u00e1rio ao t\u00e9rmino da loca\u00e7\u00e3o, nos termos do art. 23, inciso III, da Lei n\u00ba 8.245/91 e do art. 569 do C\u00f3digo Civil Brasileiro.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 4 \u2014 Prazo de Manifesta\u00e7\u00e3o do Locat\u00e1rio', s['clausula_titulo']))
    story.append(Paragraph(u'O locat\u00e1rio ter\u00e1 10 (dez) dias corridos, a partir da assinatura deste laudo, para apresentar qualquer contesta\u00e7\u00e3o por escrito.', s['destaque']))
    story.append(Paragraph(u'<b>4.1</b> O locat\u00e1rio ter\u00e1 o prazo de <b>10 (dez) dias corridos</b>, contados da data de assinatura deste laudo, para apresentar, por escrito, qualquer contesta\u00e7\u00e3o, ressalva ou apontamento sobre itens n\u00e3o observados, omitidos ou divergentes do estado de conserva\u00e7\u00e3o registrado.', s['normal']))
    if is_imobiliaria:
        story.append(Paragraph(f'<b>4.2</b> A manifesta\u00e7\u00e3o dever\u00e1 ser enviada por escrito ao e-mail da imobili\u00e1ria ou corretor respons\u00e1vel \u2014 <b>{email_contestacao}</b> \u2014 com descri\u00e7\u00e3o clara do item contestado e, preferencialmente, acompanhada de registro fotogr\u00e1fico.', s['normal']))
    else:
        story.append(Paragraph(f'<b>4.2</b> A manifesta\u00e7\u00e3o dever\u00e1 ser enviada por escrito diretamente ao locador/propriet\u00e1rio pelo e-mail \u2014 <b>{email_contestacao}</b> \u2014 com descri\u00e7\u00e3o clara do item contestado e, preferencialmente, acompanhada de registro fotogr\u00e1fico.', s['normal']))
    story.append(Paragraph(u'<b>4.3</b> Decorrido o prazo sem manifesta\u00e7\u00e3o formal, este laudo ser\u00e1 considerado <b>aceito integralmente por ambas as partes</b>, constituindo prova plena do estado do im\u00f3vel na data da vistoria, para todos os fins legais e contratuais.', s['normal']))
    story.append(Paragraph(u'<b>4.4</b> Eventuais aditamentos aceitos pelas partes ser\u00e3o formalizados por escrito, assinados por todos os envolvidos, e passar\u00e3o a integrar este documento como anexo, com a mesma for\u00e7a jur\u00eddica do laudo original.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 5 \u2014 Responsabilidades do Locat\u00e1rio', s['clausula_titulo']))
    story.append(Paragraph(u'<b>5.1</b> O locat\u00e1rio declara ter ci\u00eancia do estado do im\u00f3vel e se compromete a:', s['normal']))
    story.append(Paragraph(u'a) Conservar o im\u00f3vel e devolv\u00ea-lo nas mesmas condi\u00e7\u00f5es, ressalvado o desgaste natural do uso normal, nos termos do art. 23, inciso III, da Lei n\u00ba 8.245/91;', s['item']))
    story.append(Paragraph(u'b) N\u00e3o realizar obras ou modifica\u00e7\u00f5es estruturais sem pr\u00e9via autoriza\u00e7\u00e3o escrita do locador;', s['item']))
    story.append(Paragraph(u'c) Comunicar imediatamente ao ' + (u'locador ou \u00e0 imobili\u00e1ria' if is_imobiliaria else u'locador') + u' qualquer dano ou necessidade de reparo que surja durante a loca\u00e7\u00e3o;', s['item']))
    story.append(Paragraph(u'd) Permitir a vistoria peri\u00f3dica mediante aviso pr\u00e9vio de 24 (vinte e quatro) horas.', s['item']))
    story.append(Paragraph(u'<b>5.2</b> Danos causados por mau uso, neglig\u00eancia ou imper\u00edcia do locat\u00e1rio, seus dependentes ou visitantes s\u00e3o de sua exclusiva responsabilidade.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 6 \u2014 Responsabilidades do Locador', s['clausula_titulo']))
    story.append(Paragraph(u'<b>6.1</b> O locador declara que o im\u00f3vel est\u00e1 em condi\u00e7\u00f5es de habitabilidade para a finalidade a que se destina, conforme descrito neste laudo.', s['normal']))
    story.append(Paragraph(u'<b>6.2</b> Defeitos ou v\u00edcios ocultos n\u00e3o identificados nesta vistoria que se manifestarem durante a loca\u00e7\u00e3o sem culpa do locat\u00e1rio ser\u00e3o de responsabilidade do locador, nos termos do art. 22, inciso IV, da Lei n\u00ba 8.245/91.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 7 \u2014 Integra\u00e7\u00e3o ao Contrato de Loca\u00e7\u00e3o', s['clausula_titulo']))
    story.append(Paragraph(u'<b>7.1</b> Este Laudo de Vistoria de Entrada \u00e9 <b>parte integrante e insepar\u00e1vel do contrato de loca\u00e7\u00e3o</b> celebrado entre as partes, devendo ser interpretado em conjunto com este, complementando-o em todos os aspectos relativos ao estado de conserva\u00e7\u00e3o do im\u00f3vel.', s['normal']))
    story.append(Paragraph(u'<b>7.2</b> Em caso de diverg\u00eancia entre o contrato de loca\u00e7\u00e3o e este laudo quanto ao estado do im\u00f3vel, prevalecer\u00e3o as disposi\u00e7\u00f5es deste laudo, por ser documento espec\u00edfico e contempor\u00e2neo \u00e0 vistoria.', s['normal']))
    story.append(Paragraph(u'<b>7.3</b> Este laudo dever\u00e1 ser arquivado por todas as partes durante toda a vig\u00eancia do contrato e pelo prazo prescricional aplic\u00e1vel ap\u00f3s seu t\u00e9rmino.', s['normal']))
    story.append(Paragraph(u'<b>7.4</b> A aus\u00eancia ou n\u00e3o assinatura deste laudo n\u00e3o exime nenhum dos envolvidos das obriga\u00e7\u00f5es contratuais, por\u00e9m poder\u00e1 limitar as possibilidades de prova em eventual lit\u00edgio.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 8 \u2014 Validade Jur\u00eddica e Assinaturas', s['clausula_titulo']))
    story.append(Paragraph(u'<b>8.1</b> Este laudo constitui documento de valor jur\u00eddico, nos termos do art. 406 do C\u00f3digo Civil e da Lei n\u00ba 14.063/2020 (Lei de Assinatura Eletr\u00f4nica).', s['normal']))
    story.append(Paragraph(u'<b>8.2</b> As assinaturas digitais realizadas por meio da plataforma Autentique t\u00eam validade jur\u00eddica equivalente \u00e0 assinatura manuscrita, conforme a Lei n\u00ba 14.063/2020 e o Decreto n\u00ba 10.278/2020.', s['normal']))
    story.append(Paragraph(u'<b>8.3</b> O documento ser\u00e1 considerado v\u00e1lido ap\u00f3s a aposi\u00e7\u00e3o da assinatura digital de todas as partes indicadas na Parte 4.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 9 \u2014 Foro', s['clausula_titulo']))
    story.append(Paragraph(u'As partes elegem o foro da comarca onde se situa o im\u00f3vel locado para dirimir quaisquer controv\u00e9rsias, renunciando a qualquer outro foro, por mais privilegiado que seja.', s['normal']))


def add_clausulas_saida(story, s, email_contestacao, is_imobiliaria=False, creci=''):
    add_parte(story, s, u'Parte 3 \u2014 Cl\u00e1usulas')

    story.append(Paragraph(u'Cl\u00e1usula 1 \u2014 Identifica\u00e7\u00e3o e Finalidade', s['clausula_titulo']))
    story.append(Paragraph(
        u'O presente Laudo de Vistoria de Sa\u00edda tem por finalidade registrar o estado de '
        u'conserva\u00e7\u00e3o do im\u00f3vel na data de devolu\u00e7\u00e3o e encerramento da loca\u00e7\u00e3o, '
        u'possibilitando a compara\u00e7\u00e3o com o Laudo de Vistoria de Entrada, nos termos do '
        u'art. 23, inciso III, da Lei n\u00ba 8.245/91 e do art. 569 do C\u00f3digo Civil Brasileiro.', s['normal']))
    if is_imobiliaria:
        story.append(Paragraph(
            u'Este laudo foi elaborado por vistoriador habilitado, com registro no CRECI n\u00ba '
            + _safe(creci) +
            u', utilizando recursos fotogr\u00e1ficos e tecnol\u00f3gicos, constituindo documento '
            u'de valor jur\u00eddico entre as partes.', s['normal']))
    else:
        story.append(Paragraph(
            u'Esta vistoria foi realizada diretamente pelo propriet\u00e1rio do im\u00f3vel, utilizando '
            u'recursos fotogr\u00e1ficos e tecnol\u00f3gicos disponibilizados pelo sistema izyLAUDO, '
            u'constituindo documento de valor jur\u00eddico entre as partes.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 2 \u2014 Comparativo com o Laudo de Entrada', s['clausula_titulo']))
    story.append(Paragraph(u'<b>2.1</b> Este laudo deve ser analisado em conjunto com o Laudo de Vistoria de Entrada, que registrou o estado original do im\u00f3vel no in\u00edcio da loca\u00e7\u00e3o.', s['normal']))
    story.append(Paragraph(u'<b>2.2</b> S\u00e3o considerados danos indeniz\u00e1veis pelo locat\u00e1rio apenas aqueles que excedam o desgaste natural do uso normal, conforme compara\u00e7\u00e3o entre os dois laudos.', s['normal']))
    story.append(Paragraph(u'<b>2.3</b> Itens classificados como "Regular" no laudo de entrada e que se apresentem em estado id\u00eantico ou melhor na sa\u00edda n\u00e3o poder\u00e3o ser objeto de cobran\u00e7a.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 3 \u2014 Metodologia da Vistoria', s['clausula_titulo']))
    story.append(Paragraph(u'<b>3.1</b> A vistoria foi realizada de forma presencial na data de devolu\u00e7\u00e3o, com inspe\u00e7\u00e3o visual detalhada de todos os ambientes, itens e instala\u00e7\u00f5es.', s['normal']))
    story.append(Paragraph(
        u'<b>3.2</b> Cada ambiente foi fotografado com registro numerado. As descri\u00e7\u00f5es foram '
        u'geradas com aux\u00edlio de intelig\u00eancia artificial (IA izyLAUDO) e revisadas pelo '
        + (u'vistoriador respons\u00e1vel' if is_imobiliaria else u'pr\u00f3prio propriet\u00e1rio')
        + u'.', s['normal']))
    story.append(Paragraph(u'<b>3.3</b> Os itens foram classificados como: Bom, Regular, Ruim e Danificado \u2014 este \u00faltimo indicando dano causado pelo locat\u00e1rio al\u00e9m do desgaste natural esperado.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 4 \u2014 Responsabilidade pelos Danos Identificados', s['clausula_titulo']))
    story.append(Paragraph(u'<b>4.1</b> S\u00e3o de responsabilidade do locat\u00e1rio os danos que excedam o desgaste natural do uso normal, identificados pela compara\u00e7\u00e3o entre o laudo de entrada e este laudo de sa\u00edda, nos termos do art. 23, inciso III, da Lei n\u00ba 8.245/91.', s['normal']))
    story.append(Paragraph(u'<b>4.2</b> O locat\u00e1rio ter\u00e1 o prazo de 30 (trinta) dias corridos, contados da assinatura deste laudo, para executar os reparos necess\u00e1rios ou ressarcir o locador pelo valor equivalente, mediante or\u00e7amento apresentado.', s['normal']))
    story.append(Paragraph(u'<b>4.3</b> N\u00e3o sendo executados os reparos no prazo estipulado, o locador poder\u00e1 contratar os servi\u00e7os necess\u00e1rios e cobrar os custos do locat\u00e1rio, acrescidos de multa de 10% sobre o valor total.', s['normal']))
    story.append(Paragraph(u'<b>4.4</b> O desgaste natural decorrente do uso normal \u00e9 de responsabilidade do locador, n\u00e3o podendo ser cobrado do locat\u00e1rio.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 5 \u2014 Dep\u00f3sito Cau\u00e7\u00e3o e Acerto Final', s['clausula_titulo']))
    story.append(Paragraph(u'<b>5.1</b> Caso haja dep\u00f3sito cau\u00e7\u00e3o ou garantia locat\u00edcia, seu valor ser\u00e1 utilizado para cobrir eventuais danos identificados neste laudo, mediante acordo entre as partes.', s['normal']))
    story.append(Paragraph(u'<b>5.2</b> N\u00e3o havendo danos indeniz\u00e1veis, o dep\u00f3sito cau\u00e7\u00e3o dever\u00e1 ser devolvido integralmente ao locat\u00e1rio no prazo previsto no contrato de loca\u00e7\u00e3o.', s['normal']))
    story.append(Paragraph(u'<b>5.3</b> O valor do dep\u00f3sito cau\u00e7\u00e3o n\u00e3o limita a responsabilidade do locat\u00e1rio em caso de danos superiores ao seu montante.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 6 \u2014 Declara\u00e7\u00e3o de Devolu\u00e7\u00e3o do Im\u00f3vel', s['clausula_titulo']))
    story.append(Paragraph(u'<b>6.1</b> Pela assinatura deste laudo, o locat\u00e1rio declara formalmente que est\u00e1 devolvendo o im\u00f3vel ao locador na data indicada, encerrando a posse direta do bem.', s['normal']))
    story.append(Paragraph(u'<b>6.2</b> A assinatura deste laudo pelo locador n\u00e3o implica quita\u00e7\u00e3o autom\u00e1tica de eventuais d\u00e9bitos pendentes, salvo declara\u00e7\u00e3o expressa em contr\u00e1rio.', s['normal']))
    story.append(Paragraph(u'<b>6.3</b> O locador declara ter recebido o im\u00f3vel no estado descrito neste laudo, reservando-se o direito de exigir os reparos ou ressarcimentos identificados na Cl\u00e1usula 4.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 7 \u2014 Integra\u00e7\u00e3o ao Contrato de Loca\u00e7\u00e3o', s['clausula_titulo']))
    story.append(Paragraph(u'<b>7.1</b> Este Laudo de Vistoria de Sa\u00edda \u00e9 parte integrante e insepar\u00e1vel do contrato de loca\u00e7\u00e3o, devendo ser lido em conjunto com o Laudo de Entrada e o contrato de loca\u00e7\u00e3o.', s['normal']))
    story.append(Paragraph(u'<b>7.2</b> Este laudo encerra o ciclo documental da loca\u00e7\u00e3o, juntamente com o Laudo de Entrada, constituindo o conjunto probat\u00f3rio completo do per\u00edodo de uso do im\u00f3vel.', s['normal']))
    story.append(Paragraph(u'<b>7.3</b> Ambos os laudos dever\u00e3o ser arquivados pelas partes pelo prazo prescricional aplic\u00e1vel ap\u00f3s o t\u00e9rmino da loca\u00e7\u00e3o.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 8 \u2014 Validade Jur\u00eddica e Assinaturas', s['clausula_titulo']))
    story.append(Paragraph(u'<b>8.1</b> Este laudo constitui documento de valor jur\u00eddico, nos termos do art. 406 do C\u00f3digo Civil e da Lei n\u00ba 14.063/2020 (Lei de Assinatura Eletr\u00f4nica).', s['normal']))
    story.append(Paragraph(u'<b>8.2</b> As assinaturas digitais realizadas por meio da plataforma Autentique t\u00eam validade jur\u00eddica equivalente \u00e0 assinatura manuscrita, conforme a Lei n\u00ba 14.063/2020 e o Decreto n\u00ba 10.278/2020.', s['normal']))
    story.append(Paragraph(u'<b>8.3</b> O documento ser\u00e1 considerado v\u00e1lido ap\u00f3s a aposi\u00e7\u00e3o da assinatura digital de todas as partes indicadas na Parte 4.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 9 \u2014 Foro', s['clausula_titulo']))
    story.append(Paragraph(u'As partes elegem o foro da comarca onde se situa o im\u00f3vel locado para dirimir quaisquer controv\u00e9rsias, renunciando a qualquer outro foro, por mais privilegiado que seja.', s['normal']))



def add_clausulas_temporada(story, s, email_contestacao, is_imobiliaria=False, creci=''):
    add_parte(story, s, u'Parte 3 \u2014 Cl\u00e1usulas')

    story.append(Paragraph(u'Cl\u00e1usula 1 \u2014 Identifica\u00e7\u00e3o e Finalidade', s['clausula_titulo']))
    story.append(Paragraph(
        u'O presente Laudo de Vistoria de Temporada tem por finalidade registrar de forma '
        u'detalhada o estado de conserva\u00e7\u00e3o e o invent\u00e1rio completo de m\u00f3veis, utens\u00edlios '
        u'e equipamentos do im\u00f3vel na data do check-in, servindo como instrumento de prova '
        u'para eventual compara\u00e7\u00e3o ao t\u00e9rmino da estadia.', s['normal']))
    if is_imobiliaria:
        story.append(Paragraph(
            u'Este laudo foi elaborado por vistoriador habilitado, com registro no CRECI n\u00ba '
            + _safe(creci) +
            u', utilizando recursos fotogr\u00e1ficos e tecnol\u00f3gicos do sistema izyLAUDO.', s['normal']))
    else:
        story.append(Paragraph(
            u'Esta vistoria foi realizada diretamente pelo anfitri\u00e3o/propriet\u00e1rio do im\u00f3vel, '
            u'utilizando recursos fotogr\u00e1ficos e tecnol\u00f3gicos disponibilizados pelo sistema izyLAUDO.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 2 \u2014 Invent\u00e1rio Completo', s['clausula_titulo']))
    story.append(Paragraph(u'<b>2.1</b> Por tratar-se de im\u00f3vel para loca\u00e7\u00e3o de temporada, este laudo contempla invent\u00e1rio detalhado de todos os itens presentes, incluindo:', s['normal']))
    story.append(Paragraph(u'\u2022 M\u00f3veis e equipamentos de cada ambiente;', s['item']))
    story.append(Paragraph(u'\u2022 Eletrodom\u00e9sticos e eletr\u00f4nicos;', s['item']))
    story.append(Paragraph(u'\u2022 Utens\u00edlios de cozinha (talheres, pratos, copos, panelas e demais itens);', s['item']))
    story.append(Paragraph(u'\u2022 Roupas de cama, banho e demais itens de enxoval;', s['item']))
    story.append(Paragraph(u'\u2022 Itens decorativos e de uso comum.', s['item']))
    story.append(Paragraph(u'<b>2.2</b> O invent\u00e1rio completo com quantidade, estado e registro fotogr\u00e1fico est\u00e1 na Parte 2 deste laudo.', s['normal']))
    story.append(Paragraph(u'<b>2.3</b> Itens n\u00e3o constantes neste invent\u00e1rio s\u00e3o presumidos como inexistentes no im\u00f3vel na data do check-in.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 3 \u2014 Prazo de Manifesta\u00e7\u00e3o do H\u00f3spede', s['clausula_titulo']))
    story.append(Paragraph(u'<b>3.1</b> O h\u00f3spede/ocupante ter\u00e1 o prazo de 24 (vinte e quatro) horas, contadas do momento do check-in, para apresentar por escrito qualquer contesta\u00e7\u00e3o sobre itens n\u00e3o observados, omitidos ou divergentes do estado registrado.', s['normal']))
    story.append(Paragraph(f'<b>3.2</b> A manifesta\u00e7\u00e3o dever\u00e1 ser enviada ao e-mail \u2014 <b>{email_contestacao}</b> \u2014 com descri\u00e7\u00e3o clara e, preferencialmente, registro fotogr\u00e1fico.', s['normal']))
    story.append(Paragraph(u'<b>3.3</b> Decorrido o prazo sem manifesta\u00e7\u00e3o, este laudo ser\u00e1 considerado aceito integralmente, constituindo prova plena do estado do im\u00f3vel e do invent\u00e1rio no momento do check-in.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 4 \u2014 Responsabilidades do H\u00f3spede', s['clausula_titulo']))
    story.append(Paragraph(u'<b>4.1</b> O h\u00f3spede/ocupante recebe o im\u00f3vel no estado descrito neste laudo e se compromete a:', s['normal']))
    story.append(Paragraph(u'a) Zelar pelo im\u00f3vel, seus m\u00f3veis, utens\u00edlios e equipamentos durante toda a estadia;', s['item']))
    story.append(Paragraph(u'b) N\u00e3o realizar qualquer modifica\u00e7\u00e3o no im\u00f3vel sem autoriza\u00e7\u00e3o expressa do anfitri\u00e3o;', s['item']))
    story.append(Paragraph(u'c) Comunicar imediatamente ao anfitri\u00e3o qualquer dano acidental ocorrido durante a estadia;', s['item']))
    story.append(Paragraph(u'd) Respeitar o n\u00famero m\u00e1ximo de ocupantes indicado no contrato de reserva;', s['item']))
    story.append(Paragraph(u'e) Devolver o im\u00f3vel na data e hora do check-out nas mesmas condi\u00e7\u00f5es em que o recebeu.', s['item']))
    story.append(Paragraph(u'<b>4.2</b> Danos causados por mau uso, neglig\u00eancia ou imper\u00edcia do h\u00f3spede, seus acompanhantes ou animais de estima\u00e7\u00e3o s\u00e3o de sua exclusiva responsabilidade.', s['normal']))
    story.append(Paragraph(u'<b>4.3</b> A quebra, extravio ou dano de qualquer item do invent\u00e1rio ser\u00e1 cobrada pelo valor de reposi\u00e7\u00e3o ou reparo do item.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 5 \u2014 Danos Durante a Estadia', s['clausula_titulo']))
    story.append(Paragraph(u'<b>5.1</b> Ao t\u00e9rmino da estadia ser\u00e1 realizada vistoria de sa\u00edda comparando o estado atual com o registrado neste laudo de check-in.', s['normal']))
    story.append(Paragraph(u'<b>5.2</b> Danos identificados na vistoria de sa\u00edda e ausentes neste laudo ser\u00e3o de responsabilidade do h\u00f3spede.', s['normal']))
    story.append(Paragraph(u'<b>5.3</b> O h\u00f3spede autoriza expressamente o d\u00e9bito do valor dos danos na cau\u00e7\u00e3o ou garantia fornecida na reserva, caso exista.', s['normal']))
    story.append(Paragraph(u'<b>5.4</b> N\u00e3o havendo cau\u00e7\u00e3o suficiente, o h\u00f3spede se compromete a ressarcir o anfitri\u00e3o no prazo de 5 (cinco) dias \u00fateis ap\u00f3s o check-out.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 6 \u2014 Regras de Uso e Condi\u00e7\u00f5es da Estadia', s['clausula_titulo']))
    story.append(Paragraph(u'<b>6.1</b> O uso do im\u00f3vel, suas instala\u00e7\u00f5es, m\u00f3veis e equipamentos pelo h\u00f3spede/ocupante dever\u00e1 observar estritamente as regras e condi\u00e7\u00f5es estabelecidas no contrato de reserva celebrado entre as partes, seja por plataforma digital (Airbnb, Booking, etc.) ou diretamente entre anfitri\u00e3o e h\u00f3spede.', s['normal']))
    story.append(Paragraph(u'<b>6.2</b> O h\u00f3spede declara ter lido, compreendido e concordado com todas as regras de uso definidas no contrato de reserva, incluindo mas n\u00e3o se limitando a: capacidade m\u00e1xima de ocupantes, pol\u00edtica de animais de estima\u00e7\u00e3o, regras de sil\u00eancio, pol\u00edtica de cancelamento e demais condi\u00e7\u00f5es espec\u00edficas do im\u00f3vel.', s['normal']))
    story.append(Paragraph(u'<b>6.3</b> O descumprimento de qualquer regra prevista no contrato de reserva poder\u00e1 ensejar a rescis\u00e3o imediata da estadia, sem direito a reembolso, al\u00e9m da responsabiliza\u00e7\u00e3o pelos danos causados.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 7 \u2014 Integra\u00e7\u00e3o ao Contrato de Reserva', s['clausula_titulo']))
    story.append(Paragraph(u'<b>7.1</b> Este laudo \u00e9 parte integrante do contrato de reserva celebrado entre as partes, seja por plataforma digital ou diretamente entre anfitri\u00e3o e h\u00f3spede.', s['normal']))
    story.append(Paragraph(u'<b>7.2</b> Em caso de diverg\u00eancia entre o contrato de reserva e este laudo no que se refere ao estado do im\u00f3vel e invent\u00e1rio, prevalecer\u00e3o as disposi\u00e7\u00f5es deste laudo.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 8 \u2014 Validade Jur\u00eddica e Assinaturas', s['clausula_titulo']))
    story.append(Paragraph(u'<b>8.1</b> Este laudo constitui documento de valor jur\u00eddico, nos termos do art. 406 do C\u00f3digo Civil e da Lei n\u00ba 14.063/2020 (Lei de Assinatura Eletr\u00f4nica).', s['normal']))
    story.append(Paragraph(u'<b>8.2</b> As assinaturas digitais realizadas por meio da plataforma Autentique t\u00eam validade jur\u00eddica equivalente \u00e0 assinatura manuscrita, conforme a Lei n\u00ba 14.063/2020 e o Decreto n\u00ba 10.278/2020.', s['normal']))
    story.append(Paragraph(u'<b>8.3</b> O documento ser\u00e1 considerado v\u00e1lido ap\u00f3s a aposi\u00e7\u00e3o da assinatura digital de todas as partes indicadas na Parte 4.', s['normal']))

    story.append(Paragraph(u'Cl\u00e1usula 9 \u2014 Foro', s['clausula_titulo']))
    story.append(Paragraph(u'As partes elegem o foro da comarca onde se situa o im\u00f3vel locado para dirimir quaisquer controv\u00e9rsias, renunciando a qualquer outro foro, por mais privilegiado que seja.', s['normal']))


def add_assinaturas(story, s, partes, local_data):
    add_parte(story, s, u'Parte 4 \u2014 Declara\u00e7\u00e3o e Assinaturas')
    story.append(Paragraph(
        u'As partes declaram ter lido e compreendido integralmente este laudo, '
        u'concordando com os registros fotogr\u00e1ficos, descri\u00e7\u00f5es e estados de '
        u'conserva\u00e7\u00e3o nele contidos, cientes de que este documento \u00e9 <b>parte '
        u'integrante do contrato de loca\u00e7\u00e3o</b> em vigor.', s['normal']))
    story.append(Paragraph(f'Local e data: {local_data}', s['data']))
    for nome, papel, cpf in partes:
        story.append(HRFlowable(width='65%', thickness=0.8, color=PRETO,
                                spaceBefore=24, spaceAfter=4))
        story.append(Paragraph(f'{nome.upper()} \u2014 {papel} \u00b7 CPF: {cpf}', s['assinatura']))

def add_rodape(story, s):
    story.append(Spacer(1, 16))
    story.append(hr(0, 4, 0.3))
    story.append(Paragraph(
        u'Documento gerado pelo sistema izyLAUDO \u2014 Vistorias Imobili\u00e1rias \u00b7 '
        u'Assinatura digital via Autentique \u00b7 Lei n\u00ba 14.063/2020', s['rodape']))

# âââ FUN\u00c7\u00c3O DO TEMPLATE âââââââââââââââââââââââââââââââââââââ
def gerar_laudo_entrada_proprietario(dados_imovel, dados_locador,
                                      dados_locatario, dados_corretor, dados_imobiliaria,
                                      ambientes, local_data, output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=MT, leftMargin=ML,
        bottomMargin=MB, rightMargin=MR,
        title=u'Laudo de Vistoria de Entrada \u2014 Propriet\u00e1rio Direto',
        author='izyLAUDO'
    )
    s = mk_styles()
    story = []

    add_cabecalho(story, s,
        'LAUDO DE VISTORIA DE ENTRADA',
        f'N\u00ba {dados_imovel["numero_laudo"]} \u00b7 Propriet\u00e1rio Direto')

    add_parte(story, s, u'Parte 1 \u2014 Qualifica\u00e7\u00e3o')

    story.append(Paragraph(u'1.1 Dados do Im\u00f3vel', s['secao']))
    add_campo(story, s, u'Endere\u00e7o', dados_imovel['endereco'])
    add_campo(story, s, 'Complemento', dados_imovel['complemento'])
    add_campo(story, s, 'Bairro', dados_imovel['bairro'])
    add_campo(story, s, 'Cidade / UF', dados_imovel['cidade_uf'])
    add_campo(story, s, 'CEP', dados_imovel['cep'])
    add_campo(story, s, u'Tipo do im\u00f3vel', dados_imovel['tipo'])
    add_campo(story, s, u'\u00c1rea aproximada', dados_imovel['area'])
    add_campo(story, s, 'Data da vistoria', dados_imovel['data_hora'])

    story.append(Paragraph(u'1.2 Locador(es) \u2014 Propriet\u00e1rio', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locador['nome'])
    add_campo(story, s, 'CPF', dados_locador['cpf'])
    add_campo(story, s, 'Telefone', dados_locador['telefone'])
    add_campo(story, s, 'E-mail', dados_locador['email'])

    story.append(Paragraph(u'1.3 Locat\u00e1rio(s)', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locatario['nome'])
    add_campo(story, s, 'CPF', dados_locatario['cpf'])
    add_campo(story, s, 'Telefone', dados_locatario['telefone'])
    add_campo(story, s, 'E-mail', dados_locatario['email'])

    # 1.4 Imobiliaria (only if data exists)
    if dados_imobiliaria.get('nome'):
        story.append(Paragraph(u'1.4 Imobili\u00e1ria', s['secao']))
        add_campo(story, s, 'Nome', dados_imobiliaria['nome'])
        if dados_imobiliaria.get('cnpj'):
            add_campo(story, s, 'CNPJ', dados_imobiliaria['cnpj'])
        if dados_imobiliaria.get('telefone'):
            add_campo(story, s, 'Telefone', dados_imobiliaria['telefone'])
        if dados_imobiliaria.get('endereco'):
            add_campo(story, s, u'Endere\u00e7o', dados_imobiliaria['endereco'])

    # 1.5 Corretor (only if data exists)
    if dados_corretor.get('nome'):
        story.append(Paragraph(u'1.5 Corretor', s['secao']))
        add_campo(story, s, 'Nome', dados_corretor['nome'])
        if dados_corretor.get('creci'):
            add_campo(story, s, 'CRECI', dados_corretor['creci'])
        if dados_corretor.get('telefone'):
            add_campo(story, s, 'Telefone', dados_corretor['telefone'])
        if dados_corretor.get('email'):
            add_campo(story, s, 'E-mail', dados_corretor['email'])

    add_ambientes(story, s, ambientes)
    add_clausulas_entrada(story, s, dados_locador['email'], is_imobiliaria=False)

    partes_sig = [
        (dados_locador['nome'],    u'Locador / Propriet\u00e1rio', dados_locador['cpf']),
        (dados_locatario['nome'],  u'Locat\u00e1rio',              dados_locatario['cpf']),
    ]
    if dados_imobiliaria.get('nome'):
        partes_sig.append((dados_imobiliaria['nome'], u'Imobili\u00e1ria', dados_imobiliaria.get('cnpj', '')))
    if dados_corretor.get('nome'):
        partes_sig.append((dados_corretor['nome'], u'Corretor \u00b7 CRECI ' + dados_corretor.get('creci', ''), ''))
    add_assinaturas(story, s, partes_sig, local_data)

    add_rodape(story, s)
    doc.build(story)


# âââ HELPERS DE MAPEAMENTO ââââââââââââââââââââââââââââââââââ

MESES_PT = {
    1: 'JANEIRO', 2: 'FEVEREIRO', 3: u'MAR\u00c7O', 4: 'ABRIL',
    5: 'MAIO', 6: 'JUNHO', 7: 'JULHO', 8: 'AGOSTO',
    9: 'SETEMBRO', 10: 'OUTUBRO', 11: 'NOVEMBRO', 12: 'DEZEMBRO',
}

# Alias: Modelo 2 = Entrada + Proprietario (already defined above)
gerar_laudo_modelo2 = gerar_laudo_entrada_proprietario

def gerar_laudo_modelo1(dados_imovel, dados_locador, dados_locatario,
                        dados_corretor, dados_imobiliaria,
                        ambientes, local_data, output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=MT, leftMargin=ML,
        bottomMargin=MB, rightMargin=MR,
        title=u'Laudo de Vistoria de Entrada \u2014 Imobili\u00e1ria/Corretor',
        author='izyLAUDO'
    )
    s = mk_styles()
    story = []

    add_cabecalho(story, s,
        'LAUDO DE VISTORIA DE ENTRADA',
        f'N\u00ba {dados_imovel["numero_laudo"]} \u00b7 Imobili\u00e1ria/Corretor')

    add_parte(story, s, u'Parte 1 \u2014 Qualifica\u00e7\u00e3o')

    story.append(Paragraph(u'1.1 Dados do Im\u00f3vel', s['secao']))
    add_campo(story, s, u'Endere\u00e7o', dados_imovel['endereco'])
    add_campo(story, s, 'Complemento', dados_imovel['complemento'])
    add_campo(story, s, 'Bairro', dados_imovel['bairro'])
    add_campo(story, s, 'Cidade / UF', dados_imovel['cidade_uf'])
    add_campo(story, s, 'CEP', dados_imovel['cep'])
    add_campo(story, s, u'Tipo do im\u00f3vel', dados_imovel['tipo'])
    add_campo(story, s, u'\u00c1rea aproximada', dados_imovel['area'])
    add_campo(story, s, 'Data da vistoria', dados_imovel['data_hora'])

    story.append(Paragraph(u'1.2 Imobili\u00e1ria / Corretor', s['secao']))
    if dados_imobiliaria.get('nome'):
        add_campo(story, s, 'Nome', dados_imobiliaria['nome'])
        if dados_imobiliaria.get('cnpj'):
            add_campo(story, s, 'CNPJ', dados_imobiliaria['cnpj'])
        if dados_imobiliaria.get('telefone'):
            add_campo(story, s, 'Telefone', dados_imobiliaria['telefone'])
    if dados_corretor.get('nome'):
        add_campo(story, s, 'Corretor', dados_corretor['nome'])
        if dados_corretor.get('creci'):
            add_campo(story, s, 'CRECI', dados_corretor['creci'])
        if dados_corretor.get('telefone'):
            add_campo(story, s, 'Telefone', dados_corretor['telefone'])
        if dados_corretor.get('email'):
            add_campo(story, s, 'E-mail', dados_corretor['email'])

    story.append(Paragraph(u'1.3 Locador(es)', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locador['nome'])
    add_campo(story, s, 'CPF', dados_locador['cpf'])
    add_campo(story, s, 'Telefone', dados_locador['telefone'])
    add_campo(story, s, 'E-mail', dados_locador['email'])

    story.append(Paragraph(u'1.4 Locat\u00e1rio(s)', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locatario['nome'])
    add_campo(story, s, 'CPF', dados_locatario['cpf'])
    add_campo(story, s, 'Telefone', dados_locatario['telefone'])
    add_campo(story, s, 'E-mail', dados_locatario['email'])

    add_ambientes(story, s, ambientes)

    email_cont = dados_imobiliaria.get('email', '') or dados_corretor.get('email', '') or ''
    creci_val = dados_corretor.get('creci', '')
    add_clausulas_entrada(story, s, email_cont, is_imobiliaria=True, creci=creci_val)

    partes_sig = [
        (dados_locador['nome'], u'Locador', dados_locador['cpf']),
        (dados_locatario['nome'], u'Locat\u00e1rio', dados_locatario['cpf']),
    ]
    if dados_imobiliaria.get('nome'):
        partes_sig.append((dados_imobiliaria['nome'], u'Imobili\u00e1ria', dados_imobiliaria.get('cnpj', '')))
    if dados_corretor.get('nome'):
        partes_sig.append((dados_corretor['nome'], u'Corretor \u00b7 CRECI ' + dados_corretor.get('creci', ''), ''))
    add_assinaturas(story, s, partes_sig, local_data)

    add_rodape(story, s)
    doc.build(story)


def gerar_laudo_modelo3(dados_imovel, dados_locador, dados_locatario,
                        dados_corretor, dados_imobiliaria,
                        ambientes, local_data, output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=MT, leftMargin=ML,
        bottomMargin=MB, rightMargin=MR,
        title=u'Laudo de Vistoria de Sa\u00edda \u2014 Imobili\u00e1ria/Corretor',
        author='izyLAUDO'
    )
    s = mk_styles()
    story = []

    add_cabecalho(story, s,
        u'LAUDO DE VISTORIA DE SA\u00cdDA',
        f'N\u00ba {dados_imovel["numero_laudo"]} \u00b7 Imobili\u00e1ria/Corretor')

    add_parte(story, s, u'Parte 1 \u2014 Qualifica\u00e7\u00e3o')

    story.append(Paragraph(u'1.1 Dados do Im\u00f3vel', s['secao']))
    add_campo(story, s, u'Endere\u00e7o', dados_imovel['endereco'])
    add_campo(story, s, 'Complemento', dados_imovel['complemento'])
    add_campo(story, s, 'Bairro', dados_imovel['bairro'])
    add_campo(story, s, 'Cidade / UF', dados_imovel['cidade_uf'])
    add_campo(story, s, 'CEP', dados_imovel['cep'])
    add_campo(story, s, u'Tipo do im\u00f3vel', dados_imovel['tipo'])
    add_campo(story, s, u'\u00c1rea aproximada', dados_imovel['area'])
    add_campo(story, s, 'Data da vistoria', dados_imovel['data_hora'])

    story.append(Paragraph(u'1.2 Imobili\u00e1ria / Corretor', s['secao']))
    if dados_imobiliaria.get('nome'):
        add_campo(story, s, 'Nome', dados_imobiliaria['nome'])
        if dados_imobiliaria.get('cnpj'):
            add_campo(story, s, 'CNPJ', dados_imobiliaria['cnpj'])
        if dados_imobiliaria.get('telefone'):
            add_campo(story, s, 'Telefone', dados_imobiliaria['telefone'])
    if dados_corretor.get('nome'):
        add_campo(story, s, 'Corretor', dados_corretor['nome'])
        if dados_corretor.get('creci'):
            add_campo(story, s, 'CRECI', dados_corretor['creci'])
        if dados_corretor.get('email'):
            add_campo(story, s, 'E-mail', dados_corretor['email'])

    story.append(Paragraph(u'1.3 Locador(es)', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locador['nome'])
    add_campo(story, s, 'CPF', dados_locador['cpf'])
    add_campo(story, s, 'Telefone', dados_locador['telefone'])
    add_campo(story, s, 'E-mail', dados_locador['email'])

    story.append(Paragraph(u'1.4 Locat\u00e1rio(s)', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locatario['nome'])
    add_campo(story, s, 'CPF', dados_locatario['cpf'])
    add_campo(story, s, 'Telefone', dados_locatario['telefone'])
    add_campo(story, s, 'E-mail', dados_locatario['email'])

    add_ambientes(story, s, ambientes)

    email_cont = dados_imobiliaria.get('email', '') or dados_corretor.get('email', '') or ''
    creci_val = dados_corretor.get('creci', '')
    add_clausulas_saida(story, s, email_cont, is_imobiliaria=True, creci=creci_val)

    partes_sig = [
        (dados_locador['nome'], u'Locador', dados_locador['cpf']),
        (dados_locatario['nome'], u'Locat\u00e1rio', dados_locatario['cpf']),
    ]
    if dados_imobiliaria.get('nome'):
        partes_sig.append((dados_imobiliaria['nome'], u'Imobili\u00e1ria', dados_imobiliaria.get('cnpj', '')))
    if dados_corretor.get('nome'):
        partes_sig.append((dados_corretor['nome'], u'Vistoriador/Corretor \u00b7 CRECI ' + dados_corretor.get('creci', ''), ''))
    add_assinaturas(story, s, partes_sig, local_data)

    add_rodape(story, s)
    doc.build(story)


def gerar_laudo_modelo4(dados_imovel, dados_locador, dados_locatario,
                        dados_corretor, dados_imobiliaria,
                        ambientes, local_data, output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=MT, leftMargin=ML,
        bottomMargin=MB, rightMargin=MR,
        title=u'Laudo de Vistoria de Sa\u00edda \u2014 Propriet\u00e1rio Direto',
        author='izyLAUDO'
    )
    s = mk_styles()
    story = []

    add_cabecalho(story, s,
        u'LAUDO DE VISTORIA DE SA\u00cdDA',
        f'N\u00ba {dados_imovel["numero_laudo"]} \u00b7 Propriet\u00e1rio Direto')

    add_parte(story, s, u'Parte 1 \u2014 Qualifica\u00e7\u00e3o')

    story.append(Paragraph(u'1.1 Dados do Im\u00f3vel', s['secao']))
    add_campo(story, s, u'Endere\u00e7o', dados_imovel['endereco'])
    add_campo(story, s, 'Complemento', dados_imovel['complemento'])
    add_campo(story, s, 'Bairro', dados_imovel['bairro'])
    add_campo(story, s, 'Cidade / UF', dados_imovel['cidade_uf'])
    add_campo(story, s, 'CEP', dados_imovel['cep'])
    add_campo(story, s, u'Tipo do im\u00f3vel', dados_imovel['tipo'])
    add_campo(story, s, u'\u00c1rea aproximada', dados_imovel['area'])
    add_campo(story, s, 'Data da vistoria', dados_imovel['data_hora'])

    story.append(Paragraph(u'1.2 Locador(es) \u2014 Propriet\u00e1rio', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locador['nome'])
    add_campo(story, s, 'CPF', dados_locador['cpf'])
    add_campo(story, s, 'Telefone', dados_locador['telefone'])
    add_campo(story, s, 'E-mail', dados_locador['email'])

    story.append(Paragraph(u'1.3 Locat\u00e1rio(s)', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locatario['nome'])
    add_campo(story, s, 'CPF', dados_locatario['cpf'])
    add_campo(story, s, 'Telefone', dados_locatario['telefone'])
    add_campo(story, s, 'E-mail', dados_locatario['email'])

    if dados_imobiliaria.get('nome'):
        story.append(Paragraph(u'1.4 Imobili\u00e1ria', s['secao']))
        add_campo(story, s, 'Nome', dados_imobiliaria['nome'])
        if dados_imobiliaria.get('cnpj'):
            add_campo(story, s, 'CNPJ', dados_imobiliaria['cnpj'])
    if dados_corretor.get('nome'):
        story.append(Paragraph(u'1.5 Corretor', s['secao']))
        add_campo(story, s, 'Nome', dados_corretor['nome'])
        if dados_corretor.get('creci'):
            add_campo(story, s, 'CRECI', dados_corretor['creci'])

    add_ambientes(story, s, ambientes)
    add_clausulas_saida(story, s, dados_locador['email'], is_imobiliaria=False)

    partes_sig = [
        (dados_locador['nome'], u'Locador / Propriet\u00e1rio', dados_locador['cpf']),
        (dados_locatario['nome'], u'Locat\u00e1rio', dados_locatario['cpf']),
    ]
    if dados_imobiliaria.get('nome'):
        partes_sig.append((dados_imobiliaria['nome'], u'Imobili\u00e1ria', dados_imobiliaria.get('cnpj', '')))
    if dados_corretor.get('nome'):
        partes_sig.append((dados_corretor['nome'], u'Corretor \u00b7 CRECI ' + dados_corretor.get('creci', ''), ''))
    add_assinaturas(story, s, partes_sig, local_data)

    add_rodape(story, s)
    doc.build(story)


def gerar_laudo_modelo5(dados_imovel, dados_locador, dados_locatario,
                        dados_corretor, dados_imobiliaria,
                        ambientes, local_data, output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=MT, leftMargin=ML,
        bottomMargin=MB, rightMargin=MR,
        title=u'Laudo de Vistoria de Temporada \u2014 Imobili\u00e1ria/Corretor',
        author='izyLAUDO'
    )
    s = mk_styles()
    story = []

    add_cabecalho(story, s,
        'LAUDO DE VISTORIA DE TEMPORADA',
        f'N\u00ba {dados_imovel["numero_laudo"]} \u00b7 Imobili\u00e1ria/Corretor')

    add_parte(story, s, u'Parte 1 \u2014 Qualifica\u00e7\u00e3o')

    story.append(Paragraph(u'1.1 Dados do Im\u00f3vel', s['secao']))
    add_campo(story, s, u'Endere\u00e7o', dados_imovel['endereco'])
    add_campo(story, s, 'Complemento', dados_imovel['complemento'])
    add_campo(story, s, 'Bairro', dados_imovel['bairro'])
    add_campo(story, s, 'Cidade / UF', dados_imovel['cidade_uf'])
    add_campo(story, s, 'CEP', dados_imovel['cep'])
    add_campo(story, s, u'Tipo do im\u00f3vel', dados_imovel['tipo'])
    add_campo(story, s, u'\u00c1rea aproximada', dados_imovel['area'])
    add_campo(story, s, 'Data da vistoria', dados_imovel['data_hora'])

    story.append(Paragraph(u'1.2 Imobili\u00e1ria / Corretor', s['secao']))
    if dados_imobiliaria.get('nome'):
        add_campo(story, s, 'Nome', dados_imobiliaria['nome'])
        if dados_imobiliaria.get('cnpj'):
            add_campo(story, s, 'CNPJ', dados_imobiliaria['cnpj'])
        if dados_imobiliaria.get('telefone'):
            add_campo(story, s, 'Telefone', dados_imobiliaria['telefone'])
    if dados_corretor.get('nome'):
        add_campo(story, s, 'Corretor', dados_corretor['nome'])
        if dados_corretor.get('creci'):
            add_campo(story, s, 'CRECI', dados_corretor['creci'])
        if dados_corretor.get('email'):
            add_campo(story, s, 'E-mail', dados_corretor['email'])

    story.append(Paragraph(u'1.3 Locador / Anfitri\u00e3o', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locador['nome'])
    add_campo(story, s, 'CPF', dados_locador['cpf'])
    add_campo(story, s, 'Telefone', dados_locador['telefone'])
    add_campo(story, s, 'E-mail', dados_locador['email'])

    story.append(Paragraph(u'1.4 H\u00f3spede(s) / Ocupante(s)', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locatario['nome'])
    add_campo(story, s, 'CPF', dados_locatario['cpf'])
    add_campo(story, s, 'Telefone', dados_locatario['telefone'])
    add_campo(story, s, 'E-mail', dados_locatario['email'])

    add_ambientes(story, s, ambientes)

    email_cont = dados_imobiliaria.get('email', '') or dados_corretor.get('email', '') or ''
    creci_val = dados_corretor.get('creci', '')
    add_clausulas_temporada(story, s, email_cont, is_imobiliaria=True, creci=creci_val)

    partes_sig = [
        (dados_locador['nome'], u'Anfitri\u00e3o / Locador', dados_locador['cpf']),
        (dados_locatario['nome'], u'H\u00f3spede / Ocupante', dados_locatario['cpf']),
    ]
    if dados_imobiliaria.get('nome'):
        partes_sig.append((dados_imobiliaria['nome'], u'Imobili\u00e1ria', dados_imobiliaria.get('cnpj', '')))
    if dados_corretor.get('nome'):
        partes_sig.append((dados_corretor['nome'], u'Vistoriador/Corretor \u00b7 CRECI ' + dados_corretor.get('creci', ''), ''))
    add_assinaturas(story, s, partes_sig, local_data)

    add_rodape(story, s)
    doc.build(story)


def gerar_laudo_modelo6(dados_imovel, dados_locador, dados_locatario,
                        dados_corretor, dados_imobiliaria,
                        ambientes, local_data, output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=MT, leftMargin=ML,
        bottomMargin=MB, rightMargin=MR,
        title=u'Laudo de Vistoria de Temporada \u2014 Propriet\u00e1rio Direto',
        author='izyLAUDO'
    )
    s = mk_styles()
    story = []

    add_cabecalho(story, s,
        'LAUDO DE VISTORIA DE TEMPORADA',
        f'N\u00ba {dados_imovel["numero_laudo"]} \u00b7 Propriet\u00e1rio Direto')

    add_parte(story, s, u'Parte 1 \u2014 Qualifica\u00e7\u00e3o')

    story.append(Paragraph(u'1.1 Dados do Im\u00f3vel', s['secao']))
    add_campo(story, s, u'Endere\u00e7o', dados_imovel['endereco'])
    add_campo(story, s, 'Complemento', dados_imovel['complemento'])
    add_campo(story, s, 'Bairro', dados_imovel['bairro'])
    add_campo(story, s, 'Cidade / UF', dados_imovel['cidade_uf'])
    add_campo(story, s, 'CEP', dados_imovel['cep'])
    add_campo(story, s, u'Tipo do im\u00f3vel', dados_imovel['tipo'])
    add_campo(story, s, u'\u00c1rea aproximada', dados_imovel['area'])
    add_campo(story, s, 'Data da vistoria', dados_imovel['data_hora'])

    story.append(Paragraph(u'1.2 Locador / Anfitri\u00e3o \u2014 Propriet\u00e1rio', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locador['nome'])
    add_campo(story, s, 'CPF', dados_locador['cpf'])
    add_campo(story, s, 'Telefone', dados_locador['telefone'])
    add_campo(story, s, 'E-mail', dados_locador['email'])

    story.append(Paragraph(u'1.3 H\u00f3spede(s) / Ocupante(s)', s['secao']))
    add_campo(story, s, 'Nome completo', dados_locatario['nome'])
    add_campo(story, s, 'CPF', dados_locatario['cpf'])
    add_campo(story, s, 'Telefone', dados_locatario['telefone'])
    add_campo(story, s, 'E-mail', dados_locatario['email'])

    if dados_imobiliaria.get('nome'):
        story.append(Paragraph(u'1.4 Imobili\u00e1ria', s['secao']))
        add_campo(story, s, 'Nome', dados_imobiliaria['nome'])
        if dados_imobiliaria.get('cnpj'):
            add_campo(story, s, 'CNPJ', dados_imobiliaria['cnpj'])
    if dados_corretor.get('nome'):
        story.append(Paragraph(u'1.5 Corretor', s['secao']))
        add_campo(story, s, 'Nome', dados_corretor['nome'])
        if dados_corretor.get('creci'):
            add_campo(story, s, 'CRECI', dados_corretor['creci'])

    add_ambientes(story, s, ambientes)
    add_clausulas_temporada(story, s, dados_locador['email'], is_imobiliaria=False)

    partes_sig = [
        (dados_locador['nome'], u'Anfitri\u00e3o / Locador / Propriet\u00e1rio', dados_locador['cpf']),
        (dados_locatario['nome'], u'H\u00f3spede / Ocupante', dados_locatario['cpf']),
    ]
    if dados_imobiliaria.get('nome'):
        partes_sig.append((dados_imobiliaria['nome'], u'Imobili\u00e1ria', dados_imobiliaria.get('cnpj', '')))
    if dados_corretor.get('nome'):
        partes_sig.append((dados_corretor['nome'], u'Corretor \u00b7 CRECI ' + dados_corretor.get('creci', ''), ''))
    add_assinaturas(story, s, partes_sig, local_data)

    add_rodape(story, s)
    doc.build(story)


def _parse_date(date_str):
    if not date_str:
        return datetime.now()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S',
                '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return datetime.now()

def _format_date_extenso(dt):
    return f'{dt.day} DE {MESES_PT.get(dt.month, "")} DE {dt.year}'

def _format_date_display(date_str):
    dt = _parse_date(date_str)
    return dt.strftime('%d/%m/%Y')

def _safe(val, fallback=u'\u2014'):
    if val is None:
        return fallback
    v = str(val).strip()
    return v if v else fallback

def _foto_bytes(data_url):
    """Converte data URL base64 para bytes."""
    if not data_url:
        return None
    try:
        header, b64 = data_url.split(',', 1)
        return base64.b64decode(b64)
    except Exception:
        return None


def _build_ambientes_from_json(json_str):
    """Converte ambientes_json do frontend para formato esperado pelo PDF."""
    import json as _json
    try:
        data = _json.loads(json_str)
    except Exception:
        return []
    ambientes = []
    for amb in data:
        itens = []
        for foto in amb.get('fotos', []):
            foto_bytes_list = []
            src = foto.get('src', '')
            if src:
                fb = _foto_bytes(src)
                if fb:
                    foto_bytes_list.append(fb)
            itens.append({
                'nome': _safe(foto.get('item', ''), 'Item'),
                'estado': _safe(foto.get('estado', ''), u'N\u00e3o informado'),
                'descricao_ia': _safe(foto.get('desc', ''), ''),
                'observacao': '',
                'fotos': foto_bytes_list,
            })
        ambientes.append({
            'nome': _safe(amb.get('nome', ''), 'Ambiente'),
            'itens': itens,
            'verificacoes': amb.get('verificacoes', {}),
            'observacoes_gerais': _safe(amb.get('observacoes', ''), ''),
        })
    return ambientes


def _build_ambientes(rooms_data):
    ambientes = []
    for room in rooms_data:
        itens = []
        for item in room.get('items', []):
            foto_bytes_list = []
            photo_path = item.get('photo_path', '')
            if photo_path and os.path.isfile(photo_path):
                try:
                    with open(photo_path, 'rb') as f:
                        foto_bytes_list.append(f.read())
                except Exception:
                    pass

            itens.append({
                'nome': _safe(item.get('name'), 'Item'),
                'estado': _safe(item.get('condition'), u'N\u00e3o informado'),
                'descricao_ia': _safe(item.get('ai_description'), ''),
                'observacao': _safe(item.get('manual_description'), ''),
                'fotos': foto_bytes_list,
            })

        amb = {
            'nome': _safe(room.get('name'), 'Ambiente'),
            'itens': itens,
            'verificacoes': {},
            'observacoes_gerais': _safe(room.get('observations'), ''),
        }
        ambientes.append(amb)
    return ambientes

def _generate_numero_laudo(inspection_data):
    tipo = (inspection_data.get('type') or 'entrada').lower()
    prefixo = 'VE' if tipo == 'entrada' else 'VS'
    dt = _parse_date(inspection_data.get('inspection_date'))
    ano = dt.year
    insp_id = inspection_data.get('id', '0000')
    seq = insp_id[:4].upper()
    return f'{prefixo}-{ano}-{seq}'


# âââ FUN\u00c7\u00c3O PRINCIPAL (mant\u00e9m assinatura compat\u00edvel) ââââââââ

def generate_pdf(inspection_data: dict, rooms_data: list,
                 signatures_data: list, output_path: str) -> bool:
    """
    Gera o Laudo de Vistoria em PDF.
    Assinatura compat\u00edvel com GeneratePDFHandler em server.py.
    """
    try:
        insp = inspection_data

        address = _safe(insp.get('property_address'))
        inspection_date_str = _safe(insp.get('inspection_date'), '')
        dt = _parse_date(inspection_date_str)
        date_display = _format_date_display(inspection_date_str)

        cidade_raw = _safe(insp.get('cidade'), '')
        estado_raw = _safe(insp.get('estado'), '')
        if cidade_raw and estado_raw:
            cidade_uf = u'{} / {}'.format(cidade_raw, estado_raw)
        elif cidade_raw:
            cidade_uf = cidade_raw
        elif estado_raw:
            cidade_uf = estado_raw
        else:
            cidade_uf = u'\u2014'

        dados_imovel = {
            'endereco'    : address,
            'complemento' : _safe(insp.get('complemento'), u'\u2014'),
            'bairro'      : _safe(insp.get('bairro'), u'\u2014'),
            'cidade_uf'   : cidade_uf,
            'cep'         : _safe(insp.get('cep'), u'\u2014'),
            'tipo'        : _safe(insp.get('property_type'), u'\u2014'),
            'area'        : _safe(insp.get('property_area'), u'\u2014'),
            'data_hora'   : date_display,
            'numero_laudo': _generate_numero_laudo(insp),
        }

        dados_locador = {
            'nome'     : _safe(insp.get('locador_name'), u'\u2014'),
            'cpf'      : _safe(insp.get('locador_cpf'), u'\u2014'),
            'telefone' : _safe(insp.get('locador_phone'), u'\u2014'),
            'email'    : _safe(insp.get('locador_email'), u'\u2014'),
        }

        dados_locatario = {
            'nome'     : _safe(insp.get('locatario_name'), u'\u2014'),
            'cpf'      : _safe(insp.get('locatario_cpf'), u'\u2014'),
            'telefone' : _safe(insp.get('locatario_phone'), u'\u2014'),
            'email'    : _safe(insp.get('locatario_email'), u'\u2014'),
        }

        dados_corretor = {
            'nome'     : _safe(insp.get('corretor_name'), ''),
            'creci'    : _safe(insp.get('corretor_creci'), ''),
            'telefone' : _safe(insp.get('corretor_phone'), ''),
            'email'    : _safe(insp.get('corretor_email'), ''),
        }

        dados_imobiliaria = {
            'nome'     : _safe(insp.get('imobiliaria_name'), ''),
            'cnpj'     : _safe(insp.get('imobiliaria_cnpj'), ''),
            'telefone' : _safe(insp.get('imobiliaria_phone'), ''),
            'endereco' : _safe(insp.get('imobiliaria_address'), ''),
            'email'    : _safe(insp.get('corretor_email'), ''),
        }

        amb_json = insp.get('ambientes_json', '')
        if amb_json:
            ambientes = _build_ambientes_from_json(amb_json)
        else:
            ambientes = _build_ambientes(rooms_data)

        local_data = _format_date_extenso(dt)

        # ---- Selecao do modelo baseado em tipo x responsavel ----
        tipo = _safe(insp.get('type', 'entrada')).lower().strip()
        responsavel = _safe(insp.get('responsavel', 'proprietario')).lower().strip()

        args = (dados_imovel, dados_locador, dados_locatario,
                dados_corretor, dados_imobiliaria,
                ambientes, local_data, output_path)

        if tipo == 'entrada' and responsavel == 'imobiliaria':
            gerar_laudo_modelo1(*args)
        elif tipo == 'entrada':
            gerar_laudo_modelo2(*args)
        elif tipo == 'saida' and responsavel == 'imobiliaria':
            gerar_laudo_modelo3(*args)
        elif tipo == 'saida':
            gerar_laudo_modelo4(*args)
        elif tipo == 'temporada' and responsavel == 'imobiliaria':
            gerar_laudo_modelo5(*args)
        elif tipo == 'temporada':
            gerar_laudo_modelo6(*args)
        else:
            gerar_laudo_modelo2(*args)  # fallback

        logger.info(f'PDF gerado com sucesso: {output_path}')
        return True

    except Exception as e:
        logger.error(f'Erro ao gerar PDF: {e}', exc_info=True)
        return False
