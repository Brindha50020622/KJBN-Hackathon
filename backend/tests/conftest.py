import os

# Must run before any app import, so tests never touch the real database.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/sales_test"
)
os.environ["ENABLE_TEST_CLOCK"] = "true"
os.environ["MAX_UPLOAD_MB"] = "20"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402


@pytest.fixture(scope="session")
def _schema():
    import app.models  # noqa: F401
    from app.db import Base, engine

    assert engine.url.database.endswith("_test"), "tests must use a *_test database"
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture
def db(_schema):
    from app.db import SessionLocal
    from app.seed import seed_stores

    with SessionLocal.begin() as session:
        session.execute(
            text(
                "TRUNCATE transactions, import_errors, import_batches, "
                "product_aliases, products, stores RESTART IDENTITY CASCADE"
            )
        )
    seed_stores()


@pytest.fixture
def client(db):
    from app.main import app

    return TestClient(app)
