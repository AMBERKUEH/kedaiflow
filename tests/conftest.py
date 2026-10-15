import pytest
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from services.api import db, main, worker, telegram
from services.api.models import Base


@pytest.fixture
def env(tmp_path, monkeypatch):
    # Tests must never use real provider keys from the operator's private .env.
    monkeypatch.setattr(main.settings, 'groq_key', '')
    monkeypatch.setattr(main.settings, 'elevenlabs_key', '')
    engine = db.make_engine('sqlite:///' + str(tmp_path / 'test.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(db, 'Session', factory)
    def tx(business_id=None):
        return db.transaction(factory=factory, business_id=business_id)
    for module in (main, worker, telegram):
        monkeypatch.setattr(module, 'Session', factory)
        monkeypatch.setattr(module, 'transaction', tx)
    monkeypatch.setattr(main.settings, 'media', tmp_path / 'media')
    main.auth_attempts.clear()
    with TestClient(main.app) as client:
        yield client, factory, tx
    engine.dispose()


@pytest.fixture
def client(env):
    return env[0]
