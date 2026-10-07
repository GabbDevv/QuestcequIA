import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DATABASE_PATH = Path(__file__).resolve().with_name("questcequia.db")


@contextmanager
def get_connection(
	database_path: Path = DATABASE_PATH,
) -> Iterator[sqlite3.Connection]:
	connection = sqlite3.connect(database_path)
	connection.row_factory = sqlite3.Row
	try:
		yield connection
		connection.commit()
	except Exception:
		connection.rollback()
		raise
	finally:
		connection.close()


def initialize_database(database_path: Path = DATABASE_PATH) -> None:
	with get_connection(database_path) as connection:
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS responses (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				question TEXT NOT NULL,
				answer TEXT NOT NULL,
				created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
			)
			"""
		)


if __name__ == "__main__":
	initialize_database()
	print(f"Base de données initialisée : {DATABASE_PATH}")
