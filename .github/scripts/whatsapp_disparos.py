#!/usr/bin/env python3
"""
WhatsApp Disparos Automaticos — Push 107
=========================================
Script que envia templates aprovados pelo Business Manager para usuarios
elegiveis segundo cada gatilho.

Roda como GitHub Action a cada 15 minutos entre 8h-18h BRT.

6 gatilhos suportados:
  1. boas_vindas          — 5 min apos cadastro
  2. video_tutorial       — 6 min apos cadastro (1 min apos boas_vindas)
  3. reengajamento_sem_laudo — 2 dias apos cadastro sem gerar laudo
  4. vistoria_parada      — vistoria em andamento > 24h
  5. primeiro_laudo       — ao gerar 1o laudo finalizado
  6. sumiu_7_dias         — 7 dias sem acessar (last_login)

Regras:
- Horario: somente 8h-18h BRT (o cron do workflow ja restringe)
- Max 1 mensagem por gatilho por usuario (UNIQUE (phone, gatilho))
- Min 24h entre disparos diferentes pro mesmo usuario
- Skip se telefone esta em whatsapp_opt_out
- Skip se nao tem telefone cadastrado em users.phone

Variaveis de ambiente:
  WHATSAPP_ACCESS_TOKEN     — token permanente do izy Bot
  WHATSAPP_PHONE_NUMBER_ID  — 1163184123537455
  DATABASE_URL              — postgres do izyLAUDO
  RESEND_API_KEY            — pra alertas de erro
  EMAIL_FROM, EMAIL_RECIPIENT — opcionais
  LINK_VIDEO_TUTORIAL       — placeholder (default: app.izylaudo.com.br)
"""
import os
import sys
import json
import traceback
from datetime import datetime, timedelta, timezone

import requests
import psycopg2
import psycopg2.extras

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'izyLAUDO Automation <noreply@izylaudo.com.br>')
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', 'cansliban@gmail.com')

# Placeholders — substituir quando definir
LINK_VIDEO_TUTORIAL = os.environ.get('LINK_VIDEO_TUTORIAL', 'https://www.izylaudo.com.br/tutorial')

GRAPH_API = 'https://graph.facebook.com/v21.0'

# Intervalo minimo entre disparos diferentes pro mesmo usuario (24h)
MIN_INTERVAL_HOURS = 24

# DATABASE_URL pode vir como postgres:// — normaliza pra postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)


def _log(event, **kw):
    parts = ' '.join(f'{k}={str(v)[:160]}' for k, v in kw.items())
    print(f'[DISPARO] {event} {parts}', flush=True)


def _conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


# ----------------------------------------------------------------------------
# DEFINICAO DOS GATILHOS
# ----------------------------------------------------------------------------
# Cada gatilho define:
#   - template_name: nome do template aprovado no Business Manager
#   - language: codigo de lingua do template (pt_BR)
#   - sql: query que retorna {user_id, phone, name} dos usuarios elegiveis.
#          O script ja filtra automaticamente quem ja recebeu esse gatilho.
#   - components_fn(row): retorna lista de components com variaveis ({{1}}, {{2}}…)
GATILHOS = {

    # 1. Boas-vindas: 5-30 min apos cadastro
    'boas_vindas': {
        'template_name': 'izy_boas_vindas',
        'language': 'pt_BR',
        'sql': """
            SELECT u.id::TEXT AS user_id, u.phone, u.name
            FROM users u
            WHERE u.phone IS NOT NULL AND u.phone <> ''
              AND u.created_at >= NOW() - INTERVAL '30 minutes'
              AND u.created_at <= NOW() - INTERVAL '5 minutes'
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_mensagens_enviadas w
                  WHERE w.phone = u.phone AND w.gatilho = 'boas_vindas'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_opt_out o WHERE o.phone = u.phone
              )
        """,
        'components_fn': lambda row: [
            {'type': 'body', 'parameters': [
                {'type': 'text', 'text': _first_name(row.get('name')) or 'amigo(a)'},
            ]},
        ],
    },

    # 2. Video tutorial: 6-15 min apos cadastro (entra 1 min depois da boas_vindas)
    'video_tutorial': {
        'template_name': 'izy_video_tutorial',
        'language': 'pt_BR',
        'sql': """
            SELECT u.id::TEXT AS user_id, u.phone, u.name
            FROM users u
            JOIN whatsapp_mensagens_enviadas wbv
              ON wbv.phone = u.phone AND wbv.gatilho = 'boas_vindas'
            WHERE u.phone IS NOT NULL AND u.phone <> ''
              AND wbv.sent_at <= NOW() - INTERVAL '1 minute'
              AND wbv.sent_at >= NOW() - INTERVAL '30 minutes'
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_mensagens_enviadas w
                  WHERE w.phone = u.phone AND w.gatilho = 'video_tutorial'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_opt_out o WHERE o.phone = u.phone
              )
        """,
        'components_fn': lambda row: [
            {'type': 'body', 'parameters': [
                {'type': 'text', 'text': LINK_VIDEO_TUTORIAL},
            ]},
        ],
    },

    # 3. Reengajamento — 2 dias sem gerar laudo nenhum
    'reengajamento_sem_laudo': {
        'template_name': 'izy_reengajamento_sem_laudo',
        'language': 'pt_BR',
        'sql': """
            SELECT u.id::TEXT AS user_id, u.phone, u.name
            FROM users u
            WHERE u.phone IS NOT NULL AND u.phone <> ''
              AND u.created_at <= NOW() - INTERVAL '2 days'
              AND u.created_at >= NOW() - INTERVAL '7 days'
              AND NOT EXISTS (
                  SELECT 1 FROM inspections i WHERE i.user_id = u.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_mensagens_enviadas w
                  WHERE w.phone = u.phone AND w.gatilho = 'reengajamento_sem_laudo'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_opt_out o WHERE o.phone = u.phone
              )
        """,
        'components_fn': lambda row: [
            {'type': 'body', 'parameters': [
                {'type': 'text', 'text': _first_name(row.get('name')) or 'amigo(a)'},
            ]},
        ],
    },

    # 4. Vistoria parada — em andamento ha mais de 24h
    'vistoria_parada': {
        'template_name': 'izy_vistoria_parada',
        'language': 'pt_BR',
        'sql': """
            SELECT DISTINCT u.id::TEXT AS user_id, u.phone, u.name
            FROM users u
            JOIN inspections i ON i.user_id = u.id
            WHERE u.phone IS NOT NULL AND u.phone <> ''
              AND i.status IN ('draft', 'em_andamento', 'pending')
              AND i.created_at <= NOW() - INTERVAL '24 hours'
              AND i.created_at >= NOW() - INTERVAL '7 days'
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_mensagens_enviadas w
                  WHERE w.phone = u.phone AND w.gatilho = 'vistoria_parada'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_opt_out o WHERE o.phone = u.phone
              )
        """,
        'components_fn': lambda row: [
            {'type': 'body', 'parameters': [
                {'type': 'text', 'text': _first_name(row.get('name')) or 'amigo(a)'},
            ]},
        ],
    },

    # 5. Primeiro laudo gerado
    'primeiro_laudo': {
        'template_name': 'izy_primeiro_laudo',
        'language': 'pt_BR',
        'sql': """
            SELECT u.id::TEXT AS user_id, u.phone, u.name
            FROM users u
            JOIN inspections i ON i.user_id = u.id
            WHERE u.phone IS NOT NULL AND u.phone <> ''
              AND i.status = 'completed'
              AND i.updated_at >= NOW() - INTERVAL '30 minutes'
              AND (
                  SELECT COUNT(*) FROM inspections ii
                  WHERE ii.user_id = u.id AND ii.status = 'completed'
              ) = 1
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_mensagens_enviadas w
                  WHERE w.phone = u.phone AND w.gatilho = 'primeiro_laudo'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_opt_out o WHERE o.phone = u.phone
              )
        """,
        'components_fn': lambda row: [
            {'type': 'body', 'parameters': [
                {'type': 'text', 'text': _first_name(row.get('name')) or 'amigo(a)'},
            ]},
        ],
    },

    # 6. Sumiu 7 dias — sem acessar (last_login >= 7d)
    'sumiu_7_dias': {
        'template_name': 'izy_sumiu_7_dias',
        'language': 'pt_BR',
        'sql': """
            SELECT u.id::TEXT AS user_id, u.phone, u.name
            FROM users u
            WHERE u.phone IS NOT NULL AND u.phone <> ''
              AND u.last_login IS NOT NULL
              AND u.last_login <= NOW() - INTERVAL '7 days'
              AND u.last_login >= NOW() - INTERVAL '30 days'
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_mensagens_enviadas w
                  WHERE w.phone = u.phone AND w.gatilho = 'sumiu_7_dias'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM whatsapp_opt_out o WHERE o.phone = u.phone
              )
        """,
        'components_fn': lambda row: [
            {'type': 'body', 'parameters': [
                {'type': 'text', 'text': _first_name(row.get('name')) or 'amigo(a)'},
            ]},
        ],
    },
}


# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------
def _first_name(full_name):
    if not full_name:
        return ''
    return full_name.strip().split(' ')[0]


def _normalize_phone(phone: str) -> str:
    """Remove tudo que nao for digito. Adiciona DDI 55 se faltar (BR)."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if not digits:
        return ''
    # Se tem 10 ou 11 digitos (DDD + numero), adiciona DDI 55
    if len(digits) in (10, 11) and not digits.startswith('55'):
        digits = '55' + digits
    return digits


def _has_recent_disparo(conn, phone: str) -> bool:
    """True se o usuario recebeu QUALQUER disparo nas ultimas 24h."""
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM whatsapp_mensagens_enviadas "
        "WHERE phone = %s AND sent_at >= NOW() - INTERVAL '%s hours' LIMIT 1",
        (phone, MIN_INTERVAL_HOURS),
    )
    return cur.fetchone() is not None


def send_template(to_phone: str, template_name: str, language: str, components: list) -> dict:
    """Envia template via Meta Graph API. Retorna {ok, message_id, error}."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        return {'ok': False, 'error': 'env_missing'}
    payload = {
        'messaging_product': 'whatsapp',
        'to': to_phone,
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {'code': language},
        },
    }
    if components:
        payload['template']['components'] = components
    try:
        r = requests.post(
            f'{GRAPH_API}/{WHATSAPP_PHONE_NUMBER_ID}/messages',
            headers={
                'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=15,
        )
        data = r.json() if r.content else {}
        if r.status_code != 200:
            return {'ok': False, 'error': f'http {r.status_code}: {str(data)[:300]}'}
        msg_id = ((data.get('messages') or [{}])[0]).get('id', '')
        return {'ok': True, 'message_id': msg_id}
    except Exception as e:
        return {'ok': False, 'error': str(e)[:200]}


def _record_disparo(conn, user_id, phone, gatilho, template_name, ok, msg_id, err):
    """Insere registro em whatsapp_mensagens_enviadas. Usa ON CONFLICT pra ser idempotente."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO whatsapp_mensagens_enviadas
                (user_id, phone, gatilho, template_name, status, meta_message_id, error)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (phone, gatilho) DO NOTHING
            """,
            (
                user_id,
                phone,
                gatilho,
                template_name,
                'sent' if ok else 'failed',
                msg_id if ok else None,
                None if ok else err,
            ),
        )
        conn.commit()
    except Exception as e:
        _log('record_error', err=str(e)[:200])
        conn.rollback()


# ----------------------------------------------------------------------------
# RUNNER POR GATILHO
# ----------------------------------------------------------------------------
def run_gatilho(conn, slug: str, cfg: dict) -> dict:
    """Executa um gatilho. Retorna {total, sent, failed, skipped}."""
    stats = {'total': 0, 'sent': 0, 'failed': 0, 'skipped': 0}
    cur = conn.cursor()
    try:
        cur.execute(cfg['sql'])
        rows = cur.fetchall()
    except Exception as e:
        _log('sql_error', gatilho=slug, err=str(e)[:200])
        conn.rollback()
        return stats

    stats['total'] = len(rows)
    _log('gatilho_start', slug=slug, eligible=len(rows))

    for row in rows:
        phone = _normalize_phone(row.get('phone'))
        user_id = row.get('user_id', '')
        if not phone:
            stats['skipped'] += 1
            continue

        # Respeita intervalo minimo 24h entre disparos diferentes
        if _has_recent_disparo(conn, phone):
            stats['skipped'] += 1
            _log('skip_recent', slug=slug, phone=phone)
            continue

        components = cfg['components_fn'](row) if cfg.get('components_fn') else None
        result = send_template(phone, cfg['template_name'], cfg['language'], components)

        _record_disparo(
            conn,
            user_id=user_id,
            phone=phone,
            gatilho=slug,
            template_name=cfg['template_name'],
            ok=result['ok'],
            msg_id=result.get('message_id'),
            err=result.get('error'),
        )

        if result['ok']:
            stats['sent'] += 1
            _log('sent', slug=slug, phone=phone, msg_id=result.get('message_id'))
        else:
            stats['failed'] += 1
            _log('failed', slug=slug, phone=phone, err=result.get('error'))

    _log('gatilho_end', slug=slug, **stats)
    return stats


# ----------------------------------------------------------------------------
# ALERTA POR EMAIL EM CASO DE FALHAS
# ----------------------------------------------------------------------------
def send_alert_email(report: dict) -> None:
    """Envia email pra Carlos se houver falhas significativas."""
    if not RESEND_API_KEY:
        return
    total_failed = sum(s.get('failed', 0) for s in report.values())
    if total_failed == 0:
        return
    rows_html = ''
    for slug, s in report.items():
        rows_html += (
            f'<tr><td>{slug}</td><td>{s["total"]}</td>'
            f'<td>{s["sent"]}</td><td style="color:#dc2626">{s["failed"]}</td>'
            f'<td>{s["skipped"]}</td></tr>'
        )
    html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;padding:24px">
<div style="max-width:600px;margin:0 auto;background:#fef2f2;border-left:4px solid #dc2626;padding:24px;border-radius:8px">
<h2 style="color:#dc2626">⚠️ Falhas em disparos WhatsApp</h2>
<p>O job de disparos automaticos teve {total_failed} falhas.</p>
<table style="width:100%;border-collapse:collapse">
<thead><tr style="background:#f3f4f6"><th>Gatilho</th><th>Total</th><th>Sent</th><th>Failed</th><th>Skipped</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
<p style="color:#6b7280;font-size:12px;margin-top:24px">🤖 izyLAUDO WhatsApp Disparos</p>
</div></body></html>"""
    try:
        requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'from': EMAIL_FROM,
                'to': [EMAIL_RECIPIENT],
                'subject': f'⚠️ {total_failed} falhas em disparos WhatsApp izyLAUDO',
                'html': html,
            },
            timeout=15,
        )
    except Exception as e:
        _log('alert_email_error', err=str(e)[:200])


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    if not DATABASE_URL:
        print('ERRO: DATABASE_URL nao definida', file=sys.stderr)
        sys.exit(1)
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print('ERRO: variaveis WHATSAPP_* nao definidas', file=sys.stderr)
        sys.exit(1)

    _log('start', timestamp=datetime.now(timezone.utc).isoformat())

    conn = _conn()
    report = {}

    try:
        for slug, cfg in GATILHOS.items():
            try:
                report[slug] = run_gatilho(conn, slug, cfg)
            except Exception as e:
                _log('gatilho_exception', slug=slug, err=str(e)[:300], tb=traceback.format_exc()[:500])
                report[slug] = {'total': 0, 'sent': 0, 'failed': 1, 'skipped': 0}
    finally:
        conn.close()

    print('\n=== REPORT ===')
    print(json.dumps(report, indent=2))

    send_alert_email(report)

    # Exit code: 1 se TODOS os gatilhos falharam, 0 caso contrario
    total_sent = sum(s.get('sent', 0) for s in report.values())
    total_failed = sum(s.get('failed', 0) for s in report.values())
    if total_failed > 0 and total_sent == 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
