#!/usr/bin/env python3
"""
Seed the Manifold Lite database with sample data.
Safe to re-run: creates tables if missing, then inserts sample rows
only if the proposals table is currently empty.

Run: python3 seed.py
"""

import os
import sqlite3

DB_PATH = os.environ.get("MANIFOLD_DB_PATH", os.path.join(os.path.dirname(__file__), "manifold.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def main():
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())

    count = conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
    if count > 0:
        print(f"Database already has {count} proposal(s) — skipping seed.")
        conn.close()
        return

    conn.execute(
        "INSERT INTO technicians (name, phone) VALUES (?, ?)", ("Dana Ruiz", "555-0101")
    )
    conn.execute(
        "INSERT INTO technicians (name, phone) VALUES (?, ?)", ("Marcus Lee", "555-0102")
    )

    conn.execute(
        "INSERT INTO proposals (customer_name, customer_address, description, amount_cents, status) "
        "VALUES (?, ?, ?, ?, 'draft')",
        ("Alicia Grant", "142 Birchwood Ln", "Replace condenser unit, 3-ton, R410A", 425000),
    )
    conn.execute(
        "INSERT INTO proposals (customer_name, customer_address, description, amount_cents, status) "
        "VALUES (?, ?, ?, ?, 'draft')",
        ("Tom Whitfield", "88 Sequoia Ct", "Annual furnace maintenance + filter replacement", 18500),
    )

    conn.commit()
    conn.close()
    print("Seeded 2 technicians and 2 sample proposals.")


if __name__ == "__main__":
    main()
