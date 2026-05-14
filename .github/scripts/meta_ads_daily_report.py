#!/usr/bin/env python3
"""
Meta Ads — Relatorio Diario Automatizado (Push 92, Fase 1)

Le dados da Marketing API (Meta Graph API), aplica regras de otimizacao
e gera um relatorio diario com recomendacoes (scale/pause/warn) que
ENVIA POR EMAIL para Carlos. NAO toma acoes automaticas ainda — apenas
sugere. Apos validacao manual, Fase 2 ativa acoes automaticas.

Variaveis de ambiente requeridas:
  META_ADS_TOKEN        — System User Token do BM Liban (nao expira)
  META_AD_ACCOUNT_ID    — 293213758001508 (descoberto no Push 91)
  META_API_VERSION      — opcional, padrao "v21.0"
  ANTHROPIC_API_KEY     — para insights gerados por IA (opcional)
  EMAIL_USER / EMAIL_PASS / EMAIL_RECIPIENT — credenciais SMTP do izyLAUDO

Executado automaticamente todo dia 9h BRT via GitHub Actions cron.
"""

import os
import sys
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

# ---------- CONFIG ----------
TOKEN = os.environ.get('META_ADS_TOKEN')
AD_ACCOUNT = os.environ.get('META_AD_ACCOUNT_ID', '293213758001508')
API_VERSION = os.environ.get('META_API_VERSION', 'v21.0')
BASE_URL = f'https://graph.facebook.com/{API_VERSION}'

EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', 'cansliban@gmail.com')

# Regras de otimizacao — calibradas com base nas campanhas atuais do Carlos
# (campanhas vencedoras com CPC R$0.16; gasto historico R$558 em 30 dias)
RULES = {
    'scale_threshold_cpc_max': 0.30,      # CPC <= 0.30 = vencedora -> escalar
    'scale_threshold_budget_used': 0.80,  # 80% gasto = ja entregou bem
    'scale_increase_pct': 20,             # +20% no budget (recomendado)
    'pause_threshold_cpc_min': 0.80,      # CPC > 0.80 = perdedora -> pausar
    'pause_threshold_ctr_min': 0.5,       # CTR < 0.5% = baixo engajamento
    'warn_threshold_cpc_min': 0.50,       # CPC > 0.50 = alerta
}

# ---------- HELPERS ----------
def graph_get(endpoint, params=None):
    """GET autenticado na Graph API."""
    if params is None:
        params = {}
    params['access_token'] = TOKEN
    url = f'{BASE_URL}/{endpoint}'
    r = requests.get(url, params=params, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'Graph API erro {r.status_code}: {r.text[:500]}')
    return r.json()


def check_token_expiration():
    """Verifica quantos dias o token ainda tem de validade.
    Retorna numero de dias restantes (0 = expira hoje, -1 = nao expira).
    Avisa por email se <= 7 dias para renovar (Plano C — User Access Token).
    """
    try:
        url = f'{BASE_URL}/debug_token'
        params = {'input_token': TOKEN, 'access_token': TOKEN}
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            print(f'[token-check] falha: {r.status_code}')
            return None
        data = r.json().get('data', {})
        expires_at = data.get('expires_at', 0)
        if expires_at == 0:
            print('[token-check] token nao expira (System User)')
            return -1
        now = int(datetime.now(timezone.utc).timestamp())
        days_left = max(0, int((expires_at - now) / 86400))
        print(f'[token-check] token expira em {days_left} dias')
        return days_left
    except Exception as e:
        print(f'[token-check] erro: {e}')
        return None


def send_token_warning(days_left):
    """Envia alerta urgente se token esta proximo do vencimento."""
    if not EMAIL_USER or not EMAIL_PASS:
        return
    subject = f'⚠️ TOKEN META ADS expira em {days_left} dias — RENOVAR'
    body_html = f'''<!DOCTYPE html><html><body style="font-family:sans-serif;padding:24px">
<div style="max-width:600px;margin:0 auto;background:#fef2f2;border-left:4px solid #dc2626;padding:24px;border-radius:8px">
<h1 style="color:#dc2626;margin:0 0 16px 0">⚠️ Atencao: Token Meta Ads expira em {days_left} dias</h1>
<p>O token <code>META_ADS_TOKEN</code> usado pela automacao Meta Ads do izyLAUDO
esta proximo do vencimento. Se nao renovar antes, a automacao vai PARAR.</p>

<h2 style="color:#1f2937">Como renovar (3 minutos):</h2>
<ol style="line-height:1.8">
<li>Acesse: <a href="https://developers.facebook.com/tools/explorer/999362752748273">Graph API Explorer com app izyLAUDO</a></li>
<li>Loga com a conta <strong>cansliban@gmail.com</strong> se necessario</li>
<li>Clica em <strong>"Generate Access Token"</strong></li>
<li>Marca os scopes: <code>ads_management</code>, <code>ads_read</code>, <code>business_management</code>, <code>pages_read_engagement</code></li>
<li>Confirma e copia o token gerado</li>
<li>Clica no botao <strong>"i"</strong> (info) ao lado do token</li>
<li>No popup, clica em <strong>"Extend Access Token"</strong> (estende para 60 dias)</li>
<li>Copia o novo token estendido</li>
<li>Acessa o <a href="https://railway.app/project/">Railway</a> -> projeto izyLAUDO -> Variables</li>
<li>Edita a variavel <code>META_ADS_TOKEN</code> e cola o novo valor</li>
<li>Salva. Pronto, mais 60 dias garantidos.</li>
</ol>

<p style="color:#6b7280;font-size:12px;margin-top:24px">
🤖 Este alerta vai aparecer todo dia ate o token ser renovado.<br>
Apos renovar, esse email para automaticamente.
</p>
</div></body></html>'''
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_RECIPIENT
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as s:
            s.login(EMAIL_USER, EMAIL_PASS)
            s.send_message(msg)
        print(f'[token-warning] alerta enviado: {days_left} dias para expirar')
    except Exception as e:
        print(f'[token-warning] erro envio: {e}')


def fetch_campaigns():
    """Retorna lista de campanhas ativas + paused do ad account."""
    data = graph_get(f'act_{AD_ACCOUNT}/campaigns', {
        'fields': 'id,name,status,objective,daily_budget,lifetime_budget,created_time',
        'limit': 100,
    })
    return data.get('data', [])


def fetch_insights(campaign_id, days=7):
    """Retorna metricas dos ultimos N dias para uma campanha."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
    until = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    data = graph_get(f'{campaign_id}/insights', {
        'fields': 'spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions',
        'time_range': json.dumps({'since': since, 'until': until}),
        'level': 'campaign',
    })
    rows = data.get('data', [])
    if not rows:
        return None
    row = rows[0]
    # actions = lista de conversoes por tipo (link_click, lead, etc)
    actions = {a['action_type']: int(a['value']) for a in row.get('actions', [])}
    return {
        'spend': float(row.get('spend', 0)),
        'impressions': int(row.get('impressions', 0)),
        'clicks': int(row.get('clicks', 0)),
        'ctr': float(row.get('ctr', 0)),
        'cpc': float(row.get('cpc', 0)),
        'cpm': float(row.get('cpm', 0)),
        'reach': int(row.get('reach', 0)),
        'frequency': float(row.get('frequency', 0)),
        'leads': actions.get('lead', 0),
        'page_views': actions.get('landing_page_view', 0),
        'link_clicks': actions.get('link_click', 0),
    }


def classify_campaign(insights):
    """Aplica regras de otimizacao e retorna recomendacao."""
    if not insights or insights['spend'] == 0:
        return {'action': 'no_data', 'reason': 'Sem dados ou nenhum gasto'}
    cpc = insights['cpc']
    ctr = insights['ctr']
    spend = insights['spend']

    # SCALE — CPC baixo + bom gasto
    if cpc <= RULES['scale_threshold_cpc_max'] and spend > 50:
        return {
            'action': 'scale',
            'reason': f'CPC R${cpc:.2f} (excelente, abaixo de R${RULES["scale_threshold_cpc_max"]})',
            'suggestion': f'Aumentar budget em +{RULES["scale_increase_pct"]}%'
        }

    # PAUSE — CPC alto ou CTR baixo
    if cpc >= RULES['pause_threshold_cpc_min']:
        return {
            'action': 'pause',
            'reason': f'CPC R${cpc:.2f} (acima do limite R${RULES["pause_threshold_cpc_min"]})',
            'suggestion': 'Pausar e revisar criativo/audiencia'
        }
    if ctr < RULES['pause_threshold_ctr_min']:
        return {
            'action': 'pause',
            'reason': f'CTR {ctr:.2f}% (baixo engajamento)',
            'suggestion': 'Pausar e testar criativo novo'
        }

    # WARN — performance media
    if cpc >= RULES['warn_threshold_cpc_min']:
        return {
            'action': 'warn',
            'reason': f'CPC R${cpc:.2f} (acima da media historica)',
            'suggestion': 'Observar nos proximos 2 dias'
        }

    # KEEP — perfomance OK mas nao excepcional
    return {
        'action': 'keep',
        'reason': f'CPC R${cpc:.2f}, CTR {ctr:.2f}% (dentro do padrao)',
        'suggestion': 'Manter como esta'
    }


def render_html_report(campaigns_with_insights, summary):
    """Gera HTML do relatorio com tabelas + cores."""
    rows_html = []
    for c in campaigns_with_insights:
        ins = c['insights']
        rec = c['recommendation']
        if not ins:
            continue
        color = {
            'scale': '#10b981',  # verde
            'pause': '#ef4444',  # vermelho
            'warn': '#f59e0b',   # amarelo
            'keep': '#6b7280',   # cinza
            'no_data': '#9ca3af',
        }.get(rec['action'], '#6b7280')
        emoji = {
            'scale': '🟢',
            'pause': '🔴',
            'warn': '🟡',
            'keep': '⚪',
            'no_data': '⚫',
        }.get(rec['action'], '⚪')

        rows_html.append(f'''
        <tr>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb">{emoji}</td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;font-weight:600">{c["name"][:60]}</td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb">{c["status"]}</td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;text-align:right">R$ {ins["spend"]:.2f}</td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;text-align:right">R$ {ins["cpc"]:.2f}</td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;text-align:right">{ins["ctr"]:.2f}%</td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;text-align:right">{ins["impressions"]:,}</td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;text-align:right">{ins["clicks"]:,}</td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;color:{color};font-weight:700">{rec["action"].upper()}</td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;font-size:12px">{rec["suggestion"]}</td>
        </tr>
        ''')

    today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y')

    return f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f3f4f6;margin:0;padding:24px">
<div style="max-width:1100px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">

<h1 style="color:#1f2937;margin:0 0 8px 0;font-size:24px">📊 Relatorio Diario Meta Ads — izyLAUDO</h1>
<p style="color:#6b7280;margin:0 0 24px 0">Periodo: ultimos 7 dias  •  Gerado em {today}</p>

<div style="background:#f9fafb;padding:20px;border-radius:8px;margin-bottom:24px">
  <h2 style="color:#1f2937;margin:0 0 12px 0;font-size:18px">Resumo</h2>
  <div style="display:flex;gap:24px;flex-wrap:wrap">
    <div><div style="color:#6b7280;font-size:12px">GASTO TOTAL</div><div style="color:#1f2937;font-size:24px;font-weight:700">R$ {summary["total_spend"]:.2f}</div></div>
    <div><div style="color:#6b7280;font-size:12px">IMPRESSOES</div><div style="color:#1f2937;font-size:24px;font-weight:700">{summary["total_impressions"]:,}</div></div>
    <div><div style="color:#6b7280;font-size:12px">CLIQUES</div><div style="color:#1f2937;font-size:24px;font-weight:700">{summary["total_clicks"]:,}</div></div>
    <div><div style="color:#6b7280;font-size:12px">CPC MEDIO</div><div style="color:#1f2937;font-size:24px;font-weight:700">R$ {summary["avg_cpc"]:.2f}</div></div>
    <div><div style="color:#6b7280;font-size:12px">CTR MEDIO</div><div style="color:#1f2937;font-size:24px;font-weight:700">{summary["avg_ctr"]:.2f}%</div></div>
  </div>
</div>

<h2 style="color:#1f2937;font-size:18px;margin:24px 0 12px 0">📌 Recomendacoes</h2>
<div style="background:#fffbeb;border-left:4px solid #f59e0b;padding:16px;border-radius:6px;margin-bottom:24px">
  <strong>🟢 Escalar:</strong> {summary["count_scale"]} campanhas (CPC baixo, vale aumentar budget)<br>
  <strong>🔴 Pausar:</strong> {summary["count_pause"]} campanhas (CPC alto ou CTR ruim)<br>
  <strong>🟡 Atencao:</strong> {summary["count_warn"]} campanhas (revisar nos proximos dias)<br>
  <strong>⚪ Manter:</strong> {summary["count_keep"]} campanhas (performance estavel)
</div>

<h2 style="color:#1f2937;font-size:18px;margin:24px 0 12px 0">Detalhe por campanha</h2>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead>
  <tr style="background:#f9fafb">
    <th style="padding:12px;text-align:left">●</th>
    <th style="padding:12px;text-align:left">Campanha</th>
    <th style="padding:12px;text-align:left">Status</th>
    <th style="padding:12px;text-align:right">Gasto</th>
    <th style="padding:12px;text-align:right">CPC</th>
    <th style="padding:12px;text-align:right">CTR</th>
    <th style="padding:12px;text-align:right">Impr.</th>
    <th style="padding:12px;text-align:right">Cliques</th>
    <th style="padding:12px;text-align:left">Acao</th>
    <th style="padding:12px;text-align:left">Sugestao</th>
  </tr>
</thead>
<tbody>{''.join(rows_html)}</tbody>
</table>

<div style="margin-top:32px;padding-top:24px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:12px">
  🤖 Relatorio gerado automaticamente pelo sistema de automacao Meta Ads do izyLAUDO.<br>
  Em Fase 2, as recomendacoes serao executadas automaticamente apos validacao.
</div>

</div>
</body>
</html>'''


def send_email(html_body, summary):
    """Envia o relatorio por email via SMTP."""
    if not EMAIL_USER or not EMAIL_PASS:
        print('[email] EMAIL_USER/EMAIL_PASS nao configurados, pulando envio')
        return
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'📊 Meta Ads izyLAUDO — Gasto R${summary["total_spend"]:.2f}, {summary["count_scale"]} pra escalar, {summary["count_pause"]} pra pausar'
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_RECIPIENT
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as s:
            s.login(EMAIL_USER, EMAIL_PASS)
            s.send_message(msg)
        print(f'[email] enviado para {EMAIL_RECIPIENT}')
    except Exception as e:
        print(f'[email] erro: {e}')


# ---------- MAIN ----------
def main():
    if not TOKEN:
        print('ERRO: META_ADS_TOKEN nao definido em env vars')
        sys.exit(1)

    # Plano C: verifica expiracao do User Access Token (60 dias)
    days_left = check_token_expiration()
    if days_left is not None and 0 <= days_left <= 7:
        send_token_warning(days_left)

    print(f'[meta-ads] Buscando campanhas do ad account {AD_ACCOUNT}...')
    campaigns = fetch_campaigns()
    print(f'[meta-ads] {len(campaigns)} campanhas encontradas')

    results = []
    summary = {
        'total_spend': 0, 'total_impressions': 0, 'total_clicks': 0,
        'count_scale': 0, 'count_pause': 0, 'count_warn': 0, 'count_keep': 0,
    }

    for c in campaigns:
        try:
            insights = fetch_insights(c['id'], days=7)
        except Exception as e:
            print(f'[meta-ads] erro insights {c["name"]}: {e}')
            insights = None

        rec = classify_campaign(insights) if insights else {'action': 'no_data', 'reason': '-', 'suggestion': '-'}

        results.append({
            'id': c['id'],
            'name': c['name'],
            'status': c.get('status', 'UNKNOWN'),
            'insights': insights,
            'recommendation': rec,
        })

        if insights:
            summary['total_spend'] += insights['spend']
            summary['total_impressions'] += insights['impressions']
            summary['total_clicks'] += insights['clicks']
            summary[f'count_{rec["action"]}'] = summary.get(f'count_{rec["action"]}', 0) + 1

    summary['avg_cpc'] = (summary['total_spend'] / summary['total_clicks']) if summary['total_clicks'] else 0
    summary['avg_ctr'] = (summary['total_clicks'] / summary['total_impressions'] * 100) if summary['total_impressions'] else 0

    print(f'[meta-ads] Resumo: gasto=R${summary["total_spend"]:.2f}, CPC=R${summary["avg_cpc"]:.2f}, CTR={summary["avg_ctr"]:.2f}%')
    print(f'[meta-ads] Recomendacoes: scale={summary["count_scale"]}, pause={summary["count_pause"]}, warn={summary["count_warn"]}, keep={summary["count_keep"]}')

    html = render_html_report(results, summary)
    send_email(html, summary)

    print('[meta-ads] Concluido.')


if __name__ == '__main__':
    main()
