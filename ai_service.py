import anthropic
import base64
import json
import re
import time

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """
Voce e um perito especializado em vistorias imobiliarias brasileiras.
Sua funcao e analisar fotografias de ambientes e itens de imoveis.

REGRAS ABSOLUTAS - NUNCA VIOLE:
1. Descreva APENAS o que e CLARAMENTE visivel na foto - jamais invente, suponha ou interprete
2. MATERIAL: Mencione apenas se identificavel com absoluta certeza visual. Se nao tiver certeza - NAO MENCIONE
3. MEDIDAS: NUNCA mencione dimensoes ou medidas - nem estimadas, nem aproximadas
4. ELEMENTOS SECUNDARIOS: Ignore completamente qualquer elemento visivel ao fundo atraves de portas ou aberturas
5. AVARIAS: Descreva exatamente o que ve - nunca infira defeitos a partir de fotos amplas de contexto
6. CORES: Descreva cores claramente visiveis - "branco", "bege claro", "cinza" - sem inventar tons especificos
7. LUMINARIAS: "Ponto de iluminacao sem lampada ativa" - nunca "falta luminaria" ou "buraco no teto"
8. Estado de conservacao: use apenas Bom, Regular ou Com avaria - nunca "Excelente"
9. Seja objetivo e direto - sem floreios, sem suposicoes
"""

def analisar_foto(imagem_base64: str, nome_ambiente: str, mime_type: str = "image/jpeg") -> dict:
    """
    Analisa uma foto de vistoria e retorna descricao tecnica completa.

    Retorna:
    {
        "item": str,
        "ambiente_detectado": str,
        "estado": str,
        "cor": str,
        "material": str,
        "descricao": str,
        "observacao": str,
        "novo_ambiente": bool,
        "success": bool
    }
    """

    prompt = f"""Analise esta foto de vistoria imobiliaria.
Ambiente informado pelo vistoriador: {nome_ambiente}

Retorne APENAS este JSON (sem markdown, sem texto fora do JSON):
{{
  "item": "nome tecnico do item principal fotografado (ex: Parede norte, Piso ceramico, Guarda-roupa, Janela basculante)",
  "ambiente_detectado": "nome do ambiente que voce identifica visualmente na foto",
  "estado": "Bom ou Regular ou Com avaria",
  "cor": "cor principal do item (seja especifico: branco gelo, carvalho medio, cinza claro, etc)",
  "material": "material identificado (tinta acrilica, ceramica 60x60cm, MDF, madeira macica, etc)",
  "descricao": "descricao tecnica detalhada em 4 a 6 linhas. Inclua: tipo do item, cor exata, material, dimensoes estimadas se visiveis, estado de conservacao detalhado, presenca de avarias com localizacao e extensao estimada",
  "observacao": "descricao da anomalia se houver (vazio se nao houver problema)",
  "novo_ambiente": false
}}

IMPORTANTE:
- Se o ambiente visivel na foto for DIFERENTE de '{nome_ambiente}', coloque o nome correto em 'ambiente_detectado' e defina 'novo_ambiente' como true
- Se for o mesmo ambiente, repita '{nome_ambiente}' em 'ambiente_detectado' e mantenha 'novo_ambiente' como false
- Estado 'Com avaria' apenas se houver dano visivel real: rachadura, descascamento, infiltracao, quebra, mofo, etc"""

    for tentativa in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": imagem_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )

            texto = response.content[0].text.strip()
            texto = re.sub(r'```json\s*', '', texto)
            texto = re.sub(r'```\s*', '', texto)
            texto = texto.strip()

            dados = json.loads(texto, strict=False)
            dados['success'] = True

            # Normalizar estado
            estado = dados.get('estado', 'Bom')
            if 'avaria' in estado.lower() or 'mau' in estado.lower():
                dados['estado'] = 'Com avaria'
            elif 'regular' in estado.lower():
                dados['estado'] = 'Regular'
            else:
                dados['estado'] = 'Bom'

            return dados

        except json.JSONDecodeError:
            # Tentar extrair JSON do texto
            match = re.search(r'\{[\s\S]*\}', texto)
            if match:
                try:
                    dados = json.loads(match.group())
                    dados['success'] = True
                    return dados
                except:
                    pass
        except Exception as e:
            if tentativa < 2:
                time.sleep(2 ** tentativa)
            else:
                return {
                    "item": "Item nao identificado",
                    "ambiente_detectado": nome_ambiente,
                    "estado": "Bom",
                    "cor": "",
                    "material": "",
                    "descricao": f"Erro ao analisar imagem: {str(e)}",
                    "observacao": "",
                    "novo_ambiente": False,
                    "success": False
                }

    return {
        "item": "Item nao identificado",
        "ambiente_detectado": nome_ambiente,
        "estado": "Bom",
        "cor": "",
        "material": "",
        "descricao": "Nao foi possivel analisar a imagem apos 3 tentativas.",
        "observacao": "",
        "novo_ambiente": False,
        "success": False
    }


def consolidar_ambiente(nome_ambiente: str, descricoes: list) -> dict:
    """
    Consolida todas as descricoes de fotos de um ambiente em sintese estruturada.
    """
    if not descricoes:
        return {"resumo": "", "success": False}

    itens_texto = ""
    for i, d in enumerate(descricoes, 1):
        itens_texto += f"Foto {i} -- {d.get('item', 'Item')}: {d.get('descricao', '')}\n"

    prompt = f"""Voce e um perito em vistorias imobiliarias. Com base nas descricoes das fotos abaixo do ambiente '{nome_ambiente}', gere uma SINTESE ESTRUTURADA profissional.

DESCRICOES DAS FOTOS:
{itens_texto}

INSTRUCOES:
- Organize a sintese por elementos construtivos identificados nas fotos
- Para cada elemento mencione: material, cor e estado de conservacao
- Se houver avaria, descreva com precisao e destaque claramente
- Use linguagem tecnica de laudo pericial
- Seja objetivo e preciso
- Conclua com o estado geral do ambiente

Retorne APENAS este JSON sem markdown:
{{
  "resumo": "SINTESE:\n\nPiso: [material, cor, estado]\n\nParedes: [material, cor, estado, avarias se houver]\n\nTeto: [material, cor, estado]\n\nEsquadrias: [portas e janelas, estado]\n\nObservacoes: [itens adicionais identificados]\n\nEstado geral: [Bom / Regular / Com avaria] -- [justificativa resumida]"
}}"""

    for tentativa in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=800,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            texto = response.content[0].text.strip()
            texto = re.sub(r'```json\s*', '', texto)
            texto = re.sub(r'```\s*', '', texto)
            texto = texto.strip()
            dados = json.loads(texto, strict=False)
            dados['success'] = True
            return dados
        except Exception as e:
            if tentativa < 2:
                time.sleep(2 ** tentativa)

    return {"resumo": "", "success": False}


def analisar_foto_simples(imagem_base64: str, nome_ambiente: str = "Ambiente", mime_type: str = "image/jpeg") -> dict:
    """
    Modo legado -- compatibilidade com codigo anterior.
    Chama analisar_foto e normaliza para formato antigo.
    """
    resultado = analisar_foto(imagem_base64, nome_ambiente, mime_type)

    return {
        "description": resultado.get("descricao", ""),
        "estado": resultado.get("estado", "Bom"),
        "descricao_geral": resultado.get("descricao", ""),
        "item": resultado.get("item", ""),
        "ambiente_detectado": resultado.get("ambiente_detectado", nome_ambiente),
        "cor": resultado.get("cor", ""),
        "material": resultado.get("material", ""),
        "observacao": resultado.get("observacao", ""),
        "novo_ambiente": resultado.get("novo_ambiente", False),
        "itens": [
            {
                "nome": resultado.get("item", "Item"),
                "estado": resultado.get("estado", "Bom"),
                "descricao": resultado.get("descricao", "")
            }
        ],
        "observacoes": [resultado.get("observacao")] if resultado.get("observacao") else [],
        "condition": resultado.get("estado", "Bom"),
        "success": resultado.get("success", False)
    }


# Funcao principal chamada pelo server.py
def analisar_imagem(imagem_base64: str, ambiente: str = "Ambiente", modo: str = "completo", mime_type: str = "image/jpeg") -> dict:
    """
    Ponto de entrada principal.
    modo: 'completo' (novo) | 'simples' (legado)
    """
    if modo == 'simples':
        return analisar_foto_simples(imagem_base64, ambiente, mime_type)
    else:
        return analisar_foto(imagem_base64, ambiente, mime_type)

def analisar_batch(imagens: list, nome_ambiente: str) -> dict:
    """
    Analisa um lote de fotos do mesmo ambiente em uma unica chamada.
    """
    last_error = ""
    if not imagens:
        return {"resumo": "", "estado_geral": "Bom", "success": False}

    LOTE_MAX = 20
    lotes = [imagens[i:i+LOTE_MAX] for i in range(0, len(imagens), LOTE_MAX)]
    resumos = []

    for lote in lotes:
        content = []
        for img in lote:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.get("mime_type", "image/jpeg"),
                    "data": img["base64"]
                }
            })

        prompt = f"""Voce recebeu {len(lote)} foto(s) do ambiente '{nome_ambiente}'.

PASSO 1 - CLASSIFICACAO DAS FOTOS (OBRIGATORIO):
Antes de descrever, classifique CADA foto em um destes 3 tipos:

a) FOTO AMPLA (visao geral do ambiente)
   - Mostra o ambiente como um todo
   - Use APENAS para: cores de paredes/piso/teto, distribuicao do espaco,
     identificar presenca de moveis/equipamentos/tomadas/interruptores

b) FOTO ESPECIFICA DE ITEM
   - Focada em elemento especifico: armario, guarda-roupa, movel,
     eletrodomestico, porta, janela, luminaria, etc.
   - Use para descrever detalhadamente ESTE item (material, cor, estado)

c) FOTO ESPECIFICA DE DEFEITO/AVARIA
   - Focada diretamente em um problema: trinca, rachadura, mancha,
     furo, quebra, desgaste, dano visivel
   - Use para descrever a avaria com precisao

PASSO 2 - REGRA DE PRIORIDADE (CRITICO):
1. Fotos de DEFEITOS tem MAIOR prioridade - use ESTAS para descrever avarias
2. Fotos de ITENS tem prioridade media - use ESTAS para descrever cada item
3. Fotos AMPLAS tem MENOR prioridade - use APENAS para contexto geral

REGRAS DE INTERPRETACAO:
- NUNCA infira defeitos a partir de fotos amplas - so reporte avarias que aparecem em fotos especificas de defeitos
- NUNCA descreva um item com base em foto ampla se existe foto especifica dele
- NAO duplique informacoes entre fotos
- NAO invente informacoes nao visiveis
- NAO omita defeitos que aparecem em fotos especificas
- NUNCA mencione medidas ou dimensoes
- Material APENAS se tiver certeza absoluta visual

Retorne APENAS este JSON sem markdown:
{{
  "resumo": "SINTESE DO AMBIENTE:\n\nPiso: [descricao, cor, estado]\n\nParedes: [descricao, cor, estado, avarias se houver]\n\nTeto: [descricao, cor, estado]\n\nEsquadrias: [portas e janelas visiveis, estado]\n\nInstalacoes: [pontos de luz, tomadas, interruptores - estado]\n\nMoveis e equipamentos: [itens visiveis e estados detalhados]\n\nObservacoes: [avarias identificadas em fotos especificas]\n\nEstado geral: [Bom / Regular / Com avaria] - [justificativa breve]",
  "estado_geral": "Bom ou Regular ou Com avaria"
}}"""

        content.append({"type": "text", "text": prompt})

        for tentativa in range(3):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=4000,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": content}]
                )
                texto = response.content[0].text.strip()
                texto = re.sub(r'```json\s*', '', texto)
                texto = re.sub(r'```\s*', '', texto)
                texto = texto.strip()
                dados = json.loads(texto, strict=False)
                resumos.append(dados.get("resumo", ""))
                break
            except Exception as e:
                last_error = str(e)
                print(f"[analisar_batch] Tentativa {tentativa+1}/3 falhou: {e}")
                if tentativa < 2:
                    time.sleep(2 ** tentativa)

    resumo_final = "\n\n".join([r for r in resumos if r])
    estado = "Bom"
    if "com avaria" in resumo_final.lower() or "avaria" in resumo_final.lower():
        estado = "Com avaria"
    elif "regular" in resumo_final.lower():
        estado = "Regular"

    result = {"resumo": resumo_final, "estado_geral": estado, "success": bool(resumo_final)}
    if not resumo_final and last_error:
        result["error"] = last_error
    return result


def analyze_batch(images: list, environment_name: str) -> dict:
    return analisar_batch(images, environment_name)


# Aliases em ingles para compatibilidade com server.py
def analyze_photo(image_base64: str, environment: str = "Ambiente", mime_type: str = "image/jpeg") -> dict:
    return analisar_foto(image_base64, environment, mime_type)

def analyze_photos(images_base64: list, environment: str = "Ambiente", mime_type: str = "image/jpeg") -> list:
    return [analisar_foto(img, environment, mime_type) for img in images_base64]

def consolidate_environment(environment_name: str, descriptions: list) -> dict:
    return consolidar_ambiente(environment_name, descriptions)

def analyze_image(image_base64: str, environment: str = "Ambiente", mode: str = "completo", mime_type: str = "image/jpeg") -> dict:
    return analisar_imagem(image_base64, environment, mode, mime_type)
