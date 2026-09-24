"""Build read-only Chinook from the vendored, checksummed SQL snapshot.

Run with: python -m scripts.build_database
Test fixtures also call build_database() with an isolated destination path.
"""

# --- Imports -----------------------------------------------------------------

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

# --- Source files and default output -----------------------------------------

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "Chinook_Sqlite.sql"
MANIFEST = ROOT / "data" / "source.json"
DATABASE = ROOT / "data" / "chinook.sqlite"


# --- Build and verify before publishing the read-only file --------------------


def build_database(destination: Path = DATABASE) -> Path:
    """Build, validate and publish the pinned database at a new destination path.

    Verify the SQL checksum before execution, then check SQLite integrity and
    foreign keys in a temporary sibling file. Publish with a no-overwrite hard
    link and read-only permissions; always remove the temporary name. Return the
    destination Path. Existing targets raise FileExistsError, failed checks raise
    ValueError, and filesystem/SQLite errors propagate without replacing a target.
    """
    source = SOURCE.read_bytes()
    expected = json.loads(MANIFEST.read_text())["sha256"]
    if hashlib.sha256(source).hexdigest() != expected:
        raise ValueError("Chinook source checksum mismatch; inspect the source before rebuilding")
    if destination.exists():
        raise FileExistsError(f"Database already exists: {destination}; choose a new output path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".sqlite")
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.executescript(source.decode("utf-8-sig"))
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Chinook integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Chinook foreign key check failed")
            connection.commit()
        finally:
            connection.close()
        temporary.chmod(0o444)
        # Link without overwriting even if another process created the destination.
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


# --- Command-line entry point ------------------------------------------------

if __name__ == "__main__":
    if DATABASE.exists():
        print(f"Already exists (left unchanged): {DATABASE}")
    else:
        print(f"Built read-only database: {build_database()}")
