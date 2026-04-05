import anthropic
import base64
import json
import os
import re

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

def _encode_image(image_path):
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def analyze_photos(image_paths, item_name='', room_name='', modo='simples'):
    """
    Analisa fotos de um ambiente para vistoria imobiliária.
    
    modo='simples': retorna {description, estado} — compatibilidade legada
    modo='completo': retorna {itens, observacoes, descricao_geral, estado}
    """
    if not ANTHROPIC_API_KEY:
        return {
            'description': 'Configure ANTHROPIC_API_KEY para análise automática.',
            'estado': 'Regular',
            'itens': [],
            'observacoes': [],
            'descricao_geral': 'API não configurada.'
        }

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Preparar imagens
    images_content = []
    for path in image_paths:
        try:
            img_data = _encode_image(path)
            images_content.append({
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': 'image/jpeg',
                    'data': img_data
                }
            })
        except Exception:
            pass

    if not images_content:
        return {
            'description': 'Não foi possível processar a imagem.',
            'estado': 'Regular',
            'itens': [],
            'observacoes': [],
            'descricao_geral': 'Imagem inválida.'
        }

    # Itens esperados no ambiente
    itens_lista = [i.strip() for i in item_name.split(',') if i.strip()] if item_name else []

    # ── MODO COMPLETO ─────────────────────────────────────
    if modo == 'completo':
        itens_str = '\n'.join(['- ' + i for i in itens_lista]) if itens_lista else '- piso\n- parede\n- teto\n- porta\n- janela\n- iluminação'

        system_msg = """Você é um perito em vistoria imobiliária profissional. 
Analisa fotos de imóveis com precisão técnica e linguagem objetiva.
NUNCA invente informações. Descreva apenas o que é visível na foto.
Sempre retorne JSON válido conforme solicitado."""

        prompt = f"""Analise esta foto do ambiente: {room_name}

ITENS PARA AVALIAR:
{itens_str}

Para cada item VISÍVEL na foto, determine:
- estado: "Bom", "Regular" ou "Com avaria"
- descricao: frase técnica objetiva sobre o estado

Detecte também OBSERVAÇÕES IMPORTANTES como:
- trincas, fissuras, rachaduras
- infiltração, umidade, mofo, manchas
- ferrugem, corrosão
- descascamento, desgaste acentuado
- itens quebrados ou danificados

RETORNE APENAS JSON VÁLIDO neste formato exato:
{{
  "descricao_geral": "Descrição técnica geral do ambiente em 1-2 frases",
  "estado": "Bom|Regular|Com avaria",
  "itens": [
    {{"nome": "nome do item", "estado": "Bom|Regular|Com avaria", "descricao": "descrição técnica do item"}}
  ],
  "observacoes": [
    "Observação importante detectada 1",
    "Observação importante detectada 2"
  ]
}}

REGRAS:
- Inclua apenas itens VISÍVEIS na foto
- Se o item não estiver visível, NÃO inclua no array
- observacoes deve ser array vazio [] se não houver anomalias
- Seja objetivo e técnico, sem exageros
- NÃO use markdown, retorne apenas o JSON"""

    # ── MODO SIMPLES (legado) ─────────────────────────────
    else:
        system_msg = """Você é um perito em vistoria imobiliária. 
Analisa fotos com precisão técnica.
NUNCA invente. Descreva apenas o visível.
Retorne JSON válido."""

        prompt = f"""Analise esta foto do item: {item_name}
Ambiente: {room_name}

Retorne JSON:
{{
  "condition": "Bom|Regular|Ruim",
  "estado": "Bom|Regular|Ruim", 
  "description": "Descrição técnica objetiva do estado de conservação",
  "descricao_geral": "mesma description",
  "itens": [{{"nome": "{item_name}", "estado": "Bom|Regular|Ruim", "descricao": "descrição"}}],
  "observacoes": []
}}"""

    # ── CHAMADA À API ─────────────────────────────────────
    content = images_content + [{'type': 'text', 'text': prompt}]

    for tentativa in range(3):
        try:
            response = client.messages.create(
                model='claude-sonnet-4-5',
                max_tokens=1500,
                system=system_msg,
                messages=[{'role': 'user', 'content': content}]
            )

            text = response.content[0].text.strip()

            # Limpar markdown se houver
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()

            # Extrair JSON
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                text = match.group(0)

            d = json.loads(text)

            # Normalizar campos para garantir compatibilidade
            resultado = {
                'description': d.get('description') or d.get('descricao_geral', ''),
                'estado': d.get('estado') or d.get('condition', 'Regular'),
                'descricao_geral': d.get('descricao_geral') or d.get('description', ''),
                'itens': d.get('itens') or d.get('items') or [],
                'observacoes': d.get('observacoes') or d.get('observations') or [],
                'condition': d.get('condition') or d.get('estado', 'Regular'),
                'success': True
            }

            # Garantir que description esteja preenchido
            if not resultado['description'] and resultado['descricao_geral']:
                resultado['description'] = resultado['descricao_geral']
            if not resultado['descricao_geral'] and resultado['description']:
                resultado['descricao_geral'] = resultado['description']

            return resultado

        except json.JSONDecodeError:
            # Fallback — retornar o texto como descrição
            if tentativa == 2:
                return {
                    'description': text[:500] if 'text' in dir() else 'Erro ao processar resposta.',
                    'estado': 'Regular',
                    'descricao_geral': text[:500] if 'text' in dir() else '',
                    'itens': [],
                    'observacoes': [],
                    'condition': 'Regular',
                    'success': False
                }
        except Exception as e:
            if tentativa == 2:
                return {
                    'description': f'Erro na análise: {str(e)}',
                    'estado': 'Regular',
                    'descricao_geral': '',
                    'itens': [],
                    'observacoes': [],
                    'condition': 'Regular',
                    'success': False
                }

    return {
        'description': 'Não foi possível analisar a imagem.',
        'estado': 'Regular',
        'descricao_geral': '',
        'itens': [],
        'observacoes': [],
        'condition': 'Regular',
        'success': False
    }


def analyze_photo(image_path, item_name='', room_name='', modo='simples'):
    """Wrapper para análise de foto única — mantém compatibilidade."""
    return analyze_photos([image_path], item_name, room_name, modo)
