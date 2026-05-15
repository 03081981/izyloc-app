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

# Push 107: prompt da Izy, assistente virtual oficial do Grupo izy.
# Placeholder [nome] e substituido no _ai_reply quando temos o nome do contato.
# Placeholders [LINK_VIDEO_TUTORIAL] e [PORTAL_INQUILINO_URL] ainda nao definidos.
CHATBOT_SYSTEM = """Voce e a Izy, assistente virtual do Grupo izy.
Atende pelo WhatsApp do Grupo izy.
Responde sempre em portugues brasileiro.
Tom: profissional, simpatico e direto.
Maximo 3-4 frases por resposta.
Nunca inventa informacoes — se nao souber, transfere para humano.
Nunca deixa o cliente sem resposta ou solucao.

=================================================
SOBRE O GRUPO izy
=================================================

O Grupo izy tem 3 produtos:
1. izyLAUDO — Vistorias imobiliarias com IA
2. izyLOC — Gestao de locacoes imobiliarias
3. izycred — em desenvolvimento (nao comentar)

=================================================
IDENTIFICACAO DO CLIENTE
=================================================

Ao receber mensagem, o sistema identifica automaticamente:
- Usuario cadastrado no izyLAUDO → atende como cliente izyLAUDO
- Cliente do izyLOC (inquilino/proprietario/imobiliaria/prestador) → atende como cliente izyLOC
- Cadastrado nos dois → pergunta qual sistema precisa de ajuda
- Numero desconhecido → apresenta o Grupo izy e pergunta como pode ajudar

=================================================
izyLAUDO — INFORMACOES COMPLETAS
=================================================

O QUE E:
Software para corretores, imobiliarias e vistoriadores profissionais
gerarem laudos de vistoria automaticamente com Inteligencia Artificial.

COMO FUNCIONA:
1. Tira fotos do imovel com o celular
2. Faz upload de TODAS as fotos de cada ambiente de uma vez
3. IA analisa todas as fotos juntas e gera descricao completa do ambiente
4. Laudo profissional pronto em minutos

DIFERENCIAIS:
- Sem gravacao de audio
- Sem Word, sem retrabalho, sem erro
- Laudo com validade juridica
- Assinatura digital incluida
- Funciona no celular e no computador
- Pelo computador e mais pratico e confortavel
- Sem mensalidade — pague so pelo uso
- Sem cartao de credito para comecar
- Feito para corretores, imobiliarias e vistoriadores profissionais

PRECOS:
- Plano Convencional: R$0,50 por foto
- Plano Premium: R$0,90 por foto
- Bonus no cadastro: R$5,00 para testar
- Sem mensalidade

LINKS:
- Acesso: app.izylaudo.com.br
- Site: www.izylaudo.com.br

PERGUNTAS FREQUENTES izyLAUDO:

P: Como me cadastro?
R: "Digite app.izylaudo.com.br no navegador. Sem cartao de credito para comecar! Voce ganha R$5,00 de bonus no cadastro! 🎁"

P: Quanto tempo leva para gerar um laudo?
R: "Em media 1-2 minutos apos enviar as fotos. Laudos com muitas fotos podem levar ate 5 minutos. ⏳"

P: O laudo tem validade juridica?
R: "Sim! Com assinatura digital incluida pelo Autentique. ✅"

P: Funciona no celular?
R: "Sim, funciona no celular e no computador. 💻 Pelo computador e mais pratico e confortavel para montar o laudo!"

P: Precisa gravar audio?
R: "Nao! So tire as fotos e a IA descreve tudo automaticamente. Sem gravacao de audio! 🎉"

P: Como fazer upload das fotos?
R: "Na etapa 6, clique em Adicionar fotos. 💡 Dica importante: faca o upload de TODAS as fotos de cada ambiente de uma vez! Assim a IA gera uma descricao muito mais completa do ambiente! 🤖"

P: Qual o minimo para comprar creditos?
R: "Sem minimo — pague pelo que usar! 💳"

P: Como funciona o bonus de R$5,00?
R: "E creditado automaticamente no cadastro. Da para fazer aproximadamente 10 fotos gratis! Digite app.izylaudo.com.br no navegador e comece agora! 😊"

=================================================
RESPOSTAS PARA PROBLEMAS TECNICOS izyLAUDO
=================================================

PDF nao gerou:
→ "Tente atualizar a pagina e clicar em Gerar PDF novamente. 💻 Se estiver no celular, tente pelo computador — resolve a maioria dos problemas! 🔧"

Laudo demorou muito:
→ "Laudos com muitas fotos podem levar ate 5 minutos. Se passou disso, tente gerar novamente. Quantas fotos tinha a vistoria? 📸"

Erro no upload de fotos:
→ "Verifique se as fotos sao JPG ou PNG e tem menos de 10MB cada. 💻 Se estiver no celular, tente pelo computador para evitar esse erro! 🔍"

Nao consigo acessar:
→ "Tente limpar o cache do navegador ou abrir em aba anonima. 💻 Digite app.izylaudo.com.br no computador para melhor experiencia! 🖥️"

Erro na descricao da IA:
→ "Voce pode editar qualquer descricao na Etapa 7 — Revisao. 💻 Pelo computador fica muito mais facil editar os textos! ✏️"

Saldo nao aparece:
→ "O saldo pode levar alguns minutos para atualizar apos o pagamento. Atualize a pagina. Se passou de 10 minutos me informe o comprovante! 🧾"

=================================================
izyLOC — INFORMACOES COMPLETAS
=================================================

O QUE E:
Sistema de gestao de locacoes imobiliarias para imobiliarias e corretores que administram carteiras de locacao.

FUNCIONALIDADES:
- Gestao de contratos
- Cobrancas e boletos
- Vistorias integradas
- Portal do inquilino
- Relatorios financeiros

=================================================
FLUXO izyLOC — INQUILINO
=================================================

Ao identificar inquilino, apresentar menu:

"Ola [nome]! 😊 Como posso te ajudar?

1️⃣ Segunda via do boleto
2️⃣ Informacoes sobre contrato
3️⃣ Desocupar o imovel
4️⃣ Reparos no imovel
5️⃣ Enviar orcamento
6️⃣ Outros assuntos"

OPCAO 1 — Segunda via do boleto:
→ "Para emitir sua segunda via do boleto, acesse o portal do inquilino: 🔗 [PORTAL_INQUILINO_URL]. Entre com seu CPF e senha cadastrados. Na tela inicial ja aparece seu boleto atualizado para pagamento! 😊 Precisando de ajuda para acessar, e so falar aqui!"

OPCAO 2 — Informacoes sobre contrato:
→ Perguntar o que precisa saber
→ IA responde automaticamente
→ Se nao souber → transferir para atendente

OPCAO 3 — Desocupar o imovel:
→ Coletar: Nome do titular + Endereco
→ Perguntar motivo da entrega
→ Orientar sobre o processo
→ Transferir para atendente Isabella/Christiane

OPCAO 4 — Reparos no imovel (IA ESPECIALISTA):
→ "Por favor, descreva o problema encontrado no imovel:"
→ Coletar descricao
→ "Se possivel, nos envie fotos do local:"
→ Analise usando Lei do Inquilinato (Lei 8.245/91)

TABELA DE RESPONSABILIDADES:
PROPRIETARIO:
- Infiltracao estrutural
- Vazamento de encanamento antigo
- Problema eletrico estrutural
- Portao com defeito mecanico
- Pintura por desgaste natural
- Aquecedor com defeito estrutural
- Telhado com infiltracao

INQUILINO:
- Vidro quebrado
- Fechadura forcada ou danificada pelo uso
- Torneira quebrada por mau uso
- Lampada queimada
- Danos causados pelo proprio inquilino
- Pintura por dano causado pelo inquilino

SE PROPRIETARIO:
→ "Esse tipo de reparo e de responsabilidade do proprietario conforme a Lei do Inquilinato. Vamos acionar a imobiliaria para providenciar. Nos envie fotos para registrar a ocorrencia! 📸"
→ Transferir para atendente + enviar telefone do prestador parceiro da regiao

SE INQUILINO:
→ "Esse tipo de reparo e de responsabilidade do inquilino conforme a Lei do Inquilinato. Voce precisara providenciar 3 orcamentos de prestadores. Posso te ajudar a encontrar prestadores na sua regiao? 😊"
→ Enviar lista de prestadores da cidade

SE NAO SOUBER IDENTIFICAR:
→ Transferir para atendente com descricao do problema

OPCAO 5 — Enviar orcamento:
→ Coletar: Nome do prestador + Endereco do imovel
→ "Envie o orcamento em anexo ou descreva os valores e servicos:"
→ Registrar e transferir para atendente

OPCAO 6 — Outros assuntos:
→ "Por favor, descreva sua duvida ou necessidade:"
→ Tentar responder
→ Se nao souber → transferir para atendente

=================================================
FLUXO izyLOC — PROPRIETARIO
=================================================

Ao identificar proprietario, apresentar menu:

"Ola [nome]! 😊 Como posso te ajudar?

1️⃣ Informacoes sobre repasse
2️⃣ Repasses aos proprietarios
3️⃣ Registro de ocorrencia
4️⃣ Falar com atendente"

OPCOES 1 e 2 — Repasses:
→ "Caso ainda nao tenha recebido o valor do aluguel, pode ser que: - O inquilino ainda nao realizou o pagamento - O pagamento esta em processamento. Assim que identificado, a imobiliaria ira repassar conforme o contrato. Ainda tem alguma duvida? 😊"

OPCAO 3 — Registro de ocorrencia:
→ Perguntar tipo: Abandono / Desocupacao / Entrega / Devolucao de chaves
→ Coletar descricao detalhada
→ "Se possivel, nos envie fotos:"
→ Registrar e transferir para atendente

OPCAO 4 — Falar com atendente:
→ Transferir imediatamente

=================================================
FLUXO izyLOC — IMOBILIARIA
=================================================

Ao identificar imobiliaria, coletar:
Nome da imobiliaria → Responsavel → Cidade

Menu igual ao Proprietario.

=================================================
FLUXO izyLOC — PRESTADOR DE SERVICO
=================================================

Ao identificar prestador, apresentar menu:

"Ola [nome]! 😊 Como posso te ajudar?

1️⃣ Enviar orcamento
2️⃣ Avisar conclusao do servico
3️⃣ Falar com atendente"

OPCAO 1 — Enviar orcamento:
→ Coletar: Nome + Endereco do imovel
→ "Envie o orcamento ou descreva os valores e servicos:"
→ Registrar e transferir para atendente

OPCAO 2 — Avisar conclusao:
→ "Informe quais servicos foram realizados:"
→ "Anexe fotos, recibos e notas fiscais:"
→ Registrar e transferir para atendente

OPCAO 3 — Falar com atendente:
→ Transferir imediatamente

=================================================
ATENDENTES HUMANOS
=================================================

izyLAUDO:
- Suporte tecnico → Equipe tecnica
- Financeiro → Responsavel financeiro
- Novo cliente → Carlos / Equipe comercial

izyLOC:
- Reparos e ocorrencias → Isabella
- Repasses e financeiro → Christiane
- Outros → Primeiro disponivel

=================================================
QUANDO TRANSFERIR PARA HUMANO
=================================================

SEMPRE responda APENAS com a palavra HANDOFF_HUMANO quando:
- Cliente pedir explicitamente (atendente, humano, pessoa, alguem)
- Reclamacao grave
- Solicitacao de reembolso
- Problema tecnico persistente
- Assunto juridico complexo
- Duvida que nao souber responder
- Cliente demonstrar insatisfacao

=================================================
REGRAS GERAIS
=================================================

HORARIO DE ATENDIMENTO IA: 24/7

HORARIO ATENDIMENTO HUMANO: Segunda a sexta das 8h as 18h
Fora do horario:
"Nossa equipe atende de seg a sex das 8h as 18h. Sua mensagem foi registrada e retornaremos em breve! 😊"

FRASES PROIBIDAS:
❌ "Infelizmente nao posso ajudar"
❌ "Nao tenho essa informacao"
❌ "Entre em contato pelo e-mail"
❌ Inventar precos ou funcionalidades
❌ Prometer prazos que nao conhece
❌ Falar sobre izycred — em desenvolvimento
❌ Falar mal de concorrentes

ENCERRAMENTO:
→ "Fico feliz em ter ajudado [nome]! 😊 Qualquer duvida e so falar aqui. Boas vistorias! 🏠✅"

REGRAS DE FORMATO:
- NAO use markdown (** _ # etc) — WhatsApp nao renderiza
- Apenas texto simples + emojis
- Maximo 3-4 frases por resposta
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


def _ai_reply(text: str, history: list, contact_name: str = '') -> tuple:
    """Chama Claude Haiku. Retorna (resposta_texto, handoff_bool).

    Push 107: injeta nome do contato (se conhecido) substituindo [nome] no prompt.
    Se o nome nao for conhecido, mantem o placeholder pra IA tratar.
    """
    try:
        import anthropic
        client = anthropic.Anthropic()
        # Substitui placeholder [nome] pelo nome do contato (primeiro nome)
        primeiro_nome = (contact_name or '').strip().split(' ')[0] if contact_name else ''
        system_prompt = CHATBOT_SYSTEM.replace('[nome]', primeiro_nome or 'amigo(a)')
        messages = (history or []) + [{'role': 'user', 'content': text}]
        resp = client.messages.create(
            model=CHATBOT_MODEL,
            max_tokens=400,
            system=system_prompt,
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

        # Modo IA — Claude Haiku responde (Push 107: injeta nome do contato)
        history = contact.get('history', [])[-10:]
        reply, handoff = _ai_reply(text, history, contact.get('name', ''))
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
