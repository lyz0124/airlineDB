import pymysql
from contextlib import contextmanager


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "air_reservation",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}


def get_conn():
    return pymysql.connect(**DB_CONFIG)


@contextmanager
def with_db():
    """Context manager that ensures the connection is always closed."""
    conn = None
    try:
        conn = get_conn()
        yield conn
    finally:
        if conn:
            conn.close()


@contextmanager
def with_cursor():
    """Context manager that provides a cursor and ensures the connection is always closed."""
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            yield cur
    finally:
        if conn:
            conn.close()
