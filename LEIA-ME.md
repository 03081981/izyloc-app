# 🏠 IZYLO — Sistema de Vistoria de Imóveis

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

No celular: acesse o IP da sua máquina na mesma rede WiFi.
Ex: `http://192.168.1.100:8888`

---

## Para Hospedar na Nuvem (Produção)

### Railway (recomendado - grátis para começar)
1. Criee conta em railway.app
2. Conecte seu repositório GitHub
3. Defina as variáveis de ambiente: ANTHROPIC_API_KEY e SECRET_KEY
4. Deploy automático!

### Render
1. Crie conta em render.com
2. New > Web Service
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python server.py`

---

## Chave API Anthropic (para análise de fotos com IA)
1. Acesse: https://console.anthropic.com/
2. Crie uma conta
3. Vá em "API Keys" e gere uma nova chave
4. Cole no arquivo .env: `ANTHROPIC_API_KEY=sk-ant-...`

Custo estimado: ~R$ 0,10 a R$ 0,50 por laudo completo

---

## Estrutura do Projeto
```
izylo/
├── server.py          # Servidor web (Tornado)
├── database.py        # Banco de dados SQLite
├── ai_service.py     # Integração com IA (Claude)
├── pdf_service.py     # Geração de laudos PDF
├── requirements.txt   # Dependências Python
├── .env.example       # Modelo de configuração
├── static/
│   └── index.html     # App web (frontend)
├── db/
│   └── izylo.db       # Banco de dados (criado automaticamente)
└── uploads/           # Fotos enviadas (criado automaticamente)
```
