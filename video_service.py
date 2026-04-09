import os
import json
import base64
import tempfile
import subprocess
import time
from pathlib import Path

# OpenAI para Whisper (lazy init)
openai_client = None

def _get_openai_client():
    global openai_client
    if openai_client is None:
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
        except Exception:
            pass
    return openai_client

# Palavras-chave que disparam frame forcado
PALAVRAS_AVARIA = [
    'avaria', 'quebrado', 'quebrada', 'rachado', 'rachada', 'trinca', 'trincado',
    'trincada', 'fissura', 'rachadura', 'mofo', 'bolor', 'infiltracao', 'infiltracao',
    'vazamento', 'vazando', 'mancha', 'manchado', 'manchada', 'furo', 'buraco',
    'descascando', 'descascado', 'descascada', 'desgastado', 'desgastada',
    'danificado', 'danificada', 'problema', 'defeito', 'solto', 'solta',
    'oxidado', 'oxidada', 'ferrugem', 'entupido', 'entupida', 'atencao',
    'olha aqui', 'repara aqui', 'veja aqui'
]

PALAVRAS_TESTE_OK = [
    'funcionando', 'funciona', 'funcionou', 'ok', 'ta bom', 'esta bom',
    'normal', 'tem chave', 'abre e fecha', 'abrindo', 'fechando', 'ligou',
    'acendeu', 'esta funcionando', 'funcionamento'
]

PALAVRAS_TESTE_NOK = [
    'nao funciona', 'nao funcionou', 'com defeito', 'sem energia', 'nao abre',
    'nao fecha', 'nao liga', 'nao acende', 'sem energia', 'queimado', 'queimada',
    'travado', 'travada', 'emperrado', 'emperrada'
]

PALAVRAS_NA = [
    'nao tem', 'nao existe', 'nao ha', 'sem ar', 'sem chuveiro',
    'nao possui', 'inexistente', 'ausente'
]

PALAVRAS_AMBIENTE = [
    'entrando', 'estou na', 'estou no', 'agora e', 'agora eh',
    'proximo ambiente', 'indo para', 'vou para', 'aqui e', 'aqui eh',
    'estamos no', 'estamos na', 'agora o', 'agora a'
]

PALAVRAS_CONCLUIR = [
    'proximo ambiente', 'proxima', 'concluindo', 'terminei', 'finalizando',
    'vamos para', 'vou para o', 'vou para a'
]


def extrair_frames(video_path: str, output_dir: str, fps: float = 0.5) -> list:
    """
    Extrai frames do video usando FFmpeg.
    fps=0.5 significa 1 frame a cada 2 segundos.
    Retorna lista de dicts com {path, timestamp, segundo}
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Extrair frames por deteccao de cena + fps fixo
    output_pattern = os.path.join(output_dir, 'frame_%04d.jpg')
    
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', f'fps={fps},scale=1280:-1',
        '-q:v', '2',
        '-y',
        output_pattern
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        raise Exception(f'FFmpeg erro: {result.stderr}')
    
    # Listar frames gerados
    frames = []
    frame_files = sorted(Path(output_dir).glob('frame_*.jpg'))
    
    for i, f in enumerate(frame_files):
        segundo = i * (1.0 / fps)
        frames.append({
            'path': str(f),
            'timestamp': segundo,
            'segundo': round(segundo, 1),
            'index': i
        })
    
    return frames


def extrair_frame_timestamp(video_path: str, output_dir: str, segundo: float, index: int) -> dict:
    """
    Extrai um frame especifico em um timestamp (para frames forcados por avaria).
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'frame_forced_{index:04d}_{int(segundo*1000):08d}.jpg')
    
    cmd = [
        'ffmpeg', '-i', video_path,
        '-ss', str(segundo),
        '-vframes', '1',
        '-q:v', '2',
        '-y',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    if result.returncode != 0:
        return None
    
    return {
        'path': output_path,
        'timestamp': segundo,
        'segundo': round(segundo, 1),
        'index': index,
        'forcado': True
    }


def transcrever_audio(video_path: str) -> list:
    """
    Transcreve o audio do video usando Whisper via OpenAI API.
    Retorna lista de segmentos com {texto, inicio, fim}
    """
    # Extrair audio do video
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_audio:
        audio_path = tmp_audio.name
    
    try:
        cmd = [
            'ffmpeg', '-i', video_path,
            '-q:a', '0', '-map', 'a',
            '-y', audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            return []
        
        # Transcrever com Whisper
        with open(audio_path, 'rb') as audio_file:
            client = _get_openai_client()
        if not client:
            return []
        transcript = client.audio.transcriptions.create(
                model='whisper-1',
                file=audio_file,
                language='pt',
                response_format='verbose_json',
                timestamp_granularities=['segment', 'word']
            )
        
        print(f"[VIDEO-SVC] transcrever_audio: Whisper retornou, processando segmentos...")
        segmentos = []
        if hasattr(transcript, 'segments') and transcript.segments:
            print(f"[VIDEO-SVC] transcrever_audio: {len(transcript.segments)} segmentos encontrados")
            for seg in transcript.segments:
                segmentos.append({
                    'texto': seg.text.strip().lower(),
                    'inicio': seg.start,
                    'fim': seg.end
                })
        
        return segmentos
        
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)


def detectar_eventos(segmentos: list) -> list:
    """
    Analisa os segmentos de transcricao e detecta eventos:
    - avaria (frame forcado)
    - teste ok/nok/na
    - mudanca de ambiente
    - concluir ambiente
    """
    eventos = []
    
    for seg in segmentos:
        texto = seg['texto']
        timestamp = seg['inicio']
        
        # Verificar avaria
        for palavra in PALAVRAS_AVARIA:
            if palavra in texto:
                eventos.append({
                    'tipo': 'avaria',
                    'palavra': palavra,
                    'texto': texto,
                    'timestamp': timestamp,
                    'frame_forcado': True
                })
                break
        
        # Verificar teste OK
        for palavra in PALAVRAS_TESTE_OK:
            if palavra in texto:
                eventos.append({
                    'tipo': 'teste_ok',
                    'texto': texto,
                    'timestamp': timestamp
                })
                break
        
        # Verificar teste NOK
        for palavra in PALAVRAS_TESTE_NOK:
            if palavra in texto:
                eventos.append({
                    'tipo': 'teste_nok',
                    'texto': texto,
                    'timestamp': timestamp
                })
                break
        
        # Verificar N/A
        for palavra in PALAVRAS_NA:
            if palavra in texto:
                eventos.append({
                    'tipo': 'teste_na',
                    'texto': texto,
                    'timestamp': timestamp
                })
                break
        
        # Verificar mudanca de ambiente
        for palavra in PALAVRAS_AMBIENTE:
            if palavra in texto:
                eventos.append({
                    'tipo': 'novo_ambiente',
                    'texto': texto,
                    'timestamp': timestamp
                })
                break
        
        # Verificar concluir ambiente
        for palavra in PALAVRAS_CONCLUIR:
            if palavra in texto:
                eventos.append({
                    'tipo': 'concluir_ambiente',
                    'texto': texto,
                    'timestamp': timestamp
                })
                break
    
    return eventos


def classificar_frames_por_ambiente(frames: list, eventos: list, ambientes: list) -> dict:
    """
    Classifica cada frame no ambiente correto baseado nos eventos de audio.
    Retorna dict {nome_ambiente: [frames]}
    """
    if not ambientes:
        ambientes = ['Ambiente principal']
    
    resultado = {amb: [] for amb in ambientes}
    ambiente_atual = ambientes[0]
    amb_idx = 0
    
    # Ordenar eventos por timestamp
    eventos_ordenados = sorted(eventos, key=lambda e: e['timestamp'])
    evento_idx = 0
    
    for frame in frames:
        ts = frame['timestamp']
        
        # Processar eventos ate o timestamp do frame
        while evento_idx < len(eventos_ordenados):
            ev = eventos_ordenados[evento_idx]
            if ev['timestamp'] > ts:
                break
            
            if ev['tipo'] == 'novo_ambiente' or ev['tipo'] == 'concluir_ambiente':
                # Tentar identificar qual ambiente pelo texto
                texto = ev['texto']
                novo_amb = _identificar_ambiente_pelo_texto(texto, ambientes)
                if novo_amb and novo_amb != ambiente_atual:
                    ambiente_atual = novo_amb
            
            evento_idx += 1
        
        # Adicionar frame ao ambiente atual
        if ambiente_atual not in resultado:
            resultado[ambiente_atual] = []
        resultado[ambiente_atual].append(frame)
    
    return resultado


def _identificar_ambiente_pelo_texto(texto: str, ambientes: list) -> str:
    """
    Tenta identificar o ambiente mencionado no texto.
    """
    texto_lower = texto.lower()
    
    # Mapeamento de palavras-chave para tipos de ambiente
    mapa = {
        'suite': ['suite', 'su\u00edte'],
        'dormitorio': ['dormitorio', 'quarto', 'dormit\u00f3rio'],
        'banheiro': ['banheiro', 'lavabo', 'lavabo'],
        'cozinha': ['cozinha'],
        'sala': ['sala', 'estar', 'jantar'],
        'servico': ['servico', 'servi\u00e7o', 'lavanderia'],
        'garagem': ['garagem'],
        'externa': ['externa', 'fachada', 'quintal'],
        'corredor': ['corredor', 'hall'],
        'varanda': ['varanda', 'sacada']
    }
    
    for tipo, palavras in mapa.items():
        for palavra in palavras:
            if palavra in texto_lower:
                # Buscar ambiente correspondente na lista
                for amb in ambientes:
                    if tipo in amb.lower() or palavra in amb.lower():
                        return amb
                # Se nao encontrou exato, retornar o tipo
                return tipo.capitalize()
    
    return None


def frame_para_base64(frame_path: str) -> str:
    """
    Converte um frame (arquivo jpg) para base64.
    """
    with open(frame_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def processar_video_completo(video_path: str, ambientes: list, output_dir: str) -> dict:
    """
    Pipeline completo de processamento de video:
    1. Extrair frames
    2. Transcrever audio
    3. Detectar eventos
    4. Frames forcados para avarias
    5. Classificar frames por ambiente
    
    Retorna dict com resultado completo.
    """
    resultado = {
        'frames_por_ambiente': {},
        'eventos': [],
        'transcricao': [],
        'total_frames': 0,
        'success': False,
        'erro': None
    }
    
    try:
        print(f"[VIDEO-SVC] processar_video_completo: inicio")
        print(f"[VIDEO-SVC] video_path={video_path}, exists={os.path.exists(video_path)}, size={os.path.getsize(video_path) if os.path.exists(video_path) else 'N/A'}")
        print(f"[VIDEO-SVC] ambientes={ambientes}")
        print(f"[VIDEO-SVC] output_dir={output_dir}")
        # 1. Extrair frames (1 frame a cada 2 segundos)
        frames = extrair_frames(video_path, output_dir, fps=0.5)
        resultado['total_frames'] = len(frames)
        print(f"[VIDEO-SVC] Frames extraidos: {len(frames)}")
        
        # 2. Transcrever audio
        segmentos = transcrever_audio(video_path)
        resultado['transcricao'] = segmentos
        
        # 3. Detectar eventos
        eventos = detectar_eventos(segmentos)
        resultado['eventos'] = eventos
        
        # 4. Frames forcados para avarias
        frames_forcados = []
        for ev in eventos:
            if ev.get('frame_forcado'):
                frame_f = extrair_frame_timestamp(
                    video_path, output_dir,
                    ev['timestamp'],
                    len(frames) + len(frames_forcados)
                )
                if frame_f:
                    frame_f['avaria'] = ev['palavra']
                    frame_f['texto_narrado'] = ev['texto']
                    frames_forcados.append(frame_f)
        
        # Combinar frames normais e forcados
        todos_frames = frames + frames_forcados
        todos_frames.sort(key=lambda f: f['timestamp'])
        
        # 5. Classificar por ambiente
        print(f"[VIDEO-SVC] Total frames (normais+forcados): {len(todos_frames)}")
        frames_por_amb = classificar_frames_por_ambiente(todos_frames, eventos, ambientes)
        for k, v in frames_por_amb.items():
            print(f"[VIDEO-SVC] Ambiente '{k}': {len(v)} frames")
        
        # Converter frames para base64
        print(f"[VIDEO-SVC] Convertendo frames para base64...")
        resultado_final = {}
        for amb, frs in frames_por_amb.items():
            resultado_final[amb] = []
            for fr in frs:
                try:
                    b64 = frame_para_base64(fr['path'])
                    resultado_final[amb].append({
                        'base64': b64,
                        'timestamp': fr['timestamp'],
                        'segundo': fr['segundo'],
                        'forcado': fr.get('forcado', False),
                        'avaria': fr.get('avaria', None),
                        'texto_narrado': fr.get('texto_narrado', None),
                        'mime_type': 'image/jpeg'
                    })
                except Exception:
                    pass
        
        resultado['frames_por_ambiente'] = resultado_final
        total_b64 = sum(len(v) for v in resultado_final.values())
        print(f"[VIDEO-SVC] Conversao completa: {total_b64} frames em base64")
        resultado['success'] = True
        print(f"[VIDEO-SVC] processar_video_completo: SUCESSO")
        
    except Exception as e:
        import traceback
        print(f"[VIDEO-SVC] processar_video_completo: EXCEPTION: {str(e)}")
        traceback.print_exc()
        resultado['erro'] = str(e)
        resultado['success'] = False
    
    finally:
        # Limpar arquivos temporarios
        try:
            import shutil
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)
        except Exception:
            pass
    
    return resultado
