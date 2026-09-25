"""ERP/IoT Data Hub facade with replaceable SQLite demo storage."""

from __future__ import annotations

import sqlite3
import os
import json
import re
from pathlib import Path
from typing import Any


class ImjingangRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS lots (
                    lot_id TEXT PRIMARY KEY, parent_lot_id TEXT, process TEXT NOT NULL,
                    product_name TEXT NOT NULL, quantity_kg REAL NOT NULL,
                    supplier TEXT, origin TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS process_measurements (
                    measurement_id INTEGER PRIMARY KEY, lot_id TEXT NOT NULL,
                    process TEXT NOT NULL, equipment_id TEXT NOT NULL,
                    salinity REAL, ph REAL, temperature REAL, acidity REAL,
                    weight_kg REAL, equipment_status TEXT NOT NULL, measured_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ccp_checks (
                    check_id INTEGER PRIMARY KEY, lot_id TEXT NOT NULL, ccp_name TEXT NOT NULL,
                    result TEXT NOT NULL, value REAL, unit TEXT, defect_type TEXT,
                    checked_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fermentation_predictions (
                    prediction_id INTEGER PRIMARY KEY, lot_id TEXT NOT NULL,
                    model_name TEXT NOT NULL, predicted_grade TEXT NOT NULL,
                    remaining_hours REAL, abnormal_risk REAL NOT NULL,
                    model_status TEXT NOT NULL, predicted_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    item_code TEXT PRIMARY KEY, item_name TEXT NOT NULL, category TEXT NOT NULL,
                    quantity_kg REAL NOT NULL, safety_stock_kg REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shipments (
                    shipment_id TEXT PRIMARY KEY, lot_id TEXT NOT NULL, customer TEXT NOT NULL,
                    destination TEXT NOT NULL, quantity_kg REAL NOT NULL,
                    approval_status TEXT NOT NULL, shipped_at TEXT
                );
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY, shipment_id TEXT NOT NULL, claim_type TEXT NOT NULL,
                    detail TEXT NOT NULL, received_at TEXT NOT NULL, status TEXT NOT NULL
                );
                """
            )
            if connection.execute("SELECT COUNT(*) FROM lots").fetchone()[0] == 0:
                self._seed(connection)
            self._initialize_knowledge(connection)

    @staticmethod
    def _seed(connection: sqlite3.Connection) -> None:
        connection.executemany(
            "INSERT INTO lots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("RAW-260901-001", None, "원재료 입고", "배추", 11000, "공급처 A", "연천", "사용완료", "2026-09-01 07:20"),
                ("SORT-260901-001", "RAW-260901-001", "선별", "배추", 10500, None, None, "완료", "2026-09-01 09:00"),
                ("SALT-260901-001", "SORT-260901-001", "세척·절임", "절임배추", 10100, None, None, "완료", "2026-09-01 10:30"),
                ("MIX-260902-001", "SALT-260901-001", "양념·혼합", "율무 포기김치", 9900, None, None, "완료", "2026-09-02 08:40"),
                ("FERM-260902-001", "MIX-260902-001", "발효·숙성", "율무 포기김치", 9800, None, None, "숙성중", "2026-09-02 10:10"),
                ("PACK-260903-001", "FERM-260902-001", "포장", "율무 포기김치", 9600, None, None, "출하검토", "2026-09-03 09:00"),
                ("FERM-260903-002", None, "발효·숙성", "율무 총각김치", 4200, None, None, "이상검토", "2026-09-03 07:30"),
                ("RAW-260904-002", None, "원재료 입고", "무", 5200, "공급처 B", "파주", "검사완료", "2026-09-04 06:50"),
                ("SALT-260904-002", "RAW-260904-002", "세척·절임", "절임무", 4900, None, None, "진행중", "2026-09-04 08:20"),
                ("PACK-260904-002", "SALT-260904-002", "포장", "율무 총각김치", 4600, None, None, "대기", "2026-09-04 13:10"),
            ],
        )
        connection.executemany(
            "INSERT INTO process_measurements VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "SALT-260901-001", "세척·절임", "SALTING-01", 2.4, 5.8, 12.2, None, 10100, "정상", "2026-09-01 16:30"),
                (2, "FERM-260902-001", "발효·숙성", "AGING-01", 2.1, 4.35, 4.2, 0.62, 9800, "정상", "2026-09-03 10:20"),
                (3, "PACK-260903-001", "포장", "PACK-01", None, None, 6.1, None, 9600, "정상", "2026-09-03 10:30"),
                (4, "FERM-260903-002", "발효·숙성", "AGING-02", 1.6, 3.72, 8.8, 0.91, 4200, "온도주의", "2026-09-03 10:25"),
            ],
        )
        connection.executemany(
            "INSERT INTO ccp_checks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "MIX-260902-001", "혼합·덤퍼 CCP", "적합", 9900, "kg", None, "2026-09-02 09:50"),
                (2, "PACK-260903-001", "금속검출 CCP", "적합", 0, "NG", None, "2026-09-03 10:40"),
                (3, "FERM-260903-002", "혼합·덤퍼 CCP", "주의", 1, "건", "배합 확인 필요", "2026-09-03 08:20"),
            ],
        )
        connection.executemany(
            "INSERT INTO fermentation_predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "FERM-260902-001", "RF+SVR+XGBoost+LSTM Ensemble", "A 예상", 6.5, 0.12, "시제품 데모", "2026-09-03 10:30"),
                (2, "FERM-260903-002", "RF+SVR+XGBoost+LSTM Ensemble", "C 위험", 14.0, 0.78, "시제품 데모", "2026-09-03 10:30"),
            ],
        )
        connection.executemany(
            "INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("R001", "배추", "원재료", 14500, 10000, "2026-09-03 10:00"),
                ("R002", "율무", "원재료", 720, 800, "2026-09-03 10:00"),
                ("F001", "율무 포기김치", "완제품", 9600, 5000, "2026-09-03 10:30"),
                ("F002", "율무 총각김치", "완제품", 3800, 3000, "2026-09-03 10:30"),
            ],
        )
        connection.executemany(
            "INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("SHP-260903-001", "PACK-260903-001", "울타리몰", "미국", 3200, "승인대기", None),
                ("SHP-260902-004", "PACK-260903-001", "국내 거래처 A", "대한민국", 1800, "승인", "2026-09-03 08:30"),
            ],
        )
        connection.execute(
            "INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?)",
            ("CLM-260903-01", "SHP-260902-004", "숙성 편차", "도착 후 산미 편차 문의", "2026-09-03 09:20", "분석중"),
        )

    def dashboard(self) -> dict[str, Any]:
        with self._connect() as connection:
            output = connection.execute("SELECT COALESCE(SUM(quantity_kg),0) FROM lots WHERE process='포장'").fetchone()[0]
            ccp = connection.execute("SELECT COUNT(*) FROM ccp_checks WHERE result!='적합'").fetchone()[0]
            risk = connection.execute("SELECT COUNT(*) FROM fermentation_predictions WHERE abnormal_risk>=0.5").fetchone()[0]
            shortage = connection.execute("SELECT COUNT(*) FROM inventory WHERE quantity_kg<safety_stock_kg").fetchone()[0]
            pending = connection.execute("SELECT COUNT(*) FROM shipments WHERE approval_status='승인대기'").fetchone()[0]
        return {"packed_kg": output, "current_capacity_kg": 10000, "three_year_target_kg": 30000, "ccp_alerts": ccp, "fermentation_risks": risk, "stock_shortages": shortage, "shipment_pending": pending}

    def all_lots(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return self._rows(connection.execute("SELECT * FROM lots ORDER BY created_at DESC").fetchall())

    def lot_trace(self, lot_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """WITH RECURSIVE lineage AS (
                       SELECT * FROM lots WHERE lot_id=?
                       UNION SELECT l.* FROM lots l JOIN lineage x
                       ON l.lot_id=x.parent_lot_id OR l.parent_lot_id=x.lot_id
                   ) SELECT * FROM lineage ORDER BY created_at""", (lot_id,)
            ).fetchall()
        return self._rows(rows)

    def fermentation_status(self, lot_id: str | None) -> list[dict[str, Any]]:
        query = """SELECT l.lot_id,l.product_name,l.status,m.salinity,m.ph,m.temperature,m.acidity,
                          p.model_name,p.predicted_grade,p.remaining_hours,p.abnormal_risk,p.model_status,p.predicted_at
                   FROM lots l LEFT JOIN process_measurements m ON m.lot_id=l.lot_id
                   LEFT JOIN fermentation_predictions p ON p.lot_id=l.lot_id
                   WHERE l.process='발효·숙성'"""
        params: tuple[Any, ...] = ()
        if lot_id:
            query += " AND l.lot_id=?"
            params = (lot_id,)
        query += " ORDER BY p.abnormal_risk DESC"
        with self._connect() as connection:
            return self._rows(connection.execute(query, params).fetchall())

    def ccp_deviations(self, date: str | None) -> list[dict[str, Any]]:
        query = "SELECT * FROM ccp_checks WHERE result!='적합'"
        params: tuple[Any, ...] = ()
        if date:
            query += " AND checked_at LIKE ?"
            params = (f"{date}%",)
        query += " ORDER BY checked_at DESC"
        with self._connect() as connection:
            return self._rows(connection.execute(query, params).fetchall())

    def inventory_status(self, item: str | None, shortage_only: bool) -> list[dict[str, Any]]:
        query = """SELECT *,CASE WHEN quantity_kg<safety_stock_kg THEN '부족' ELSE '정상' END AS stock_status
                   FROM inventory WHERE 1=1"""
        params: list[Any] = []
        if item:
            query += " AND item_name LIKE ?"
            params.append(f"%{item}%")
        if shortage_only:
            query += " AND quantity_kg<safety_stock_kg"
        query += " ORDER BY stock_status,item_name"
        with self._connect() as connection:
            return self._rows(connection.execute(query, params).fetchall())

    def shipment_readiness(self, lot_id: str | None) -> list[dict[str, Any]]:
        query = "SELECT s.*, l.product_name, l.status AS lot_status FROM shipments s JOIN lots l ON l.lot_id=s.lot_id"
        params = ()
        if lot_id:
            query += " WHERE s.lot_id=?"
            params = (lot_id,)
        records = self._query(query + " ORDER BY s.shipment_id", params)
        for record in records:
            trace = self.lot_trace(record["lot_id"])
            ids = {row["lot_id"] for row in trace}
            predictions = [row for row in self.fermentation_status(None) if row["lot_id"] in ids]
            risks = [row["abnormal_risk"] for row in predictions if row["abnormal_risk"] is not None]
            checks = [row for row in self._query("SELECT * FROM ccp_checks") if row["lot_id"] in ids]
            record["abnormal_risk"] = max(risks) if risks else None
            record["ccp_alerts"] = sum(row["result"] != "적합" for row in checks)
            record["ccp_records"] = len(checks)
            record["evidence_status"] = "샘플 기록 조회·담당자 검토 필요" if checks and risks else "검사 또는 예측 미확인"
        return records

    def claim_trace(self, claim_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            claim = connection.execute(
                """SELECT c.*,s.lot_id,s.customer,s.destination,s.quantity_kg FROM claims c
                   JOIN shipments s ON s.shipment_id=c.shipment_id WHERE c.claim_id=?""", (claim_id,)
            ).fetchone()
        if not claim:
            return {"claim": None, "lot_trace": []}
        record = dict(claim)
        return {"claim": record, "lot_trace": self.lot_trace(record["lot_id"])}

    def process_measurements(self, lot_id: str | None) -> list[dict[str, Any]]:
        query = "SELECT * FROM process_measurements WHERE 1=1"
        params: tuple[Any, ...] = ()
        if lot_id:
            query += " AND lot_id=?"
            params = (lot_id,)
        query += " ORDER BY measured_at DESC"
        with self._connect() as connection:
            return self._rows(connection.execute(query, params).fetchall())



    @staticmethod
    def _initialize_knowledge(connection: sqlite3.Connection) -> None:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                document_id TEXT PRIMARY KEY, filename TEXT, content TEXT,
                source TEXT, status TEXT
            );
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT PRIMARY KEY, name TEXT, source_table TEXT,
                condition TEXT, owner TEXT, action TEXT, source_document TEXT,
                revision TEXT, status TEXT
            );
            CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT);
        """)
        documents = [
            ("IMJ-KB-001", "IMJ-KB-001_공정흐름_LOT.md", "원재료 입고→선별→세척·절임→양념·혼합→발효·숙성→포장→출하 순으로 LOT를 연결한다. 분할·합류 발생 시 원본 LOT와 새 LOT의 관계를 모두 기록한다."),
            ("IMJ-KB-002", "IMJ-KB-002_원재료_입고검사.md", "배추·무·율무 입고 시 공급처, 산지, 중량, 외관, 이물, 검사일시와 판정자를 확인한다. 부적합 원료는 사용 전 격리하고 검토 이력을 남긴다."),
            ("IMJ-KB-003", "IMJ-KB-003_세척_절임.md", "세척·절임 공정은 작업 LOT, 설비, 시작·종료시각, 염도, 온도, 중량을 기록한다. 기준 이탈 시 임의 조정하지 않고 품질담당자에게 보고한다."),
            ("IMJ-KB-004", "IMJ-KB-004_양념_혼합.md", "양념 배합과 혼합 시 투입 원료 LOT, 계량값, 작업자, 설비, 혼합 시간을 확인한다. 승인된 배합표와 다른 경우 후속 공정을 진행하지 않는다."),
            ("IMJ-KB-005", "IMJ-KB-005_발효_숙성.md", "발효·숙성 검토에서는 pH, 산도, 염도, 온도, 측정시각과 장비 상태를 함께 본다. 단일 수치만으로 적합을 확정하지 않고 승인된 품목별 기준서를 확인한다."),
            ("IMJ-KB-006", "IMJ-KB-006_CCP_이탈검토.md", "CCP 주의·이탈 발생 시 LOT, 발생시각, 측정값, 장비상태, 임시조치, 확인자를 기록한다. 격리·폐기·출하 여부는 승인 권한자가 결정한다."),
            ("IMJ-KB-007", "IMJ-KB-007_재고_부족.md", "재고 부족은 현재고, 안전재고, 사용예정량, 입고예정일을 함께 검토한다. 부족량은 안전재고에서 현재고를 뺀 값으로 표시하되 발주는 담당자 승인 후 진행한다."),
            ("IMJ-KB-008", "IMJ-KB-008_포장_출하검토.md", "출하 전 포장 LOT 계보, 금속검출 CCP, 발효 기록, 표시사항, 수량, 고객·목적지와 승인상태를 확인한다. 미확인 기록은 정상으로 간주하지 않는다."),
            ("IMJ-KB-009", "IMJ-KB-009_클레임_역추적.md", "클레임 접수 시 출하번호와 포장 LOT를 기준으로 발효, 혼합, 절임, 원재료 LOT를 역추적한다. 관련 측정값·CCP·출하·보관 기록의 시각을 함께 보존한다."),
            ("IMJ-KB-010", "IMJ-KB-010_데이터품질_예측검증.md", "예측값은 모델명, 버전, 예측시각, 입력 누락, 검증 지표와 함께 해석한다. 예측 정확도 목표를 실적으로 표시하지 않고 품질 판정을 자동 실행하지 않는다."),
        ]
        connection.executemany(
            "INSERT OR IGNORE INTO knowledge_documents (document_id, filename, content, source, status) VALUES (?, ?, ?, '로컬 샘플', '미승인 샘플')",
            documents,
        )

    def knowledge_documents(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM knowledge_documents ORDER BY document_id")

    def search_knowledge(self, query: str) -> list[dict[str, Any]]:
        # Local lexical retrieval: Korean bigrams tolerate particles and spacing.
        words = re.findall(r"[가-힣a-zA-Z0-9]+", query.lower())
        terms = set(words + [word[i:i+2] for word in words for i in range(len(word)-1)])
        terms = {term for term in terms if len(term) >= 2}
        matches = []
        for doc in self.knowledge_documents():
            content = doc["content"] or ""
            searchable = (doc["filename"] + " " + content).lower()
            score = sum(term in searchable for term in terms)
            if score and content:
                matches.append({"filename": doc["filename"], "document_id": doc["document_id"],
                                "text": content, "match_count": score, "source": doc["source"]})
        return sorted(matches, key=lambda item: (-item["match_count"], item["filename"]))[:5]

    def get_rules(self) -> list[dict[str, Any]]:
        return self.table_records("rules")

    def setting(self, key: str) -> str | None:
        rows = self._query("SELECT value FROM app_settings WHERE key=?", (key,))
        return rows[0]["value"] if rows else None

    def save_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO app_settings VALUES (?, ?)", (key, value))

    def save_uploaded_document(self, file_id: str, filename: str, content: str | None) -> None:
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO knowledge_documents VALUES (?, ?, ?, ?, ?)",
                (file_id, filename, content, "업로드 문서", "File Search 인덱싱 완료"))

    @staticmethod
    def _dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return self._dicts(connection.execute(sql, params).fetchall())

    def table_inventory(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            existing = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            return [
                {"table": name, "label": label, "exists": name in existing,
                 "count": connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                 if name in existing else 0}
                for name, label in self.TABLE_LABELS.items()
            ]

    def table_records(self, table: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        if table not in self.TABLE_LABELS:
            raise ValueError("조회할 수 없는 테이블입니다.")
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("조회 범위가 올바르지 않습니다.")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                return []
            # Stable paging uses the table's declared columns; identifiers come from SQLite.
            columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            order = ", ".join('"' + row[1].replace('"', '""') + '"' for row in columns)
            return self._dicts(connection.execute(
                f'SELECT * FROM "{table}" ORDER BY {order} LIMIT ? OFFSET ?', (limit, offset)
            ).fetchall())

    TABLE_LABELS = {"lots":"LOT 계보", "process_measurements":"공정 측정", "ccp_checks":"CCP 검사", "fermentation_predictions":"발효 예측", "inventory":"원료·제품 재고", "shipments":"출하", "claims":"클레임", "rules":"판정 룰"}

class _PostgresRow(dict):
    """Dictionary row with SQLite-compatible integer indexing for shared code."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class _PostgresCursor:
    def __init__(self, cursor: Any) -> None:
        self.cursor = cursor

    def _row(self, row: Any) -> _PostgresRow | None:
        if row is None:
            return None
        names = [column.name for column in self.cursor.description or ()]
        return _PostgresRow(zip(names, row))

    def fetchone(self) -> _PostgresRow | None:
        return self._row(self.cursor.fetchone())

    def fetchall(self) -> list[_PostgresRow]:
        return [self._row(row) for row in self.cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class _PostgresConnection:
    """Small adapter so repository query methods stay backend-independent."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @staticmethod
    def _sql(sql: str) -> str:
        return sql.replace("?", "%s").replace("INSERT OR IGNORE INTO", "INSERT INTO")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _PostgresCursor:
        if "INSERT OR IGNORE INTO" in sql:
            sql = self._sql(sql) + " ON CONFLICT DO NOTHING"
        cursor = self.connection.execute(self._sql(sql), params)
        return _PostgresCursor(cursor)

    def executemany(self, sql: str, params: list[tuple[Any, ...]]) -> None:
        with self.connection.cursor() as cursor:
            cursor.executemany(self._sql(sql), params)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def __enter__(self) -> "_PostgresConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if exc_type:
            self.connection.rollback()
        else:
            self.connection.commit()
        self.connection.close()


class PostgresRepository(ImjingangRepository):
    """PostgreSQL + pgvector Data Hub used when DATABASE_URL is configured."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.db_path = None
        self._initialize()

    def _connect(self, *, register_vector_type: bool = True) -> _PostgresConnection:
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as exc:
            raise RuntimeError("PostgreSQL 사용에는 psycopg[binary] 설치가 필요합니다.") from exc
        raw = psycopg.connect(self.database_url)
        try:
            if register_vector_type:
                register_vector(raw)
        except Exception:
            raw.close()
            raise
        return _PostgresConnection(raw)

    def _initialize(self) -> None:
        # A fresh database has no vector type until this transaction commits.
        with self._connect(register_vector_type=False) as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        super()._initialize()
        with self._connect() as connection:
            connection.execute("ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS embedding vector(1536)")
            connection.execute("ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS embedding_model TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS knowledge_documents_embedding_idx ON knowledge_documents USING hnsw (embedding vector_cosine_ops)")

    def table_inventory(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [
                {"table": name, "label": label,
                 "exists": bool(connection.execute(
                     "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=?", (name,)
                 ).fetchone()),
                 "count": connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                 if connection.execute(
                     "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=?", (name,)
                 ).fetchone() else 0}
                for name, label in self.TABLE_LABELS.items()
            ]

    def table_records(self, table: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        if table not in self.TABLE_LABELS:
            raise ValueError("조회할 수 없는 테이블입니다.")
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("조회 범위가 올바르지 않습니다.")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=?", (table,)
            ).fetchone()
            if not exists:
                return []
            columns = connection.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=? ORDER BY ordinal_position",
                (table,),
            ).fetchall()
            order = ", ".join('"' + row[0].replace('"', '""') + '"' for row in columns)
            return [dict(row) for row in connection.execute(
                f'SELECT * FROM "{table}" ORDER BY {order} LIMIT ? OFFSET ?', (limit, offset)
            ).fetchall()]

    def save_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (key, value))

    def save_uploaded_document(self, file_id: str, filename: str, content: str | None, embedding: list[float] | None = None, embedding_model: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute("""INSERT INTO knowledge_documents (document_id, filename, content, source, status, embedding, embedding_model)
                VALUES (?, ?, ?, '업로드 문서', '인덱싱 완료', ?, ?)
                ON CONFLICT (document_id) DO UPDATE SET filename=EXCLUDED.filename, content=EXCLUDED.content,
                status=EXCLUDED.status, embedding=EXCLUDED.embedding, embedding_model=EXCLUDED.embedding_model""",
                (file_id, filename, content, embedding, embedding_model))

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> int:
        if table not in self.TABLE_LABELS or table == "knowledge_documents":
            raise ValueError("마이그레이션할 수 없는 테이블입니다.")
        if not rows:
            return 0
        columns = list(rows[0])
        names = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("%s" for _ in columns)
        sql = f'INSERT INTO "{table}" ({names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
        with self._connect() as connection:
            connection.executemany(sql, [tuple(row[column] for column in columns) for row in rows])
        return len(rows)

    def insert_knowledge_rows(self, rows: list[dict[str, Any]]) -> int:
        """Insert migrated documents while preserving IDs and optional vectors."""
        if not rows:
            return 0
        sql = """INSERT INTO knowledge_documents
            (document_id, filename, content, source, status, embedding, embedding_model)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_id) DO UPDATE SET filename=EXCLUDED.filename,
              content=EXCLUDED.content, source=EXCLUDED.source, status=EXCLUDED.status,
              embedding=COALESCE(EXCLUDED.embedding, knowledge_documents.embedding),
              embedding_model=COALESCE(EXCLUDED.embedding_model, knowledge_documents.embedding_model)"""
        with self._connect() as connection:
            connection.executemany(sql, [(
                row.get("document_id"), row.get("filename"), row.get("content"),
                row.get("source"), row.get("status"), row.get("embedding"), row.get("embedding_model"),
            ) for row in rows])
        return len(rows)

    def reset_data_for_migration(self) -> None:
        """Clear demo/previous rows before a full SQLite replacement import."""
        tables = [*self.TABLE_LABELS.keys(), "knowledge_documents", "app_settings"]
        with self._connect() as connection:
            connection.execute("TRUNCATE TABLE " + ", ".join(f'\"{table}\"' for table in tables) + " CASCADE")

    def vector_search_knowledge(self, embedding: list[float], limit: int = 5) -> list[dict[str, Any]]:
        """Nearest-neighbor retrieval for callers that provide a 1536-d embedding."""
        if not 1 <= limit <= 50:
            raise ValueError("조회 범위가 올바르지 않습니다.")
        with self._connect() as connection:
            return [dict(row) for row in connection.execute("""
                SELECT document_id, filename, content, source, status,
                       embedding <=> ?::vector AS distance
                FROM knowledge_documents
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> ?::vector
                LIMIT ?
            """, (embedding, embedding, limit)).fetchall()]


def create_repository(sqlite_path: str | Path) -> ImjingangRepository:
    """Use PostgreSQL in configured environments and retain SQLite for offline tests."""
    database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    return PostgresRepository(database_url) if database_url else ImjingangRepository(sqlite_path)
