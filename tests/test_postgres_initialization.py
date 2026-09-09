"""Fresh-database regression test; requires a local PostgreSQL admin URL."""

import os
import uuid

import pytest

from imjingang_agent.data_hub import PostgresRepository


def test_initializes_fresh_database_and_can_reopen(tmp_path):
    admin_url = os.environ.get("TEST_POSTGRES_ADMIN_URL")
    if not admin_url:
        pytest.skip("Set TEST_POSTGRES_ADMIN_URL to test with PostgreSQL + pgvector")

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    database = "imj_test_" + uuid.uuid4().hex
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            url = make_conninfo(admin_url, dbname=database)
            with psycopg.connect(url) as raw:
                assert raw.execute("SELECT to_regtype('vector')").fetchone()[0] is None

            repo = PostgresRepository(url)
            assert repo.dashboard()["packed_kg"] == 9600
            with repo._connect() as connection:
                assert connection.execute("SELECT '[1,2,3]'::vector").fetchone()[0].tolist() == [1, 2, 3]
                assert connection.execute(
                    "SELECT to_regclass('knowledge_documents_embedding_idx')"
                ).fetchone()[0] is not None
            assert len(repo.lot_trace("PACK-260903-001")) == 6
            assert repo.shipment_readiness(None)
            assert len(repo.knowledge_documents()) == 10
            from imjingang_agent import ImjingangRepository
            from scripts.migrate_sqlite_to_postgres import migrate
            source = tmp_path / "source.db"
            local = ImjingangRepository(source)
            local.save_setting("migrated", "yes")
            migrate(source, url)
            first = repo.table_inventory()
            migrate(source, url)
            assert repo.table_inventory() == first
            assert repo.setting("migrated") == "yes"
            vector = [1.0] + [0.0] * 1535
            repo.save_uploaded_document("vector-test", "test.txt", "발효 테스트", vector, "test")
            assert repo.vector_search_knowledge(vector)[0]["document_id"] == "vector-test"
            repo.save_setting("initialization_test", "preserved")
            assert PostgresRepository(url).setting("initialization_test") == "preserved"
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
