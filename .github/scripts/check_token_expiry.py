#!/usr/bin/env python3
"""
Check Token Expiry — alerta diario de expiracao de tokens Meta (Push 99)

Verifica META_ADS_TOKEN e INSTAGRAM_ACCESS_TOKEN (mesmo token na pratica
hoje, mas mantemos separados pra flexibilidade futura) via Graph API
debug_token endpoint. Se algum estiver <= 14 dias da expiracao, envia
email consolidado de alerta via Resend, com tutorial de renovacao.

Workflow associado: .github/workflows/token-expiry-check.yml
Roda diariamente as 8h BRT (11h UTC).
"""

import os
import sys
import requests
from datetime import datetime, timezone

GRAPH_API = 'https://graph.facebook.com/v21.0'
APP_ID = '999362752748273'

# Tokens a verificar (nome amigavel -> env var name)
TOKENS_TO_CHECK = [
    ('Meta Ads Token', 'META_ADS_TOKEN'),
    ('Instagram Access Token', 'INSTAGRAM_ACCESS_TOKEN'),
]

# Limites de alerta
WARN_DAYS = 14    # comeca alertar 14 dias antes
CRITICAL_DAYS = 7  # alerta critico 7 dias antes

RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'izyLAUDO Automation <noreply@izylaudo.com.br>')
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', 'cansliban@gmail.com')


def check_token(label, token):
    """Retorna dict com info do token via Graph API debug_token."""
    if not token:
        return {'label': label, 'valid': False, 'error': 'env var nao definida'}
    try:
        r = requests.get(
            f'{GRAPH_API}/debug_token',
            params={'input_token': token, 'access_token': token},
            timeout=20,
        )
        if r.status_code != 200:
            return {'label': label, 'valid': False, 'error': f'HTTP {r.status_code}: {r.text[:200]}'}
        data = r.json().get('data', {})
        if not data.get('is_valid'):
            return {'label': label, 'valid': False, 'error': data.get('error', {}).get('message', 'invalido')}
        expires_at = data.get('expires_at', 0)
        if expires_at == 0:
            days = -1  # nao expira
        else:
            days = max(0, int((expires_at - datetime.now(timezone.utc).timestamp()) / 86400))
        return {
            'label': label,
            'valid': True,
            'days_left': days,
            'expires_at_str': datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime('%d/%m/%Y %H:%M UTC') if expires_at else 'nao expira',
            'scopes': data.get('scopes', []),
        }
    except Exception as e:
        return {'label': label, 'valid': False, 'error': str(e)}


def render_email(results, severity):
    """Gera HTML do alerta."""
    color = '#dc2626' if severity == 'critical' else '#f59e0b'
    icon = '🚨' if severity == 'critical' else '⚠️'
    rows = []
    for r in results:
        if r['valid']:
            color_row = '#dc2626' if r.get('days_left', 999) <= CRITICAL_DAYS else ('#f59e0b' if r.get('days_left', 999) <= WARN_DAYS else '#10b981')
            days_label = 'nao expira' if r['days_left'] == -1 else f'{r["days_left"]} dias'
            rows.append(f'''
            <tr>
              <td style="padding:12px;border-bottom:1px solid #e5e7eb">{r["label"]}</td>
              <td style="padding:12px;border-bottom:1px solid #e5e7eb;color:{color_row};font-weight:700">{days_label}</td>
              <td style="padding:12px;border-bottom:1px solid #e5e7eb;font-size:12px">{r["expires_at_str"]}</td>
              <td style="padding:12px;border-bottom:1px solid #e5e7eb;font-size:11px">{', '.join(r.get('scopes', [])[:5])}{('...' if len(r.get('scopes',[]))>5 else '')}</td>
            </tr>''')
        else:
            rows.append(f'''
            <tr>
              <td style="padding:12px;border-bottom:1px solid #e5e7eb">{r["label"]}</td>
              <td colspan="3" style="padding:12px;border-bottom:1px solid #e5e7eb;color:#dc2626">ERRO: {r.get("error","desconhecido")[:150]}</td>
            </tr>''')

    return f'''<!DOCTYPE html><html><body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;padding:24px;background:#f3f4f6;margin:0">
<div style="max-width:760px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
  <div style="background:{color};padding:24px;color:#fff">
    <h1 style="margin:0;font-size:22px">{icon} Tokens Meta — Status de Expiracao</h1>
    <p style="margin:8px 0 0 0;opacity:0.9;font-size:14px">Verificado em {datetime.now(timezone.utc).astimezone(timezone(__import__('datetime').timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M BRT')}</p>
  </div>
  <div style="padding:24px">
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead><tr style="background:#f9fafb">
        <th style="padding:12px;text-align:left">Token</th>
        <th style="padding:12px;text-align:left">Dias restantes</th>
        <th style="padding:12px;text-align:left">Expira em</th>
        <th style="padding:12px;text-align:left">Scopes</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>

    <div style="background:#fffbeb;border-left:4px solid #f59e0b;padding:16px;border-radius:6px;margin:24px 0;font-size:13px;line-height:1.6">
      <h3 style="margin:0 0 12px 0;color:#92400e">Como renovar (3 minutos):</h3>
      <ol style="margin:0;padding-left:20px">
        <li>Acesse o <a href="https://developers.facebook.com/tools/explorer/{APP_ID}">Graph API Explorer com app izyLAUDO</a></li>
        <li>Faca login com a conta Facebook que tem acesso a Ad Account 293213758001508</li>
        <li>Clica <strong>"Gerar token de acesso"</strong> com os 11 scopes (ads_management, ads_read, business_management, pages_show_list, pages_read_engagement, instagram_basic, instagram_content_publish, instagram_manage_comments, instagram_manage_insights, whatsapp_business_management, whatsapp_business_messaging)</li>
        <li>Copia o token gerado, abre o <a href="https://developers.facebook.com/tools/debug/accesstoken/">Access Token Debugger</a>, cola e clica <strong>"Estender token de acesso"</strong> (60 dias)</li>
        <li>Copia o token estendido</li>
        <li>Atualiza nos 2 lugares:
          <ul>
            <li><strong>Railway:</strong> <a href="https://railway.com/project/3589ba5e-42d0-40c4-af08-a15c366bb9c7/service/90773bbf-c4c7-4a33-ad7f-1caffddba463/variables">Variables do izyloc-app</a> → edita <code>META_ADS_TOKEN</code> (Overwrite)</li>
            <li><strong>GitHub Secrets:</strong> <a href="https://github.com/03081981/izyloc-app/settings/secrets/actions">Actions secrets</a> → atualiza <code>INSTAGRAM_ACCESS_TOKEN</code></li>
          </ul>
        </li>
        <li>Deploy no Railway. Pronto, +60 dias.</li>
      </ol>
    </div>

    <p style="color:#6b7280;font-size:11px;margin:24px 0 0 0">
      🤖 Este alerta vai chegar diariamente ate que todos os tokens estejam com > {WARN_DAYS} dias de validade.
      Workflow: <code>.github/workflows/token-expiry-check.yml</code>
    </p>
  </div>
</div></body></html>'''


def send_email(html, subject):
    if not RESEND_API_KEY:
        print('[email] RESEND_API_KEY nao configurada')
        return
    try:
        r = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'},
            json={'from': EMAIL_FROM, 'to': [EMAIL_RECIPIENT], 'subject': subject, 'html': html},
            timeout=30,
        )
        if r.status_code in (200, 202):
            print(f'[email] alerta enviado pra {EMAIL_RECIPIENT}')
        else:
            print(f'[email] erro {r.status_code}: {r.text[:200]}')
    except Exception as e:
        print(f'[email] excecao: {e}')


def main():
    results = []
    for label, env_name in TOKENS_TO_CHECK:
        token = os.environ.get(env_name)
        info = check_token(label, token)
        info['env_name'] = env_name
        results.append(info)
        if info['valid']:
            d = info['days_left']
            d_str = 'nao expira' if d == -1 else f'{d} dias'
            print(f'[check] {label}: {d_str} — expira em {info["expires_at_str"]}')
        else:
            print(f'[check] {label}: ERRO — {info.get("error","?")}')

    # Decide severidade
    severity = None
    min_days = None
    for r in results:
        if r['valid'] and r.get('days_left', 999) >= 0:
            if min_days is None or r['days_left'] < min_days:
                min_days = r['days_left']
        if not r['valid']:
            severity = 'critical'

    if min_days is not None:
        if min_days <= CRITICAL_DAYS:
            severity = 'critical'
        elif min_days <= WARN_DAYS:
            severity = severity or 'warn'

    if severity:
        subject_prefix = '🚨 CRITICO' if severity == 'critical' else '⚠️ Aviso'
        days_part = f' (em {min_days} dias)' if min_days is not None else ''
        subject = f'{subject_prefix}: Tokens Meta izyLAUDO precisam renovacao{days_part}'
        html = render_email(results, severity)
        send_email(html, subject)
        print(f'[main] alerta {severity} disparado')
    else:
        print(f'[main] todos os tokens OK (>{WARN_DAYS} dias). Nenhum alerta enviado.')


if __name__ == '__main__':
    main()
