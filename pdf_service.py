# -*- coding: utf-8 -*-
"""
pdf_service.py — izyLAUDO · Geração de Laudos de Vistoria em PDF
6 modelos · Entrada/Saída/Temporada · Imobiliária ou Proprietário
Cláusulas oficiais aprovadas — NÃO ALTERAR textos das cláusulas.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, HRFlowable, PageBreak)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from PIL import Image as PILImage
import io
import json
import base64
from datetime import datetime

# ─── CORES ───────────────────────────────────────────────────────────────────
IZY_BLUE   = colors.HexColor('#2d7dd2')
DARK_TEXT   = colors.HexColor('#1a1a1a')
GRAY        = colors.HexColor('#6B7280')
LINE_COL    = colors.HexColor('#D1D5DB')
LIGHT_BG    = colors.HexColor('#F8F9FB')

# ─── FONTES (Helvetica = fallback para Calibri) ─────────────────────────────
FONT_MAIN   = 'Helvetica'
FONT_BOLD   = 'Helvetica-Bold'
FONT_ITALIC = 'Helvetica-Oblique'
FS = 12  # tamanho base

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def upper(text):
    """CAIXA ALTA, preservando e-mails e URLs."""
    if not text:
        return ''
    s = str(text)
    if '@' in s or 'http' in s.lower() or '.com' in s.lower():
        return s
    return s.upper()


def tipo_label(insp):
    """Retorna label do tipo de vistoria."""
    t = (insp.get('type') or 'entrada').lower()
    if t == 'saida':
        return 'SAÍDA'
    if t == 'temporada':
        return 'TEMPORADA'
    return 'ENTRADA'


def select_model(insp):
    """Seleciona modelo 1-6 automaticamente."""
    t = (insp.get('type') or 'entrada').lower()
    has_imob = bool(insp.get('imobiliaria_name') or insp.get('corretor_name')
                    or insp.get('corretor_creci'))
    if t == 'entrada':
        return 1 if has_imob else 2
    elif t == 'saida':
        return 3 if has_imob else 4
    else:
        return 5 if has_imob else 6


# ─── CLÁUSULAS OFICIAIS ─────────────────────────────────────────────────────
# Cláusulas 8 e 9 são comuns a todos os modelos
def _clausula8():
    return ('CLÁUSULA 8ª — VALIDADE JURÍDICA E ASSINATURAS',
        '8.1 Este laudo constitui documento de valor jurídico, nos termos do art. 406 do Código Civil e da '
        'Lei nº 14.063/2020 (Lei de Assinatura Eletrônica).\n'
        '8.2 As assinaturas digitais realizadas por meio da plataforma Autentique têm validade jurídica equivalente '
        'à assinatura manuscrita, conforme a Lei nº 14.063/2020 e o Decreto nº 10.278/2020.\n'
        '8.3 O documento será considerado válido após a aposição da assinatura digital de todas as partes indicadas '
        'na Parte 4.')


def _clausula9(insp):
    cidade = insp.get('property_city') or '___'
    estado = insp.get('property_state') or '___'
    return ('CLÁUSULA 9ª — FORO',
        f'As partes elegem o foro da comarca de {cidade} / {estado}, onde se situa o imóvel locado, para dirimir '
        f'quaisquer controvérsias, renunciando a qualquer outro foro, por mais privilegiado que seja.')


# MODELO 1 — Entrada + Imobiliária/Corretor
def _clausulas_modelo1(insp):
    creci = insp.get('corretor_creci') or '___'
    email_imob = insp.get('corretor_email') or insp.get('imobiliaria_email') or '___'
    return [
        ('CLÁUSULA 1ª — IDENTIFICAÇÃO E FINALIDADE',
         f'O presente Laudo de Vistoria de Entrada tem por finalidade registrar, de forma detalhada e imparcial, '
         f'o estado de conservação do imóvel descrito neste documento na data de realização da vistoria, servindo '
         f'como instrumento de prova e referência para comparação ao término do contrato de locação, nos termos do '
         f'art. 22, inciso V, e art. 23, inciso III, da Lei nº 8.245/91.\n'
         f'Este laudo foi elaborado por vistoriador habilitado, com registro no CRECI nº {creci}, '
         f'utilizando recursos fotográficos e tecnológicos, constituindo documento de valor jurídico entre as partes.'),

        ('CLÁUSULA 2ª — METODOLOGIA DA VISTORIA',
         '2.1 A vistoria foi realizada de forma presencial, com inspeção visual detalhada de todos os ambientes do '
         'imóvel, incluindo paredes, pisos, tetos, esquadrias, instalações elétricas, hidráulicas e demais elementos '
         'construtivos e de acabamento.\n'
         '2.2 Cada ambiente foi fotografado individualmente, com registro fotográfico numerado de cada item relevante. '
         'As descrições foram geradas com auxílio de inteligência artificial (IA izyLAUDO) e revisadas pelo vistoriador '
         'responsável, sendo de sua inteira responsabilidade o conteúdo final deste documento.\n'
         '2.3 Os itens foram classificados segundo os seguintes estados de conservação:\n'
         '• Bom: item em perfeito estado, sem danos, desgastes ou necessidade de reparos;\n'
         '• Regular: item com desgaste natural ou pequenas imperfeições que não comprometem o uso;\n'
         '• Ruim: item com danos, defeitos ou deterioração que comprometem o uso ou a estética.'),

        ('CLÁUSULA 3ª — ESTADO GERAL DO IMÓVEL NA ENTRADA',
         '3.1 O estado detalhado de cada ambiente está registrado na Parte 2 deste laudo, acompanhado do respectivo '
         'registro fotográfico numerado.\n'
         '3.2 Todos os itens não mencionados neste laudo são presumidos como inexistentes ou em estado satisfatório '
         'de conservação na data da realização da vistoria.\n'
         '3.3 Itens classificados como "Regular", decorrentes de desgaste natural, não poderão ser cobrados do locatário '
         'ao término da locação, nos termos do art. 23, inciso III, da Lei nº 8.245/91 e do art. 569 do Código Civil Brasileiro.'),

        ('CLÁUSULA 4ª — PRAZO DE MANIFESTAÇÃO DO LOCATÁRIO',
         f'4.1 O locatário terá o prazo de 10 (dez) dias corridos, contados da data de assinatura deste laudo, para '
         f'apresentar, por escrito, qualquer contestação, ressalva ou apontamento sobre itens não observados, omitidos '
         f'ou divergentes do estado de conservação registrado.\n'
         f'4.2 A manifestação deverá ser enviada por escrito ao e-mail da imobiliária ou corretor responsável — '
         f'{email_imob} — com descrição clara do item contestado e, preferencialmente, acompanhada de registro fotográfico.\n'
         f'4.3 Decorrido o prazo de 10 (dez) dias sem manifestação formal, este laudo será considerado aceito '
         f'integralmente por ambas as partes, constituindo prova plena do estado do imóvel na data da vistoria, '
         f'para todos os fins legais e contratuais.\n'
         f'4.4 Eventuais aditamentos aceitos pelas partes serão formalizados por escrito, assinados por todos os '
         f'envolvidos, e passarão a integrar este documento como anexo, com a mesma força jurídica do laudo original.'),

        ('CLÁUSULA 5ª — RESPONSABILIDADES DO LOCATÁRIO',
         '5.1 O locatário declara ter ciência do estado do imóvel e se compromete a:\n'
         'a) Conservar o imóvel e devolvê-lo nas mesmas condições, ressalvado o desgaste natural do uso normal, '
         'nos termos do art. 23, inciso III, da Lei nº 8.245/91;\n'
         'b) Não realizar obras ou modificações estruturais sem prévia autorização escrita do locador;\n'
         'c) Comunicar imediatamente ao locador ou à imobiliária qualquer dano ou necessidade de reparo;\n'
         'd) Permitir a vistoria periódica mediante aviso prévio de 24 (vinte e quatro) horas.\n'
         '5.2 Danos causados por mau uso, negligência ou imperícia do locatário, seus dependentes ou visitantes '
         'são de sua exclusiva responsabilidade.'),

        ('CLÁUSULA 6ª — RESPONSABILIDADES DO LOCADOR',
         '6.1 O locador declara que o imóvel está em condições de habitabilidade para a finalidade a que se destina, '
         'conforme descrito neste laudo.\n'
         '6.2 Defeitos ou vícios ocultos não identificados nesta vistoria que se manifestarem durante a locação sem '
         'culpa do locatário serão de responsabilidade do locador, nos termos do art. 22, inciso IV, da Lei nº 8.245/91.'),

        ('CLÁUSULA 7ª — INTEGRAÇÃO AO CONTRATO DE LOCAÇÃO',
         '7.1 Este Laudo de Vistoria de Entrada é parte integrante e inseparável do contrato de locação celebrado entre '
         'as partes, devendo ser interpretado em conjunto com este, complementando-o em todos os aspectos relativos ao '
         'estado de conservação do imóvel.\n'
         '7.2 Em caso de divergência entre o contrato de locação e este laudo quanto ao estado do imóvel, prevalecerão '
         'as disposições deste laudo, por ser documento específico e contemporâneo à vistoria.\n'
         '7.3 Este laudo deverá ser arquivado por todas as partes durante toda a vigência do contrato e pelo prazo '
         'prescricional aplicável após seu término.\n'
         '7.4 A ausência ou não assinatura deste laudo não exime nenhum dos envolvidos das obrigações contratuais, '
         'porém poderá limitar as possibilidades de prova em eventual litígio.'),

        _clausula8(),
        _clausula9(insp),
    ]


# MODELO 2 — Entrada + Proprietário Direto
def _clausulas_modelo2(insp):
    email_loc = insp.get('locador_email') or '___'
    return [
        ('CLÁUSULA 1ª — IDENTIFICAÇÃO E FINALIDADE',
         'O presente Laudo de Vistoria de Entrada tem por finalidade registrar, de forma detalhada e imparcial, '
         'o estado de conservação do imóvel descrito neste documento na data de realização da vistoria, servindo '
         'como instrumento de prova e referência para comparação ao término do contrato de locação, nos termos do '
         'art. 22, inciso V, e art. 23, inciso III, da Lei nº 8.245/91.\n'
         'Esta vistoria foi realizada diretamente pelo proprietário do imóvel, utilizando recursos fotográficos '
         'e tecnológicos disponibilizados pelo sistema izyLAUDO.'),

        ('CLÁUSULA 2ª — METODOLOGIA DA VISTORIA',
         '2.1 A vistoria foi realizada de forma presencial, com inspeção visual detalhada de todos os ambientes do '
         'imóvel, incluindo paredes, pisos, tetos, esquadrias, instalações elétricas, hidráulicas e demais elementos '
         'construtivos e de acabamento.\n'
         '2.2 Cada ambiente foi fotografado individualmente, com registro fotográfico numerado de cada item relevante. '
         'As descrições foram geradas com auxílio de inteligência artificial (IA izyLAUDO) e revisadas pelo próprio '
         'proprietário, sendo de sua inteira responsabilidade o conteúdo final deste documento.\n'
         '2.3 Os itens foram classificados segundo os seguintes estados de conservação:\n'
         '• Bom: item em perfeito estado, sem danos, desgastes ou necessidade de reparos;\n'
         '• Regular: item com desgaste natural ou pequenas imperfeições que não comprometem o uso;\n'
         '• Ruim: item com danos, defeitos ou deterioração que comprometem o uso ou a estética.'),

        ('CLÁUSULA 3ª — ESTADO GERAL DO IMÓVEL NA ENTRADA',
         '3.1 O estado detalhado de cada ambiente está registrado na Parte 2 deste laudo, acompanhado do respectivo '
         'registro fotográfico numerado.\n'
         '3.2 Todos os itens não mencionados neste laudo são presumidos como inexistentes ou em estado satisfatório '
         'de conservação na data da realização da vistoria.\n'
         '3.3 Itens classificados como "Regular", decorrentes de desgaste natural, não poderão ser cobrados do locatário '
         'ao término da locação, nos termos do art. 23, inciso III, da Lei nº 8.245/91 e do art. 569 do Código Civil Brasileiro.'),

        ('CLÁUSULA 4ª — PRAZO DE MANIFESTAÇÃO DO LOCATÁRIO',
         f'4.1 O locatário terá o prazo de 10 (dez) dias corridos, contados da data de assinatura deste laudo, para '
         f'apresentar, por escrito, qualquer contestação, ressalva ou apontamento sobre itens não observados, omitidos '
         f'ou divergentes do estado de conservação registrado.\n'
         f'4.2 A manifestação deverá ser enviada por escrito ao e-mail do locador — '
         f'{email_loc} — com descrição clara do item contestado e, preferencialmente, acompanhada de registro fotográfico.\n'
         f'4.3 Decorrido o prazo de 10 (dez) dias sem manifestação formal, este laudo será considerado aceito '
         f'integralmente por ambas as partes, constituindo prova plena do estado do imóvel na data da vistoria, '
         f'para todos os fins legais e contratuais.\n'
         f'4.4 Eventuais aditamentos aceitos pelas partes serão formalizados por escrito, assinados por todos os '
         f'envolvidos, e passarão a integrar este documento como anexo, com a mesma força jurídica do laudo original.'),

        ('CLÁUSULA 5ª — RESPONSABILIDADES DO LOCATÁRIO',
         '5.1 O locatário declara ter ciência do estado do imóvel e se compromete a:\n'
         'a) Conservar o imóvel e devolvê-lo nas mesmas condições, ressalvado o desgaste natural do uso normal, '
         'nos termos do art. 23, inciso III, da Lei nº 8.245/91;\n'
         'b) Não realizar obras ou modificações estruturais sem prévia autorização escrita do locador;\n'
         'c) Comunicar imediatamente ao locador qualquer dano ou necessidade de reparo;\n'
         'd) Permitir a vistoria periódica mediante aviso prévio de 24 (vinte e quatro) horas.\n'
         '5.2 Danos causados por mau uso, negligência ou imperícia do locatário, seus dependentes ou visitantes '
         'são de sua exclusiva responsabilidade.'),

        ('CLÁUSULA 6ª — RESPONSABILIDADES DO LOCADOR',
         '6.1 O locador declara que o imóvel está em condições de habitabilidade para a finalidade a que se destina, '
         'conforme descrito neste laudo.\n'
         '6.2 Defeitos ou vícios ocultos não identificados nesta vistoria que se manifestarem durante a locação sem '
         'culpa do locatário serão de responsabilidade do locador, nos termos do art. 22, inciso IV, da Lei nº 8.245/91.'),

        ('CLÁUSULA 7ª — INTEGRAÇÃO AO CONTRATO DE LOCAÇÃO',
         '7.1 Este Laudo de Vistoria de Entrada é parte integrante e inseparável do contrato de locação celebrado entre '
         'as partes, devendo ser interpretado em conjunto com este, complementando-o em todos os aspectos relativos ao '
         'estado de conservação do imóvel.\n'
         '7.2 Em caso de divergência entre o contrato de locação e este laudo quanto ao estado do imóvel, prevalecerão '
         'as disposições deste laudo, por ser documento específico e contemporâneo à vistoria.\n'
         '7.3 Este laudo deverá ser arquivado por todas as partes durante toda a vigência do contrato e pelo prazo '
         'prescricional aplicável após seu término.\n'
         '7.4 A ausência ou não assinatura deste laudo não exime nenhum dos envolvidos das obrigações contratuais, '
         'porém poderá limitar as possibilidades de prova em eventual litígio.'),

        _clausula8(),
        _clausula9(insp),
    ]


# MODELO 3 — Saída + Imobiliária/Corretor
def _clausulas_modelo3(insp):
    creci = insp.get('corretor_creci') or '___'
    data_entrada = insp.get('data_vistoria_entrada') or '___'
    return [
        ('CLÁUSULA 1ª — IDENTIFICAÇÃO E FINALIDADE',
         f'O presente Laudo de Vistoria de Saída tem por finalidade registrar o estado de conservação do imóvel na '
         f'data de devolução e encerramento da locação, possibilitando a comparação com o Laudo de Vistoria de Entrada, '
         f'nos termos do art. 23, inciso III, da Lei nº 8.245/91 e do art. 569 do Código Civil Brasileiro.\n'
         f'Este laudo foi elaborado por vistoriador habilitado, com registro no CRECI nº {creci}, '
         f'utilizando recursos fotográficos e tecnológicos, constituindo documento de valor jurídico entre as partes.'),

        ('CLÁUSULA 2ª — COMPARATIVO COM O LAUDO DE ENTRADA',
         f'2.1 Este laudo deve ser analisado em conjunto com o Laudo de Vistoria de Entrada realizado em '
         f'{data_entrada}, que registrou o estado original do imóvel no início da locação.\n'
         f'2.2 São considerados danos indenizáveis pelo locatário apenas aqueles que excedam o desgaste natural do uso '
         f'normal, conforme comparação entre os dois laudos.\n'
         f'2.3 Itens classificados como "Regular" no laudo de entrada e que se apresentem em estado idêntico ou melhor '
         f'na saída não poderão ser objeto de cobrança.'),

        ('CLÁUSULA 3ª — METODOLOGIA DA VISTORIA',
         '3.1 A vistoria foi realizada de forma presencial na data de devolução, com inspeção visual detalhada de todos '
         'os ambientes, itens e instalações.\n'
         '3.2 Cada ambiente foi fotografado com registro numerado. As descrições foram geradas com auxílio de inteligência '
         'artificial (IA izyLAUDO) e revisadas pelo vistoriador responsável.\n'
         '3.3 Os itens foram classificados como: Bom, Regular, Ruim e Danificado — este último indicando dano causado '
         'pelo locatário além do desgaste natural esperado.'),

        ('CLÁUSULA 4ª — RESPONSABILIDADE PELOS DANOS IDENTIFICADOS',
         '4.1 São de responsabilidade do locatário os danos que excedam o desgaste natural do uso normal, identificados '
         'pela comparação entre o laudo de entrada e este laudo de saída, nos termos do art. 23, inciso III, da '
         'Lei nº 8.245/91.\n'
         '4.2 O locatário terá o prazo de 30 (trinta) dias corridos, contados da assinatura deste laudo, para executar '
         'os reparos necessários ou ressarcir o locador pelo valor equivalente, mediante orçamento apresentado.\n'
         '4.3 Não sendo executados os reparos no prazo estipulado, o locador poderá contratar os serviços necessários e '
         'cobrar os custos do locatário, acrescidos de multa de 10% sobre o valor total.\n'
         '4.4 O desgaste natural decorrente do uso normal é de responsabilidade do locador, não podendo ser cobrado do locatário.'),

        ('CLÁUSULA 5ª — DEPÓSITO CAUÇÃO E ACERTO FINAL',
         '5.1 Caso haja depósito caução ou garantia locatícia, seu valor será utilizado para cobrir eventuais danos '
         'identificados neste laudo, mediante acordo entre as partes.\n'
         '5.2 Não havendo danos indenizáveis, o depósito caução deverá ser devolvido integralmente ao locatário no '
         'prazo previsto no contrato de locação.\n'
         '5.3 O valor do depósito caução não limita a responsabilidade do locatário em caso de danos superiores ao seu montante.'),

        ('CLÁUSULA 6ª — DECLARAÇÃO DE DEVOLUÇÃO DO IMÓVEL',
         '6.1 Pela assinatura deste laudo, o locatário declara formalmente que está devolvendo o imóvel ao locador na '
         'data indicada, encerrando a posse direta do bem.\n'
         '6.2 A assinatura deste laudo pelo locador não implica quitação automática de eventuais débitos pendentes, '
         'salvo declaração expressa em contrário.\n'
         '6.3 O locador declara ter recebido o imóvel no estado descrito neste laudo, reservando-se o direito de '
         'exigir os reparos ou ressarcimentos identificados na Cláusula 4.'),

        ('CLÁUSULA 7ª — INTEGRAÇÃO AO CONTRATO DE LOCAÇÃO',
         '7.1 Este Laudo de Vistoria de Saída é parte integrante e inseparável do contrato de locação, devendo ser '
         'lido em conjunto com o Laudo de Entrada e o contrato de locação.\n'
         '7.2 Este laudo encerra o ciclo documental da locação, juntamente com o Laudo de Entrada, constituindo o '
         'conjunto probatório completo do período de uso do imóvel.\n'
         '7.3 Ambos os laudos deverão ser arquivados pelas partes pelo prazo prescricional aplicável após o término da locação.'),

        _clausula8(),
        _clausula9(insp),
    ]


# MODELO 4 — Saída + Proprietário Direto
def _clausulas_modelo4(insp):
    data_entrada = insp.get('data_vistoria_entrada') or '___'
    return [
        ('CLÁUSULA 1ª — IDENTIFICAÇÃO E FINALIDADE',
         'O presente Laudo de Vistoria de Saída tem por finalidade registrar o estado de conservação do imóvel na '
         'data de devolução e encerramento da locação, possibilitando a comparação com o Laudo de Vistoria de Entrada, '
         'nos termos do art. 23, inciso III, da Lei nº 8.245/91 e do art. 569 do Código Civil Brasileiro.\n'
         'Esta vistoria foi realizada diretamente pelo proprietário do imóvel, utilizando recursos fotográficos '
         'e tecnológicos disponibilizados pelo sistema izyLAUDO.'),

        ('CLÁUSULA 2ª — COMPARATIVO COM O LAUDO DE ENTRADA',
         f'2.1 Este laudo deve ser analisado em conjunto com o Laudo de Vistoria de Entrada realizado em '
         f'{data_entrada}, que registrou o estado original do imóvel no início da locação.\n'
         f'2.2 São considerados danos indenizáveis pelo locatário apenas aqueles que excedam o desgaste natural do uso '
         f'normal, conforme comparação entre os dois laudos.\n'
         f'2.3 Itens classificados como "Regular" no laudo de entrada e que se apresentem em estado idêntico ou melhor '
         f'na saída não poderão ser objeto de cobrança.'),

        ('CLÁUSULA 3ª — METODOLOGIA DA VISTORIA',
         '3.1 A vistoria foi realizada de forma presencial na data de devolução, com inspeção visual detalhada de todos '
         'os ambientes, itens e instalações.\n'
         '3.2 Cada ambiente foi fotografado com registro numerado. As descrições foram geradas com auxílio de inteligência '
         'artificial (IA izyLAUDO) e revisadas pelo próprio proprietário.\n'
         '3.3 Os itens foram classificados como: Bom, Regular, Ruim e Danificado — este último indicando dano causado '
         'pelo locatário além do desgaste natural esperado.'),

        ('CLÁUSULA 4ª — RESPONSABILIDADE PELOS DANOS IDENTIFICADOS',
         '4.1 São de responsabilidade do locatário os danos que excedam o desgaste natural do uso normal, identificados '
         'pela comparação entre o laudo de entrada e este laudo de saída, nos termos do art. 23, inciso III, da '
         'Lei nº 8.245/91.\n'
         '4.2 O locatário terá o prazo de 30 (trinta) dias corridos, contados da assinatura deste laudo, para executar '
         'os reparos necessários ou ressarcir o locador pelo valor equivalente, mediante orçamento apresentado.\n'
         '4.3 Não sendo executados os reparos no prazo estipulado, o locador poderá contratar os serviços necessários e '
         'cobrar os custos do locatário, acrescidos de multa de 10% sobre o valor total.\n'
         '4.4 O desgaste natural decorrente do uso normal é de responsabilidade do locador, não podendo ser cobrado do locatário.'),

        ('CLÁUSULA 5ª — DEPÓSITO CAUÇÃO E ACERTO FINAL',
         '5.1 Caso haja depósito caução ou garantia locatícia, seu valor será utilizado para cobrir eventuais danos '
         'identificados neste laudo, mediante acordo entre as partes.\n'
         '5.2 Não havendo danos indenizáveis, o depósito caução deverá ser devolvido integralmente ao locatário no '
         'prazo previsto no contrato de locação.\n'
         '5.3 O valor do depósito caução não limita a responsabilidade do locatário em caso de danos superiores ao seu montante.'),

        ('CLÁUSULA 6ª — DECLARAÇÃO DE DEVOLUÇÃO DO IMÓVEL',
         '6.1 Pela assinatura deste laudo, o locatário declara formalmente que está devolvendo o imóvel ao locador na '
         'data indicada, encerrando a posse direta do bem.\n'
         '6.2 A assinatura deste laudo pelo locador não implica quitação automática de eventuais débitos pendentes, '
         'salvo declaração expressa em contrário.\n'
         '6.3 O locador declara ter recebido o imóvel no estado descrito neste laudo, reservando-se o direito de '
         'exigir os reparos ou ressarcimentos identificados na Cláusula 4.'),

        ('CLÁUSULA 7ª — INTEGRAÇÃO AO CONTRATO DE LOCAÇÃO',
         '7.1 Este Laudo de Vistoria de Saída é parte integrante e inseparável do contrato de locação, devendo ser '
         'lido em conjunto com o Laudo de Entrada e o contrato de locação.\n'
         '7.2 Este laudo encerra o ciclo documental da locação, juntamente com o Laudo de Entrada, constituindo o '
         'conjunto probatório completo do período de uso do imóvel.\n'
         '7.3 Ambos os laudos deverão ser arquivados pelas partes pelo prazo prescricional aplicável após o término da locação.'),

        _clausula8(),
        _clausula9(insp),
    ]


# MODELO 5 — Temporada + Imobiliária/Corretor
def _clausulas_modelo5(insp):
    creci = insp.get('corretor_creci') or '___'
    email_imob = insp.get('corretor_email') or insp.get('imobiliaria_email') or '___'
    return [
        ('CLÁUSULA 1ª — IDENTIFICAÇÃO E FINALIDADE',
         f'O presente Laudo de Vistoria de Temporada tem por finalidade registrar de forma detalhada o estado de '
         f'conservação e o inventário completo de móveis, utensílios e equipamentos do imóvel na data do check-in, '
         f'servindo como instrumento de prova para eventual comparação ao término da estadia.\n'
         f'Este laudo foi elaborado por vistoriador habilitado, com registro no CRECI nº {creci}, '
         f'utilizando recursos fotográficos e tecnológicos do sistema izyLAUDO.'),

        ('CLÁUSULA 2ª — INVENTÁRIO COMPLETO',
         '2.1 Por tratar-se de imóvel para locação de temporada, este laudo contempla inventário detalhado de todos '
         'os itens presentes, incluindo:\n'
         'a) Móveis e equipamentos de cada ambiente;\n'
         'b) Eletrodomésticos e eletrônicos;\n'
         'c) Utensílios de cozinha (talheres, pratos, copos, panelas e demais itens);\n'
         'd) Roupas de cama, banho e demais itens de enxoval;\n'
         'e) Itens decorativos e de uso comum.\n'
         '2.2 O inventário completo com quantidade, estado e registro fotográfico está na Parte 2 deste laudo.\n'
         '2.3 Itens não constantes neste inventário são presumidos como inexistentes no imóvel na data do check-in.'),

        ('CLÁUSULA 3ª — PRAZO DE MANIFESTAÇÃO DO HÓSPEDE',
         f'3.1 O hóspede/ocupante terá o prazo de 24 (vinte e quatro) horas, contadas do momento do check-in, para '
         f'apresentar por escrito qualquer contestação sobre itens não observados, omitidos ou divergentes do estado '
         f'registrado.\n'
         f'3.2 A manifestação deverá ser enviada ao e-mail — {email_imob} — com descrição clara e, preferencialmente, '
         f'registro fotográfico.\n'
         f'3.3 Decorrido o prazo sem manifestação, este laudo será considerado aceito integralmente, constituindo prova '
         f'plena do estado do imóvel e do inventário no momento do check-in.'),

        ('CLÁUSULA 4ª — RESPONSABILIDADES DO HÓSPEDE',
         '4.1 O hóspede/ocupante recebe o imóvel no estado descrito neste laudo e se compromete a:\n'
         'a) Zelar pelo imóvel, seus móveis, utensílios e equipamentos durante toda a estadia;\n'
         'b) Não realizar qualquer modificação no imóvel sem autorização expressa do anfitrião;\n'
         'c) Comunicar imediatamente ao anfitrião qualquer dano acidental ocorrido durante a estadia;\n'
         'd) Respeitar o número máximo de ocupantes indicado no contrato de reserva;\n'
         'e) Devolver o imóvel na data e hora do check-out nas mesmas condições em que o recebeu.\n'
         '4.2 Danos causados por mau uso, negligência ou imperícia do hóspede, seus acompanhantes ou animais de '
         'estimação são de sua exclusiva responsabilidade.\n'
         '4.3 A quebra, extravio ou dano de qualquer item do inventário será cobrada pelo valor de reposição ou '
         'reparo do item.'),

        ('CLÁUSULA 5ª — DANOS DURANTE A ESTADIA',
         '5.1 Ao término da estadia será realizada vistoria de saída comparando o estado atual com o registrado neste '
         'laudo de check-in.\n'
         '5.2 Danos identificados na vistoria de saída e ausentes neste laudo serão de responsabilidade do hóspede.\n'
         '5.3 O hóspede autoriza expressamente o débito do valor dos danos na caução ou garantia fornecida na reserva, '
         'caso exista.\n'
         '5.4 Não havendo caução suficiente, o hóspede se compromete a ressarcir o anfitrião no prazo de 5 (cinco) '
         'dias úteis após o check-out.'),

        ('CLÁUSULA 6ª — REGRAS DE USO E CONDIÇÕES DA ESTADIA',
         '6.1 O uso do imóvel, suas instalações, móveis e equipamentos pelo hóspede/ocupante deverá observar '
         'estritamente as regras e condições estabelecidas no contrato de reserva celebrado entre as partes, seja por '
         'plataforma digital (Airbnb, Booking, etc.) ou diretamente entre anfitrião e hóspede.\n'
         '6.2 O hóspede declara ter lido, compreendido e concordado com todas as regras de uso definidas no contrato de '
         'reserva, incluindo mas não se limitando a: capacidade máxima de ocupantes, política de animais de estimação, '
         'regras de silêncio, política de cancelamento e demais condições específicas do imóvel.\n'
         '6.3 O descumprimento de qualquer regra prevista no contrato de reserva poderá ensejar a rescisão imediata da '
         'estadia, sem direito a reembolso, além da responsabilização pelos danos causados.'),

        ('CLÁUSULA 7ª — INTEGRAÇÃO AO CONTRATO DE RESERVA',
         '7.1 Este laudo é parte integrante do contrato de reserva celebrado entre as partes, seja por plataforma digital '
         'ou diretamente entre anfitrião e hóspede.\n'
         '7.2 Em caso de divergência entre o contrato de reserva e este laudo no que se refere ao estado do imóvel e '
         'inventário, prevalecerão as disposições deste laudo.'),

        _clausula8(),
        _clausula9(insp),
    ]


# MODELO 6 — Temporada + Proprietário Direto
def _clausulas_modelo6(insp):
    email_loc = insp.get('locador_email') or '___'
    return [
        ('CLÁUSULA 1ª — IDENTIFICAÇÃO E FINALIDADE',
         'O presente Laudo de Vistoria de Temporada tem por finalidade registrar de forma detalhada o estado de '
         'conservação e o inventário completo de móveis, utensílios e equipamentos do imóvel na data do check-in, '
         'servindo como instrumento de prova para eventual comparação ao término da estadia.\n'
         'Esta vistoria foi realizada diretamente pelo anfitrião/proprietário do imóvel, utilizando recursos '
         'fotográficos e tecnológicos do sistema izyLAUDO.'),

        ('CLÁUSULA 2ª — INVENTÁRIO COMPLETO',
         '2.1 Por tratar-se de imóvel para locação de temporada, este laudo contempla inventário detalhado de todos '
         'os itens presentes, incluindo:\n'
         'a) Móveis e equipamentos de cada ambiente;\n'
         'b) Eletrodomésticos e eletrônicos;\n'
         'c) Utensílios de cozinha (talheres, pratos, copos, panelas e demais itens);\n'
         'd) Roupas de cama, banho e demais itens de enxoval;\n'
         'e) Itens decorativos e de uso comum.\n'
         '2.2 O inventário completo com quantidade, estado e registro fotográfico está na Parte 2 deste laudo.\n'
         '2.3 Itens não constantes neste inventário são presumidos como inexistentes no imóvel na data do check-in.'),

        ('CLÁUSULA 3ª — PRAZO DE MANIFESTAÇÃO DO HÓSPEDE',
         f'3.1 O hóspede/ocupante terá o prazo de 24 (vinte e quatro) horas, contadas do momento do check-in, para '
         f'apresentar por escrito qualquer contestação sobre itens não observados, omitidos ou divergentes do estado '
         f'registrado.\n'
         f'3.2 A manifestação deverá ser enviada ao e-mail — {email_loc} — com descrição clara e, preferencialmente, '
         f'registro fotográfico.\n'
         f'3.3 Decorrido o prazo sem manifestação, este laudo será considerado aceito integralmente, constituindo prova '
         f'plena do estado do imóvel e do inventário no momento do check-in.'),

        ('CLÁUSULA 4ª — RESPONSABILIDADES DO HÓSPEDE',
         '4.1 O hóspede/ocupante recebe o imóvel no estado descrito neste laudo e se compromete a:\n'
         'a) Zelar pelo imóvel, seus móveis, utensílios e equipamentos durante toda a estadia;\n'
         'b) Não realizar qualquer modificação no imóvel sem autorização expressa do anfitrião;\n'
         'c) Comunicar imediatamente ao anfitrião qualquer dano acidental ocorrido durante a estadia;\n'
         'd) Respeitar o número máximo de ocupantes indicado no contrato de reserva;\n'
         'e) Devolver o imóvel na data e hora do check-out nas mesmas condições em que o recebeu.\n'
         '4.2 Danos causados por mau uso, negligência ou imperícia do hóspede, seus acompanhantes ou animais de '
         'estimação são de sua exclusiva responsabilidade.\n'
         '4.3 A quebra, extravio ou dano de qualquer item do inventário será cobrada pelo valor de reposição ou '
         'reparo do item.'),

        ('CLÁUSULA 5ª — DANOS DURANTE A ESTADIA',
         '5.1 Ao término da estadia será realizada vistoria de saída comparando o estado atual com o registrado neste '
         'laudo de check-in.\n'
         '5.2 Danos identificados na vistoria de saída e ausentes neste laudo serão de responsabilidade do hóspede.\n'
         '5.3 O hóspede autoriza expressamente o débito do valor dos danos na caução ou garantia fornecida na reserva, '
         'caso exista.\n'
         '5.4 Não havendo caução suficiente, o hóspede se compromete a ressarcir o anfitrião no prazo de 5 (cinco) '
         'dias úteis após o check-out.'),

        ('CLÁUSULA 6ª — REGRAS DE USO E CONDIÇÕES DA ESTADIA',
         '6.1 O uso do imóvel, suas instalações, móveis e equipamentos pelo hóspede/ocupante deverá observar '
         'estritamente as regras e condições estabelecidas no contrato de reserva celebrado entre as partes, seja por '
         'plataforma digital (Airbnb, Booking, etc.) ou diretamente entre anfitrião e hóspede.\n'
         '6.2 O hóspede declara ter lido, compreendido e concordado com todas as regras de uso definidas no contrato de '
         'reserva, incluindo mas não se limitando a: capacidade máxima de ocupantes, política de animais de estimação, '
         'regras de silêncio, política de cancelamento e demais condições específicas do imóvel.\n'
         '6.3 O descumprimento de qualquer regra prevista no contrato de reserva poderá ensejar a rescisão imediata da '
         'estadia, sem direito a reembolso, além da responsabilização pelos danos causados.'),

        ('CLÁUSULA 7ª — INTEGRAÇÃO AO CONTRATO DE RESERVA',
         '7.1 Este laudo é parte integrante do contrato de reserva celebrado entre as partes, seja por plataforma digital '
         'ou diretamente entre anfitrião e hóspede.\n'
         '7.2 Em caso de divergência entre o contrato de reserva e este laudo no que se refere ao estado do imóvel e '
         'inventário, prevalecerão as disposições deste laudo.'),

        _clausula8(),
        _clausula9(insp),
    ]


def get_clausulas(model, insp):
    """Retorna lista de cláusulas para o modelo selecionado."""
    funcs = {
        1: _clausulas_modelo1,
        2: _clausulas_modelo2,
        3: _clausulas_modelo3,
        4: _clausulas_modelo4,
        5: _clausulas_modelo5,
        6: _clausulas_modelo6,
    }
    return funcs.get(model, _clausulas_modelo1)(insp)


# ─── ESTILOS ─────────────────────────────────────────────────────────────────
def get_styles():
    def ps(name, **kw):
        defaults = dict(fontName=FONT_MAIN, fontSize=FS, leading=FS * 1.5,
                        textColor=DARK_TEXT, alignment=TA_LEFT)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    return {
        'Normal':      ps('Normal', alignment=TA_JUSTIFY),
        'Title':       ps('Title', fontName=FONT_BOLD, fontSize=16, leading=20,
                          alignment=TA_CENTER, spaceBefore=4, spaceAfter=4),
        'SubTitle':    ps('SubTitle', fontName=FONT_MAIN, fontSize=9, leading=11,
                          textColor=GRAY, alignment=TA_CENTER, spaceAfter=6),
        'Section':     ps('Section', fontName=FONT_BOLD, fontSize=13, leading=16,
                          textColor=IZY_BLUE, spaceBefore=14, spaceAfter=6),
        'FieldLabel':  ps('FieldLabel', fontName=FONT_BOLD, fontSize=8, leading=10,
                          textColor=GRAY, spaceAfter=1),
        'FieldValue':  ps('FieldValue', fontSize=FS, leading=FS * 1.4),
        'RoomTitle':   ps('RoomTitle', fontName=FONT_BOLD, fontSize=13, leading=16,
                          spaceBefore=10, spaceAfter=4),
        'ItemName':    ps('ItemName', fontName=FONT_BOLD, fontSize=FS, leading=14),
        'Condition':   ps('Condition', fontName=FONT_BOLD, fontSize=9, leading=11,
                          textColor=GRAY),
        'IADesc':      ps('IADesc', fontName=FONT_ITALIC, fontSize=10, leading=13,
                          textColor=DARK_TEXT, alignment=TA_JUSTIFY),
        'Obs':         ps('Obs', fontName=FONT_ITALIC, fontSize=10, leading=13,
                          textColor=GRAY, alignment=TA_JUSTIFY, spaceAfter=4),
        'ClauseTitle': ps('ClauseTitle', fontName=FONT_BOLD, fontSize=FS, leading=14,
                          spaceBefore=10, spaceAfter=3),
        'ClauseText':  ps('ClauseText', fontSize=FS, leading=FS * 1.6,
                          alignment=TA_JUSTIFY, spaceAfter=6),
        'SignLabel':   ps('SignLabel', fontName=FONT_BOLD, fontSize=FS, leading=14,
                          alignment=TA_CENTER),
        'SignSub':     ps('SignSub', fontSize=9, leading=11, textColor=GRAY,
                          alignment=TA_CENTER),
        'Small':       ps('Small', fontSize=9, leading=11, textColor=GRAY),
        'FotoNum':     ps('FotoNum', fontSize=7, leading=9, textColor=GRAY,
                          alignment=TA_CENTER),
    }


# ─── CANVAS CALLBACK — CABEÇALHO E RODAPÉ ───────────────────────────────────
def _draw_header_footer(canvas, doc, inspection):
    canvas.saveState()
    w, h = A4
    lm = 3 * cm
    rm = 2 * cm

    # ── Cabeçalho ──
    logo_y = h - 1.7 * cm

    canvas.setFont(FONT_BOLD, 24)
    canvas.setFillColor(IZY_BLUE)
    izy_w = canvas.stringWidth('izy', FONT_BOLD, 24)
    canvas.drawString(lm, logo_y, 'izy')

    canvas.setFillColor(DARK_TEXT)
    canvas.drawString(lm + izy_w, logo_y, 'LAUDO')

    tipo = tipo_label(inspection)
    canvas.setFont(FONT_MAIN, 8)
    canvas.setFillColor(GRAY)
    canvas.drawRightString(w - rm, logo_y + 4, f'LAUDO DE VISTORIA DE {tipo}')
    canvas.drawRightString(w - rm, logo_y - 8, f'Página {doc.page}')

    canvas.setStrokeColor(IZY_BLUE)
    canvas.setLineWidth(1.5)
    canvas.line(lm, h - 2.2 * cm, w - rm, h - 2.2 * cm)

    # ── Rodapé ──
    canvas.setStrokeColor(LINE_COL)
    canvas.setLineWidth(0.5)
    canvas.line(lm, 1.8 * cm, w - rm, 1.8 * cm)

    footer = 'Documento gerado pelo sistema izyLAUDO · Assinatura digital via Autentique'
    canvas.setFont(FONT_MAIN, 8)
    canvas.setFillColor(GRAY)
    canvas.drawCentredString(w / 2, 1.2 * cm, footer)

    canvas.restoreState()


# ─── COMPONENTES REUTILIZÁVEIS ───────────────────────────────────────────────
def section_header(title, styles):
    return Paragraph(title, styles['Section'])


def field_row(pairs, styles, col_widths=None):
    """Renderiza uma linha de campos label+valor."""
    cells = []
    for label, value, is_email in pairs:
        v = value if is_email else upper(str(value) if value else '')
        cell = [
            Paragraph(label, styles['FieldLabel']),
            Paragraph(v if v else '—', styles['FieldValue'])
        ]
        cells.append(cell)
    if not col_widths:
        cw = 14 * cm / max(len(pairs), 1)
        col_widths = [cw] * len(pairs)
    t = Table([cells], colWidths=col_widths)
    t.setStyle(TableStyle([
        ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',     (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 5),
        ('LEFTPADDING',    (0, 0), (-1, -1), 7),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 7),
        ('BACKGROUND',     (0, 0), (-1, -1), LIGHT_BG),
        ('LINEBELOW',      (0, 0), (-1, -1), 0.5, LINE_COL),
        ('BOX',            (0, 0), (-1, -1), 0.3, LINE_COL),
    ]))
    return t


def _load_image(photo_data, width_cm, height_cm):
    """Decodifica base64 e retorna Image do reportlab ou None."""
    try:
        data = photo_data
        if ',' in data:
            data = data.split(',', 1)[1]
        raw = base64.b64decode(data)
        buf = io.BytesIO(raw)
        pil = PILImage.open(buf)
        pil = pil.convert('RGB')
        pil.thumbnail((int(width_cm * 118), int(height_cm * 118)), PILImage.LANCZOS)
        out = io.BytesIO()
        pil.save(out, format='JPEG', quality=80, optimize=True)
        out.seek(0)
        return Image(out, width=width_cm * cm, height=height_cm * cm)
    except Exception:
        return None


def _parse_people(json_str, fallback_name, fallback_cpf, fallback_phone, fallback_email):
    """Tenta parsear JSON de pessoas; usa campos únicos como fallback."""
    if json_str:
        try:
            lst = json.loads(json_str)
            if lst:
                return lst
        except Exception:
            pass
    if fallback_name:
        return [{'name': fallback_name, 'cpf': fallback_cpf or '',
                 'phone': fallback_phone or '', 'email': fallback_email or ''}]
    return []


# ─── FUNÇÃO PRINCIPAL ────────────────────────────────────────────────────────
def generate_pdf(inspection_data: dict, rooms_data: list,
                 signatures_data: list, output_path: str) -> bool:
    """
    Gera o Laudo de Vistoria em PDF.
    Mantém assinatura compatível com GeneratePDFHandler em server.py.
    """
    try:
        insp = inspection_data
        model = select_model(insp)
        styles = get_styles()

        def on_page(canvas, doc):
            _draw_header_footer(canvas, doc, insp)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=3 * cm,
            rightMargin=2 * cm,
            topMargin=3 * cm,
            bottomMargin=2 * cm,
            title='Laudo de Vistoria — izyLAUDO',
            author='izyLAUDO',
        )

        story = []

        # ── Título ────────────────────────────────────────────────────────
        tipo_str = tipo_label(insp)
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(f'LAUDO DE VISTORIA DE {tipo_str}', styles['Title']))
        story.append(Paragraph(f'Modelo {model}', styles['SubTitle']))
        story.append(HRFlowable(width='100%', thickness=1.5, color=IZY_BLUE, spaceAfter=6))
        story.append(Spacer(1, 0.3 * cm))

        # ─────────────────────────────────────────────────────────────────
        # PARTE 1 — QUALIFICAÇÃO
        # ─────────────────────────────────────────────────────────────────
        story.append(section_header('PARTE 1 — QUALIFICAÇÃO', styles))
        story.append(Spacer(1, 0.2 * cm))

        # 1.1 Dados do imóvel
        story.append(Paragraph('1.1 DADOS DO IMÓVEL', styles['ClauseTitle']))
        story.append(field_row([
            ('ENDEREÇO COMPLETO', insp.get('property_address', ''), False),
        ], styles, [14 * cm]))
        story.append(field_row([
            ('TIPO DE IMÓVEL',    insp.get('property_type', ''),  False),
            ('ÁREA APROXIMADA',   insp.get('property_area', ''),  False),
            ('DATA DA VISTORIA',  insp.get('inspection_date', datetime.now().strftime('%d/%m/%Y')), False),
        ], styles, [5.5 * cm, 4.5 * cm, 4 * cm]))
        story.append(Spacer(1, 0.3 * cm))

        # Campos adicionais para saída
        if model in (3, 4):
            story.append(field_row([
                ('DATA DA VISTORIA DE ENTRADA', insp.get('data_vistoria_entrada', ''), False),
                ('PERÍODO DE LOCAÇÃO', insp.get('periodo_locacao', ''), False),
            ], styles, [7 * cm, 7 * cm]))
            story.append(Spacer(1, 0.2 * cm))

        # Campos adicionais para temporada
        if model in (5, 6):
            story.append(field_row([
                ('CHECK-IN', insp.get('data_checkin', ''), False),
                ('CHECK-OUT', insp.get('data_checkout', ''), False),
                ('Nº HÓSPEDES', insp.get('num_hospedes', ''), False),
                ('PLATAFORMA', insp.get('plataforma', ''), False),
            ], styles, [3.5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm]))
            story.append(Spacer(1, 0.2 * cm))

        # 1.2 Imobiliária/Corretor (apenas modelos 1, 3, 5)
        if model in (1, 3, 5):
            story.append(Paragraph('1.2 IMOBILIÁRIA / CORRETOR', styles['ClauseTitle']))
            imob_name  = insp.get('imobiliaria_name') or insp.get('corretor_name') or ''
            imob_cnpj  = insp.get('imobiliaria_cnpj') or ''
            imob_creci = insp.get('corretor_creci') or ''
            imob_phone = insp.get('imobiliaria_phone') or insp.get('corretor_phone') or ''
            imob_email = insp.get('corretor_email') or ''
            imob_addr  = insp.get('imobiliaria_address') or ''
            story.append(field_row([
                ('NOME / RAZÃO SOCIAL', imob_name,  False),
                ('CNPJ / CPF',          imob_cnpj,  False),
            ], styles, [8 * cm, 6 * cm]))
            story.append(field_row([
                ('CRECI',    imob_creci,  False),
                ('TELEFONE', imob_phone,  False),
                ('E-MAIL',   imob_email,  True),
            ], styles, [4 * cm, 5 * cm, 5 * cm]))
            if imob_addr:
                story.append(field_row([('ENDEREÇO', imob_addr, False)], styles, [14 * cm]))
            story.append(Spacer(1, 0.3 * cm))
            next_section = '1.3'
        else:
            next_section = '1.2'

        # Locadores
        locadores = _parse_people(
            insp.get('locadores_json'),
            insp.get('locador_name'), insp.get('locador_cpf'),
            insp.get('locador_phone'), insp.get('locador_email')
        )
        if locadores:
            loc_title = 'LOCADOR(ES) — PROPRIETÁRIO' if model in (2, 4) else (
                'LOCADOR / ANFITRIÃO' if model in (5, 6) else 'LOCADOR(ES) / PROPRIETÁRIO(S)')
            story.append(Paragraph(f'{next_section} {loc_title}', styles['ClauseTitle']))
            for i, loc in enumerate(locadores):
                story.append(field_row([
                    ('NOME COMPLETO', loc.get('name', ''), False),
                    ('CPF',           loc.get('cpf', ''),  False),
                ], styles, [8 * cm, 6 * cm]))
                story.append(field_row([
                    ('TELEFONE', loc.get('phone', ''), False),
                    ('E-MAIL',   loc.get('email', ''), True),
                ], styles, [5 * cm, 9 * cm]))
                if i < len(locadores) - 1:
                    story.append(Spacer(1, 0.15 * cm))
            story.append(Spacer(1, 0.3 * cm))

        next_section2 = str(int(next_section.split('.')[-1]) + 1)
        next_section2 = f'1.{next_section2}'

        # Locatários / Hóspedes
        locatarios = _parse_people(
            insp.get('locatarios_json'),
            insp.get('locatario_name'), insp.get('locatario_cpf'),
            insp.get('locatario_phone'), insp.get('locatario_email')
        )
        if locatarios:
            loc_tipo = 'HÓSPEDE(S) / OCUPANTE(S)' if model in (5, 6) else 'LOCATÁRIO(S)'
            story.append(Paragraph(f'{next_section2} {loc_tipo}', styles['ClauseTitle']))
            for i, loc in enumerate(locatarios):
                story.append(field_row([
                    ('NOME COMPLETO', loc.get('name', ''), False),
                    ('CPF',           loc.get('cpf', ''),  False),
                ], styles, [8 * cm, 6 * cm]))
                story.append(field_row([
                    ('TELEFONE', loc.get('phone', ''), False),
                    ('E-MAIL',   loc.get('email', ''), True),
                ], styles, [5 * cm, 9 * cm]))
                if i < len(locatarios) - 1:
                    story.append(Spacer(1, 0.15 * cm))
            story.append(Spacer(1, 0.3 * cm))

        # ─────────────────────────────────────────────────────────────────
        # PARTE 2 — VISTORIA DOS AMBIENTES
        # ─────────────────────────────────────────────────────────────────
        parte2_title = 'PARTE 2 — INVENTÁRIO E VISTORIA' if model in (5, 6) else 'PARTE 2 — VISTORIA DOS AMBIENTES'
        story.append(section_header(parte2_title, styles))

        foto_num = 1
        for room in rooms_data:
            room_name = upper(room.get('name') or room.get('room_name', ''))
            story.append(Paragraph(room_name, styles['RoomTitle']))

            items = room.get('items', [])
            for item in items:
                item_name = upper(item.get('name') or item.get('item_name', ''))
                condition = upper(item.get('condition', ''))
                story.append(Paragraph(item_name, styles['ItemName']))

                if condition:
                    cond_color = '#22c55e' if 'BOM' in condition.upper() else (
                           '#f59e0b' if 'REGULAR' in condition.upper() else '#ef4444')
                    story.append(Paragraph(
                        f'<font color="{cond_color}">Estado: {condition}</font>',
                        styles['Condition']))

                ai_desc = item.get('ai_description') or item.get('description', '')
                if ai_desc:
                    story.append(Paragraph(ai_desc, styles['IADesc']))

                obs = item.get('observations', '')
                if obs:
                    story.append(Paragraph(f'Obs: {obs}', styles['Obs']))

                # Fotos do item
                photos = item.get('photos', [])
                if photos:
                    photo_cells = []
                    for photo in photos[:4]:
                        photo_data = photo if isinstance(photo, str) else photo.get('data', '')
                        if photo_data:
                            img = _load_image(photo_data, 3.2, 2.4)
                            if img:
                                photo_cells.append([
                                    img,
                                    Paragraph(f'Foto {foto_num}', styles['FotoNum'])
                                ])
                                foto_num += 1

                    if photo_cells:
                        ncols = min(len(photo_cells), 4)
                        col_w = 3.5 * cm
                        pt = Table([photo_cells], colWidths=[col_w] * ncols)
                        pt.setStyle(TableStyle([
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
                            ('TOPPADDING', (0, 0), (-1, -1), 3),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ]))
                        story.append(pt)

                story.append(Spacer(1, 0.3 * cm))
            story.append(Spacer(1, 0.2 * cm))

        # ─────────────────────────────────────────────────────────────────
        # PARTE 3 — CLÁUSULAS
        # ────────────────────────────────────────────────────────────────
        story.append(PageBreak())
        story.append(section_header('PARTE 3 — CLÁUSULAS', styles))

        clausulas = get_clausulas(model, insp)
        for titulo, texto in clausulas:
            story.append(Paragraph(titulo, styles['ClauseTitle']))
            texto_html = texto.replace('\n', '<br/>')
            story.append(Paragraph(texto_html, styles['ClauseText']))

        # ─────────────────────────────────────────────────────────────────
        # PARTE 4 — ASSINATURAS
        # ─────────────────────────────────────────────────────────────────
        story.append(Spacer(1, 1 * cm))
        story.append(section_header('PARTE 4 — ASSINATURAS', styles))

        cidade = insp.get('property_city') or '___'
        data_ext = insp.get('inspection_date') or datetime.now().strftime('%d/%m/%Y')
        story.append(Paragraph(f'{upper(cidade)}, {data_ext}', styles['Normal']))
        story.append(Spacer(1, 0.5 * cm))

        decl = ('As partes declaram ter lido e compreendido integralmente este laudo, '
                'cientes de que é parte integrante do contrato de locação/reserva.')
        story.append(Paragraph(decl, styles['ClauseText']))
        story.append(Spacer(1, 0.8 * cm))

        # Blocos de assinatura
        sig_blocks = []

        for loc in locadores:
            nome = upper(loc.get('name', ''))
            cpf = loc.get('cpf', '')
            role = 'Anfitrião/Locador' if model in (5, 6) else 'Locador'
            sig_blocks.append((nome, f'{role} · CPF: {cpf}'))

        for loc in locatarios:
            nome = upper(loc.get('name', ''))
            cpf = loc.get('cpf', '')
            role = 'Hóspede/Ocupante' if model in (5, 6) else 'Locatário'
            sig_blocks.append((nome, f'{role} · CPF: {cpf}'))

        if model in (1, 3, 5):
            v_name = upper(insp.get('imobiliaria_name') or insp.get('corretor_name') or '')
            v_creci = insp.get('corretor_creci') or ''
            sig_blocks.append((v_name, f'Vistoriador/Corretor · CRECI: {v_creci}'))

        for nome, sub in sig_blocks:
            story.append(Spacer(1, 0.8 * cm))
            story.append(Paragraph('_' * 50, styles['SignLabel']))
            story.append(Paragraph(nome, styles['SignLabel']))
            story.append(Paragraph(sub, styles['SignSub']))

        # Build PDF
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False
