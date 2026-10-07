import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DATABASE_PATH = Path(__file__).resolve().with_name("questcequia.db")


def create_user(
	email: str,
	full_name: str,
	database_path: Path = DATABASE_PATH,
) -> int:
	with get_connection(database_path) as connection:
		cursor = connection.execute(
			"INSERT INTO users (email, full_name) VALUES (?, ?)",
			(email, full_name),
		)
		return cursor.lastrowid


@contextmanager
def get_connection(
	database_path: Path = DATABASE_PATH,
) -> Iterator[sqlite3.Connection]:
	connection = sqlite3.connect(database_path)
	connection.row_factory = sqlite3.Row
	connection.execute("PRAGMA foreign_keys = ON")
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
		response_columns = {
			row["name"]
			for row in connection.execute("PRAGMA table_info(responses)")
		}
		if response_columns and not {"user_id", "project_id"}.issubset(response_columns):
			legacy_table_exists = connection.execute(
				"SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'legacy_responses'"
			).fetchone()
			if legacy_table_exists:
				raise RuntimeError(
					"Cannot migrate responses: legacy_responses already exists."
				)
			connection.execute("ALTER TABLE responses RENAME TO legacy_responses")

		connection.executescript(
			"""
			CREATE TABLE IF NOT EXISTS users (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				email TEXT NOT NULL UNIQUE,
				full_name TEXT NOT NULL
			);

			CREATE TABLE IF NOT EXISTS question_sets (
				id INTEGER PRIMARY KEY AUTOINCREMENT
			);

			CREATE TABLE IF NOT EXISTS questions (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				question_set_id INTEGER NOT NULL,
				statement TEXT NOT NULL,
				possible_answers TEXT NOT NULL,
				FOREIGN KEY (question_set_id) REFERENCES question_sets(id)
			);

			CREATE TABLE IF NOT EXISTS projects (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
				description TEXT NOT NULL,
				question_set_id INTEGER NOT NULL,
				FOREIGN KEY (question_set_id) REFERENCES question_sets(id)
			);

			CREATE TABLE IF NOT EXISTS user_projects (
				user_id INTEGER NOT NULL,
				project_id INTEGER NOT NULL,
				PRIMARY KEY (user_id, project_id),
				FOREIGN KEY (user_id) REFERENCES users(id),
				FOREIGN KEY (project_id) REFERENCES projects(id)
			);

			CREATE TABLE IF NOT EXISTS responses (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER NOT NULL,
				project_id INTEGER NOT NULL,
				FOREIGN KEY (user_id, project_id)
					REFERENCES user_projects(user_id, project_id)
			)
			"""
		)


if __name__ == "__main__":
	#initialize_database()
	print(f"Base de données initialisée : {DATABASE_PATH}")
	create_user("john.doe@example.com", "John Doe", DATABASE_PATH)
