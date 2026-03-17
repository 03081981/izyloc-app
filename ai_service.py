import requests
import base64
import os
import json

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'

def analyze_photo(image_path: str, item_name: str, room_name: str) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"success": False, "description": "Chave de API da IA não configurada", "condition": "não avaliado"}
    try:
        with open(image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')
        ext = os.path.splitext(image_path)[1].lower()
        media_types = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif'}
        media_type = media_types.get(ext, 'image/jpeg')
        prompt = f"Você é um vistoriador profissional. Analise esta foto do item {item_name} no ambiente {room_name}. Responda em JSON."
        headers = {'x-api-key': ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
        payload = {'model': 'claude-sonnet-4-5', 'max_tokens': 800, 'messages': [{'role': 'user', 'content': [{ 'type': 'image', 'source': {'type': 'base64', 'media_type': media_type, 'data': image_data}}, {'type': 'text', 'text': prompt}]}]}
        response = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            text = response.json()['content'][0]['text'].strip()
            try:
                import json
                if '```json' in text: text = text.split('```json')[1].split('```')[0].strip()
                analysis = json.loads(text)
                return {"success": True, "condition": analysis.get("condition", "avaliado"), "description": analysis.get("description", ""), "material": analysis.get("material", ""), "color": analysis.get("color", ""), "problems": analysis.get("problems", []), "cleanliness": analysis.get("cleanliness", ""), "technical_notes": analysis.get("technical_notes", ""), "full_analysis": analysis}
            except: return {"success": True, "condition": "avaliado", "description": text, "problems": []}
        else: return {"success": False, "description": f"Erro: {response.status_code}", "condition": "não avaliado"}
    except Exception as e: return {"success": False, "description": f"Erro: {str(e)}", "condition": "não avaliado"}
