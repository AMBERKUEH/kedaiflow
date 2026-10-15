from pathlib import Path
from sqlalchemy import text
from services.api.db import engine, migrate

if engine.dialect.name == 'sqlite':
    migrate()
    print('Local SQLite schema ready.')
else:
    sql = (Path(__file__).resolve().parents[1] / 'database/migrations/0001_initial.sql').read_text(encoding='utf-8')
    with engine.connect() as connection:
        exists = connection.execute(text("SELECT to_regclass('public.schema_migrations')")).scalar()
        if exists:
            print('Initial PostgreSQL schema already applied.')
        else:
            connection.commit()
            connection.exec_driver_sql(sql)
            connection.commit()
            print('PostgreSQL migration 0001 applied. Apply 0002 separately only on Supabase.')
    # Additive FLOW tables reuse the current database. Existing ledger tables are
    # never altered. SQLAlchemy creates composite tenant evidence constraints.
    flow_sql = (Path(__file__).resolve().parents[1] / 'database/migrations/0003_bijaksense.sql').read_text(encoding='utf-8')
    with engine.begin() as connection:
        connection.exec_driver_sql(flow_sql)
    print('FLOW market intelligence tables ready (FAISS retrieval; SQL numerics).')
