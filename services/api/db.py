from contextlib import contextmanager
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from .config import settings
from .models import Base, Business


def make_engine(url):
    engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 30} if url.startswith('sqlite') else {}, pool_pre_ping=True)
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def pragmas(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('PRAGMA busy_timeout=30000')
    return engine


engine = make_engine(settings.database_url)
Session = sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory=Session, business_id=None):
    with factory() as db:
        try:
            if db.bind.dialect.name == 'sqlite':
                db.execute(text('BEGIN IMMEDIATE'))
            elif business_id:
                # Serializes all business financial mutations and approval checks.
                db.execute(select(Business).where(Business.id == business_id).with_for_update())
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def migrate():
    Base.metadata.create_all(engine)
