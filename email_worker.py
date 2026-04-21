"""
izyLAUDO - Email Worker (Push 3)

Async worker que processa a tabela email_queue e envia via Resend HTTP API.
Usa tornado.httpclient.AsyncHTTPClient (zero dep nova, idiomatico Tornado).

Ciclo de vida:
  status='pending' -> worker escolhe (batch 10, mais antigos primeiro)
  sucesso: status='sent', provider='resend', provider_id=<msg_id>, sent_at=NOW()
  falha  : attempts++, next_retry_at = NOW() + backoff (1m/5m/15m/1h/6h)
  attempts >= max_attempts -> status='failed', last_error preservado

Defensivo: se RESEND_API_KEY ausente, loga e skip (nao crasha).
"""
import os
import json
from tornado import ioloop, httpclient

from database import get_conn

RESEND_API_URL = 'https://api.resend.com/emails'
POLL_INTERVAL_MS = 30_000  # 30 segundos
BATCH_SIZE = 10
HTTP_TIMEOUT = 10.0  # segundos
# Backoff exponencial: 1min, 5min, 15min, 1h, 6h
BACKOFF_SCHEDULE = [60, 300, 900, 3600, 21600]


def _log(event, **kw):
    """Log estruturado com prefixo [EMAIL] para filtragem no Railway."""
    extras = ''
    if kw:
        parts = []
        for k, v in kw.items():
            s = str(v)
            if len(s) > 160:
                s = s[:160] + '...'
            parts.append(f'{k}={s}')
        extras = ' ' + ' '.join(parts)
    print(f'[EMAIL] {event}{extras}', flush=True)


def _handle_failure(row, err):
    """Aplica backoff ou marca como failed permanente."""
    new_attempts = (row.get('attempts') or 0) + 1
    max_att = row.get('max_attempts') or 5
    row_id = row['id']
    try:
        if new_attempts >= max_att:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE email_queue SET status='failed', attempts=?, "
                    "last_error=?, updated_at=NOW() WHERE id=?",
                    (new_attempts, err, row_id)
                )
            _log('failed_permanent', id=row_id, attempts=new_attempts, err=err)
        else:
            backoff_s = BACKOFF_SCHEDULE[min(new_attempts - 1, len(BACKOFF_SCHEDULE) - 1)]
            with get_conn() as conn:
                conn.execute(
                    "UPDATE email_queue SET attempts=?, last_error=?, "
                    "next_retry_at=NOW() + make_interval(secs => ?), "
                    "updated_at=NOW() WHERE id=?",
                    (new_attempts, err, backoff_s, row_id)
                )
            _log('retry_scheduled', id=row_id, attempts=new_attempts,
                 in_s=backoff_s, err=err)
    except Exception as e:
        _log('handle_failure_error', id=row_id, err=str(e)[:200])


async def _process_one(row, api_key, from_addr):
    """Envia um email via Resend. Atualiza a linha conforme resultado."""
    client = httpclient.AsyncHTTPClient()
    body = {
        'from': from_addr,
        'to': [row['to_email']],
        'subject': row['subject'],
        'html': row['body_html'],
        'text': row['body_text'],
    }
    try:
        resp = await client.fetch(
            RESEND_API_URL,
            method='POST',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            body=json.dumps(body),
            request_timeout=HTTP_TIMEOUT,
            raise_error=False,
        )
        if 200 <= resp.code < 300:
            try:
                data = json.loads(resp.body.decode('utf-8')) if resp.body else {}
            except Exception:
                data = {}
            provider_id = (data.get('id') or '')[:100]
            with get_conn() as conn:
                conn.execute(
                    "UPDATE email_queue SET status='sent', provider='resend', "
                    "provider_id=?, sent_at=NOW(), updated_at=NOW() WHERE id=?",
                    (provider_id, row['id'])
                )
            _log('sent', id=row['id'], to=row['to_email'], provider_id=provider_id)
            return True
        else:
            body_text = ''
            try:
                if resp.body:
                    body_text = resp.body.decode('utf-8', errors='replace')
            except Exception:
                body_text = ''
            err = f'HTTP {resp.code}: {body_text}'[:500]
            _handle_failure(row, err)
            return False
    except httpclient.HTTPError as e:
        err = f'HTTPError {getattr(e, "code", "?")}: {str(e)}'[:500]
        _handle_failure(row, err)
        return False
    except Exception as e:
        _handle_failure(row, str(e)[:500])
        return False


async def _tick():
    """Um ciclo do worker: poll + process batch."""
    api_key = os.environ.get('RESEND_API_KEY')
    from_raw = os.environ.get('EMAIL_FROM', 'noreply@send.izylaudo.com.br')
    # Formato RFC 5322: 'Nome <email@dominio>'
    if '<' not in from_raw:
        from_addr = f'izyLAUDO <{from_raw}>'
    else:
        from_addr = from_raw
    if not api_key:
        # Log uma vez por tick para nao poluir; sem crash.
        _log('skipping_tick reason=missing_RESEND_API_KEY')
        return
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id, user_id, to_email, subject, body_html, body_text, "
                "attempts, max_attempts "
                "FROM email_queue "
                "WHERE status='pending' "
                "AND (next_retry_at IS NULL OR next_retry_at <= NOW()) "
                "ORDER BY created_at LIMIT ?",
                (BATCH_SIZE,)
            ).fetchall()
    except Exception as e:
        _log('tick_poll_error', err=str(e)[:200])
        return

    if not rows:
        return

    _log('polling', batch=len(rows))
    for row in rows:
        # Converter RealDictRow para dict simples para acesso .get()
        row_dict = dict(row)
        try:
            await _process_one(row_dict, api_key, from_addr)
        except Exception as e:
            _log('process_one_error', id=row_dict.get('id'), err=str(e)[:200])


def start_email_worker():
    """Inicia o worker. Deve ser chamado apos app.listen(port) e antes de IOLoop.start()."""
    api_key_present = bool(os.environ.get('RESEND_API_KEY'))
    _log(f'Worker started interval_s={POLL_INTERVAL_MS // 1000} '
         f'batch={BATCH_SIZE} api_key_present={api_key_present}')
    # Primeiro tick apos 3s para deixar IOLoop estabilizar.
    io = ioloop.IOLoop.current()
    io.call_later(3, lambda: io.add_callback(_tick))
    pc = ioloop.PeriodicCallback(_tick, POLL_INTERVAL_MS)
    pc.start()
    return pc
