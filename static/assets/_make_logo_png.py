#!/usr/bin/env python3
"""Gera izylaudo-logo-pdf.png a partir do SVG oficial.

Desenha o mesmo layout do SVG mas com cores pensadas para fundo branco
do PDF (LAUDO em navy ao inves de branco, tagline em cinza medio).
Renderizado em alta resolucao (4x scale) para anti-aliasing.
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(OUT_DIR, 'izylaudo-logo-pdf.png')

# SVG original: viewBox 220x55, fonte Arial 28pt bold/light, tagline 10pt
# Usamos Liberation Sans (clone metricamente compativel com Arial)
FONT_BOLD = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
FONT_REG = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'

# Alta resolucao para PDF (scale 4x), tamanho final ~440x110
SCALE = 4
W, H = 220 * SCALE, 55 * SCALE
img = Image.new('RGBA', (W, H), (255, 255, 255, 0))
d = ImageDraw.Draw(img)

# Cores para PDF (fundo branco):
#  - izy: #2d7dd2 (mantido - azul da marca)
#  - LAUDO: #1a2540 (navy do tema) em vez de branco
#  - tagline: #8898aa (cinza medio) em vez de white-60
font_size_main = 28 * SCALE
font_size_tag = 10 * SCALE
fb = ImageFont.truetype(FONT_BOLD, font_size_main)
fr = ImageFont.truetype(FONT_REG, font_size_main)
ft = ImageFont.truetype(FONT_REG, font_size_tag)

# Baseline do texto principal: y=32 no SVG
baseline_y = 32 * SCALE
# PIL .text usa top-left como referencia, entao convertemos
# usando getbbox para o ascent da fonte
_ax, _ay, _bx, _by = fb.getbbox('izy')
ascent = -_ay  # offset negativo
top_main = baseline_y - (_by - _ay) - _ay

# "izy" bold azul em x=0
x_cursor = 0 * SCALE
d.text((x_cursor, top_main), 'izy', fill='#2d7dd2', font=fb)
w_izy = fb.getbbox('izy')[2]

# "LAUDO" light navy imediatamente apos
d.text((x_cursor + w_izy, top_main), 'LAUDO', fill='#1a2540', font=fr)

# Tagline "Vistorias Imobiliárias" em x=41, y=48 no SVG (baseline)
tag = 'Vistorias Imobiliárias'
_t0, _t1, _t2, _t3 = ft.getbbox(tag)
top_tag = 48 * SCALE - (_t3 - _t1) - _t1
d.text((41 * SCALE, top_tag), tag, fill='#8898aa', font=ft)

# Salva com fundo transparente mas achatado em branco para o PDF
# (o cabecalho do PDF e branco, entao transparente funciona tambem)
img.save(OUT, 'PNG', optimize=True)
print('Saved:', OUT, img.size)
