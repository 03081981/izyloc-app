import requests
import base64
import os
import json

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'


def _encode_image(image_path: str) -> tuple:
    """Encode image to base64 and detect media type."""
    ext = os.path.splitext(image_path)[1].lower()
    media_types = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif'
    }
    media_type = media_types.get(ext, 'image/jpeg')
    with open(image_path, 'rb') as f:
        image_data = base64.standard_b64encode(f.read()).decode('utf-8')
    return image_data, media_type


def analyze_photos(image_paths: list, item_name: str, room_name: str) -> dict:
    """
    Analisa uma ou mÃºltiplas fotos de vistoria usando Claude Vision.
    Foco em identificar defeitos especÃ­ficos para laudo imobiliÃ¡rio.
    Retorna descriÃ§Ã£o objetiva dos problemas encontrados.
    """
    if not ANTHROPIC_API_KEY:
        return {
            "success": False,
            "description": "Chave de API da IA nÃ£o configurada. Configure ANTHROPIC_API_KEY.",
            "condition": "nÃ£o avaliado",
            "problems": []
        }

    if not image_paths:
        return {
            "success": False,
            "description": "Nenhuma foto para analisar.",
            "condition": "nÃ£o avaliado",
            "problems": []
        }

    try:
        # Monta os blocos de imagem para o Claude
        content = []
        valid_paths = []

        for path in image_paths:
            if not os.path.exists(path):
                continue
            image_data, media_type = _encode_image(path)
            content.append({
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': media_type,
                    'data': image_data
                }
            })
            valid_paths.append(path)

        if not content:
            return {
                "success": False,
                "description": "Fotos nÃ£o encontradas no servidor.",
                "condition": "nÃ£o avaliado",
                "problems": []
            }

        n = len(content)
        foto_str = "esta foto" if n == 1 else f"estas {n} fotos"

        prompt = f"""VocÃª Ã© um vistoriador tÃ©cnico de imÃ³veis com mais de 15 anos de experiÃªncia em laudos imobiliÃ¡rios profissionais. Analise {foto_str} do item "{item_name}" no ambiente "{room_name}" e redija uma descriÃ§Ã£o tÃ©cnica completa, como constaria em um laudo oficial de vistoria.

INSTRUÃÃES DE ANÃLISE â descreva TUDO que for visÃ­vel:

1. CARACTERÃSTICAS GERAIS
   - Tipo e cor da pintura (ex: tinta acrÃ­lica branca, tinta lÃ¡tex bege, textura grafiato, etc.)
   - Tipo de revestimento de piso (porcelanato, cerÃ¢mica, madeira, vinÃ­lico, cimentado, etc.) e sua cor/padrÃ£o
   - Tipo de revestimento de parede/teto quando aplicÃ¡vel (azulejo, gesso, reboco, etc.)

2. ELEMENTOS ESPECÃFICOS DO ITEM
   - Para esquadrias (portas/janelas): material (madeira, alumÃ­nio, PVC), cor, tipo de abertura, estado das dobradiÃ§as, fechaduras e maÃ§anetas
   - Para luminÃ¡rias: tipo (pendente, embutida, arandela), quantidade de lÃ¢mpadas, funcionamento aparente
   - Para mÃ³veis e equipamentos: material, cor, dimensÃµes aproximadas se relevante
   - Para estruturas: tipo de material, acabamento

3. ESTADO DE CONSERVAÃÃO
   - Descreva o estado geral com objetividade
   - Aponte defeitos especÃ­ficos se existirem: rachaduras, manchas, umidade, ferrugem, descascamentos, furos, peÃ§as faltantes/soltas, vidros trincados, etc.
   - Se nÃ£o houver defeitos, registre que estÃ¡ em bom estado

4. OBSERVAÃÃES TÃCNICAS
   - Qualquer detalhe relevante para a vistoria (sinais de uso normal, desgaste natural, etc.)

FORMATO DA DESCRIÃÃO:
- Escreva em prosa tÃ©cnica corrida (nÃ£o lista de itens)
- Linguagem formal e profissional, como em um laudo real
- Seja especÃ­fico e detalhado (mÃ­nimo 2-3 frases)
- Exemplo de qualidade esperada: "Piso em porcelanato retificado de grande formato, cor off-white, sem defeitos aparentes. RodapÃ© em cerÃ¢mica branca, Ã­ntegro. Paredes com pintura acrÃ­lica branca em bom estado de conservaÃ§Ã£o, sem manchas ou imperfeiÃ§Ãµes visÃ­veis. Janela de correr em alumÃ­nio anodizado, vidro liso 4mm, com fechadura e trilhos em bom estado de funcionamento."

Responda SOMENTE com um JSON vÃ¡lido, sem texto adicional:
{{
  "condition": "Ã³timo|bom|regular|ruim|pÃ©ssimo",
  "description": "descriÃ§Ã£o tÃ©cnica completa do item conforme laudo profissional",
  "problems": ["defeito 1 se houver", "defeito 2 se houver"]
}}

CritÃ©rio para "condition":
- Ã³timo: novo ou como novo, sem qualquer defeito ou sinal de uso
- bom: pequenos sinais de uso natural, sem defeitos que comprometam a funcionalidade
- regular: defeitos leves a moderados presentes, funcional mas com problemas visÃ­veis
- ruim: defeitos sÃ©rios que necessitam reparo antes de nova locaÃ§Ã£o
- pÃ©ssimo: danos graves, inutilizÃ¡vel ou comprometendo a seguranÃ§a"""

        content.append({'type': 'text', 'text': prompt})

        headers = {
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

        payload = {
            'model': 'claude-opus-4-6',
            'max_tokens': 1024,
            'messages': [{'role': 'user', 'content': content}]
        }

        response = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            text = result['content'][0]['text'].strip()

            # Remove markdown code blocks se presentes
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()

            try:
                analysis = json.loads(text)
                return {
                    "success": True,
                    "condition": analysis.get("condition", "avaliado"),
                    "description": analysis.get("description", ""),
                    "problems": analysis.get("problems", [])
                }
            except json.JSONDecodeError:
                # Resposta nÃ£o era JSON â usa o texto direto
                return {
                    "success": True,
                    "condition": "avaliado",
                    "description": text,
                    "problems": []
                }

        else:
            error_msg = response.json().get('error', {}).get('message', 'Erro desconhecido')
            return {
                "success": False,
                "description": f"Erro na anÃ¡lise: {error_msg}",
                "condition": "nÃ£o avaliado",
                "problems": []
            }

    except FileNotFoundError:
        return {"success": False, "description": "Foto nÃ£o encontrada", "condition": "nÃ£o avaliado", "problems": []}
    except requests.Timeout:
        return {"success": False, "description": "Tempo de resposta da IA esgotado", "condition": "nÃ£o avaliado", "problems": []}
    except Exception as e:
        return {"success": False, "description": f"Erro: {str(e)}", "condition": "nÃ£o avaliado", "problems": []}


def analyze_photo(image_path: str, item_name: str, room_name: str) -> dict:
    """Compatibilidade retroativa: analisa uma Ãºnica foto."""
    return analyze_photos([image_path], item_name, room_name)
