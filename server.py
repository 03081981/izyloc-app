# deploy: 2026-03-18
#!/usr/bin/env python3
"""
IZYLO - Sistema de Vistoria de ImÃ³veis
Backend: Python + Tornado
"""

import tornado.ioloop
import tornado.web
import tornado.escape
import json
import os
import uuid
import jwt
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

from database import get_conn, init_db
from ai_service import analyze_photos, analyze_photo
from pdf_service import generate_pdf

load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY', 'izylo-secret-key-change-in-production-2024')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
PDF_DIR = os.path.join(os.path.dirname(__file__), 'pdfs')
Path(UPLOAD_DIR).mkdir(exist_ok=True)
Path(PDF_DIR).mkdir(exist_ok=True)

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def create_token(user_id, email):
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except Exception:
        return None


class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.set_header("Content-Type", "application/json")

    def options(self, *args):
        self.set_status(204)
        self.finish()

    def get_current_user(self):
        auth = self.request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
            payload = verify_token(token)
            if payload:
                return payload
        # Aceita token via query param para download direto de PDF
        token = self.get_argument('token', None)
        if token:
            payload = verify_token(token)
            if payload:
                return payload
        return None

    def require_auth(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({'error': 'NÃ£o autenticado'})
            self.finish()
            return None
        return user

    def json_body(self):
        try:
            return json.loads(self.request.body)
        except Exception:
            return {}

    def ok(self, data=None, status=200):
        self.set_status(status)
        self.write(data or {'ok': True})

    def err(self, msg, status=400):
        self.set_status(status)
        self.write({'error': msg})

    def row_to_dict(self, row):
        if row is None:
            return None
        return dict(row)

    def rows_to_list(self, rows):
        return [dict(r) for r in rows]


# âââ AUTH ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

class RegisterHandler(BaseHandler):
    def post(self):
        data = self.json_body()
        required = ['name', 'email', 'password', 'company_name']
        for f in required:
            if not data.get(f):
                return self.err(f'Campo obrigatÃ³rio: {f}')

        conn = get_conn()
        try:
            existing = conn.execute('SELECT id FROM users WHERE email=?', (data['email'],)).fetchone()
            if existing:
                return self.err('E-mail jÃ¡ cadastrado')

            user_id = str(uuid.uuid4())
            conn.execute('''INSERT INTO users (id, name, email, password_hash, company_name, creci, phone)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (user_id, data['name'], data['email'],
                         hash_password(data['password']),
                         data['company_name'],
                         data.get('creci', ''),
                         data.get('phone', '')))
            conn.commit()
            token = create_token(user_id, data['email'])
            self.ok({'token': token, 'user': {
                'id': user_id, 'name': data['name'],
                'email': data['email'], 'company_name': data['company_name']
            }}, 201)
        finally:
            conn.close()


class LoginHandler(BaseHandler):
    def post(self):
        data = self.json_body()
        if not data.get('email') or not data.get('password'):
            return self.err('E-mail e senha obrigatÃ³rios')

        conn = get_conn()
        try:
            user = conn.execute('SELECT * FROM users WHERE email=? AND active=1',
                               (data['email'],)).fetchone()
            if not user or user['password_hash'] != hash_password(data['password']):
                return self.err('E-mail ou senha incorretos', 401)

            token = create_token(user['id'], user['email'])
            self.ok({'token': token, 'user': {
                'id': user['id'], 'name': user['name'],
                'email': user['email'],
                'company_name': user['company_name'],
                'plan': user['plan'],
                'creci': user['creci'],
                'phone': user['phone'],
            }})
        finally:
            conn.close()


class MeHandler(BaseHandler):
    def get(self):
        user = self.require_auth()
        if not user:
            return
        conn = get_conn()
        try:
            row = conn.execute('SELECT * FROM users WHERE id=?', (user['user_id'],)).fetchone()
            if not row:
                return self.err('UsuÃ¡rio nÃ£o encontrado', 404)
            u = self.row_to_dict(row)
            u.pop('password_hash', None)
            self.ok(u)
        finally:
            conn.close()


# âââ INSPECTIONS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

class InspectionsHandler(BaseHandler):
    def get(self):
        user = self.require_auth()
        if not user:
            return
        conn = get_conn()
        try:
            rows = conn.execute(
                'SELECT * FROM inspections WHERE user_id=? ORDER BY created_at DESC',
                (user['user_id'],)).fetchall()
            self.ok({'inspections': self.rows_to_list(rows)})
        finally:
            conn.close()

    def post(self):
        user = self.require_auth()
        if not user:
            return
        data = self.json_body()
        if not data.get('type') or data['type'] not in ('entrada', 'saida'):
            return self.err('Tipo de vistoria invÃ¡lido (entrada ou saida)')

        conn = get_conn()
        try:
            insp_id = str(uuid.uuid4())
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            fields = [
                'id', 'user_id', 'type', 'status', 'property_address', 'property_type',
                'property_area', 'inspection_date',
                'locador_name', 'locador_cpf', 'locador_rg', 'locador_phone', 'locador_email',
                'locatario_name', 'locatario_cpf', 'locatario_rg', 'locatario_phone', 'locatario_email',
                'locadores_json', 'locatarios_json',
                'corretor_name', 'corretor_creci', 'corretor_phone', 'corretor_email',
                'imobiliaria_name', 'imobiliaria_cnpj', 'imobiliaria_phone', 'imobiliaria_address',
                'observations', 'created_at', 'updated_at'
            ]
            values = [
                insp_id, user['user_id'], data['type'], 'rascunho',
                data.get('property_address', ''), data.get('property_type', ''),
                data.get('property_area', ''), data.get('inspection_date', datetime.now().strftime('%d/%m/%Y')),
                data.get('locador_name', ''), data.get('locador_cpf', ''),
                data.get('locador_rg', ''), data.get('locador_phone', ''), data.get('locador_email', ''),
                data.get('locatario_name', ''), data.get('locatario_cpf', ''),
                data.get('locatario_rg', ''), data.get('locatario_phone', ''), data.get('locatario_email', ''),
                json.dumps(data.get('locadores', [])), json.dumps(data.get('locatarios', [])),
                data.get('corretor_name', ''), data.get('corretor_creci', ''),
                data.get('corretor_phone', ''), data.get('corretor_email', ''),
                data.get('imobiliaria_name', ''), data.get('imobiliaria_cnpj', ''),
                data.get('imobiliaria_phone', ''), data.get('imobiliaria_address', ''),
                data.get('observations', ''), now, now
            ]
            placeholders = ','.join(['?'] * len(fields))
            col_names = ','.join(fields)
            conn.execute(f'INSERT INTO inspections ({col_names}) VALUES ({placeholders})', values)
            conn.commit()
            row = conn.execute('SELECT * FROM inspections WHERE id=?', (insp_id,)).fetchone()
            self.ok(self.row_to_dict(row), 201)
        finally:
            conn.close()


class InspectionHandler(BaseHandler):
    def get(self, insp_id):
        user = self.require_auth()
        if not user:
            return
        conn = get_conn()
        try:
            insp = conn.execute(
                'SELECT * FROM inspections WHERE id=? AND user_id=?',
                (insp_id, user['user_id'])).fetchone()
            if not insp:
                return self.err('Vistoria nÃ£o encontrada', 404)
            result = self.row_to_dict(insp)

            # Inclui ambientes + itens
            rooms = conn.execute(
                'SELECT * FROM rooms WHERE inspection_id=? ORDER BY order_num', (insp_id,)).fetchall()
            rooms_list = []
            for room in rooms:
                room_dict = self.row_to_dict(room)
                items = conn.execute(
                    'SELECT * FROM room_items WHERE room_id=? ORDER BY created_at', (room['id'],)).fetchall()
                items_list = self.rows_to_list(items)
                # Inclui lista de fotos de cada item
                for it in items_list:
                    photos = conn.execute(
                        'SELECT id, filename FROM item_photos WHERE item_id=? ORDER BY created_at',
                        (it['id'],)).fetchall()
                    it['photos'] = [{'id': p['id'], 'url': f'/uploads/{p["filename"]}'} for p in photos]
                room_dict['items'] = items_list
                rooms_list.append(room_dict)
            result['rooms'] = rooms_list

            # Assinaturas
            sigs = conn.execute(
                'SELECT * FROM signatures WHERE inspection_id=?', (insp_id,)).fetchall()
            result['signatures'] = self.rows_to_list(sigs)
            self.ok(result)
        finally:
            conn.close()

    def put(self, insp_id):
        user = self.require_auth()
        if not user:
            return
        data = self.json_body()
        conn = get_conn()
        try:
            insp = conn.execute(
                'SELECT id FROM inspections WHERE id=? AND user_id=?',
                (insp_id, user['user_id'])).fetchone()
            if not insp:
                return self.err('Vistoria nÃ£o encontrada', 404)

            updatable = [
                'property_address', 'property_type', 'property_area', 'inspection_date', 'status',
                'locador_name', 'locador_cpf', 'locador_rg', 'locador_phone', 'locador_email',
                'locatario_name', 'locatario_cpf', 'locatario_rg', 'locatario_phone', 'locatario_email',
                'corretor_name', 'corretor_creci', 'corretor_phone', 'corretor_email',
                'imobiliaria_name', 'imobiliaria_cnpj', 'imobiliaria_phone', 'imobiliaria_address',
                'observations'
            ]
            sets = []
            vals = []
            # Handle JSON array fields for multiple parties
            if 'locadores' in data:
                sets.append('locadores_json=?')
                vals.append(json.dumps(data['locadores']))
            if 'locatarios' in data:
                sets.append('locatarios_json=?')
                vals.append(json.dumps(data['locatarios']))
            for f in updatable:
                if f in data:
                    sets.append(f'{f}=?')
                    vals.append(data[f])

            if sets:
                sets.append('updated_at=?')
                vals.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                vals.append(insp_id)
                conn.execute(f'UPDATE inspections SET {",".join(sets)} WHERE id=?', vals)
                conn.commit()

            row = conn.execute('SELECT * FROM inspections WHERE id=?', (insp_id,)).fetchone()
            self.ok(self.row_to_dict(row))
        finally:
            conn.close()


# âââ ROOMS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

class RoomsHandler(BaseHandler):
    def post(self, insp_id):
        user = self.require_auth()
        if not user:
            return
        data = self.json_body()
        if not data.get('name'):
            return self.err('Nome do ambiente obrigatÃ³rio')

        conn = get_conn()
        try:
            insp = conn.execute(
                'SELECT id FROM inspections WHERE id=? AND user_id=?',
                (insp_id, user['user_id'])).fetchone()
            if not insp:
                return self.err('Vistoria nÃ£o encontrada', 404)

            # Conta ambientes existentes para order_num
            count = conn.execute('SELECT COUNT(*) FROM rooms WHERE inspection_id=?',
                                  (insp_id,)).fetchone()['count']
            room_id = str(uuid.uuid4())
            conn.execute(
                'INSERT INTO rooms (id, inspection_id, name, order_num, general_condition, observations) VALUES (?,?,?,?,?,?)',
                (room_id, insp_id, data['name'], count,
                 data.get('general_condition', ''), data.get('observations', '')))
            conn.commit()
            row = conn.execute('SELECT * FROM rooms WHERE id=?', (room_id,)).fetchone()
            room_dict = self.row_to_dict(row)
            room_dict['items'] = []
            self.ok(room_dict, 201)
        finally:
            conn.close()


class RoomHandler(BaseHandler):
    def put(self, room_id):
        user = self.require_auth()
        if not user:
            return
        data = self.json_body()
        conn = get_conn()
        try:
            room = conn.execute(
                '''SELECT r.* FROM rooms r
                   JOIN inspections i ON r.inspection_id=i.id
                   WHERE r.id=? AND i.user_id=?''',
                (room_id, user['user_id'])).fetchone()
            if not room:
                return self.err('Ambiente nÃ£o encontrado', 404)

            conn.execute('''UPDATE rooms SET name=?, general_condition=?, observations=?
                           WHERE id=?''',
                        (data.get('name', room['name']),
                         data.get('general_condition', room['general_condition']),
                         data.get('observations', room['observations']),
                         room_id))
            conn.commit()
            row = conn.execute('SELECT * FROM rooms WHERE id=?', (room_id,)).fetchone()
            self.ok(self.row_to_dict(row))
        finally:
            conn.close()

    def delete(self, room_id):
        user = self.require_auth()
        if not user:
            return
        conn = get_conn()
        try:
            room = conn.execute(
                '''SELECT r.* FROM rooms r
                   JOIN inspections i ON r.inspection_id=i.id
                   WHERE r.id=? AND i.user_id=?''',
                (room_id, user['user_id'])).fetchone()
            if not room:
                return self.err('Ambiente nÃ£o encontrado', 404)
            conn.execute('DELETE FROM room_items WHERE room_id=?', (room_id,))
            conn.execute('DELETE FROM rooms WHERE id=?', (room_id,))
            conn.commit()
            self.ok({'deleted': True})
        finally:
            conn.close()


# âââ ROOM ITEMS ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

class RoomItemsHandler(BaseHandler):
    def post(self, room_id):
        user = self.require_auth()
        if not user:
            return
        data = self.json_body()
        if not data.get('name'):
            return self.err('Nome do item obrigatÃ³rio')

        conn = get_conn()
        try:
            room = conn.execute(
                '''SELECT r.* FROM rooms r
                   JOIN inspections i ON r.inspection_id=i.id
                   WHERE r.id=? AND i.user_id=?''',
                (room_id, user['user_id'])).fetchone()
            if not room:
                return self.err('Ambiente nÃ£o encontrado', 404)

            item_id = str(uuid.uuid4())
            conn.execute(
                '''INSERT INTO room_items
                   (id, room_id, name, condition, ai_description, manual_description, photo_path, photo_filename)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (item_id, room_id, data['name'],
                 data.get('condition', ''),
                 data.get('ai_description', ''),
                 data.get('manual_description', ''),
                 data.get('photo_path', ''),
                 data.get('photo_filename', '')))
            conn.commit()
            row = conn.execute('SELECT * FROM room_items WHERE id=?', (item_id,)).fetchone()
            self.ok(self.row_to_dict(row), 201)
        finally:
            conn.close()


class RoomItemHandler(BaseHandler):
    def put(self, item_id):
        user = self.require_auth()
        if not user:
            return
        data = self.json_body()
        conn = get_conn()
        try:
            item = conn.execute(
                '''SELECT ri.* FROM room_items ri
                   JOIN rooms r ON ri.room_id=r.id
                   JOIN inspections i ON r.inspection_id=i.id
                   WHERE ri.id=? AND i.user_id=?''',
                (item_id, user['user_id'])).fetchone()
            if not item:
                return self.err('Item nÃ£o encontrado', 404)

            updatable = ['name', 'condition', 'ai_description', 'manual_description']
            sets = []
            vals = []
            for f in updatable:
                if f in data:
                    sets.append(f'{f}=?')
                    vals.append(data[f])
            if sets:
                vals.append(item_id)
                conn.execute(f'UPDATE room_items SET {",".join(sets)} WHERE id=?', vals)
                conn.commit()
            row = conn.execute('SELECT * FROM room_items WHERE id=?', (item_id,)).fetchone()
            self.ok(self.row_to_dict(row))
        finally:
            conn.close()

    def delete(self, item_id):
        user = self.require_auth()
        if not user:
            return
        conn = get_conn()
        try:
            item = conn.execute(
                '''SELECT ri.* FROM room_items ri
                   JOIN rooms r ON ri.room_id=r.id
                   JOIN inspections i ON r.inspection_id=i.id
                   WHERE ri.id=? AND i.user_id=?''',
                (item_id, user['user_id'])).fetchone()
            if not item:
                return self.err('Item nÃ£o encontrado', 404)

            # Remove arquivo de foto se existir
            if item['photo_path'] and os.path.exists(item['photo_path']):
                try:
                    os.remove(item['photo_path'])
                except Exception:
                    pass

            conn.execute('DELETE FROM room_items WHERE id=?', (item_id,))
            conn.commit()
            self.ok({'deleted': True})
        finally:
            conn.close()


# âââ FOTO UPLOAD + ANÃLISE IA ââââââââââââââââââââââââââââââââââââââââââââââââââ

class PhotoUploadHandler(BaseHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.set_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.set_header("Content-Type", "application/json")

    def post(self, item_id):
        user = self.require_auth()
        if not user:
            return

        conn = get_conn()
        try:
            item = conn.execute(
                '''SELECT ri.*, r.name as room_name FROM room_items ri
                   JOIN rooms r ON ri.room_id=r.id
                   JOIN inspections i ON r.inspection_id=i.id
                   WHERE ri.id=? AND i.user_id=?''',
                (item_id, user['user_id'])).fetchone()
            if not item:
                return self.err('Item nÃ£o encontrado', 404)

            if 'photo' not in self.request.files:
                return self.err('Nenhuma foto enviada')

            file_info = self.request.files['photo'][0]
            ext = os.path.splitext(file_info['filename'])[1].lower() or '.jpg'
            allowed = ['.jpg', '.jpeg', '.png', '.webp']
            if ext not in allowed:
                return self.err('Formato de arquivo invÃ¡lido. Use JPG, PNG ou WebP')

            # Salva com nome Ãºnico (UUID) para permitir mÃºltiplas fotos por item
            photo_id = str(uuid.uuid4())
            filename = f"{photo_id}{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)

            with open(filepath, 'wb') as f:
                f.write(file_info['body'])

            # Registra na tabela item_photos
            conn.execute(
                'INSERT INTO item_photos (id, item_id, filename) VALUES (?,?,?)',
                (photo_id, item_id, filename))

            # Atualiza photo_path principal no item (Ãºltima foto adicionada)
            conn.execute('UPDATE room_items SET photo_path=?, photo_filename=? WHERE id=?',
                        (filepath, filename, item_id))
            conn.commit()

            # Busca TODAS as fotos do item para anÃ¡lise conjunta
            all_photos = conn.execute(
                'SELECT filename FROM item_photos WHERE item_id=? ORDER BY created_at',
                (item_id,)).fetchall()
            all_paths = [os.path.join(UPLOAD_DIR, p['filename']) for p in all_photos if os.path.exists(os.path.join(UPLOAD_DIR, p['filename']))]

            # Analisa com IA usando todas as fotos disponÃ­veis
            ai_result = analyze_photos(all_paths, item['name'], item['room_name'])

            # Atualiza descriÃ§Ã£o da IA no banco
            if ai_result.get('success') and ai_result.get('description'):
                conn.execute('''UPDATE room_items
                               SET ai_description=?, condition=?
                               WHERE id=?''',
                            (ai_result.get('description', ''),
                             ai_result.get('condition', ''),
                             item_id))
                conn.commit()

            row = conn.execute('SELECT * FROM room_items WHERE id=?', (item_id,)).fetchone()
            result = self.row_to_dict(row)
            result['ai_result'] = ai_result
            result['photo_id'] = photo_id
            result['photo_url'] = f'/uploads/{filename}'
            result['total_photos'] = len(all_paths)
            self.ok(result)
        finally:
            conn.close()


class ItemPhotosHandler(BaseHandler):
    """Lista todas as fotos de um item."""
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.set_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.set_header("Content-Type", "application/json")

    def get(self, item_id):
        user = self.require_auth()
        if not user:
            return
        conn = get_conn()
        try:
            # Verifica que o item pertence ao usuÃ¡rio
            item = conn.execute(
                '''SELECT ri.id FROM room_items ri
                   JOIN rooms r ON ri.room_id=r.id
                   JOIN inspections i ON r.inspection_id=i.id
                   WHERE ri.id=? AND i.user_id=?''',
                (item_id, user['user_id'])).fetchone()
            if not item:
                return self.err('Item nÃ£o encontrado', 404)

            photos = conn.execute(
                'SELECT id, filename, created_at FROM item_photos WHERE item_id=? ORDER BY created_at',
                (item_id,)).fetchall()

            result = [{
                'id': p['id'],
                'url': f'/uploads/{p["filename"]}',
                'created_at': p['created_at']
            } for p in photos]
            self.ok({'photos': result})
        finally:
            conn.close()


class PhotoDeleteHandler(BaseHandler):
    """Exclui uma foto especÃ­fica de um item."""
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.set_header("Access-Control-Allow-Methods", "DELETE, OPTIONS")
        self.set_header("Content-Type", "application/json")

    def options(self, item_id, photo_id):
        self.set_status(204)
        self.finish()

    def delete(self, item_id, photo_id):
        user = self.require_auth()
        if not user:
            return
        conn = get_conn()
        try:
            # Verifica pertencimento
            item = conn.execute(
                '''SELECT ri.* FROM room_items ri
                   JOIN rooms r ON ri.room_id=r.id
                   JOIN inspections i ON r.inspection_id=i.id
                   WHERE ri.id=? AND i.user_id=?''',
                (item_id, user['user_id'])).fetchone()
            if not item:
                return self.err('Item nÃ£o encontrado', 404)

            photo = conn.execute(
                'SELECT * FROM item_photos WHERE id=? AND item_id=?',
                (photo_id, item_id)).fetchone()
            if not photo:
                return self.err('Foto nÃ£o encontrada', 404)

            # Remove o arquivo fÃ­sico
            try:
                if os.path.exists(os.path.join(UPLOAD_DIR, photo['filename'])):
                    os.remove(os.path.join(UPLOAD_DIR, photo['filename']))
            except Exception:
                pass

            conn.execute('DELETE FROM item_photos WHERE id=?', (photo_id,))

            # Atualiza photo_path principal para a foto mais recente restante
            remaining = conn.execute(
                'SELECT filename FROM item_photos WHERE item_id=? ORDER BY created_at DESC LIMIT 1',
                (item_id,)).fetchone()
            if remaining:
                conn.execute('UPDATE room_items SET photo_path=?, photo_filename=? WHERE id=?',
                            (os.path.join(UPLOAD_DIR, remaining['filename']), remaining['filename'], item_id))
            else:
                conn.execute('UPDATE room_items SET photo_path=NULL, photo_filename=NULL WHERE id=?',
                            (item_id,))

            conn.commit()
            self.ok({'deleted': True, 'photo_id': photo_id})
        finally:
            conn.close()


# âââ ASSINATURAS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

class SignaturesHandler(BaseHandler):
    def post(self, insp_id):
        user = self.require_auth()
        if not user:
            return
        data = self.json_body()
        if not data.get('party_type'):
            return self.err('Tipo de parte obrigatÃ³rio')

        valid_parties = ['locador', 'locatario', 'corretor', 'testemunha1', 'testemunha2']
        if data['party_type'] not in valid_parties:
            return self.err(f'Tipo de parte invÃ¡lido. Use: {", ".join(valid_parties)}')

        conn = get_conn()
        try:
            insp = conn.execute(
                'SELECT id FROM inspections WHERE id=? AND user_id=?',
                (insp_id, user['user_id'])).fetchone()
            if not insp:
                return self.err('Vistoria nÃ£o encontrada', 404)

            # Remove assinatura anterior desta parte (se houver)
            conn.execute('DELETE FROM signatures WHERE inspection_id=? AND party_type=?',
                        (insp_id, data['party_type']))

            sig_id = str(uuid.uuid4())
            conn.execute(
                'INSERT INTO signatures (id, inspection_id, party_type, party_name, signature_data) VALUES (?,?,?,?,?)',
                (sig_id, insp_id, data['party_type'],
                 data.get('party_name', ''), data.get('signature_data', '')))

            # Marca vistoria como assinada
            conn.execute("UPDATE inspections SET status='assinado', updated_at=? WHERE id=?",
                        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), insp_id))
            conn.commit()
            row = conn.execute('SELECT * FROM signatures WHERE id=?', (sig_id,)).fetchone()
            self.ok(self.row_to_dict(row), 201)
        finally:
            conn.close()


# âââ GERAR PDF âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

class GeneratePDFHandler(BaseHandler):
    def get(self, insp_id):
        user = self.require_auth()
        if not user:
            return

        conn = get_conn()
        try:
            insp = conn.execute(
                'SELECT * FROM inspections WHERE id=? AND user_id=?',
                (insp_id, user['user_id'])).fetchone()
            if not insp:
                return self.err('Vistoria nÃ£o encontrada', 404)

            inspection_data = self.row_to_dict(insp)

            # Busca ambientes e itens
            rooms = conn.execute(
                'SELECT * FROM rooms WHERE inspection_id=? ORDER BY order_num', (insp_id,)).fetchall()
            rooms_list = []
            for room in rooms:
                room_dict = self.row_to_dict(room)
                items = conn.execute(
                    'SELECT * FROM room_items WHERE room_id=? ORDER BY created_at',
                    (room['id'],)).fetchall()
                room_dict['items'] = self.rows_to_list(items)
                rooms_list.append(room_dict)

            # Busca assinaturas
            sigs = conn.execute(
                'SELECT * FROM signatures WHERE inspection_id=?', (insp_id,)).fetchall()
            signatures_list = self.rows_to_list(sigs)

            # Gera PDF
            tipo = inspection_data.get('type', 'entrada')
            pdf_filename = f"IZYLO_Laudo_{tipo}_{insp_id[:8].upper()}.pdf"
            pdf_path = os.path.join(PDF_DIR, pdf_filename)

            success = generate_pdf(inspection_data, rooms_list, signatures_list, pdf_path)

            if not success:
                return self.err('Erro ao gerar PDF', 500)

            # Marca como concluÃ­do
            conn.execute("UPDATE inspections SET status='concluido', updated_at=? WHERE id=?",
                        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), insp_id))
            conn.commit()

            self.set_header('Content-Type', 'application/pdf')
            self.set_header('Content-Disposition', f'attachment; filename="{pdf_filename}"')
            with open(pdf_path, 'rb') as f:
                self.write(f.read())
            self.finish()
        finally:
            conn.close()


# âââ SERVE FOTOS âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

class PhotoHandler(tornado.web.StaticFileHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")


# âââ SERVIR FRONTEND âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

class MainHandler(tornado.web.RequestHandler):
    def get(self, path=None):
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        self.set_header("Content-Type", "text/html; charset=utf-8")
        with open(os.path.join(static_dir, 'index.html'), 'r', encoding='utf-8') as f:
            self.write(f.read())


# âââ APP âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def make_app():
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    upload_dir = UPLOAD_DIR
    return tornado.web.Application([
        # Auth
        (r'/api/auth/register', RegisterHandler),
        (r'/api/auth/login', LoginHandler),
        (r'/api/auth/me', MeHandler),
        # Inspections
        (r'/api/inspections', InspectionsHandler),
        (r'/api/inspections/([^/]+)', InspectionHandler),
        # Rooms
        (r'/api/inspections/([^/]+)/rooms', RoomsHandler),
        (r'/api/rooms/([^/]+)', RoomHandler),
        # Items
        (r'/api/rooms/([^/]+)/items', RoomItemsHandler),
        (r'/api/items/([^/]+)', RoomItemHandler),
        (r'/api/items/([^/]+)/photo', PhotoUploadHandler),
        (r'/api/items/([^/]+)/photos', ItemPhotosHandler),
        (r'/api/items/([^/]+)/photos/([^/]+)', PhotoDeleteHandler),
        # Signatures
        (r'/api/inspections/([^/]+)/signatures', SignaturesHandler),
        # PDF
        (r'/api/inspections/([^/]+)/pdf', GeneratePDFHandler),
        # Static files
        (r'/uploads/(.*)', tornado.web.StaticFileHandler, {'path': upload_dir}),
        (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': static_dir}),
        # Frontend (SPA)
        (r'/(.*)', MainHandler),
    ], debug=True)


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8888))
    app = make_app()
    app.listen(port)
    print(f"""
âââââââââââââââââââââââââââââââââââââââââ
â          IZYLO - Iniciado!            â
â  Acesse: http://localhost:{port}        â
âââââââââââââââââââââââââââââââââââââââââ
    """)
    tornado.ioloop.IOLoop.current().start()
