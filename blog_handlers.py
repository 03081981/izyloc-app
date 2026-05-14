"""
Blog handlers - Push 75 (Fase 1)
================================
Sistema de blog com posts em markdown no filesystem.

Posts ficam em static/site/blog/posts/*.md
Cada .md tem frontmatter YAML + conteudo markdown.

Rotas:
  GET /blog                 -> lista de posts (BlogIndexHandler)
  GET /blog/(slug)          -> post individual (BlogPostHandler)
  GET /blog/categoria/(c)   -> posts da categoria (BlogCategoryHandler)
  GET /blog/rss.xml         -> feed RSS (BlogRSSHandler)

Renderiza HTML inline reusando o CSS/identidade do site institucional.
"""

import os
import re
from datetime import datetime
from html import escape as html_escape
from pathlib import Path

import markdown
import tornado.web
import yaml

# Caminho absoluto pra pasta de posts
BLOG_POSTS_DIR = Path(__file__).parent / 'static' / 'site' / 'blog' / 'posts'

# Categorias suportadas (slug -> label)
CATEGORIES = {
    'vistoria-imobiliaria': 'Vistoria Imobiliária',
    'lei-do-inquilinato': 'Lei do Inquilinato',
    'mercado-imobiliario': 'Mercado Imobiliário',
    'tecnologia-ia': 'Tecnologia e IA',
    'gestao-imobiliaria': 'Gestão Imobiliária',
}


def parse_post_file(filepath):
    """Le um .md com frontmatter YAML e retorna dict com meta + content_html.
    Retorna None se arquivo invalido."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw = f.read()
    except (OSError, IOError):
        return None
    m = re.match(r'^---\n(.*?)\n---\n(.*)', raw, re.DOTALL)
    if not m:
        return None
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None
    body_md = m.group(2).strip()
    html = markdown.markdown(
        body_md,
        extensions=['extra', 'sane_lists', 'smarty', 'toc'],
        output_format='html5',
    )
    meta['content_html'] = html
    meta['content_md'] = body_md
    meta['_filename'] = filepath.name
    return meta


def list_all_posts(category=None, limit=None):
    """Retorna lista de posts ordenada por data DESC. Filtra por categoria
    se passada. limit corta a lista."""
    if not BLOG_POSTS_DIR.exists():
        return []
    posts = []
    for filepath in BLOG_POSTS_DIR.glob('*.md'):
        meta = parse_post_file(filepath)
        if not meta or not meta.get('slug'):
            continue
        if category and meta.get('category') != category:
            continue
        posts.append(meta)
    posts.sort(key=lambda p: p.get('date', ''), reverse=True)
    if limit:
        posts = posts[:limit]
    return posts


def find_post_by_slug(slug):
    """Acha post pelo slug. Retorna None se nao existir."""
    if not BLOG_POSTS_DIR.exists():
        return None
    for filepath in BLOG_POSTS_DIR.glob('*.md'):
        # Tenta extrair slug do nome do arquivo primeiro (rapido)
        if slug not in filepath.stem:
            continue
        meta = parse_post_file(filepath)
        if meta and meta.get('slug') == slug:
            return meta
    return None


def _fmt_date_br(date_str):
    """'2026-05-13' -> '13/05/2026'"""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return d.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return date_str or ''


# ===========================================================================
# TEMPLATE HTML BASE - reutiliza identidade visual do site institucional
# ===========================================================================

BLOG_BASE_CSS = """
:root{--azul:#2d4d82;--azul-c:#2d6abf;--branco:#fff;--cinza:#f5f7fa;--txt:#1a2d4e;--txt2:#555e6e}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:'DM Sans','Segoe UI',Roboto,Arial,sans-serif;background:#fff;color:var(--txt);line-height:1.6}
a{color:var(--azul-c);text-decoration:none;transition:color .2s}
a:hover{color:var(--azul)}

/* NAV (igual ao site institucional) */
nav.blog-nav{position:fixed;top:0;left:0;right:0;z-index:1000;background:#fff;border-bottom:1px solid rgba(0,0,0,.08);padding:0 5%;height:72px;display:flex;align-items:center;justify-content:space-between}
.logo{display:flex;align-items:center;gap:8px;text-decoration:none}
.logo-txt{font-size:32px;font-weight:700;color:var(--txt)}
.logo-txt span{color:var(--azul-c)}
.logo-sub{font-size:11px;color:var(--txt2);font-weight:400;margin-top:-4px}
.nav-links{display:flex;gap:28px;list-style:none}
.nav-links a{color:var(--txt2);font-size:14px;font-weight:500}
.nav-links a.active{color:var(--azul-c);font-weight:600}
.nav-cta{background:var(--azul-c);color:#fff;padding:10px 22px;border-radius:8px;font-size:14px;font-weight:600}
.nav-cta:hover{background:var(--azul);color:#fff}
.nav-login{color:var(--txt2);font-size:14px;font-weight:500;margin-right:18px}

/* CONTAINER */
main.blog-main{max-width:1140px;margin:0 auto;padding:120px 5% 60px}

/* HEADER do blog */
.blog-header{text-align:center;margin-bottom:48px;padding:32px 0}
.blog-header h1{font-size:clamp(28px,4vw,42px);font-weight:700;color:var(--txt);margin-bottom:12px}
.blog-header p{font-size:16px;color:var(--txt2);max-width:600px;margin:0 auto}

/* CATEGORIAS (filtro) */
.cat-filter{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-bottom:40px}
.cat-filter a{padding:7px 14px;border-radius:100px;background:#eef2f7;color:var(--txt2);font-size:13px;font-weight:500;border:1px solid transparent}
.cat-filter a:hover{background:#e3edf7;color:var(--azul-c)}
.cat-filter a.active{background:var(--azul-c);color:#fff;border-color:var(--azul-c)}

/* GRID de posts */
.posts-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:28px}
.post-card{background:#fff;border:1px solid #e8eef5;border-radius:14px;overflow:hidden;transition:transform .2s,box-shadow .2s;display:flex;flex-direction:column}
.post-card:hover{transform:translateY(-4px);box-shadow:0 12px 32px rgba(45,77,130,.12)}
.post-card-img{width:100%;aspect-ratio:16/9;object-fit:cover;background:#eef2f7;display:block}
.post-card-body{padding:20px;display:flex;flex-direction:column;flex:1}
.post-card-cat{display:inline-block;background:#e8f0fe;color:var(--azul);font-size:11px;font-weight:600;padding:4px 10px;border-radius:100px;margin-bottom:10px;align-self:flex-start;text-transform:uppercase;letter-spacing:.04em}
.post-card-title{font-size:18px;font-weight:700;color:var(--txt);line-height:1.35;margin-bottom:8px}
.post-card-title a{color:inherit}
.post-card-summary{font-size:14px;color:var(--txt2);line-height:1.55;flex:1;margin-bottom:14px}
.post-card-meta{font-size:12px;color:#8898aa;display:flex;justify-content:space-between;border-top:1px solid #eef2f7;padding-top:12px;margin-top:auto}

/* POST INDIVIDUAL */
.post-back{display:inline-block;margin-bottom:24px;font-size:14px;color:var(--txt2)}
.post-back:hover{color:var(--azul-c)}
.post-hero-img{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:16px;margin-bottom:32px}
.post-cat{display:inline-block;background:#e8f0fe;color:var(--azul);font-size:12px;font-weight:600;padding:5px 14px;border-radius:100px;margin-bottom:14px;text-transform:uppercase;letter-spacing:.04em}
.post-title{font-size:clamp(28px,4vw,42px);font-weight:700;line-height:1.2;color:var(--txt);margin-bottom:18px}
.post-summary{font-size:18px;color:var(--txt2);line-height:1.5;border-left:3px solid var(--azul-c);padding-left:16px;margin-bottom:28px}
.post-meta-bar{display:flex;align-items:center;gap:16px;padding:16px 0;border-top:1px solid #eef2f7;border-bottom:1px solid #eef2f7;margin-bottom:32px;font-size:14px;color:var(--txt2)}
.post-meta-author{font-weight:600;color:var(--txt)}
.post-meta-bar .sep{color:#cbd5e0}
.post-content{font-size:17px;line-height:1.75;max-width:760px;margin:0 auto}
.post-content h2{font-size:26px;font-weight:700;color:var(--txt);margin:40px 0 16px}
.post-content h3{font-size:20px;font-weight:700;color:var(--txt);margin:32px 0 12px}
.post-content p{margin:0 0 18px}
.post-content ul,.post-content ol{margin:0 0 18px;padding-left:24px}
.post-content li{margin-bottom:6px}
.post-content strong{color:var(--txt);font-weight:700}
.post-content a{font-weight:500}
.post-content code{background:#eef2f7;padding:2px 6px;border-radius:4px;font-size:.92em}
.post-content blockquote{border-left:3px solid var(--azul-c);padding-left:16px;margin:24px 0;color:var(--txt2);font-style:italic}

/* CTA final */
.post-cta{background:linear-gradient(135deg,var(--azul) 0%,var(--azul-c) 100%);color:#fff;padding:32px 28px;border-radius:16px;text-align:center;margin:48px auto;max-width:760px}
.post-cta h3{font-size:22px;font-weight:700;margin-bottom:10px;color:#fff}
.post-cta p{font-size:15px;margin-bottom:18px;color:rgba(255,255,255,.9)}
.post-cta a{display:inline-block;background:#fff;color:var(--azul);padding:12px 28px;border-radius:8px;font-weight:600;font-size:14px}
.post-cta a:hover{background:#f8fafc;color:var(--azul)}

/* RESPONSIVE */
@media(max-width:768px){
  nav.blog-nav{padding:0 4%}
  .nav-links,.nav-login{display:none}
  main.blog-main{padding:100px 4% 40px}
  .posts-grid{grid-template-columns:1fr;gap:20px}
  .post-card-title{font-size:16px}
  .post-meta-bar{flex-wrap:wrap;gap:8px;font-size:13px}
  .post-content{font-size:16px;line-height:1.7}
  .post-content h2{font-size:22px}
  .post-content h3{font-size:18px}
}

/* FOOTER simples */
footer.blog-footer{background:#f8fafc;border-top:1px solid #eef2f7;padding:32px 5%;text-align:center;color:var(--txt2);font-size:13px;margin-top:60px}
footer.blog-footer a{margin:0 10px}
"""

NAV_HTML = """
<nav class="blog-nav">
  <a href="https://www.izylaudo.com.br/" class="logo">
    <div><div class="logo-txt"><span>izy</span>LAUDO</div>
    <div class="logo-sub">Vistorias Imobiliárias com IA</div></div>
  </a>
  <ul class="nav-links">
    <li><a href="https://www.izylaudo.com.br/#como-funciona">Como funciona</a></li>
    <li><a href="https://www.izylaudo.com.br/#beneficios">Benefícios</a></li>
    <li><a href="https://www.izylaudo.com.br/#precos">Preços</a></li>
    <li><a href="/blog" class="active">Blog</a></li>
  </ul>
  <div style="display:flex;align-items:center">
    <a href="https://app.izylaudo.com.br/login" class="nav-login">Entrar</a>
    <a href="https://app.izylaudo.com.br/cadastro" class="nav-cta">CRIAR CONTA →</a>
  </div>
</nav>
"""

FOOTER_HTML = """
<footer class="blog-footer">
  <p>© 2026 izyLAUDO · Vistorias Imobiliárias com Inteligência Artificial</p>
  <p style="margin-top:8px">
    <a href="https://www.izylaudo.com.br/">Home</a> ·
    <a href="/blog">Blog</a> ·
    <a href="https://app.izylaudo.com.br/cadastro">Criar conta</a>
  </p>
</footer>
"""

CTA_BLOCK_HTML = """
<div class="post-cta">
  <h3>Comece a usar o izyLAUDO hoje</h3>
  <p>Laudos profissionais em minutos, com validade jurídica e assinatura digital.<br>
  Sem mensalidade · Pague só pelo uso · Sem cartão de crédito</p>
  <a href="https://app.izylaudo.com.br/cadastro">COMEÇAR AGORA →</a>
</div>
"""


def _render_page(title, body_html, meta_desc='', canonical_path='/blog',
                 og_image=None):
    """Monta HTML completo com head SEO + nav + body + footer."""
    site_url = 'https://www.izylaudo.com.br'
    canonical = site_url + canonical_path
    og_img = og_image or (site_url + '/static/site/og-image.jpg')
    safe_title = html_escape(title)
    safe_desc = html_escape(meta_desc or 'Blog do izyLAUDO sobre vistorias imobiliárias, lei do inquilinato, mercado imobiliário e tecnologia.')
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title} · izyLAUDO Blog</title>
<meta name="description" content="{safe_desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{safe_title}">
<meta property="og:description" content="{safe_desc}">
<meta property="og:image" content="{og_img}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{safe_title}">
<meta name="twitter:description" content="{safe_desc}">
<meta name="twitter:image" content="{og_img}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{BLOG_BASE_CSS}</style>
</head>
<body>
{NAV_HTML}
<main class="blog-main">
{body_html}
</main>
{FOOTER_HTML}
</body>
</html>"""


def _render_post_card(post):
    img = html_escape(post.get('image_url') or '/static/site/og-image.jpg')
    alt = html_escape(post.get('image_alt') or post.get('title', ''))
    cat_slug = post.get('category', '')
    cat_label = post.get('category_label') or CATEGORIES.get(cat_slug, cat_slug)
    title = html_escape(post.get('title', ''))
    summary = html_escape(post.get('summary', ''))
    slug = post.get('slug', '')
    author = html_escape(post.get('author', ''))
    date = _fmt_date_br(post.get('date', ''))
    return f"""
<article class="post-card">
  <a href="/blog/{slug}" aria-label="{title}">
    <img src="{img}" alt="{alt}" loading="lazy" class="post-card-img">
  </a>
  <div class="post-card-body">
    <span class="post-card-cat">{html_escape(cat_label)}</span>
    <h2 class="post-card-title"><a href="/blog/{slug}">{title}</a></h2>
    <p class="post-card-summary">{summary}</p>
    <div class="post-card-meta">
      <span>{author}</span>
      <span>{date}</span>
    </div>
  </div>
</article>
"""


# ===========================================================================
# HANDLERS
# ===========================================================================

class BlogIndexHandler(tornado.web.RequestHandler):
    """GET /blog - lista todos os posts mais recentes primeiro."""
    def get(self):
        category = self.get_argument('cat', None)
        posts = list_all_posts(category=category, limit=50)

        # Filtro de categorias
        cat_links = ['<a href="/blog"' + (' class="active"' if not category else '') + '>Todos</a>']
        for slug, label in CATEGORIES.items():
            active = ' class="active"' if category == slug else ''
            cat_links.append(f'<a href="/blog?cat={slug}"{active}>{html_escape(label)}</a>')

        if not posts:
            grid_html = '<p style="text-align:center;color:#8898aa;padding:48px 0">Nenhum post ainda. Volte em breve.</p>'
        else:
            grid_html = '<div class="posts-grid">' + ''.join(_render_post_card(p) for p in posts) + '</div>'

        body = f"""
<div class="blog-header">
  <h1>Blog izyLAUDO</h1>
  <p>Vistorias imobiliárias, lei do inquilinato, mercado e tecnologia — direto ao ponto, pra quem trabalha no setor.</p>
</div>
<nav class="cat-filter" aria-label="Filtrar por categoria">
  {''.join(cat_links)}
</nav>
{grid_html}
"""
        title = 'Blog' if not category else CATEGORIES.get(category, 'Blog')
        canonical = '/blog' if not category else f'/blog?cat={category}'
        self.set_header('Content-Type', 'text/html; charset=utf-8')
        self.set_header('Cache-Control', 'public, max-age=300')
        self.write(_render_page(title, body, canonical_path=canonical))


class BlogPostHandler(tornado.web.RequestHandler):
    """GET /blog/(slug) - post individual."""
    def get(self, slug):
        post = find_post_by_slug(slug)
        if not post:
            self.set_status(404)
            self.set_header('Content-Type', 'text/html; charset=utf-8')
            body = """
<div style="text-align:center;padding:80px 20px">
  <h1 style="font-size:32px;margin-bottom:16px">Post não encontrado</h1>
  <p style="color:#8898aa;margin-bottom:24px">O artigo que você procura não existe ou foi removido.</p>
  <a href="/blog" style="display:inline-block;background:var(--azul-c);color:#fff;padding:12px 24px;border-radius:8px;font-weight:600">← Voltar para o blog</a>
</div>"""
            self.write(_render_page('Post não encontrado', body))
            return

        img = html_escape(post.get('image_url') or '/static/site/og-image.jpg')
        alt = html_escape(post.get('image_alt') or post.get('title', ''))
        cat_slug = post.get('category', '')
        cat_label = post.get('category_label') or CATEGORIES.get(cat_slug, cat_slug)
        title = html_escape(post.get('title', ''))
        summary = html_escape(post.get('summary', ''))
        author = html_escape(post.get('author', ''))
        author_role = html_escape(post.get('author_role') or '')
        date = _fmt_date_br(post.get('date', ''))
        reading_time = post.get('reading_time') or 5
        content_html = post.get('content_html', '')

        body = f"""
<a href="/blog" class="post-back">← Voltar para o blog</a>
<article>
  <span class="post-cat">{html_escape(cat_label)}</span>
  <h1 class="post-title">{title}</h1>
  <p class="post-summary">{summary}</p>
  <div class="post-meta-bar">
    <span class="post-meta-author">{author}</span>
    {('<span class="sep">·</span><span>' + author_role + '</span>') if author_role else ''}
    <span class="sep">·</span>
    <span>{date}</span>
    <span class="sep">·</span>
    <span>{reading_time} min de leitura</span>
  </div>
  <img src="{img}" alt="{alt}" class="post-hero-img" loading="eager">
  <div class="post-content">
    {content_html}
  </div>
</article>
{CTA_BLOCK_HTML}
"""
        self.set_header('Content-Type', 'text/html; charset=utf-8')
        self.set_header('Cache-Control', 'public, max-age=300')
        self.write(_render_page(
            post.get('title', 'Post'),
            body,
            meta_desc=post.get('summary', ''),
            canonical_path=f'/blog/{slug}',
            og_image=post.get('image_url'),
        ))


class BlogRSSHandler(tornado.web.RequestHandler):
    """GET /blog/rss.xml - feed RSS dos ultimos 20 posts.
    Push 95: inclui imagem do post via <enclosure> + <media:content>
    para facilitar consumo pelo n8n no fluxo de auto-post Instagram."""
    def get(self):
        posts = list_all_posts(limit=20)
        site_url = 'https://www.izylaudo.com.br'
        items_xml = ''
        for p in posts:
            pub_date = ''
            try:
                d = datetime.strptime(p.get('date', ''), '%Y-%m-%d')
                pub_date = d.strftime('%a, %d %b %Y 09:00:00 -0300')
            except (ValueError, TypeError):
                pass
            img_url = p.get('image_url') or ''
            # garantir URL absoluta pro n8n e Instagram Graph API
            if img_url and img_url.startswith('/'):
                img_url = f'{site_url}{img_url}'
            img_xml = ''
            if img_url:
                img_xml = (
                    f'<enclosure url="{html_escape(img_url)}" type="image/jpeg" length="0" />\n'
                    f'<media:content url="{html_escape(img_url)}" type="image/jpeg" medium="image" />\n'
                    f'<media:thumbnail url="{html_escape(img_url)}" />\n'
                )
            items_xml += f"""<item>
<title>{html_escape(p.get('title', ''))}</title>
<link>{site_url}/blog/{p.get('slug', '')}</link>
<description>{html_escape(p.get('summary', ''))}</description>
<author>{html_escape(p.get('author', ''))}</author>
<category>{html_escape(p.get('category_label') or '')}</category>
<pubDate>{pub_date}</pubDate>
<guid isPermaLink="true">{site_url}/blog/{p.get('slug', '')}</guid>
{img_xml}</item>
"""
        rss = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
<title>izyLAUDO Blog</title>
<link>{site_url}/blog</link>
<atom:link href="{site_url}/blog/rss.xml" rel="self" type="application/rss+xml" />
<description>Blog do izyLAUDO sobre vistorias imobiliárias, lei do inquilinato e tecnologia no setor imobiliário.</description>
<language>pt-BR</language>
{items_xml}</channel>
</rss>"""
        self.set_header('Content-Type', 'application/rss+xml; charset=utf-8')
        self.set_header('Cache-Control', 'public, max-age=600')
        self.write(rss)
