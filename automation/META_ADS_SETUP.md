# Setup do Sistema de Automação Meta Ads — izyLAUDO

Este documento explica como **Carlos** configura o System User e o token de acesso uma única vez, para que o script `meta_ads_daily_report.py` possa rodar automaticamente todo dia.

---

## Passo 1 — Vincular o app `izyLAUDO` ao BM Liban

O app `izyLAUDO` (ID `999362752748273`) foi criado no portfólio "Izylaudo Vistorias Imobiliárias", mas a conta de Ads `293213758001508` está no BM "Liban Liban". Precisamos linkar o app ao BM correto.

1. Abre: `https://business.facebook.com/settings/apps`
2. No seletor de portfólio empresarial (topo direito), escolhe **"Liban Liban"**
3. Clica **+ Adicionar → Conectar um app**
4. Cola o ID `999362752748273` ou seleciona "izyLAUDO"
5. Confirma

---

## Passo 2 — Criar System User no BM Liban

System Users geram tokens permanentes (não expiram), ideais para automação 24/7.

1. Mesmo BM "Liban Liban" → menu lateral → **Usuários do sistema**
2. Clica **+ Adicionar**
3. Preenche:
   - **Nome:** `automation_izylaudo_ads`
   - **Função do usuário do sistema:** **Administrador**
4. Clica **Criar usuário do sistema**

---

## Passo 3 — Atribuir assets ao System User

Após criar, o System User aparece na lista. Clica nele para abrir os detalhes.

**Atribui 3 assets:**

### 3a) Conta de Anúncios
- Clica **Adicionar ativos → Contas de anúncios**
- Seleciona `Liban Liban (293213758001508)`
- Permissão: **Controle total**

### 3b) App
- Clica **Adicionar ativos → Apps**
- Seleciona `izyLAUDO`
- Permissão: **Gerenciar app**

### 3c) Página Facebook
- Clica **Adicionar ativos → Páginas**
- Seleciona `Izylaudo`
- Permissão: **Criar anúncios**

---

## Passo 4 — Gerar Token de Acesso permanente

Ainda na tela do System User:

1. Clica **Gerar novo token**
2. Seleciona o app: **izyLAUDO**
3. Marca os escopos (permissions):
   - ✅ `ads_management` — criar/editar/pausar campanhas
   - ✅ `ads_read` — ler métricas
   - ✅ `business_management` — gerenciar BM
   - ✅ `pages_read_engagement` — ler engajamento da página
   - ✅ `pages_manage_posts` — postar conteúdo orgânico (opcional, para automação de posts)
4. Clica **Gerar token**

Vai aparecer uma string longa (200+ caracteres) começando com `EAAS...` ou similar.

**COPIA esse token e guarda em local SEGURO — só vai aparecer essa vez.**

---

## Passo 5 — Configurar variáveis de ambiente no Railway

No Railway, vai em **Variables** do serviço izyLAUDO e adiciona:

| Variável | Valor |
|---|---|
| `META_ADS_TOKEN` | O token gerado no Passo 4 (cola aqui) |
| `META_AD_ACCOUNT_ID` | `293213758001508` |
| `META_API_VERSION` | `v21.0` (opcional, é o padrão) |
| `EMAIL_USER` | `suporte@izylaudo.com.br` (ou Gmail) |
| `EMAIL_PASS` | App password do Gmail (não a senha normal) |
| `EMAIL_RECIPIENT` | `cansliban@gmail.com` |

---

## Passo 6 — Testar manualmente

Após configurar tudo, roda o script localmente para validar:

```bash
export META_ADS_TOKEN="EAAS..."
export META_AD_ACCOUNT_ID="293213758001508"
python3 .github/scripts/meta_ads_daily_report.py
```

Se tudo OK, vai imprimir o resumo no console e enviar o email.

---

## Passo 7 — Ativar o GitHub Action diário

Carlos adiciona o arquivo `meta-ads-daily.yml` em `.github/workflows/` via Web Editor do GitHub (porque o PAT atual não tem `workflow` scope). O conteúdo está em `automation/github_workflow_template.yml`.

Após adicionar, vai em **GitHub → Settings → Secrets** e adiciona os mesmos secrets do Passo 5.

Cron configurado: **9h BRT diariamente** (12h UTC).

---

## Próximos passos (Fase 2)

Após validar o relatório por 1-2 semanas, ativamos:
- ✅ Scaling automático de vencedoras (CPC < R$0.30 → +20% budget)
- ✅ Pausa automática de perdedoras (CPC > R$0.80 ou CTR < 0.5%)
- ✅ A/B test automático de criativos
- ✅ Retargeting automatizado
- ✅ Lookalike audiences

Cada uma dessas features vai ser ativada com seu próprio commit + flag, para Carlos poder reverter facilmente se necessário.
