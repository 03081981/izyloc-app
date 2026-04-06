import anthropic
import base64
import json
import re
import time

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """Voce e um perito especializado em vistorias imobiliarias brasileiras.
Sua funcao e analisar fotografias de ambientes e itens de imoveis com precisao tecnica.

REGRAS OBRIGATORIAS:
- Descreva APENAS o que e visivel na foto â nunca invente ou suponha
- Use linguagem tecnica objetiva, como um laudo pericial profissional
- Identifique materiais, cores, dimensoes estimadas e estado de conservacao
- Seja especifico: nao diga "parede branca" â diga "parede revestida com tinta acrilica na cor branco gelo"
- Nao diga "parece" ou "provavelmente" â seja assertivo no que e visivel
- Se houver avaria, descreva com precisao: localizacao, extensao estimada, natureza do dano
- Retorne SEMPRE um JSON valido, sem markdown, sem explicacoes fora do JSON"""

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

            dados = json.loads(texto)
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
    Consolida todas as descricoes de fotos de um ambiente em um paragrafo tecnico.
    Chamado ao clicar 'Proximo ambiente'.

    descricoes: lista de dicts retornados por analisar_foto()

    Retorna:
    {
        "resumo": str,
        "success": bool
    }
    """

    if not descricoes:
        return {"resumo": "", "success": False}

    # Montar texto com todas as descricoes
    itens_texto = ""
    avarias = []
    for i, d in enumerate(descricoes, 1):
        itens_texto += f"Foto {i} â {d.get('item', 'Item')}: {d.get('descricao', '')}\n"
        if d.get('estado') == 'Com avaria' and d.get('observacao'):
            avarias.append(d.get('observacao'))

    prompt = f"""Com base nas descricoes abaixo do ambiente '{nome_ambiente}', escreva um paragrafo tecnico consolidado.

DESCRICOES DAS FOTOS:
{itens_texto}

INSTRUCOES:
- Escreva UM paragrafo tecnico de 4 a 6 linhas
- Mencione materiais, cores e estado geral de conservacao
- Destaque CLARAMENTE qualquer avaria encontrada
- Use linguagem de laudo pericial profissional
- Seja objetivo e preciso

Retorne APENAS este JSON:
{{
  "resumo": "paragrafo tecnico consolidado aqui"
}}"""

    for tentativa in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            texto = response.content[0].text.strip()
            texto = re.sub(r'```json\s*', '', texto)
            texto = re.sub(r'```\s*', '', texto)
            dados = json.loads(texto.strip())
            dados['success'] = True
            return dados

        except Exception as e:
            if tentativa < 2:
                time.sleep(2 ** tentativa)

    return {"resumo": "", "success": False}


def analisar_foto_simples(imagem_base64: str, nome_ambiente: str = "Ambiente", mime_type: str = "image/jpeg") -> dict:
    """
    Modo legado â compatibilidade com codigo anterior.
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

# Aliases em ingles para compatibilidade com server.py
def analyze_photo(image_base64: str, environment: str = "Ambiente", mime_type: str = "image/jpeg") -> dict:
    return analisar_foto(image_base64, environment, mime_type)

def analyze_photos(images_base64: list, environment: str = "Ambiente", mime_type: str = "image/jpeg") -> list:
    return [analisar_foto(img, environment, mime_type) for img in images_base64]

def consolidate_environment(environment_name: str, descriptions: list) -> dict:
    return consolidar_ambiente(environment_name, descriptions)

def analyze_image(image_base64: str, environment: str = "Ambiente", mode: str = "completo", mime_type: str = "image/jpeg") -> dict:
    return analisar_imagem(image_base64, environment, mode, mime_type)
