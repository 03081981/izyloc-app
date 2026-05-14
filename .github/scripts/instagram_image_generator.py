#!/usr/bin/env python3
"""
Instagram Image Generator — Push 102b

Gera imagens 1080x1080 para Instagram em 2 formatos:
- Formato A (single post): logo + titulo + 3-4 bullets + CTA
- Formato B (carrossel 5 slides): capa + 3 secoes + CTA final

Identidade visual:
- Azul izyLAUDO: #1B4FBB
- Branco: #FFFFFF
- Logo izyLAUDO (PNG transparente) em automation/assets/

Fontes: tenta DejaVu/Liberation do sistema Linux (disponivel no
GitHub Actions ubuntu-latest).
"""

import io
import requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Cores oficiais
COR_AZUL = (27, 79, 187)      # #1B4FBB
COR_AZUL_ESCURO = (15, 49, 117)
COR_BRANCO = (255, 255, 255)
COR_CINZA_TEXTO = (45, 55, 72)
COR_CINZA_CLARO = (107, 114, 128)

LOGO_PATH = Path(__file__).parent.parent.parent / "automation" / "assets" / "izylaudo-logo-transparente.png"


# ---------- HELPERS ----------
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Carrega fonte do sistema. Tenta DejaVu Sans (padrao Ubuntu)."""
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """Quebra texto em linhas que cabem em max_width."""
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def paste_logo(img: Image.Image, position: str = "top", width: int = 220) -> None:
    """Cola a logo izyLAUDO em cima da imagem. Position: 'top', 'top-left', 'center'."""
    if not LOGO_PATH.exists():
        return
    logo = Image.open(LOGO_PATH).convert("RGBA")
    # Aspect ratio original 336x110 ~= 3.05:1
    new_h = int(width * logo.height / logo.width)
    logo = logo.resize((width, new_h), Image.LANCZOS)
    iw, ih = img.size
    if position == "top":
        pos = ((iw - width) // 2, 70)
    elif position == "top-left":
        pos = (60, 60)
    elif position == "center":
        pos = ((iw - width) // 2, (ih - new_h) // 2)
    else:
        pos = ((iw - width) // 2, ih - new_h - 80)
    img.paste(logo, pos, logo)


def draw_centered_lines(draw: ImageDraw.Draw, lines: list[str], font: ImageFont.FreeTypeFont,
                       y_start: int, w_total: int, color: tuple, line_height: int = None) -> int:
    """Desenha linhas centralizadas horizontalmente. Retorna y final."""
    if line_height is None:
        bbox = draw.textbbox((0, 0), "Ay", font=font)
        line_height = bbox[3] - bbox[1] + 14
    y = y_start
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        draw.text(((w_total - lw) // 2, y), line, fill=color, font=font)
        y += line_height
    return y


# ---------- FORMATO A — SINGLE POST ----------
def generate_format_a(title: str, bullets: list[str], output_path: Path) -> Path:
    """Single post 1080x1080 sobre fundo branco.
    - Logo no topo
    - Titulo grande em azul
    - 3-4 bullets em cinza
    - CTA 'Link na bio' no rodape
    """
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), COR_BRANCO)
    draw = ImageDraw.Draw(img)

    # Logo topo
    paste_logo(img, position="top", width=280)

    # Linha decorativa azul
    draw.rectangle([(W // 2 - 60, 220), (W // 2 + 60, 226)], fill=COR_AZUL)

    # Titulo
    font_title = load_font(58, bold=True)
    title_lines = wrap_text(title, font_title, W - 140, draw)[:3]
    y = 280
    y = draw_centered_lines(draw, title_lines, font_title, y, W, COR_AZUL_ESCURO, line_height=78)

    # Bullets
    font_bullet = load_font(40, bold=False)
    y += 50
    for bullet in bullets[:4]:
        bullet_text = f"→  {bullet}"
        wrapped = wrap_text(bullet_text, font_bullet, W - 180, draw)[:2]
        # Desenha alinhado a esquerda com padding
        for line in wrapped:
            draw.text((90, y), line, fill=COR_CINZA_TEXTO, font=font_bullet)
            y += 56
        y += 18

    # CTA rodape: faixa azul
    draw.rectangle([(0, H - 160), (W, H)], fill=COR_AZUL)
    font_cta = load_font(44, bold=True)
    cta = "Link na bio para ler o artigo completo"
    cta_lines = wrap_text(cta, font_cta, W - 100, draw)[:2]
    cta_total_h = len(cta_lines) * 54
    y_cta = H - 160 + (160 - cta_total_h) // 2
    draw_centered_lines(draw, cta_lines, font_cta, y_cta, W, COR_BRANCO, line_height=54)

    img.save(output_path, "JPEG", quality=92, optimize=True)
    return output_path


# ---------- FORMATO B — CARROSSEL ----------
def _fetch_image(url: str) -> Image.Image:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def _cover_fit(img: Image.Image, w: int, h: int) -> Image.Image:
    iw, ih = img.size
    ratio = max(w / iw, h / ih)
    new = img.resize((int(iw * ratio), int(ih * ratio)), Image.LANCZOS)
    left = (new.width - w) // 2
    top = (new.height - h) // 2
    return new.crop((left, top, left + w, top + h))


def generate_format_b_cover(title: str, image_url: str, output_path: Path) -> Path:
    """Slide 1 (capa): imagem de fundo Unsplash + overlay escuro + titulo branco + logo + DESLIZE."""
    W, H = 1080, 1080
    try:
        bg = _fetch_image(image_url)
        bg = _cover_fit(bg, W, H)
    except Exception:
        bg = Image.new("RGB", (W, H), COR_AZUL_ESCURO)

    # Overlay escuro pra contraste (40% black)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 110))
    bg_rgba = bg.convert("RGBA")
    composed = Image.alpha_composite(bg_rgba, overlay).convert("RGB")
    draw = ImageDraw.Draw(composed)

    # Logo topo
    paste_logo(composed, position="top", width=280)

    # Titulo grande centralizado
    font_title = load_font(80, bold=True)
    title_lines = wrap_text(title, font_title, W - 140, draw)[:4]
    total_h = len(title_lines) * 100
    y_start = (H - total_h) // 2 + 20
    draw_centered_lines(draw, title_lines, font_title, y_start, W, COR_BRANCO, line_height=100)

    # Rodape: DESLIZE →
    font_swipe = load_font(38, bold=True)
    swipe = "DESLIZE   →"
    bbox = draw.textbbox((0, 0), swipe, font=font_swipe)
    sw = bbox[2] - bbox[0]
    draw.text(((W - sw) // 2, H - 110), swipe, fill=COR_BRANCO, font=font_swipe)

    composed.save(output_path, "JPEG", quality=92, optimize=True)
    return output_path


def generate_format_b_section(idx: int, total: int, section_title: str,
                              section_body: str, output_path: Path) -> Path:
    """Slide intermediario (2 a total-1): fundo azul, titulo + texto branco, indicador N/total."""
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), COR_AZUL)
    draw = ImageDraw.Draw(img)

    # Logo top-left (pequena)
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        # versao branca por inversao: forca alfa ja existe, mas a logo tem texto azul
        # Vamos usar como esta — em fundo azul, texto azul some, entao usamos texto branco overlay
        logo_w = 140
        logo_h = int(logo_w * logo.height / logo.width)
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        # Como a logo tem texto azul, em fundo azul nao aparece. Vamos converter pra branco:
        logo_arr = logo.copy()
        # Substitui pixels nao-transparentes por branco mantendo alfa
        pixels = logo_arr.load()
        for x in range(logo_arr.width):
            for y in range(logo_arr.height):
                r, g, b, a = pixels[x, y]
                if a > 50:
                    pixels[x, y] = (255, 255, 255, a)
        img.paste(logo_arr, (60, 60), logo_arr)

    # Indicador slide N / total (canto superior direito)
    font_idx = load_font(30, bold=True)
    idx_text = f"{idx} / {total}"
    bbox = draw.textbbox((0, 0), idx_text, font=font_idx)
    iw = bbox[2] - bbox[0]
    draw.text((W - iw - 60, 75), idx_text, fill=COR_BRANCO, font=font_idx)

    # Titulo da secao
    font_section_title = load_font(64, bold=True)
    title_lines = wrap_text(section_title, font_section_title, W - 140, draw)[:3]
    y = 220
    y = draw_centered_lines(draw, title_lines, font_section_title, y, W, COR_BRANCO, line_height=82)

    # Linha decorativa branca
    y += 30
    draw.rectangle([(W // 2 - 80, y), (W // 2 + 80, y + 6)], fill=COR_BRANCO)
    y += 50

    # Body
    font_body = load_font(40, bold=False)
    body_lines = wrap_text(section_body, font_body, W - 160, draw)[:9]
    draw_centered_lines(draw, body_lines, font_body, y, W, COR_BRANCO, line_height=58)

    img.save(output_path, "JPEG", quality=92, optimize=True)
    return output_path


def generate_format_b_cta(cta_text: str, output_path: Path) -> Path:
    """Slide final: fundo branco + logo grande central + CTA em azul + 'Link na bio'."""
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), COR_BRANCO)
    draw = ImageDraw.Draw(img)

    # Logo grande no topo-centro
    paste_logo(img, position="top", width=420)

    # Linha decorativa
    draw.rectangle([(W // 2 - 80, 290), (W // 2 + 80, 298)], fill=COR_AZUL)

    # CTA texto
    font_cta = load_font(60, bold=True)
    cta_lines = wrap_text(cta_text, font_cta, W - 140, draw)[:4]
    y = 380
    y = draw_centered_lines(draw, cta_lines, font_cta, y, W, COR_AZUL_ESCURO, line_height=82)

    # "Link na bio 🔗" — destaque
    draw.rectangle([(0, H - 180), (W, H)], fill=COR_AZUL)
    font_link = load_font(54, bold=True)
    link = "Link na bio para acessar"
    link_lines = wrap_text(link, font_link, W - 100, draw)[:2]
    link_total_h = len(link_lines) * 66
    y_link = H - 180 + (180 - link_total_h) // 2
    draw_centered_lines(draw, link_lines, font_link, y_link, W, COR_BRANCO, line_height=66)

    img.save(output_path, "JPEG", quality=92, optimize=True)
    return output_path


def generate_carousel(cover_title: str, sections: list[dict], cta_text: str,
                      cover_image_url: str, output_dir: Path, slug: str) -> list[Path]:
    """Gera os 5 slides do carrossel.
    Estrutura: 1 capa + N secoes (recomendado 3) + 1 CTA = 5 slides padrao.
    Retorna lista de Path em ordem de publicacao.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    total = 1 + len(sections) + 1

    # Slide 1 — capa
    p1 = output_dir / f"{slug}-01-cover.jpg"
    generate_format_b_cover(cover_title, cover_image_url, p1)
    paths.append(p1)

    # Slides 2 ... N+1 — secoes
    for i, sec in enumerate(sections, start=2):
        p = output_dir / f"{slug}-{i:02d}-section.jpg"
        generate_format_b_section(i, total, sec.get("title", ""), sec.get("body", ""), p)
        paths.append(p)

    # Slide final — CTA
    p_final = output_dir / f"{slug}-{total:02d}-cta.jpg"
    generate_format_b_cta(cta_text, p_final)
    paths.append(p_final)
    return paths


# ---------- SMOKE TEST ----------
if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/ig-test")
    out.mkdir(parents=True, exist_ok=True)
    # Formato A
    generate_format_a(
        "Vistoria com IA: o que muda no seu fluxo de trabalho",
        [
            "Tempo cai de 3 horas para 20 minutos",
            "Menos erro humano em descricoes",
            "Laudo gerado automaticamente em PDF",
            "Funciona sem internet apos download",
        ],
        out / "format_a.jpg",
    )
    # Formato B
    generate_carousel(
        cover_title="Laudo de vistoria no Word vs com IA",
        sections=[
            {"title": "Word: 3 horas em media", "body": "Voce tira foto, abre laptop, escreve manualmente cada ambiente, formata tabela, exporta PDF. Pelo menos 3 horas por imovel."},
            {"title": "izyLAUDO: 20 minutos", "body": "Voce tira foto e a IA descreve cada ambiente sozinha. Voce so revisa, edita pontos especificos e exporta o PDF profissional."},
            {"title": "Diferenca real: 9x mais rapido", "body": "Em uma semana, voce faz 30 vistorias com o izyLAUDO contra apenas 3 com o metodo manual no Word. E sem o desgaste mental."},
        ],
        cta_text="Cadastre-se gratis e teste agora.",
        cover_image_url="https://www.izylaudo.com.br/static/site/images/og-image.jpg",
        output_dir=out,
        slug="test-carousel",
    )
    print(f"OK — imagens em {out}")
