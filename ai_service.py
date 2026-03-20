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

        prompt = f"""Você é um PERITO TÉCNICO ESPECIALISTA EM VISTORIA IMOBILIÁRIA.
Sua função é analisar imagens e gerar descrições técnicas padronizadas para laudos profissionais.

Analise {foto_str} do item "{item_name}" localizado no ambiente "{room_name}".

---

ETAPA 1 — IDENTIFICAÇÃO DO TIPO DE ITEM

Antes de descrever, identifique internamente o tipo principal do item na imagem:
janela | porta | parede | piso | teto | instalação elétrica | instalação hidráulica | equipamento | mobiliário | outro

Esta classificação orienta a descrição mas NÃO deve aparecer no texto final.

---

ETAPA 2 — REGRAS OBRIGATÓRIAS

- Descrever apenas o que é visível na imagem
- Não inventar informações
- Não estimar medidas
- Não usar "ou" para indicar dúvida sobre o que foi observado
- Não deduzir material sem evidência visual clara
- Não afirmar algo sem certeza
- Se houver dúvida, descrever de forma neutra e objetiva

---

ETAPA 3 — IDENTIFICAÇÃO DE MARCA/MODELO (para equipamentos)

- Identificar marca somente se logotipo estiver visível na imagem
- Mencionar modelo apenas se estiver claramente legível
- Caso contrário: informar "sem identificação de modelo"

---

ETAPA 4 — ESTRUTURA OBRIGATÓRIA DA DESCRIÇÃO

A descrição deve conter:
1. Identificação do item (o que é)
2. Características visuais (cor, material, tipo de abertura, acabamento)
3. Estado de conservação
4. Problemas visíveis (somente os que forem evidentes na imagem)
5. Observações técnicas relevantes

Tamanho: mínimo 3 linhas, ideal 5 a 8 linhas, máximo 10 linhas.

Finalizar SEMPRE com uma dessas frases exatas:
"Estado geral: bom" ou "Estado geral: regular" ou "Estado geral: ruim"

---

PADRÃO POR TIPO DE ITEM

JANELA: tipo de abertura (correr, abrir, basculante), material (se evidente), estado dos trilhos/estrutura, vedação, sujeira/desgaste, funcionamento aparente.

PORTA: tipo (madeira, vidro, etc.), estrutura, dobradiças, fechadura, alinhamento, sinais de uso.

PAREDE: tipo de acabamento (pintura, azulejo, etc.), integridade, manchas, sujeira, fissuras.

PISO: tipo de revestimento, estado geral, desgaste, manchas, nivelamento aparente.

TETO: acabamento, manchas, infiltração visível (somente se evidente), luminárias.

INSTALAÇÃO ELÉTRICA: tomadas, interruptores, espelhos, acabamento, sinais de desgaste, fixação.

INSTALAÇÃO HIDRÁULICA: torneiras, registros, vedação aparente, sinais de vazamento (somente se visível), conservação.

EQUIPAMENTO: tipo do equipamento, marca (se visível), modelo (se visível), estado geral, sinais de uso, acúmulo de sujeira.

---

REGRA FINAL

A precisão é mais importante que a quantidade.
Nunca invente informações.
Nunca faça suposições.
Nunca arrisque erro técnico.

---

Responda SOMENTE com um JSON válido, sem texto adicional:
{{
  "condition": "ótimo|bom|regular|ruim|péssimo",
  "description": "descrição técnica completa conforme todas as regras acima",
  "problems": ["defeito ou problema visível 1 se houver", "defeito 2 se houver"]
}}

Critério para "condition":
- ótimo: novo ou como novo, sem qualquer defeito ou sinal de uso
- bom: pequenos sinais de uso natural, sem defeitos que comprometam a funcionalidade
- regular: defeitos leves a moderados presentes, funcional mas com problemas visíveis
- ruim: defeitos sérios que necessitam reparo
- péssimo: danos graves, inutilizável ou muito comprometido

Se não houver problemas visíveis, retorne "problems" como lista vazia: []"""

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
