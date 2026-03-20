# ð  IZYLO â Sistema de Vistoria de ImÃ³veis

## Como Rodar o Sistema

### 1. Instale os requisitos (apenas na primeira vez)
```bash
pip install tornado PyJWT python-dotenv reportlab Pillow requests
```

### 2. Configure o arquivo .env
```bash
cp .env.example .env
# Edite o arquivo .env e coloque sua chave da API Anthropic
```

### 3. Inicie o servidor
```bash
python3 server.py
```

### 4. Acesse no navegador
```
http://localhost:8888
```

No celular: acesse o IP da sua mÃ¡quina na mesma rede WiFi.
Ex: `http://192.168.1.100:8888`

---

## Para Hospedar na Nuvem (ProduÃ§Ã£o)

### Railway (recomendado - grÃ¡tis para comeÃ§ar)
1. Criee conta em railway.app
2. Conecte seu repositÃ³rio GitHub
3. Defina as variÃ¡veis de ambiente: ANTHROPIC_API_KEY e SECRET_KEY
4. Deploy automÃ¡tico!

### Render
1. Crie conta em render.com
2. New > Web Service
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python server.py`

---

## Chave API Anthropic (para anÃ¡lise de fotos com IA)
1. Acesse: https://console.anthropic.com/
2. Crie uma conta
3. VÃ¡ em "API Keys" e gere uma nova chave
4. Cole no arquivo .env: `ANTHROPIC_API_KEY=sk-ant-...`

Custo estimado: ~R$ 0,10 a R$ 0,50 por laudo completo

---

## Estrutura do Projeto
```
izylo/
âââ server.py          # Servidor web (Tornado)
âââ database.py        # Banco de dados SQLite
âââ ai_service.py     # IntegraÃ§Ã£o com IA (Claude)
âââ pdf_service.py     # GeraÃ§Ã£o de laudos PDF
âââ requirements.txt   # DependÃªncias Python
âââ .env.example       # Modelo de configuraÃ§Ã£o
âââ static/
â   âââ index.html     # App web (frontend)
âââ db/
â   âââ izylo.db       # Banco de dados (criado automaticamente)
âââ uploads/           # Fotos enviadas (criado automaticamente)
```

---

## FASE 2 CONCLUÍDA — PAINEL ADMINISTRATIVO BÁSICO

> **Data de conclusão:** 19/03/2026
> **Ambiente:** Railway (produção) — https://izyloc-app-production.up.railway.app

### O que foi implementado

#### Painel Administrativo (/admin)
- Painel separado e independente do sistema principal (acesso via `/admin`)
- Autenticação própria com senha admin (variável `ADMIN_SECRET`, padrão: `izylaudo-admin-2024`)
- Token JWT exclusivo com flag `admin: true`, validade de 12h
- Arquivo estático servido por `AdminPageHandler` diretamente de `static/admin.html`

#### Dashboard de Estatísticas (`GET /api/admin/stats`)
- Total de clientes, clientes ativos e bloqueados
- Total de laudos criados
- Total de fotos enviadas
- Dados em tempo real do banco PostgreSQL

#### Gestão de Clientes (`GET/PUT /api/admin/clients` e `/api/admin/clients/:id`)
- Listagem de todos os clientes com status, plano, laudos e fotos por cliente
- Visualização detalhada de cada cliente (dados + plano + histórico)
- Bloqueio de conta: `PUT /api/admin/clients/:id` com `{ "action": "block" }` → retorna 403 no login
- Desbloqueio de conta: `{ "action": "activate" }` → acesso restaurado
- Edição de dados: `{ "action": "update" }` com name, email, phone, company_name

#### Controle de Uso por Cliente (`GET /api/admin/usage`)
- Relatório de uso por usuário: quantidade de laudos e fotos
- JOIN com tabela `item_photos` (nome correto da tabela no banco)

#### Gestão de Planos (`GET/POST /api/admin/plans` e `/api/admin/plans/:id`)
- Rotas implementadas e funcionando
- Tabelas `plans`, `user_plans` e `usage_logs` criadas no PostgreSQL
- Sem planos cadastrados ainda (próxima fase)

#### Sistema Principal Preservado
- Login, cadastro, recuperação de senha: sem alterações, funcionando normalmente
- Criação de laudos, geração de PDF, análise por IA: preservados
- Verificação de conta bloqueada no `LoginHandler`: 403 com mensagem correta

### Correções Aplicadas Durante a Fase 2

| Arquivo | Problema | Correção |
|---|---|---|
| `database.py` | `raw.close()` era chamado antes do código das tabelas admin, fechando a conexão e causando crash 502 em loop | Movido para o final de `init_db()`, depois de todos os `raw.commit()` |
| `server.py` | `AdminStatsHandler` e `AdminUsageHandler` referenciavam `FROM photos` (tabela inexistente) | Corrigido para `FROM item_photos` (nome real da tabela) |

### Novos Commits desta Fase
- `ad41e784` — Adicionar painel de administração (static/admin.html)
- `1dfddfff` — admin: add admin panel handlers (dashboard, clientes, planos, uso) + verificação de bloqueio no login
- `8e4c8af7` — admin: add tables plans, user_plans, usage_logs + colunas user status/is_admin
- `bc01b0f6` — fix: mover raw.close() para depois das tabelas admin (corrige 502)
- `fb5e5be3` — fix: corrigir nome da tabela photos → item_photos nos handlers admin

---

## Próximos Passos (Fase 3 em diante)

- **CRUD de planos** — criar, editar, ativar/desativar planos com preço e limites
- **Vincular plano ao cliente** — atribuir plano a um cliente pelo painel admin
- **Cobrança** — integração com gateway de pagamento (Stripe ou Pagar.me)
- **Assinatura digital** — assinatura eletrônica de laudos pelas partes
- **Login com Google** — autenticação OAuth via conta Google
