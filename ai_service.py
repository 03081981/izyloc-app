import anthropic
import base64
import json
import re
import time

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """
Voce e um perito especializado em vistorias imobiliarias brasileiras.
Sua funcao e analisar fotografias de ambientes e itens de imoveis com maxima precisao tecnica.

REGRAS ABSOLUTAS â NUNCA VIOLE:
1. Descreva APENAS o que e CLARAMENTE visivel â jamais invente ou suponha
2. MATERIAL: Mencione apenas se identificavel com certeza visual absoluta
   - Pedra com veios visiveis = "pedra natural" ou "marmore" â NUNCA "granito" sem certeza
   - Cuba esculpida na propria pedra = "cuba em pedra natural esculpida"
   - Se nao tiver certeza do material â descreva apenas a cor e aparencia visual
3. MEDIDAS: NUNCA mencione dimensoes, medidas ou estimativas de tamanho
4. CORES: Descreva cores visiveis de forma simples â "branco", "bege claro", "cinza"
5. LUMINARIAS: "Ponto de iluminacao sem lampada ativa" â nunca "falta luminaria" ou "buraco no teto"
6. Estado: use apenas Bom, Regular ou Com avaria â nunca "Excelente"
7. Seja objetivo e direto â sem floreios ou suposicoes
8. IDIOMA: Use portugues brasileiro com acentuacao completa e correta

REGRA CRITICA â SO DESCREVA O QUE APARECE NA FOTO:
- Teto: SO descreva se aparecer claramente na foto â se nao aparecer, NAO mencione
- Piso: SO descreva se aparecer claramente na foto â se nao aparecer, NAO mencione
- Paredes: SO descreva as paredes que aparecem na foto

REGRA CRITICA â DEFEITOS E AVARIAS:
- Examine CADA foto atentamente buscando: manchas, mofo, furos, trincas, rachaduras,
  desgaste, fios aparentes, vazamentos, descolamento, oxidacao, quebras, buracos
- Se uma foto e CLOSE-UP ou ZOOM: o fotografo esta APONTANDO para aquele detalhe â examine com atencao maxima
- Furos e buracos no piso ou paredes DEVEM ser mencionados obrigatoriamente
- Pontos escuros dispersos no piso podem indicar sujidade grave ou infestacao â reporte com precisao
- NUNCA diga "sem avarias" se qualquer irregularidade e visivel

REGRA CRITICA â OBJETOS PESSOAIS:
- Vistoria de entrada ou saida: IGNORE completamente tapetes, vasos decorativos,
  produtos de higiene, roupas, itens pessoais do morador â nao fazem parte do laudo
- Vistoria de temporada/airbnb: inclua inventario completo de todos os itens presentes
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

def analisar_batch(imagens: list, nome_ambiente: str, tipo_vistoria: str = "entrada") -> dict:
    """
    Analisa um lote de fotos do mesmo ambiente em uma unica chamada.
    """
    last_error = ""
    if not imagens:
        return {"resumo": "", "estado_geral": "Bom", "success": False}

    LOTE_MAX = 20
    lotes = [imagens[i:i+LOTE_MAX] for i in range(0, len(imagens), LOTE_MAX)]
    resumos = []
    all_extras = []

    for lote in lotes:
        content = []
        for idx_foto, img in enumerate(lote, 1):
            content.append({"type": "text", "text": f"--- FOTO {idx_foto} ---"})
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.get("mime_type", "image/jpeg"),
                    "data": img["base64"]
                }
            })

        prompt = f"""Voce recebeu {len(lote)} foto(s) do ambiente '{nome_ambiente}'.
Tipo de vistoria: {tipo_vistoria}
Cada foto esta numerada (FOTO 1, FOTO 2, etc).

PASSO 1 â CLASSIFICAR CADA FOTO:
Para cada foto identifique:
a) FOTO AMPLA â mostra o ambiente inteiro
   Use para: cores gerais, layout, presenca de elementos
b) FOTO DE ITEM â focada em elemento especifico (armario, movel, equipamento)
   Use para: descrever aquele item em detalhe
c) FOTO DE AVARIA/CLOSE-UP â focada diretamente em problema ou detalhe
   Use para: descrever o defeito com precisao maxima

PASSO 2 â EXAMINAR DEFEITOS EM CADA FOTO:
Para cada foto, verifique obrigatoriamente:
- Furos ou buracos no piso, paredes ou teto?
- Manchas escuras, mofo, bolor, umidade?
- Fissuras, trincas ou rachaduras?
- Fios ou fiacao aparente/exposta?
- Descolamento, descascamento ou desgaste?
- Rodapes soltos ou afastados da parede?
- Rejuntes falhos, escurecidos ou com mofo?
- Pontos escuros dispersos no piso (sujidade grave ou infestacao)?
- Oxidacao, ferrugem ou deterioracao em metais?

PASSO 3 â REGRAS DE DESCRICAO:
- SO descreva teto se aparecer claramente em alguma foto â se nao aparecer, OMITA a secao Teto
- SO descreva piso se aparecer claramente em alguma foto â se nao aparecer, OMITA a secao Piso
- Pedra com veios visiveis = "pedra natural" ou "marmore" â NUNCA "granito" sem certeza
- NUNCA mencione medidas ou dimensoes
- Material apenas com certeza visual absoluta
- Ignore elementos ao fundo atraves de portas/aberturas
- {"IGNORE objetos pessoais: tapetes, vasos, produtos de higiene, roupas, itens do morador" if tipo_vistoria in ["entrada", "saida"] else "INVENTARIE todos os itens presentes incluindo decoracao, utensilios e equipamentos"}

PASSO 4 â DETECTAR AMBIENTES DIFERENTES (OBRIGATORIO):
ANTES de sintetizar, verifique: as fotos correspondem ao ambiente '{nome_ambiente}'?

SINAIS DE AMBIENTE ERRADO:
- Vaso sanitario, box, chuveiro, ralo = BANHEIRO (nao dormitorio, nao sala)
- Fogao, pia de cozinha, coifa = COZINHA (nao sala, nao dormitorio)
- Cama, guarda-roupa, criado-mudo = DORMITORIO (nao sala, nao cozinha)
- Tanque, maquina de lavar = AREA DE SERVICO
- Portao, vaga de carro, piso cimentado largo, portao automatico = GARAGEM (nao sala)
- Corredor estreito, passagem entre comodos, hall = CORREDOR (nao sala, nao dormitorio)
- Jardim, quintal, area descoberta, muro externo, churrasqueira, piscina = AREA EXTERNA
- Varanda, sacada, area coberta com vista externa = VARANDA
- Fachada do imovel, frente da casa, porta de entrada vista de fora, visao geral do exterior = FACHADA (nao garagem, mesmo se portao visivel)

IMPORTANTE: Se a foto mostra um espaco amplo com piso cimentado ou sem acabamento refinado,
com portao ou acesso de veiculos, E GARAGEM â nao Sala.
Se a foto mostra area descoberta ou semicoberta com muros, E AREA EXTERNA â nao Sala.
Se a foto mostra espaco estreito de passagem sem moveis, E CORREDOR â nao Sala.
Se a foto mostra a FRENTE/EXTERIOR do imovel com foco na fachada, E FACHADA — nao Garagem, mesmo que o portao de garagem apareca na imagem.

Se as fotos mostram um ambiente DIFERENTE de '{nome_ambiente}':
- Liste TODAS as fotos que pertencem ao outro ambiente em "ambientes_extras"
- Use o nome correto (ex: 'Banheiro', 'Cozinha', 'Dormitorio', 'Garagem', 'Corredor', 'Area externa', 'Fachada')
- Se TODAS as fotos sao de outro ambiente, liste TODAS as fotos em ambientes_extras

ISTO E OBRIGATORIO. Nao descreva fotos de banheiro como se fossem dormitorio, nem fotos de garagem como se fossem sala.

PASSO 5 â SINTETIZAR:
Compile tudo em descricao unica sem omitir nenhum defeito.
Para CADA elemento ou defeito, inclua entre parenteses o numero da foto: (foto N)
Prioridade: fotos de avaria > fotos de item > fotos amplas.

Retorne APENAS este JSON sem markdown:
{{{{
  "resumo": "SINTESE DO AMBIENTE:\n\nPiso: [revestimento, cor, estado com (foto N) â furos/manchas/danos se houver â OMITIR se nao aparece]\n\nParedes: [acabamento, cor, estado com (foto N) â mofo/manchas/trincas se houver]\n\nTeto: [OMITIR COMPLETAMENTE se nao aparecer em nenhuma foto â acabamento, cor, estado com (foto N) se aparecer]\n\nEsquadrias: [portas e janelas visiveis com (foto N), estado]\n\nInstalacoes: [tomadas, interruptores, pontos de luz, chuveiro com (foto N) â fios aparentes DEVEM ser reportados]\n\nMoveis e equipamentos: [itens presentes com (foto N) e estados detalhados]\n\nObservacoes: [LISTA COMPLETA de todos os defeitos com (foto N)]\n\nEstado geral: [Bom / Regular / Com avaria] â [justificativa]",
  "estado_geral": "Bom ou Regular ou Com avaria",
  "ambientes_extras": [
    {{{{
      "nome": "Nome do ambiente detectado",
      "fotos": [1],
      "descricao": "Descricao do ambiente...",
      "estado": "Bom ou Regular ou Com avaria"
    }}}}
  ]
}}}}
Se TODAS as fotos pertencem ao ambiente "{nome_ambiente}", retorne "ambientes_extras": []"""

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
                extras = dados.get("ambientes_extras", [])
                if extras:
                    all_extras.extend(extras)
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

    result = {"resumo": resumo_final, "estado_geral": estado, "success": bool(resumo_final), "ambientes_extras": all_extras}
    if not resumo_final and last_error:
        result["error"] = last_error
    return result


def analyze_batch(images: list, environment_name: str, tipo_vistoria: str = "entrada") -> dict:
    return analisar_batch(images, environment_name, tipo_vistoria)


# Aliases em ingles para compatibilidade com server.py
def analyze_photo(image_base64: str, environment: str = "Ambiente", mime_type: str = "image/jpeg") -> dict:
    return analisar_foto(image_base64, environment, mime_type)

def analyze_photos(images_base64: list, environment: str = "Ambiente", mime_type: str = "image/jpeg") -> list:
    return [analisar_foto(img, environment, mime_type) for img in images_base64]

def consolidate_environment(environment_name: str, descriptions: list) -> dict:
    return consolidar_ambiente(environment_name, descriptions)

def analyze_image(image_base64: str, environment: str = "Ambiente", mode: str = "completo", mime_type: str = "image/jpeg") -> dict:
    return analisar_imagem(image_base64, environment, mode, mime_type)
