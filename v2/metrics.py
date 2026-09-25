"""Journey events for the pilot. Stores event names and timings only, never raw text or audio."""
from __future__ import annotations

import statistics
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from v2.work import stamp

EVENTS = ('task_opened', 'voice_started', 'voice_cancelled', 'transcript_ready', 'transcript_edited',
          'question_submitted', 'answer_ready', 'evidence_opened', 'task_saved', 'handoff_sent',
          'handoff_acknowledged', 'task_resumed', 'review_completed')

# Initial product targets from the v2.0 plan, not measured results.
TARGETS = {
    'first_task_open_median_s': 15,
    'voice_completion_rate': 0.9,
    'transcript_p95_s': 8,
    'answer_p95_s': 15,
    'journey_completion_rate': 0.85,
}


class Event(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event: Literal[EVENTS]
    journey_id: uuid.UUID
    device: Literal['mobile', 'desktop']
    source: Literal['voice', 'text', 'suggestion'] | None = None
    mode: Literal['demo', 'ai'] | None = None
    duration_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class Batch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    events: list[Event] = Field(min_length=1, max_length=20)


def percentile(values, share):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, max(0, round(share * len(ordered) + 0.5) - 1))], 2)


def summarize(rows):
    report = {}
    for device in ('mobile', 'desktop'):
        events = [r for r in rows if r['device'] == device]
        count = lambda name, **kw: sum(1 for r in events if r['event'] == name and all(r[k] == v for k, v in kw.items()))
        seconds = lambda name, **kw: [r['duration_ms'] / 1000 for r in events if r['event'] == name and r['duration_ms'] is not None and all(r[k] == v for k, v in kw.items())]
        journeys = {r['journey_id'] for r in events}
        saved = {r['journey_id'] for r in events if r['event'] == 'task_saved'}
        started, cancelled = count('voice_started'), count('voice_cancelled')
        opened = seconds('task_opened')
        report[device] = {
            'journeys': len(journeys),
            'events': {name: count(name) for name in EVENTS},
            'first_task_open_median_s': round(statistics.median(opened), 1) if opened else None,
            # Intentional cancels are counted separately, as the plan requires.
            'voice_completion_rate': round(count('question_submitted', source='voice') / (started - cancelled), 3) if started > cancelled else None,
            'transcript_p95_s': percentile(seconds('transcript_ready'), 0.95),
            'answer_p95_s': {mode: percentile(seconds('answer_ready', mode=mode), 0.95) for mode in ('demo', 'ai')},
            # Saved on this device and resumed or reviewed on any device.
            'journey_completion_rate': round(len(saved & {r['journey_id'] for r in rows if r['event'] in ('task_resumed', 'review_completed')}) / len(saved), 3) if saved else None,
        }
    return report


def install_metrics(app):
    router = APIRouter(prefix='/api')

    @router.post('/events', status_code=204)
    def record(body: Batch, request: Request):
        user = app.state.work.user(request, False)
        now = stamp()
        with app.state.repo._connect() as c:
            c.executemany('INSERT INTO v2_journey_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', [
                (str(uuid.uuid4()), e.event, str(e.journey_id), e.device, e.source, e.mode, e.duration_ms,
                 user['role'] if user else None, now) for e in body.events])
        return Response(status_code=204)

    @router.get('/metrics')
    def metrics(request: Request):
        user = app.state.work.user(request)
        if user['role'] != 'admin':
            raise HTTPException(403, '파일럿 지표는 관리자만 볼 수 있습니다.')
        with app.state.repo._connect() as c:
            rows = [dict(r) for r in c.execute('SELECT * FROM v2_journey_events').fetchall()]
        return {'targets': TARGETS, 'devices': summarize(rows), 'generated_at': stamp(),
                'note': '목표는 초기 제품 목표이며 실적이 아닙니다. 파일럿 전 현행 흐름의 기준값을 별도로 측정하세요.'}

    app.include_router(router)


def create_tables(repo):
    with repo._connect() as c:
        c.executescript('''
            CREATE TABLE IF NOT EXISTS v2_journey_events (
                id TEXT PRIMARY KEY, event TEXT NOT NULL, journey_id TEXT NOT NULL, device TEXT NOT NULL,
                source TEXT, mode TEXT, duration_ms INTEGER, role TEXT, created_at TEXT NOT NULL);
        ''')
