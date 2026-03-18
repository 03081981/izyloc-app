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
    Analisa uma ou múltiplas fotos de vistoria usando Claude Vision.
    Foco em identificar defeitos específicos para laudo imobiliário.
    Retorna descrição objetiva dos problemas encontrados.
    """
    if not ANTHROPIC_API_KEY:
        return {
            "success": False,
            "description": "Chave de API da IA não configurada. Configure ANTHROPIC_API_KEY.",
            "condition": "não avaliado",
            "problems": []
        }

    if not image_paths:
        return {
            "success": False,
            "description": "Nenhuma foto para analisar.",
            "condition": "não avaliado",
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
                "description": "Fotos não encontradas no servidor.",
                "condition": "não avaliado",
                "problems": []
            }

        n = len(content)
        foto_str = "esta foto" if n == 1 else f"estas {n} fotos"

        prompt = f"""Você é um vistoriador de imóveis experiente. Analise {foto_str} do item "{item_name}" no ambiente "{room_name}".

Sua tarefa é identificar APENAS os defeitos e problemas VISÍVEIS na foto. Procure por:
- Furos, buracos ou perfurações em paredes/tetos/pisos
- Lâmpadas queimadas, faltando ou danificadas
- Rachaduras ou trincas (em paredes, pisos, azulejos, vidros)
- Manchas, sujeira, mofo ou marcas
- Infiltrações, umidade ou bolhas na pintura
- Vidros trincados ou quebrados
- Peças faltando, soltas ou danificadas (maçanetas, fechaduras, dobradiças, etc.)
- Ferrugem ou corrosão
- Tinta descascando ou desgastada
- Qualquer outro dano visível

REGRAS IMPORTANTES:
1. Se NÃO houver problemas visíveis → responda: "Em bom estado. Sem defeitos aparentes."
2. Se houver problemas → descreva APENAS os problemas de forma direta e objetiva, como um laudo real
3. NÃO descreva o que está em bom estado. Descreva SOMENTE o que está errado.
4. Use linguagem simples e direta (não técnica demais)
5. Exemplos de boas descrições:
   - "Apresenta rachadura horizontal na parte superior da parede e mancha de umidade no canto inferior."
   - "Lâmpada queimada. Tinta descascando na região do rodapé."
   - "Vidro da janela com trinca diagonal. Maçaneta solta."

Responda SOMENTE com um JSON válido, sem texto adicional:
{{
  "condition": "ótimo|bom|regular|ruim|péssimo",
  "description": "descrição objetiva (defeitos encontrados ou 'Em bom estado. Sem defeitos aparentes.')",
  "problems": ["defeito 1", "defeito 2"]
}}

Critério para "condition":
- ótimo: sem nenhum defeito visível, novo ou como novo
- bom: pequenos sinais de uso, sem defeitos significativos
- regular: defeitos leves a moderados, funcional mas com problemas
- ruim: defeitos sérios, necessita reparos
- péssimo: danos graves, inutilizável ou perigoso"""

        content.append({'type': 'text', 'text': prompt})

        headers = {
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

        payload = {
            'model': 'claude-opus-4-5',
            'max_tokens': 400,
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
                # Resposta não era JSON — usa o texto direto
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
                "description": f"Erro na análise: {error_msg}",
                "condition": "não avaliado",
                "problems": []
            }

    except FileNotFoundError:
        return {"success": False, "description": "Foto não encontrada", "condition": "não avaliado", "problems": []}
    except requests.Timeout:
        return {"success": False, "description": "Tempo de resposta da IA esgotado", "condition": "não avaliado", "problems": []}
    except Exception as e:
        return {"success": False, "description": f"Erro: {str(e)}", "condition": "não avaliado", "problems": []}


def analyze_photo(image_path: str, item_name: str, room_name: str) -> dict:
    """Compatibilidade retroativa: analisa uma única foto."""
    return analyze_photos([image_path], item_name, room_name)
