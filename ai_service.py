import requests
import base64
import os
import json
import time

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

        prompt = f"""Você é um vistoriador técnico de imóveis com mais de 15 anos de experiência em laudos imobiliários profissionais. Analise {foto_str} do item "{item_name}" no ambiente "{room_name}" e redija uma descrição técnica completa, como constaria em um laudo oficial de vistoria.

INSTRUÇÕES DE ANÁLISE — descreva TUDO que for visível:

1. CARACTERÍSTICAS GERAIS
   - Tipo e cor da pintura (ex: tinta acrílica branca, tinta látex bege, textura grafiato, etc.)
   - Tipo de revestimento de piso (porcelanato, cerâmica, madeira, vinílico, cimentado, etc.) e sua cor/padrão
   - Tipo de revestimento de parede/teto quando aplicável (azulejo, gesso, reboco, etc.)

2. ELEMENTOS ESPECÍFICOS DO ITEM
   - Para esquadrias (portas/janelas): material (madeira, alumínio, PVC), cor, tipo de abertura, estado das dobradiças, fechaduras e maçanetas
   - Para luminárias: tipo (pendente, embutida, arandela), quantidade de lâmpadas, funcionamento aparente
   - Para móveis e equipamentos: material, cor, dimensões aproximadas se relevante
   - Para estruturas: tipo de material, acabamento

3. ESTADO DE CONSERVAÇÃO
   - Descreva o estado geral com objetividade
   - Aponte defeitos específicos se existirem: rachaduras, manchas, umidade, ferrugem, descascamentos, furos, peças faltantes/soltas, vidros trincados, etc.
   - Se não houver defeitos, registre que está em bom estado

4. OBSERVAÇÕES TÉCNICAS
   - Qualquer detalhe relevante para a vistoria (sinais de uso normal, desgaste natural, etc.)

FORMATO DA DESCRIÇÃO:
- Escreva em prosa técnica corrida (não lista de itens)
- Linguagem formal e profissional, como em um laudo real
- Seja específico e detalhado (mínimo 2-3 frases)
- Exemplo de qualidade esperada: "Piso em porcelanato retificado de grande formato, cor off-white, sem defeitos aparentes. Rodapé em cerâmica branca, íntegro. Paredes com pintura acrílica branca em bom estado de conservação, sem manchas ou imperfeições visíveis. Janela de correr em alumínio anodizado, vidro liso 4mm, com fechadura e trilhos em bom estado de funcionamento."

Responda SOMENTE com um JSON válido, sem texto adicional:
{{
  "condition": "ótimo|bom|regular|ruim|péssimo",
  "description": "descrição técnica completa do item conforme laudo profissional",
  "problems": ["defeito 1 se houver", "defeito 2 se houver"]
}}

Critério para "condition":
- ótimo: novo ou como novo, sem qualquer defeito ou sinal de uso
- bom: pequenos sinais de uso natural, sem defeitos que comprometam a funcionalidade
- regular: defeitos leves a moderados presentes, funcional mas com problemas visíveis
- ruim: defeitos sérios que necessitam reparo antes de nova locação
- péssimo: danos graves, inutilizável ou comprometendo a segurança"""

        content.append({'type': 'text', 'text': prompt})

        headers = {
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

        payload = {
            'model': 'claude-sonnet-4-6',
            'max_tokens': 1024,
            'messages': [{'role': 'user', 'content': content}]
        }

        # Retry até 3x para erro de sobrecarga (429/529)
        response = None
        for _attempt in range(3):
            response = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=60)
            if response.status_code in (429, 529):
                if _attempt < 2:
                    time.sleep(2 ** _attempt)
                    continue
            break

        if response and response.status_code == 200:
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
