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

        system_msg = """Você é um PERITO TÉCNICO ESPECIALISTA EM VISTORIA IMOBILIÁRIA com 20 anos de experiência. Analisa imagens e gera descrições técnicas para laudos profissionais.

REGRAS ABSOLUTAS — nunca viole:
1. NUNCA use "ou" para indicar incerteza de material/tipo/acabamento. Use termos neutros: "metal", "revestimento cerâmico", "material não identificado".
2. NUNCA invente ou estime medidas numéricas. Sem "90 cm", "1,20m" ou "aproximadamente X".
3. NUNCA descreva itens adjacentes fora do foco principal do laudo.
4. NUNCA afirme o que não está claramente visível na imagem.
5. A descrição deve ter 4 a 7 linhas."""

        foto_label = "esta foto" if n == 1 else f"estas {n} fotos"

        prompt = f"""Analise {foto_str} do item "{item_name}" no ambiente "{room_name}".

PADRÃO POR TIPO:
- JANELA: abertura (correr/abrir/basculante), material visível, trilhos, vedação, sujidade
- PORTA: tipo de folha, material, ferragens, estrutura, alinhamento, fechadura
- PAREDE/PISO/TETO: revestimento, cor, patologias visíveis (umidade, trinca, mancha)
- EQUIPAMENTO: marca se logotipo visível, componentes, estado, anomalias
- MOBILIÁRIO: material aparente, estado das superfícies, funcionamento visível

EXEMPLOS — NÃO fazer vs FAZER:
✗ "alumínio ou ferro" → ✓ "metal de acabamento claro"
✗ "cerâmica ou porcelanato" → ✓ "revestimento cerâmico"
✗ "vidro temperado ou laminado" → ✓ "vidro liso"
✗ "90 cm de largura" → ✓ não mencionar medidas
✗ "vista para área externa" → ✓ descrever apenas o item "{item_name}"

Responda SOMENTE com JSON válido, sem texto adicional:
{{{{
  "condition": "ótimo|bom|regular|ruim|péssimo",
  "description": "descrição técnica de 4 a 7 linhas do item visível",
  "estado_geral": "bom|regular|ruim",
  "problems": ["defeito visível 1", "defeito visível 2"]
}}}}"""
        payload = {
            'model': 'claude-sonnet-4-6',
            'max_tokens': 2048,
            'system': system_msg,
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
                estado = analysis.get("estado_geral", "")
                desc = analysis.get("description", "")
                if estado and "Estado geral:" not in desc:
                    desc = desc.rstrip() + "\n\nEstado geral: " + estado
                return {
                    "success": True,
                    "condition": analysis.get("condition", "avaliado"),
                    "description": desc,
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
