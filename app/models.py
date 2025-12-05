import csv
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

RECEIPT_FIELDS = [
    "id",
    "date",
    "vendor",
    "total_amount",
    "tax_amount",
    "currency",
    "payment_method",
    "category",
    "notes",
    "image_path",
    "raw_text",
    "created_at",
    "updated_at",
]


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS receipts (
    id TEXT PRIMARY KEY,
    date TEXT,
    vendor TEXT,
    total_amount REAL,
    tax_amount REAL,
    currency TEXT,
    payment_method TEXT,
    category TEXT,
    notes TEXT,
    image_path TEXT,
    raw_text TEXT,
    created_at TEXT,
    updated_at TEXT
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = get_connection(db_path)
    with conn:
        conn.executescript(SCHEMA_SQL)
    conn.close()


def ensure_csv_synced(db_path: str, csv_path: str) -> None:
    if not os.path.exists(csv_path):
        export_to_csv(db_path, csv_path)


def export_to_csv(db_path: str, csv_path: str) -> None:
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM receipts ORDER BY created_at DESC").fetchall()
    conn.close()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RECEIPT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def import_from_csv(db_path: str, csv_path: str) -> None:
    if not os.path.exists(csv_path):
        return
    conn = get_connection(db_path)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with conn:
            for row in reader:
                placeholders = ",".join([":" + key for key in RECEIPT_FIELDS])
                conn.execute(
                    f"INSERT OR REPLACE INTO receipts ({','.join(RECEIPT_FIELDS)}) VALUES ({placeholders})",
                    row,
                )
    conn.close()


def list_receipts(
    db_path: str,
    search: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
) -> Tuple[List[sqlite3.Row], int]:
    conn = get_connection(db_path)
    query = "SELECT * FROM receipts"
    clauses = []
    params = []
    if search:
        clauses.append("(vendor LIKE ? OR raw_text LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if category:
        clauses.append("category = ?")
        params.append(category)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY date DESC"
    total = conn.execute(
        query.replace("SELECT *", "SELECT COUNT(*)"), params
    ).fetchone()[0]
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows, total


def get_receipt(db_path: str, receipt_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
    conn.close()
    return row


def insert_receipt(db_path: str, data: Dict[str, str]) -> None:
    conn = get_connection(db_path)
    with conn:
        placeholders = ",".join([":" + key for key in RECEIPT_FIELDS])
        conn.execute(
            f"INSERT OR REPLACE INTO receipts ({','.join(RECEIPT_FIELDS)}) VALUES ({placeholders})",
            data,
        )
    conn.close()


def update_receipt(db_path: str, receipt_id: str, updates: Dict[str, str]) -> None:
    conn = get_connection(db_path)
    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    updates["id"] = receipt_id
    with conn:
        conn.execute(f"UPDATE receipts SET {set_clause} WHERE id = :id", updates)
    conn.close()


def stats(db_path: str) -> Dict[str, float]:
    conn = get_connection(db_path)
    total_receipts = conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
    total_spent = conn.execute("SELECT SUM(total_amount) FROM receipts").fetchone()[0] or 0
    recent = conn.execute(
        "SELECT * FROM receipts ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return {"count": total_receipts, "spent": total_spent, "recent": recent}


def delete_receipt(db_path: str, receipt_id: str) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
    conn.close()


def timestamp_now() -> str:
    return datetime.utcnow().isoformat()
