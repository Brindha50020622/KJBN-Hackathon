from app.config import Settings


def test_plain_postgres_urls_get_the_psycopg_driver():
    assert (
        Settings(database_url="postgres://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
    )
    assert (
        Settings(database_url="postgresql://u:p@h/db").database_url
        == "postgresql+psycopg://u:p@h/db"
    )


def test_url_with_driver_is_unchanged():
    url = "postgresql+psycopg://u:p@h/db"
    assert Settings(database_url=url).database_url == url
