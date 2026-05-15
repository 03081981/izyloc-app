"""
WhatsApp Cloud API webhook handlers — Push 106
================================================
Recebe mensagens do WhatsApp Cloud API (Meta) e responde via Claude Haiku.

4 casos de uso suportados:
  1. Lead (cliente novo, telefone nao cadastrado em users) — chatbot IA + notifica Carlos
  2. Suporte (telefone ja eh usuario do izyLAUDO)         — chatbot IA + notifica Carlos
  3. Chatbot IA (responde sozinho com Claude Haiku)        — handoff humano se cliente pedir
  4. Disparos (notificacoes) — funcao send_whatsapp_template() pra chamar de outros pontos

Variaveis de ambiente obrigatorias (definidas no Railway):
  WHATSAPP_VERIFY_TOKEN          — string aleatoria pra Meta validar o webhook
  WHATSAPP_ACCESS_TOKEN          — token permanente do System User izy Bot
  WHATSAPP_PHONE_NUMBER_ID       — ID do numero real verificado
  WHATSAPP_BUSINESS_ACCOUNT_ID   — WABA ID (Grupo izy)

Endpoints expostos:
  GET  /webhook/whatsapp  — verificacao Meta (responde hub.challenge)
  POST /webhook/whatsapp  — recebe eventos (mensagens, status)

State:
  automation/whatsapp_state.json — contatos, modo (ai/human), historico
"""
import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

import requests
import tornado.web

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_BUSINESS_ACCOUNT_ID = os.environ.get('WHATSAPP_BUSINESS_ACCOUNT_ID', '')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'cansliban@gmail.com')

GRAPH_API = 'https://graph.facebook.com/v21.0'

# Modelo Claude pra chatbot — Haiku 4.5 (rapido + barato pra mensagens curtas)
CHATBOT_MODEL = 'claude-haiku-4-5-20251001'
CHATBOT_SYSTEM = """Voce e o assistente virtual do Grupo izy no WhatsApp.

O Grupo izy reune 3 produtos de tecnologia pra mercado imobiliario:
- izyLAUDO: vistorias com IA (tira foto -> sistema descreve -> gera laudo PDF). Reduz vistoria de 3h pra 20min. Site: https://www.izylaudo.com.br  App: https://app.izylaudo.com.br  Tem teste gratis (3 laudos).
- izyLOC: sistema de gestao de carteira de locacao
- izycred: garantia locaticia

Regras de resposta:
- Tom profissional, direto e amigavel
- Portugues brasileiro com acentuacao correta
- Maximo 3-4 frases por mensagem
- Se a pessoa pedir falar com "atendente" / "humano" / "pessoa" / "alguem", responda APENAS com: HANDOFF_HUMANO
- Se perguntarem algo fora do escopo Grupo izy (ex: piada, politica, outro assunto), responda educadamente e oriente a falar com atendente
- NAO invente precos, planos ou prazos que nao foram fornecidos aqui
- Sempre que possivel, incentive o cliente a testar o izyLAUDO gratis no site
- NAO use markdown — apenas texto simples (WhatsApp nao renderiza)
"""

STATE_FILE = Path(__file__).parent / 'automation' / 'whatsapp_state.json'

# Palavras que disparam handoff manual pelo cliente
HANDOFF_TRIGGERS = (
    'atendente', 'humano', 'falar com alguem', 'falar com uma pessoa',
    'falar com vendedor', 'falar com voces', 'quero falar',
)


def _log(event, **kw):
    """Log estruturado com prefixo [WAPP] pra filtragem no Railway."""
    parts = ' '.join(f'{k}={str(v)[:160]}' for k, v in kw.items())
    print(f'[WAPP] {event} {parts}', flush=True)


# ----------------------------------------------------------------------------
# STATE
# ----------------------------------------------------------------------------
def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {'contacts': {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        _log('state_read_error', err=str(e)[:120])
        return {'contacts': {}}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
    except Exception as e:
        _log('state_write_error', err=str(e)[:120])


# ----------------------------------------------------------------------------
# WHATSAPP API HELPERS
# ----------------------------------------------------------------------------
def send_whatsapp_text(to_phone: str, text: str) -> dict:
    """Envia mensagem de texto. to_phone no formato internacional sem '+': 5511999999999."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        _log('send_skipped', reason='env_missing')
        return {'error': 'env_missing'}
    try:
        r = requests.post(
            f'{GRAPH_API}/{WHATSAPP_PHONE_NUMBER_ID}/messages',
            headers={
                'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
                'Content-Type': 'application/json',
            },
            json={
                'messaging_product': 'whatsapp',
                'to': to_phone,
                'type': 'text',
                'text': {'body': text[:4096]},
            },
            timeout=15,
        )
        data = r.json() if r.content else {}
        if r.status_code != 200:
            _log('send_error', status=r.status_code, body=str(data)[:200])
            return {'error': data}
        _log('sent', to=to_phone, n=len(text))
        return data
    except Exception as e:
        _log('send_exception', err=str(e)[:200])
        return {'error': str(e)}


def send_whatsapp_template(
    to_phone: str,
    template_name: str,
    language: str = 'pt_BR',
    components: list = None,
) -> dict:
    """Envia template aprovado pra disparos business-initiated (notificacoes, marketing).

    Templates precisam ser criados e aprovados em Business Manager antes do uso.
    components = [{'type': 'body', 'parameters': [{'type': 'text', 'text': 'valor'}]}]
    """
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        return {'error': 'env_missing'}
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
            _log('template_error', status=r.status_code, body=str(data)[:200])
            return {'error': data}
        _log('template_sent', to=to_phone, template=template_name)
        return data
    except Exception as e:
        _log('template_exception', err=str(e)[:200])
        return {'error': str(e)}


# ----------------------------------------------------------------------------
# CLASSIFICACAO E IA
# ----------------------------------------------------------------------------
def _classify_lead_or_user(phone: str) -> str:
    """Retorna 'user' se o telefone bate com um usuario do izyLAUDO, senao 'lead'."""
    try:
        from database import get_conn
        digits = ''.join(c for c in phone if c.isdigit())
        if len(digits) < 8:
            return 'lead'
        # Tenta bater os ultimos 8-11 digitos (cobre formatos com/sem DDI/9)
        tail8 = digits[-8:]
        tail11 = digits[-11:] if len(digits) >= 11 else digits
        with get_conn() as conn:
            cur = conn.execute(
                "SELECT id, email, name FROM users "
                "WHERE phone LIKE ? OR phone LIKE ? LIMIT 1",
                (f'%{tail11}', f'%{tail8}'),
            )
            row = cur.fetchone()
            if row:
                return 'user'
    except Exception as e:
        _log('classify_exception', err=str(e)[:200])
    return 'lead'


def _ai_reply(text: str, history: list) -> tuple:
    """Chama Claude Haiku. Retorna (resposta_texto, handoff_bool)."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        messages = (history or []) + [{'role': 'user', 'content': text}]
        resp = client.messages.create(
            model=CHATBOT_MODEL,
            max_tokens=400,
            system=CHATBOT_SYSTEM,
            messages=messages,
        )
        reply = resp.content[0].text.strip() if resp.content else ''
        if reply.upper().strip() == 'HANDOFF_HUMANO':
            return (
                'Beleza! Vou te conectar com a equipe do Grupo izy. Em breve alguem responde por aqui. 👋',
                True,
            )
        if not reply:
            reply = 'Pode reformular sua pergunta? Nao entendi bem.'
        return (reply, False)
    except Exception as e:
        _log('ai_exception', err=str(e)[:200])
        return (
            'Tive um problema agora. Pode tentar de novo? Ou mande "atendente" pra falar com a equipe.',
            False,
        )


# ----------------------------------------------------------------------------
# NOTIFICACAO POR EMAIL
# ----------------------------------------------------------------------------
def _notify(kind: str, phone: str, name: str, message: str, ai_reply: str = '') -> None:
    """Envia email pro Carlos quando rola um lead novo, handoff ou msg de user."""
    try:
        # importa funcao do server (evita circular import no topo)
        from server import send_email
        icon = {'lead': '🆕', 'handoff': '👤', 'user': '💬'}.get(kind, '📩')
        title = {
            'lead': 'Novo lead WhatsApp',
            'handoff': 'Cliente pediu atendente humano',
            'user': 'Mensagem de cliente izyLAUDO',
        }.get(kind, 'Mensagem WhatsApp')
        wa_phone = ''.join(c for c in phone if c.isdigit())
        ai_block = ''
        if ai_reply:
            ai_block = (
                '<p style="margin-top:16px"><strong>Resposta automatica enviada (IA):</strong></p>'
                f'<pre style="white-space:pre-wrap;font-family:inherit;background:#fffbeb;'
                f'padding:12px;border-radius:8px;border:1px solid #fde68a">{ai_reply}</pre>'
            )
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;padding:24px;background:#f9fafb">
<div style="max-width:600px;margin:0 auto;background:#fff;border-left:4px solid #10b981;padding:24px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
<h2 style="color:#10b981;margin:0 0 16px 0">{icon} {title}</h2>
<p><strong>De:</strong> {name or '(sem nome)'} &mdash; +{wa_phone}</p>
<p><strong>Mensagem do cliente:</strong></p>
<pre style="white-space:pre-wrap;font-family:inherit;background:#f0fdf4;padding:12px;border-radius:8px;border:1px solid #d1fae5">{message}</pre>
{ai_block}
<p style="margin-top:24px"><a href="https://wa.me/{wa_phone}" style="display:inline-block;background:#25D366;color:white;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:600">Responder no WhatsApp</a></p>
<p style="color:#6b7280;font-size:12px;margin-top:24px">🤖 Webhook WhatsApp izyLAUDO &mdash; {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}</p>
</div></body></html>"""
        send_email(ADMIN_EMAIL, f'{icon} WhatsApp: {title} de {name or wa_phone}', html)
    except Exception as e:
        _log('notify_exception', err=str(e)[:200])


# ----------------------------------------------------------------------------
# HANDLER TORNADO
# ----------------------------------------------------------------------------
class WhatsAppWebhookHandler(tornado.web.RequestHandler):
    """Webhook Cloud API do WhatsApp.

    GET: Meta valida o webhook batendo com hub.verify_token.
    POST: Meta entrega eventos (mensagens, status). Responde 200 rapido (timeout 5s)
          e processa em seguida.
    """

    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin', '*')

    async def get(self):
        mode = self.get_argument('hub.mode', '')
        token = self.get_argument('hub.verify_token', '')
        challenge = self.get_argument('hub.challenge', '')
        if (
            mode == 'subscribe'
            and WHATSAPP_VERIFY_TOKEN
            and token == WHATSAPP_VERIFY_TOKEN
        ):
            _log('verify_ok', challenge=challenge)
            self.set_header('Content-Type', 'text/plain')
            self.write(challenge)
        else:
            _log('verify_fail', mode=mode, token_match=(token == WHATSAPP_VERIFY_TOKEN))
            self.set_status(403)
            self.write('forbidden')

    async def post(self):
        try:
            payload = json.loads(self.request.body or b'{}')
        except Exception:
            self.set_status(400)
            self.write('bad json')
            return

        # Responde 200 imediatamente pra Meta nao re-tentar (timeout 5s deles)
        self.set_status(200)
        self.write('ok')
        await self.finish()

        # Processa depois de ja ter respondido
        try:
            self._handle_event(payload)
        except Exception as e:
            _log('handle_exception', err=str(e)[:300], tb=traceback.format_exc()[:500])

    # ------------------------------------------------------------------------
    # Pipeline de eventos
    # ------------------------------------------------------------------------
    def _handle_event(self, payload: dict) -> None:
        for entry in payload.get('entry', []) or []:
            for change in entry.get('changes', []) or []:
                value = change.get('value', {}) or {}
                # Map telefone -> nome (vem em contacts)
                contact_map = {}
                for c in value.get('contacts', []) or []:
                    wa_id = c.get('wa_id', '')
                    nm = (c.get('profile') or {}).get('name', '')
                    if wa_id:
                        contact_map[wa_id] = nm
                # Mensagens recebidas
                for msg in value.get('messages', []) or []:
                    self._handle_message(msg, contact_map)
                # Status updates (delivered/read/failed) — so loga
                for s in value.get('statuses', []) or []:
                    _log(
                        'status',
                        s_id=s.get('id', '')[:20],
                        status=s.get('status'),
                        recipient=s.get('recipient_id'),
                    )

    def _handle_message(self, msg: dict, contact_map: dict) -> None:
        msg_type = msg.get('type', '')
        from_phone = msg.get('from', '')
        name = contact_map.get(from_phone, '')
        _log('msg_in', from_phone=from_phone, type=msg_type, name=name)

        # MVP: so processa texto. Outros tipos viram mensagem informativa.
        if msg_type != 'text':
            send_whatsapp_text(
                from_phone,
                'Recebi seu arquivo. No momento so consigo responder a mensagens '
                'de texto. Pode descrever sua duvida em texto? Ou mande "atendente" '
                'pra falar com a equipe.',
            )
            _notify('user', from_phone, name, f'<{msg_type}> nao processado')
            return

        text = ((msg.get('text') or {}).get('body') or '').strip()
        if not text:
            return

        state = _load_state()
        contacts = state.setdefault('contacts', {})
        contact = contacts.setdefault(from_phone, {
            'name': name,
            'first_seen': datetime.now(timezone.utc).isoformat(),
            'mode': 'ai',
            'history': [],
            'is_user': None,
        })
        if name and not contact.get('name'):
            contact['name'] = name

        # Cache classificacao lead/user no primeiro contato
        if contact.get('is_user') is None:
            contact['is_user'] = (_classify_lead_or_user(from_phone) == 'user')

        kind_label = 'user' if contact['is_user'] else 'lead'
        is_first_msg = not contact.get('history')

        # Trigger explicito de handoff
        if any(t in text.lower() for t in HANDOFF_TRIGGERS):
            contact['mode'] = 'human'
            send_whatsapp_text(
                from_phone,
                f'Beleza{", " + contact["name"] if contact.get("name") else ""}! '
                'Vou te conectar com a equipe do Grupo izy. Em breve alguem '
                'responde por aqui. 👋',
            )
            _notify('handoff', from_phone, contact.get('name', ''), text)
            contact.setdefault('history', []).append({'role': 'user', 'content': text})
            contact['history'] = contact['history'][-20:]
            _save_state(state)
            return

        # Modo humano — bot fica calado, so loga + notifica
        if contact.get('mode') == 'human':
            _notify(kind_label, from_phone, contact.get('name', ''), text)
            contact.setdefault('history', []).append({'role': 'user', 'content': text})
            contact['history'] = contact['history'][-20:]
            _save_state(state)
            return

        # Modo IA — Claude Haiku responde
        history = contact.get('history', [])[-10:]
        reply, handoff = _ai_reply(text, history)
        send_whatsapp_text(from_phone, reply)

        contact.setdefault('history', []).append({'role': 'user', 'content': text})
        contact['history'].append({'role': 'assistant', 'content': reply})
        contact['history'] = contact['history'][-20:]

        if handoff:
            contact['mode'] = 'human'
            _notify('handoff', from_phone, contact.get('name', ''), text, reply)
        elif is_first_msg:
            # Notifica Carlos no primeiro contato — mesmo que IA tenha respondido
            _notify(kind_label, from_phone, contact.get('name', ''), text, reply)

        _save_state(state)
