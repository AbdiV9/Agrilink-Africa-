# Owner: Person 1 (Backend & Database Lead)
"""AgriLink Africa database package.

Every query module opens and closes its own SQLite connection per call
(via ``Databases.db.get_connection``) and returns plain dicts or lists of
dicts, never ``sqlite3.Row`` objects.
"""

from Databases.db import DB_FILENAME, get_connection, get_db_path, rows_to_dicts

__all__ = ["DB_FILENAME", "get_connection", "get_db_path", "rows_to_dicts"]
