# izyLAUDO — GUIA DEFINITIVO DO PROJETO

## REGRAS CRÍTICAS — NUNCA VIOLAR
- NUNCA alterar: `doLogin()`, `generatePDF()`, `downloadFile()`, `DOMContentLoaded`
- Encoding: SEMPRE editar index.html via Python no terminal — NUNCA via JavaScript no browser
- NUNCA alterar server.py sem necessidade absoluta
- Edições sempre cirúrgicas, nunca substituições globais
- Commit separado por correção — nunca vários arquivos de uma vez
- Após cada commit, aguardar deploy do Railway e confirmar funcionamento

## MÉTODO OBRIGATÓRIO PARA EDITAR index.html
```bash
python3 -c "
content = open('static/index.html', encoding='utf-8').read()
content = content.replace('TEXTO_ANTIGO', 'TEXTO_NOVO', 1)
open('static/index.html', 'w', encoding='utf-8').write(content)
"
file static/index.html  # confirmar UTF-8
git add static/index.html
git commit -m 'descricao'
git push origin main
```

## STATUS ATUAL — O QUE JÁ ESTÁ FUNCIONANDO
- Login/Cadastro/Recuperação de senha ✅
- Dashboard ✅
- Etapa 1 — Tipo de vistoria ✅
- Etapa 2 — Quem realiza (condicional: Proprietário oculta corretor) ✅
- Etapa 3 — Dados do imóvel (ViaCEP, 9 tipos, área aproximada) ✅
- Etapa 4 — Partes envolvidas (múltiplos locadores/locatários, corretor condicional) ✅
- Navegação entre etapas — gotoWStep centralizado, sem empilhamento ✅
- Stepper — 8 círculos corretos, sem "Assinaturas" ✅
- Subtítulo "Etapa X de 8" atualiza dinamicamente ✅
- nextWizStep / prevWizStep funcionando ✅
- PDF sendo gerado — layout aprovado (Modelo 2 funcionando) ✅
- Commit limpo atual: `c275b137`

## O QUE ESTÁ PENDENTE — EM ORDEM DE PRIORIDADE
1. Botão Continuar da Etapa 4 (wstep-2) não avança para Etapa 5
2. Etapa 5 — Ambientes (residencial/comercial/temporada)
3. Etapa 6 — Itens e fotos
4. Etapa 7 — Revisão final
5. Dados reais no PDF (nomes, endereços, partes, fotos)
6. Modelos 1, 3, 4, 5, 6 do PDF

## WIZARD — 8 ETAPAS
| Step | Div | Círculo | Label |
|------|-----|---------|-------|
| 0 | wstep-0 | sc-0 | Tipo |
| 1 | wstep-quem | sc-1 | Quem realiza |
| 2 | wstep-1 | sc-2 | Imóvel |
| 3 | wstep-2 | sc-3 | Partes |
| 4 | wstep-3 | sc-4 | Ambientes |
| 5 | wstep-4 | sc-5 | Itens e fotos |
| 6 | wstep-rev | sc-6 | Revisão |
| 7 | wstep-5 | sc-7 | PDF |

## 6 MODELOS DE LAUDOS
| Tipo | Responsável | Modelo | Numeração |
|------|-------------|--------|-----------|
| Entrada | Imobiliária/Corretor | Modelo 1 | VE-2026-XXXX |
| Entrada | Proprietário | Modelo 2 ✅ | VE-2026-XXXX |
| Saída | Imobiliária/Corretor | Modelo 3 | VS-2026-XXXX |
| Saída | Proprietário | Modelo 4 | VS-2026-XXXX |
| Temporada | Imobiliária/Corretor | Modelo 5 | VT-2026-XXXX |
| Temporada | Proprietário | Modelo 6 | VT-2026-XXXX |

## VARIÁVEIS GLOBAIS DO WIZARD
- `wizard.tipo` → 'entrada' | 'saida' | 'temporada'
- `wizard.responsavel` → 'imobiliaria' | 'proprietario'
- `wizard.tipoImovel` → 'residencial' | 'comercial' | 'temporada'
- `wizard.inspectionId` → ID da vistoria no banco
- `wizard.step` → step atual (0 a 7)
