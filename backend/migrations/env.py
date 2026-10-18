from alembic import context
from sqlalchemy import create_engine

import app.models  # noqa: F401
from app.config import settings
from app.db import Base

target_metadata = Base.metadata

engine = create_engine(settings.database_url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()