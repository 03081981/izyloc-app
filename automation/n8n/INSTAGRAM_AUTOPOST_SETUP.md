# Fluxo n8n: Auto-post Instagram a partir do Blog izyLAUDO

Este workflow roda 2x/dia (9h e 18h BRT) e publica automaticamente no Instagram `@izylaudo` qualquer post novo que apareça no blog.

---

## O que o fluxo faz

```
Schedule (9h/18h BRT)
  └─> Busca RSS do blog (/blog/rss.xml)
       └─> Parse XML
            └─> Extrai post mais recente + imagem
                 └─> IF é novo (vs último postado salvo)?
                      ├─ SIM:
                      │   ├─> Claude API gera caption Instagram
                      │   ├─> Instagram Graph API: cria media container
                      │   ├─> Wait 30s (Meta processar)
                      │   ├─> Instagram Graph API: publica
                      │   ├─> Salva slug no Static Data (anti-duplicata)
                      │   └─> Email de confirmação via Resend
                      └─ NÃO:
                          └─> Log "sem post novo"
```

---

## Pré-requisitos (3 coisas a configurar antes do primeiro run)

### 1. Conta Instagram Business vinculada à página Facebook Izylaudo

Pra usar a Graph API publicação, a conta `@izylaudo` precisa ser:
- Tipo **Business** ou **Creator** (não pessoal)
- Vinculada à **página Facebook "Izylaudo"** (ID 1137852659403045)

Verifica pelo app Instagram: Configurações → Conta → Mudar para conta Profissional → escolhe "Empresa" (se ainda não estiver). Depois Conexões → Página → escolhe "Izylaudo".

### 2. Obter o INSTAGRAM_USER_ID

O ID da conta Instagram Business é diferente do username. Pra descobrir:

```bash
curl "https://graph.facebook.com/v21.0/1137852659403045?fields=instagram_business_account&access_token={TOKEN}"
```

Onde `{TOKEN}` é seu User Access Token estendido (mesmo do Push 91/92, scope `pages_show_list` + `pages_read_engagement` precisam estar nele).

Resposta esperada:
```json
{
  "instagram_business_account": { "id": "17841400000000000" },
  "id": "1137852659403045"
}
```

Esse `instagram_business_account.id` (17 dígitos) é o seu **INSTAGRAM_USER_ID**.

### 3. Gerar token com scopes Instagram

O token atual (gerado no Push 91 com 7 scopes Marketing API) **NÃO inclui** os scopes Instagram. Precisa regenerar:

**No Graph API Explorer** (`https://developers.facebook.com/tools/explorer/999362752748273`), adicione os scopes:
- ✅ `instagram_basic` — leitura básica IG
- ✅ `instagram_content_publish` — publicar conteúdo IG
- ✅ `pages_show_list` (já tinha)
- ✅ `pages_read_engagement` (já tinha)
- ✅ `business_management` (já tinha)
- (opcional, mantém os anteriores: `ads_management`, `ads_read`, `whatsapp_*`)

⚠️ **Limitação importante**: `instagram_content_publish` em **modo Development do app** só funciona com:
- A conta Facebook do próprio admin/developer do app (Carlos Augusto / Augusto Santos)
- Até 25 testers cadastrados

Como `@izylaudo` é vinculada à Sua página Facebook (e você é admin do app `izyLAUDO`), **vai funcionar** sem precisar de App Review. ✅

Estende o token pra 60 dias no Access Token Debugger (mesmo procedimento do Push 91).

---

## Variáveis de ambiente no n8n

No painel do n8n (`n8n.izylaudo.com.br`), vai em **Settings → Variables** e adiciona:

| Nome | Valor |
|---|---|
| `INSTAGRAM_USER_ID` | (o ID de 17 dígitos do passo 2 acima) |
| `INSTAGRAM_ACCESS_TOKEN` | (o token estendido 60 dias do passo 3) |
| `ANTHROPIC_API_KEY` | (já existe — chave izyLAUDO-blog) |
| `RESEND_API_KEY` | (já existe — pra notificação por email) |

---

## Importar o workflow

1. No n8n abre **Workflows → Import from File**
2. Seleciona `instagram_auto_post.json` (este repo)
3. Importa
4. Verifica que cada nó está usando as variables corretas (clicar em cada nó e validar)
5. **Ativar o workflow** (toggle no topo direito)

---

## Testar manualmente antes de ativar o cron

1. Abre o workflow no editor n8n
2. Clica no nó **"Buscar RSS do Blog"**
3. Clica em **"Execute Node"** — verifica que retorna XML com posts
4. Clica no nó **"Verificar Post Novo"** → Execute Node
5. Verifica que `isNew: true` (primeira vez sempre vai ser true, depois salva o slug)
6. Manualmente roda os próximos nós (Claude, Instagram Upload, Publish)
7. Verifica que apareceu no `@izylaudo`

Se algum nó falhar, abre as execuções (Executions tab) e vê o erro JSON.

---

## Anti-duplicata

O workflow usa `$getWorkflowStaticData('global')` pra guardar o slug do último post publicado. Se o cron rodar 2x no mesmo dia e o post ainda for o mesmo, o segundo run para no IF e não duplica.

Pra resetar (ex: re-publicar o último post propositalmente): edita o workflow staticData via API n8n ou simplesmente apaga o valor `lastInstagramPostSlug` manualmente.

---

## Renovação do token Instagram (a cada 60 dias)

Mesmo processo do Meta Ads token (Push 91/93):
1. Graph API Explorer → Generate new token com os 5 scopes IG
2. Access Token Debugger → Extend (60 dias)
3. n8n → Settings → Variables → edita `INSTAGRAM_ACCESS_TOKEN`

**Sugestão**: adicionar um workflow n8n separado que verifica o token via `debug_token` endpoint e envia alerta por email 7 dias antes de expirar (similar ao que fizemos no script Python Meta Ads).

---

## Customização da caption

A caption é gerada pelo Claude com o seguinte system prompt (no nó "Claude: Gerar Caption"):

```
Voce e especialista em marketing imobiliario para Instagram.
Cria posts envolventes para o @izylaudo (vistorias imobiliarias com IA).
Regras: 
- Maximo 2200 caracteres
- 3-5 emojis estrategicos
- Tom profissional mas acessivel
- Terminar com CTA "Link na bio para ler o artigo completo"
- Hashtags fixas: #izylaudo #vistoriaimobiliaria #laudodigital
  #inteligenciaartificial #corretordeimoveis #imobiliaria
  #vistorialocacao #leidoinquilinato
```

Pra ajustar tom/estilo: edita o `system` no nó "Claude: Gerar Caption". Recomenda commitar versões via Git (export do workflow → JSON no repo).

---

## Custos estimados

Por execução (apenas quando há post novo):
- **Claude API** (Sonnet 4.5, ~500 input + 1500 output tokens): **~$0.02**
- **Instagram Graph API**: gratuito
- **Resend (1 email)**: gratuito (até 100/dia no plano free)

Frequência típica: 2x/dia × 7 dias × ~1 post/dia novo = ~7 execuções/semana = **~$0.14/semana** = ~$7/mês max.

---

## Próximos passos (futuras melhorias)

1. **Stories automáticos** — adicionar branch que também publica um story 24h após o feed post
2. **Carrossel** — usar `media_type=CAROUSEL` com 3-5 slides (capa + insights do artigo)
3. **Reels com áudio TTS** — usar ElevenLabs pra narrar e Kling pra criar vídeo de 15s
4. **Engagement bot** — outro workflow n8n que responde DMs automaticamente quando alguém pergunta sobre o post
5. **Cross-post LinkedIn** — adicionar branch que também posta na LIBAN Imobiliária no LinkedIn
