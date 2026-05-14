#!/usr/bin/env python3
"""
Instagram Auto-Post a partir do Blog izyLAUDO (Push 102b)

Mudancas vs Push 98:
- Alternancia automatica de formatos A/B:
  - Formato A: SINGLE POST 1080x1080 com logo + titulo + bullets + CTA
  - Formato B: CARROSSEL 5 slides (capa + 3 secoes + CTA final)
- Claude API agora retorna JSON estruturado com caption + format_a + format_b
- Gera imagens via Pillow (instagram_image_generator.py)
- Commita + pusha imagens em automation/instagram-uploads/
- URL publica via raw.githubusercontent.com
- Suporta carousel via Graph API (children + parent container)
- State guarda lastInstagramFormat — alterna A -> B -> A -> B...
"""

import os
import sys
import json
import time
import subprocess
import requests
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

# Importa gerador de imagens local
sys.path.insert(0, str(Path(__file__).parent))
from instagram_image_generator import generate_format_a, generate_carousel  # noqa: E402

# ---------- CONFIG ----------
IG_USER_ID = os.environ.get("INSTAGRAM_USER_ID", "17841440015991642")
IG_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "izyLAUDO Automation <noreply@izylaudo.com.br>")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "cansliban@gmail.com")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "03081981/izyloc-app")

GRAPH_API = "https://graph.facebook.com/v21.0"
RSS_URL = "https://www.izylaudo.com.br/blog/rss.xml"
STATE_FILE = Path(os.environ.get("STATE_FILE", "automation/instagram_state.json"))
UPLOADS_DIR = Path("automation/instagram-uploads")
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CLAUDE_SYSTEM = (
    "Voce e especialista em marketing imobiliario para Instagram. Crie conteudo "
    "envolvente para o @izylaudo (vistorias imobiliarias com IA). "
    "RESPONDA APENAS COM JSON VALIDO, sem texto antes ou depois, neste formato:\n\n"
    "{\n"
    '  "caption": "Texto da legenda Instagram. Max 2200 chars, com 3-5 emojis, '
    "tom profissional mas acessivel, terminar com CTA 'Link na bio para ler o "
    "artigo completo'. Hashtags fixas no final: #izylaudo #vistoriaimobiliaria "
    "#laudodigital #inteligenciaartificial #corretordeimoveis #imobiliaria "
    '#vistorialocacao #leidoinquilinato",\n'
    '  "format_a": {\n'
    '    "title_short": "Titulo curto (max 80 chars) que sera renderizado no '
    'card visual. Mais conciso que o do blog.",\n'
    '    "bullets": ["bullet 1 (max 60 chars)", "bullet 2", "bullet 3", '
    '"bullet 4 (max 4 itens)"]\n'
    "  },\n"
    '  "format_b": {\n'
    '    "cover_title": "Titulo da capa do carrossel (max 90 chars). Pode ser '
    'mais provocativo que o do blog.",\n'
    '    "sections": [\n'
    '      {"title": "Titulo secao 1 (max 50 chars)", "body": "Texto da secao '
    '1 (max 250 chars). Direto, sem encheracao."},\n'
    '      {"title": "Titulo secao 2", "body": "Texto da secao 2."},\n'
    '      {"title": "Titulo secao 3", "body": "Texto da secao 3."}\n'
    "    ],\n"
    '    "cta_text": "Frase de chamada final (max 80 chars). Ex: \\'
    "\"Cadastre-se gratis e teste agora.\\\"\"\n"
    "  }\n"
    "}\n\n"
    "REGRAS DURAS:\n"
    "- NAO usar markdown\n"
    "- NAO mencionar 'no blog' explicitamente na caption\n"
    "- Cada bullet do format_a deve ser uma pista provocativa, nao parafrasear "
    "o titulo\n"
    "- Sections do format_b: cada secao e um insight independente, nao 'parte 1 "
    "de 3' linear. Pense em '3 angulos diferentes do mesmo tema'.\n"
    "- Ano atual: SEMPRE usar 2026 se mencionar ano"
)


# ---------- RSS ----------
def fetch_latest_post():
    """Le RSS e retorna dict com title, link, summary, imageUrl, slug."""
    print(f"[ig] buscando {RSS_URL}")
    r = requests.get(RSS_URL, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    ns = {"media": "http://search.yahoo.com/mrss/", "atom": "http://www.w3.org/2005/Atom"}
    item = root.find(".//item")
    if item is None:
        raise RuntimeError("Nenhum item no RSS")

    def text(tag):
        el = item.find(tag)
        return el.text.strip() if el is not None and el.text else ""

    link = text("link")
    slug = link.rstrip("/").split("/")[-1]

    img_url = ""
    media_content = item.find("media:content", ns)
    if media_content is not None:
        img_url = media_content.get("url", "")
    if not img_url:
        media_thumb = item.find("media:thumbnail", ns)
        if media_thumb is not None:
            img_url = media_thumb.get("url", "")
    if not img_url:
        enc = item.find("enclosure")
        if enc is not None:
            img_url = enc.get("url", "")
    if not img_url:
        img_url = "https://www.izylaudo.com.br/static/site/images/og-image.jpg"

    return {
        "title": text("title"),
        "link": link,
        "summary": text("description"),
        "author": text("author"),
        "category": text("category"),
        "imageUrl": img_url,
        "slug": slug,
    }


# ---------- STATE ----------
def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def next_format(state):
    """Alterna A -> B -> A -> B. Default A no primeiro run."""
    last = state.get("lastInstagramFormat", "")
    return "B" if last == "A" else "A"


# ---------- CLAUDE ----------
def generate_content(post):
    """Chama Claude retornando dict {caption, format_a, format_b}."""
    if not ANTHROPIC_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY nao configurada")
    user = (
        f"Crie conteudo Instagram baseado neste artigo:\n\n"
        f"TITULO: {post['title']}\n\n"
        f"RESUMO: {post['summary']}\n\n"
        f"CATEGORIA: {post['category']}\n\n"
        f"LINK: {post['link']}"
    )
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2500,
        "system": CLAUDE_SYSTEM,
        "messages": [{"role": "user", "content": user}],
    }
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    r.raise_for_status()
    data = r.json()
    raw = (data.get("content") or [{}])[0].get("text", "").strip()
    # Remove eventual cerca markdown
    if raw.startswith("```"):
        import re
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[claude] erro JSON: {e}\n--- RAW ---\n{raw[:1000]}\n--- END ---", file=sys.stderr)
        raise
    return parsed


# ---------- IMAGE GEN + GIT PUSH ----------
def generate_images_for_format(fmt, post, content, slug):
    """Gera imagens conforme formato A ou B. Retorna lista de Path locais."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base_slug = f"{ts}-{slug[:50]}"

    if fmt == "A":
        fa = content["format_a"]
        out = UPLOADS_DIR / f"{base_slug}-A.jpg"
        generate_format_a(
            title=fa["title_short"],
            bullets=fa["bullets"],
            output_path=out,
        )
        return [out]

    # Formato B (carrossel)
    fb = content["format_b"]
    paths = generate_carousel(
        cover_title=fb["cover_title"],
        sections=fb["sections"],
        cta_text=fb["cta_text"],
        cover_image_url=post["imageUrl"],
        output_dir=UPLOADS_DIR,
        slug=base_slug,
    )
    return paths


def commit_and_push_images(paths, slug, fmt):
    """Commit das imagens geradas e push pra raw.githubusercontent.com ficar acessivel."""
    if not paths:
        return
    print(f"[git] commitando {len(paths)} imagens...")
    try:
        subprocess.run(["git", "config", "user.email", "automation@izylaudo.com.br"], check=True)
        subprocess.run(["git", "config", "user.name", "izyLAUDO Automation Bot"], check=True)
        subprocess.run(["git", "add"] + [str(p) for p in paths], check=True)
        msg = f"chore(automation): instagram {fmt} assets para {slug}"
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print("[git] imagens commitadas + push OK")
    except subprocess.CalledProcessError as e:
        print(f"[git] erro: {e}", file=sys.stderr)
        raise


def public_url_for(path: Path) -> str:
    """Converte Path local em URL publica raw.githubusercontent."""
    rel = path.as_posix()
    return f"{RAW_BASE}/{rel}"


# ---------- INSTAGRAM GRAPH API ----------
def ig_create_single_media(image_url, caption):
    """Cria container single post."""
    r = requests.post(
        f"{GRAPH_API}/{IG_USER_ID}/media",
        params={"image_url": image_url, "caption": caption, "access_token": IG_TOKEN},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"IG /media falhou {r.status_code}: {r.text[:500]}")
    return r.json()["id"]


def ig_create_carousel_child(image_url):
    """Cria container child do carrossel (sem caption)."""
    r = requests.post(
        f"{GRAPH_API}/{IG_USER_ID}/media",
        params={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": IG_TOKEN,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"IG /media (child) falhou {r.status_code}: {r.text[:500]}")
    return r.json()["id"]


def ig_create_carousel_parent(children_ids, caption):
    """Cria container parent do carrossel."""
    r = requests.post(
        f"{GRAPH_API}/{IG_USER_ID}/media",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
            "access_token": IG_TOKEN,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"IG /media (carousel parent) falhou {r.status_code}: {r.text[:500]}")
    return r.json()["id"]


def ig_wait_ready(container_id, max_seconds=120):
    """Polling status_code ate FINISHED."""
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        r = requests.get(
            f"{GRAPH_API}/{container_id}",
            params={"fields": "status_code", "access_token": IG_TOKEN},
            timeout=30,
        )
        if r.status_code == 200:
            status = r.json().get("status_code")
            print(f"[ig] container {container_id} status={status}")
            if status == "FINISHED":
                return True
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Container falhou: {status}")
        time.sleep(5)
    raise RuntimeError(f"Timeout aguardando container {container_id}")


def ig_publish(container_id):
    """Publica container."""
    r = requests.post(
        f"{GRAPH_API}/{IG_USER_ID}/media_publish",
        params={"creation_id": container_id, "access_token": IG_TOKEN},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"IG /media_publish falhou {r.status_code}: {r.text[:500]}")
    return r.json()["id"]


# ---------- EMAIL ----------
def send_email(post, content, fmt, media_id, image_urls):
    if not RESEND_API_KEY:
        return
    caption_preview = content.get("caption", "")[:600]
    imgs_html = "".join(
        f'<p style="margin:8px 0"><a href="{u}">{u.split("/")[-1]}</a></p>'
        for u in image_urls
    )
    html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;padding:24px">
<div style="max-width:600px;margin:0 auto;background:#f0fdf4;border-left:4px solid #10b981;padding:24px;border-radius:8px">
<h1 style="color:#10b981;margin:0 0 16px 0">📸 Instagram @izylaudo — Formato {fmt}</h1>
<p><strong>Titulo:</strong> {post['title']}</p>
<p><strong>Slug:</strong> {post['slug']}</p>
<p><strong>Formato:</strong> {'Single Post' if fmt == 'A' else 'Carrossel (5 slides)'}</p>
<p><strong>Media ID:</strong> {media_id}</p>
<p><strong>Link blog:</strong> <a href="{post['link']}">{post['link']}</a></p>
<hr>
<p><strong>Imagens publicadas:</strong></p>
{imgs_html}
<hr>
<p><strong>Caption:</strong></p>
<pre style="white-space:pre-wrap;font-family:inherit;background:#fff;padding:12px;border-radius:8px;border:1px solid #d1fae5">{caption_preview}{'…' if len(content.get('caption','')) > 600 else ''}</pre>
<p style="color:#6b7280;font-size:12px;margin-top:24px">🤖 Proximo post sera no formato {'B (carrossel)' if fmt == 'A' else 'A (single)'}</p>
</div></body></html>"""
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from": EMAIL_FROM,
                "to": [EMAIL_RECIPIENT],
                "subject": f"📸 Instagram {fmt}: {post['title'][:60]}",
                "html": html,
            },
            timeout=30,
        )
        if r.status_code in (200, 202):
            print(f"[email] enviado pra {EMAIL_RECIPIENT}")
        else:
            print(f"[email] erro {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[email] excecao: {e}")


# ---------- MAIN ----------
def main():
    if not IG_TOKEN:
        print("ERRO: INSTAGRAM_ACCESS_TOKEN nao definido", file=sys.stderr)
        sys.exit(1)

    post = fetch_latest_post()
    print(f"[ig] post mais recente: {post['slug']} — {post['title'][:60]}")

    state = load_state()
    if post["slug"] == state.get("lastInstagramPostSlug"):
        print(f"[ig] post {post['slug']} ja publicado, pulando.")
        sys.exit(0)

    fmt = next_format(state)
    print(f"[ig] novo post detectado. Formato escolhido: {fmt} (anterior: {state.get('lastInstagramFormat','none')})")

    content = generate_content(post)
    caption = content["caption"]
    print(f"[claude] conteudo gerado. caption={len(caption)} chars")

    # Gera imagens
    paths = generate_images_for_format(fmt, post, content, post["slug"])
    print(f"[ig] {len(paths)} imagem(s) geradas localmente: {[p.name for p in paths]}")

    # Commit + push pra ter URL publica
    commit_and_push_images(paths, post["slug"], fmt)
    image_urls = [public_url_for(p) for p in paths]
    print(f"[ig] aguardando 15s pra raw.githubusercontent.com propagar...")
    time.sleep(15)

    # Publica no Instagram
    if fmt == "A":
        print("[ig] publicando single post...")
        container = ig_create_single_media(image_urls[0], caption)
        ig_wait_ready(container)
        media_id = ig_publish(container)
    else:
        print(f"[ig] publicando carrossel com {len(image_urls)} slides...")
        children = []
        for i, url in enumerate(image_urls, 1):
            print(f"[ig] criando child {i}/{len(image_urls)}: {url.split('/')[-1]}")
            cid = ig_create_carousel_child(url)
            ig_wait_ready(cid)
            children.append(cid)
        print("[ig] criando parent carousel...")
        parent = ig_create_carousel_parent(children, caption)
        ig_wait_ready(parent)
        media_id = ig_publish(parent)

    print(f"[ig] publicado! media_id={media_id}")

    # Atualiza state
    now_iso = datetime.now(timezone.utc).isoformat()
    state.update({
        "lastInstagramPostSlug": post["slug"],
        "lastInstagramPostId": media_id,
        "lastInstagramPostAt": now_iso,
        "lastInstagramPostTitle": post["title"],
        "lastInstagramPostLink": post["link"],
        "lastInstagramFormat": fmt,
    })
    save_state(state)

    send_email(post, content, fmt, media_id, image_urls)
    print("[ig] concluido com sucesso.")


if __name__ == "__main__":
    main()
