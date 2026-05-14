#!/usr/bin/env python3
"""
Instagram Auto-Post a partir do Blog izyLAUDO (Push 98)

Substitui o workflow n8n que estava com problemas de volume no Railway.
Roda como GitHub Action 2x/dia (9h/18h BRT) — mesmo padrao do
meta_ads_daily_report.py.

Fluxo:
1. Le RSS do blog (/blog/rss.xml)
2. Pega post mais recente, checa se ja foi postado (state.json no repo)
3. Gera caption Instagram via Claude API (Sonnet 4.5)
4. Cria media container via Instagram Graph API (/{ig_id}/media)
5. Aguarda 30s pra Meta processar
6. Publica via /{ig_id}/media_publish
7. Atualiza state.json (commit + push pelo workflow)
8. Envia email confirmacao via Resend

Variaveis de ambiente requeridas:
  INSTAGRAM_USER_ID      — 17841440015991642 (descoberto Push 96)
  INSTAGRAM_ACCESS_TOKEN — Token Meta com instagram_basic + instagram_content_publish
  ANTHROPIC_API_KEY      — chave izyLAUDO-blog
  RESEND_API_KEY         — pra notificacao
  EMAIL_FROM, EMAIL_RECIPIENT — opcionais
  STATE_FILE             — caminho do state.json (default: automation/instagram_state.json)
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

# ---------- CONFIG ----------
IG_USER_ID = os.environ.get('INSTAGRAM_USER_ID', '17841440015991642')
IG_TOKEN = os.environ.get('INSTAGRAM_ACCESS_TOKEN')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'izyLAUDO Automation <noreply@izylaudo.com.br>')
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', 'cansliban@gmail.com')

GRAPH_API = 'https://graph.facebook.com/v21.0'
RSS_URL = 'https://www.izylaudo.com.br/blog/rss.xml'
STATE_FILE = Path(os.environ.get('STATE_FILE', 'automation/instagram_state.json'))

CLAUDE_MODEL = 'claude-sonnet-4-5-20250929'
CLAUDE_SYSTEM = (
    "Voce e especialista em marketing imobiliario para Instagram. Cria posts envolventes "
    "para o @izylaudo (vistorias imobiliarias com IA). Regras: maximo 2200 caracteres "
    "incluindo emojis e hashtags; tom profissional mas acessivel; 3-5 emojis estrategicos; "
    "terminar com CTA 'Link na bio para ler o artigo completo'; incluir hashtags fixas: "
    "#izylaudo #vistoriaimobiliaria #laudodigital #inteligenciaartificial #corretordeimoveis "
    "#imobiliaria #vistorialocacao #leidoinquilinato. NAO usar markdown — apenas texto puro. "
    "NAO mencionar que e um post de blog, escreva como conteudo original do Instagram."
)


# ---------- HELPERS ----------
def fetch_latest_post():
    """Le RSS e retorna dict com title, link, summary, imageUrl, slug."""
    print(f'[ig] buscando {RSS_URL}')
    r = requests.get(RSS_URL, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    ns = {'media': 'http://search.yahoo.com/mrss/', 'atom': 'http://www.w3.org/2005/Atom'}
    item = root.find('.//item')
    if item is None:
        raise RuntimeError('Nenhum item no RSS')

    def text(tag):
        el = item.find(tag)
        return el.text.strip() if el is not None and el.text else ''

    link = text('link')
    slug = link.rstrip('/').split('/')[-1]

    # Procura imagem (media:content, media:thumbnail, ou enclosure)
    img_url = ''
    media_content = item.find('media:content', ns)
    if media_content is not None:
        img_url = media_content.get('url', '')
    if not img_url:
        media_thumb = item.find('media:thumbnail', ns)
        if media_thumb is not None:
            img_url = media_thumb.get('url', '')
    if not img_url:
        enc = item.find('enclosure')
        if enc is not None:
            img_url = enc.get('url', '')
    if not img_url:
        img_url = 'https://www.izylaudo.com.br/static/site/images/og-image.jpg'

    return {
        'title': text('title'),
        'link': link,
        'summary': text('description'),
        'author': text('author'),
        'category': text('category'),
        'imageUrl': img_url,
        'slug': slug,
    }


def load_state():
    """Le o state.json com slug do ultimo post publicado."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state):
    """Persiste o state.json. GitHub Action commita depois."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def generate_caption(post):
    """Chama Claude API e retorna a caption gerada."""
    if not ANTHROPIC_KEY:
        raise RuntimeError('ANTHROPIC_API_KEY nao configurada')
    user_prompt = (
        f'Crie um post Instagram baseado neste artigo do blog:\n\n'
        f'TITULO: {post["title"]}\n\n'
        f'RESUMO: {post["summary"]}\n\n'
        f'CATEGORIA: {post["category"]}\n\n'
        f'LINK: {post["link"]}'
    )
    payload = {
        'model': CLAUDE_MODEL,
        'max_tokens': 1500,
        'system': CLAUDE_SYSTEM,
        'messages': [{'role': 'user', 'content': user_prompt}],
    }
    r = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': ANTHROPIC_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    caption = (data.get('content') or [{}])[0].get('text', '').strip()
    if len(caption) > 2200:
        caption = caption[:2197] + '...'
    print(f'[ig] caption gerada ({len(caption)} chars)')
    return caption


def ig_create_media(image_url, caption):
    """Cria container de media no Instagram Graph API."""
    print(f'[ig] criando media container para imagem {image_url[:60]}')
    r = requests.post(
        f'{GRAPH_API}/{IG_USER_ID}/media',
        params={
            'image_url': image_url,
            'caption': caption,
            'access_token': IG_TOKEN,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f'IG /media falhou {r.status_code}: {r.text[:500]}')
    data = r.json()
    container_id = data.get('id')
    print(f'[ig] container_id={container_id}')
    return container_id


def ig_wait_ready(container_id, max_seconds=60):
    """Polling pra esperar a Meta processar a imagem."""
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        r = requests.get(
            f'{GRAPH_API}/{container_id}',
            params={'fields': 'status_code', 'access_token': IG_TOKEN},
            timeout=30,
        )
        if r.status_code == 200:
            status = r.json().get('status_code')
            print(f'[ig] status={status}')
            if status == 'FINISHED':
                return True
            if status in ('ERROR', 'EXPIRED'):
                raise RuntimeError(f'Media container falhou: {status}')
        time.sleep(5)
    raise RuntimeError('Timeout esperando media container FINISHED')


def ig_publish(container_id):
    """Publica o media container."""
    print(f'[ig] publicando container {container_id}')
    r = requests.post(
        f'{GRAPH_API}/{IG_USER_ID}/media_publish',
        params={'creation_id': container_id, 'access_token': IG_TOKEN},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f'IG /media_publish falhou {r.status_code}: {r.text[:500]}')
    data = r.json()
    media_id = data.get('id')
    print(f'[ig] publicado! media_id={media_id}')
    return media_id


def send_email(post, caption, media_id):
    """Envia email confirmacao via Resend."""
    if not RESEND_API_KEY:
        print('[email] RESEND_API_KEY nao configurada, pulando')
        return
    html = f'''<!DOCTYPE html><html><body style="font-family:sans-serif;padding:24px">
<div style="max-width:600px;margin:0 auto;background:#f0fdf4;border-left:4px solid #10b981;padding:24px;border-radius:8px">
<h1 style="color:#10b981;margin:0 0 16px 0">📸 Post publicado no Instagram @izylaudo</h1>
<p><strong>Titulo:</strong> {post['title']}</p>
<p><strong>Slug:</strong> {post['slug']}</p>
<p><strong>Media ID:</strong> {media_id}</p>
<p><strong>Link do blog:</strong> <a href="{post['link']}">{post['link']}</a></p>
<p><strong>Imagem:</strong> <a href="{post['imageUrl']}">{post['imageUrl']}</a></p>
<hr>
<p><strong>Caption usada:</strong></p>
<pre style="white-space:pre-wrap;font-family:inherit;background:#fff;padding:12px;border-radius:8px;border:1px solid #d1fae5">{caption}</pre>
<p style="color:#6b7280;font-size:12px;margin-top:24px">🤖 Automacao izyLAUDO Instagram</p>
</div></body></html>'''
    try:
        r = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'from': EMAIL_FROM,
                'to': [EMAIL_RECIPIENT],
                'subject': f'📸 Instagram: {post["title"]}',
                'html': html,
            },
            timeout=30,
        )
        if r.status_code in (200, 202):
            print(f'[email] enviado para {EMAIL_RECIPIENT}')
        else:
            print(f'[email] erro {r.status_code}: {r.text[:200]}')
    except Exception as e:
        print(f'[email] excecao: {e}')


# ---------- MAIN ----------
def main():
    if not IG_TOKEN:
        print('ERRO: INSTAGRAM_ACCESS_TOKEN nao definido')
        sys.exit(1)

    post = fetch_latest_post()
    print(f'[ig] post mais recente: {post["slug"]} — {post["title"][:60]}')

    state = load_state()
    last_slug = state.get('lastInstagramPostSlug')
    if post['slug'] == last_slug:
        print(f'[ig] post {post["slug"]} ja foi publicado anteriormente, pulando.')
        sys.exit(0)

    print(f'[ig] novo post detectado (ultimo: {last_slug or "(nenhum)"}). Publicando...')

    caption = generate_caption(post)
    container = ig_create_media(post['imageUrl'], caption)
    ig_wait_ready(container)
    media_id = ig_publish(container)

    now_iso = datetime.now(timezone.utc).isoformat()
    state.update({
        'lastInstagramPostSlug': post['slug'],
        'lastInstagramPostId': media_id,
        'lastInstagramPostAt': now_iso,
        'lastInstagramPostTitle': post['title'],
        'lastInstagramPostLink': post['link'],
    })
    save_state(state)

    send_email(post, caption, media_id)
    print('[ig] concluido com sucesso.')


if __name__ == '__main__':
    main()
