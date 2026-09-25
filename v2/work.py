"""Persistent, authenticated review work. Never writes manufacturing records."""
from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field


def stamp():
    return datetime.now(timezone.utc).isoformat()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024).hex()
    return salt + ':' + value


class WorkStore:
    def __init__(self, repo):
        self.repo = repo
        with repo._connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS v2_users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    organization TEXT NOT NULL, role TEXT NOT NULL, password TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS v2_sessions (
                    token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS v2_work (
                    id TEXT PRIMARY KEY, organization TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS v2_answers (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS v2_login_attempts (
                    identity TEXT PRIMARY KEY, attempts INTEGER NOT NULL, reset_at REAL NOT NULL);
            ''')

    def add_user(self, username, name, organization, role, password):
        if role not in ('operator', 'reviewer', 'admin') or len(password) < 12:
            raise ValueError('역할과 12자 이상의 비밀번호를 확인하세요.')
        user_id = str(uuid.uuid4())
        with self.repo._connect() as c:
            c.execute('INSERT INTO v2_users VALUES (?, ?, ?, ?, ?, ?)',
                      (user_id, username.lower().strip(), name, organization, role, password_hash(password)))
        return user_id

    def login(self, username, password, ip):
        identity = hashlib.sha256((ip + '|' + username.lower()).encode()).hexdigest()
        now = time.time()
        with self.repo._connect() as c:
            c.execute('DELETE FROM v2_login_attempts WHERE reset_at < ?', (now,))
            row = c.execute('''INSERT INTO v2_login_attempts VALUES (?, 1, ?)
                ON CONFLICT(identity) DO UPDATE SET attempts=v2_login_attempts.attempts+1
                RETURNING attempts''', (identity, now + 900)).fetchone()
            attempts = dict(row)['attempts']
        if attempts > 10:
            raise HTTPException(429, '로그인 시도가 많습니다. 15분 후 다시 시도하세요.')
        with self.repo._connect() as c:
            row = c.execute('SELECT * FROM v2_users WHERE username=?', (username.lower().strip(),)).fetchone()
        user = dict(row) if row else None
        stored = user['password'] if user else '0'*32 + ':' + '0'*128
        if not secrets.compare_digest(password_hash(password, stored.split(':')[0]), stored):
            raise HTTPException(401, '아이디 또는 비밀번호를 확인하세요.')
        token = secrets.token_urlsafe(32)
        with self.repo._connect() as c:
            c.execute('DELETE FROM v2_sessions WHERE expires < ?', (now,))
            c.execute('DELETE FROM v2_login_attempts WHERE identity=?', (identity,))
            c.execute('INSERT INTO v2_sessions VALUES (?, ?, ?)', (hashlib.sha256(token.encode()).hexdigest(), user['id'], now + 28800))
        return token, self.public(user)

    @staticmethod
    def public(user):
        return {k: user[k] for k in ('id', 'username', 'name', 'organization', 'role')}

    def user(self, request, required=True):
        token = request.cookies.get('imj_user', '')
        with self.repo._connect() as c:
            row = c.execute('''SELECT u.* FROM v2_sessions s JOIN v2_users u ON u.id=s.user_id
                WHERE s.token=? AND s.expires>?''', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        if not row and required:
            raise HTTPException(401, '업무 저장과 인계는 로그인이 필요합니다.')
        return self.public(dict(row)) if row else None

    def get(self, work_id, user, connection=None):
        def read(c):
            row = c.execute('SELECT body FROM v2_work WHERE id=? AND organization=?', (work_id, user['organization'])).fetchone()
            if not row:
                raise HTTPException(404, '업무를 찾을 수 없습니다.')
            return json.loads(dict(row)['body'])
        if connection:
            return read(connection)
        with self.repo._connect() as c:
            return read(c)

    def capture(self, user, question, answer):
        if not user:
            return answer
        answer_id = str(uuid.uuid4())
        answer = {**answer, 'answer_id': answer_id, 'captured_at': stamp()}
        snapshot = {'question': question, 'answer': answer}
        with self.repo._connect() as c:
            c.execute('INSERT INTO v2_answers VALUES (?, ?, ?, ?)', (answer_id, user['id'], json.dumps(snapshot, ensure_ascii=False, default=str), stamp()))
        return answer


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class NewWork(BaseModel):
    request_id: uuid.UUID
    title: str = Field(min_length=1, max_length=160)
    lot_id: str | None = Field(default=None, max_length=80)
    kind: str = Field(default='quality', pattern='^(quality|shipment|claim|general)$')
    note: str = Field(default='', max_length=6000)
    answer_id: uuid.UUID | None = None


class Change(BaseModel):
    expected_version: int = Field(ge=1)
    request_id: uuid.UUID
    action: str = Field(pattern='^(note|handoff|acknowledge|complete|reopen|attach_answer)$')
    text: str = Field(default='', max_length=6000)
    recipient_id: str | None = Field(default=None, max_length=80)
    answer_id: uuid.UUID | None = None


def install_work(app):
    router = APIRouter(prefix='/api')

    @router.get('/auth/me')
    def me(request: Request):
        return {'user': app.state.work.user(request, False)}

    @router.post('/auth/login')
    def login(body: Login, request: Request, response: Response):
        token, user = app.state.work.login(body.username, body.password, request.client.host if request.client else '')
        response.set_cookie('imj_user', token, httponly=True, secure=request.url.scheme == 'https', samesite='strict', max_age=28800, path='/api')
        return {'user': user}

    @router.post('/auth/logout')
    def logout(request: Request, response: Response):
        token = request.cookies.get('imj_user', '')
        with app.state.repo._connect() as c:
            c.execute('DELETE FROM v2_sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))
        response.delete_cookie('imj_user', path='/api')
        response.delete_cookie('imj_session', path='/api')
        return {'status': 'ok'}

    @router.get('/users')
    def users(request: Request):
        user = app.state.work.user(request)
        with app.state.repo._connect() as c:
            return [app.state.work.public(dict(row)) for row in c.execute('SELECT * FROM v2_users WHERE organization=? ORDER BY name', (user['organization'],)).fetchall()]

    @router.get('/work-items')
    def listing(request: Request):
        user = app.state.work.user(request)
        with app.state.repo._connect() as c:
            items = [json.loads(dict(row)['body']) for row in c.execute('SELECT body FROM v2_work WHERE organization=?', (user['organization'],)).fetchall()]
        return sorted(items, key=lambda item: item['updated_at'], reverse=True)

    @router.get('/work-items/{work_id}')
    def detail(work_id: str, request: Request):
        return app.state.work.get(work_id, app.state.work.user(request))

    @router.post('/work-items')
    def create(body: NewWork, request: Request):
        store = app.state.work
        user = store.user(request)
        if not body.title.strip():
            raise HTTPException(422, '업무 제목을 입력하세요.')
        if body.lot_id and not app.state.repo.lot_trace(body.lot_id):
            raise HTTPException(404, 'LOT를 찾을 수 없습니다.')
        work_id = str(uuid.uuid5(uuid.NAMESPACE_URL, user['id'] + str(body.request_id)))
        with app.state.repo._connect() as c:
            existing = c.execute('SELECT body FROM v2_work WHERE id=?', (work_id,)).fetchone()
            if existing:
                return json.loads(dict(existing)['body'])
            snapshot = None
            if body.answer_id:
                row = c.execute('SELECT body FROM v2_answers WHERE id=? AND user_id=?', (str(body.answer_id), user['id'])).fetchone()
                if not row:
                    raise HTTPException(404, '저장할 답변을 찾을 수 없습니다. 로그인 후 다시 질문하세요.')
                snapshot = json.loads(dict(row)['body'])
                if snapshot['answer'].get('context', {}).get('lot_id') != body.lot_id:
                    raise HTTPException(409, '답변의 LOT와 저장 대상이 다릅니다.')
            now = stamp()
            item = {'id': work_id, 'title': body.title.strip(), 'lot_id': body.lot_id, 'kind': body.kind,
                    'status': '확인 중', 'creator_id': user['id'], 'assignee_id': user['id'], 'version': 1,
                    'created_at': now, 'updated_at': now, 'snapshot': snapshot, 'snapshots': [snapshot] if snapshot else [], 'notes': [], 'events': [], 'handoff': None}
            if body.note.strip():
                item['notes'].append({'text': body.note.strip(), 'author': user['name'], 'at': now})
            item['events'].append({'action': '업무 저장', 'actor': user['name'], 'at': now, 'request_id': str(body.request_id)})
            c.execute('INSERT INTO v2_work VALUES (?, ?, ?, ?) ON CONFLICT(id) DO NOTHING', (work_id, user['organization'], 1, json.dumps(item, ensure_ascii=False)))
            return store.get(work_id, user, c)

    @router.patch('/work-items/{work_id}')
    def change(work_id: str, body: Change, request: Request):
        store = app.state.work
        user = store.user(request)
        with app.state.repo._connect() as c:
            item = store.get(work_id, user, c)
            if any(e['request_id'] == str(body.request_id) for e in item['events']):
                return item
            if item['version'] != body.expected_version:
                raise HTTPException(409, '다른 기기에서 변경됐습니다. 최신 업무를 불러온 뒤 초안을 확인하세요.')
            if user['role'] != 'admin' and user['id'] != item['assignee_id']:
                raise HTTPException(403, '현재 담당자만 이 업무를 변경할 수 있습니다.')
            if body.action == 'complete' and user['role'] not in ('reviewer', 'admin'):
                raise HTTPException(403, '검토 완료는 품질 검토자 권한이 필요합니다.')
            if body.action in ('note', 'handoff', 'complete') and not body.text.strip():
                raise HTTPException(422, '메모 또는 검토 결과를 입력하세요.')
            now = stamp()
            if body.action == 'attach_answer':
                row = c.execute('SELECT body FROM v2_answers WHERE id=? AND user_id=?', (str(body.answer_id), user['id'])).fetchone()
                if not row:
                    raise HTTPException(404, '저장할 답변을 찾을 수 없습니다.')
                snapshot = json.loads(dict(row)['body'])
                if snapshot['answer'].get('context', {}).get('lot_id') != item['lot_id']:
                    raise HTTPException(409, '답변의 LOT와 업무 대상이 다릅니다.')
                item.setdefault('snapshots', [item['snapshot']] if item['snapshot'] else []).append(snapshot)
                item['snapshot'] = snapshot
            elif body.action == 'handoff':
                recipient = c.execute('SELECT id FROM v2_users WHERE id=? AND organization=?', (body.recipient_id, user['organization'])).fetchone()
                if not recipient or body.recipient_id == user['id']:
                    raise HTTPException(422, '같은 조직의 다른 수신자를 선택하세요.')
                item['handoff'] = {'sender_id': user['id'], 'recipient_id': body.recipient_id, 'request': body.text, 'sent_at': now, 'acknowledged_at': None}
                item['assignee_id'] = body.recipient_id
                item['status'] = '인계 대기'
            elif body.action == 'acknowledge':
                if not item['handoff'] or item['status'] != '인계 대기' or item['handoff']['recipient_id'] != user['id']:
                    raise HTTPException(409, '수신 확인할 인계가 없습니다.')
                item['handoff']['acknowledged_at'] = now
                item['status'] = '검토 대기'
            elif body.action == 'complete':
                if item['status'] == '인계 대기':
                    raise HTTPException(409, '인계 수신을 먼저 확인하세요.')
                item['status'] = '검토 완료'
            elif body.action == 'reopen':
                item['status'] = '재확인'
            if body.text.strip():
                item['notes'].append({'text': body.text.strip(), 'author': user['name'], 'at': now})
            labels = {'note': '메모 저장', 'handoff': '인계', 'acknowledge': '수신 확인', 'complete': '검토 완료', 'reopen': '재확인', 'attach_answer': '답변·근거 추가'}
            item['events'].append({'action': labels[body.action], 'actor': user['name'], 'at': now, 'request_id': str(body.request_id)})
            item['version'] += 1
            item['updated_at'] = now
            updated = c.execute('UPDATE v2_work SET body=?, version=? WHERE id=? AND version=? RETURNING id',
                                (json.dumps(item, ensure_ascii=False), item['version'], work_id, body.expected_version)).fetchone()
            if not updated:
                raise HTTPException(409, '업무가 변경됐습니다. 최신 업무를 다시 불러오세요.')
            return item

    app.include_router(router)
