from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Store

STORES = [
    ("ST01", "Sri Lakshmi Stores", "Coimbatore"),
    ("ST02", "Annai Mart", "Salem"),
    ("ST03", "Kaveri Fresh", "Chennai"),
    ("ST04", "Vaigai Bazaar", "Madurai"),
    ("ST05", "Palar Mart", "Vellore"),
    ("ST06", "Siruvani Stores", "Tiruppur"),
]


def seed_stores() -> None:
    with SessionLocal() as session:
        for code, name, city in STORES:
            stmt = (
                insert(Store)
                .values(code=code, name=name, city=city)
                .on_conflict_do_nothing(index_elements=["code"])
            )
            session.execute(stmt)
        session.commit()


if __name__ == "__main__":
    seed_stores()
    print(f"Seeded {len(STORES)} stores")
