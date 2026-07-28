#!/usr/bin/env python3
"""
Manifold Lite backend.
Stdlib only: http.server + sqlite3. No external dependencies.

Flow implemented:
  proposal (draft) -> sign -> order (open) -> dispatch (scheduled)
  -> field completion (dispatch completed, order completed)
  -> invoice (unpaid) -> payment (paid)

Run locally:
  python3 server.py

Deploy (e.g. Render):
  Reads PORT from environment, binds 0.0.0.0.
"""

import json
import os
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DB_PATH = os.environ.get("MANIFOLD_DB_PATH", os.path.join(os.path.dirname(__file__), "manifold.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")
PORT = int(os.environ.get("PORT", 8000))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist yet. Safe to call on every boot."""
    conn = get_conn()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()} if row else None


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]


# ---- Route table: (method, regex) -> handler name ----
ROUTES = []


def route(method, pattern):
    compiled = re.compile(pattern)

    def deco(fn):
        ROUTES.append((method, compiled, fn))
        return fn

    return deco


# ---------- Proposals ----------

@route("POST", r"^/api/proposals$")
def create_proposal(handler, match, body):
    required = ["customer_name", "customer_address", "description", "amount_cents"]
    missing = [f for f in required if f not in body]
    if missing:
        return 400, {"error": f"missing fields: {missing}"}
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO proposals (customer_name, customer_address, description, amount_cents, status) "
        "VALUES (?, ?, ?, ?, 'draft')",
        (body["customer_name"], body["customer_address"], body["description"], body["amount_cents"]),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM proposals WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return 201, row_to_dict(row)


@route("GET", r"^/api/proposals$")
def list_proposals(handler, match, body):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM proposals ORDER BY id DESC").fetchall()
    conn.close()
    return 200, rows_to_list(rows)


@route("GET", r"^/api/proposals/(?P<id>\d+)$")
def get_proposal(handler, match, body):
    conn = get_conn()
    row = conn.execute("SELECT * FROM proposals WHERE id = ?", (match.group("id"),)).fetchone()
    conn.close()
    if not row:
        return 404, {"error": "proposal not found"}
    return 200, row_to_dict(row)


@route("POST", r"^/api/proposals/(?P<id>\d+)/sign$")
def sign_proposal(handler, match, body):
    pid = match.group("id")
    conn = get_conn()
    proposal = conn.execute("SELECT * FROM proposals WHERE id = ?", (pid,)).fetchone()
    if not proposal:
        conn.close()
        return 404, {"error": "proposal not found"}
    if proposal["status"] == "signed":
        conn.close()
        return 400, {"error": "proposal already signed"}
    conn.execute(
        "UPDATE proposals SET status = 'signed', signed_at = datetime('now') WHERE id = ?", (pid,)
    )
    cur = conn.execute("INSERT INTO orders (proposal_id, status) VALUES (?, 'open')", (pid,))
    conn.commit()
    order_id = cur.lastrowid
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return 201, row_to_dict(order)


# ---------- Technicians ----------

@route("POST", r"^/api/technicians$")
def create_technician(handler, match, body):
    if "name" not in body:
        return 400, {"error": "missing field: name"}
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO technicians (name, phone) VALUES (?, ?)", (body["name"], body.get("phone"))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM technicians WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return 201, row_to_dict(row)


@route("GET", r"^/api/technicians$")
def list_technicians(handler, match, body):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM technicians ORDER BY id").fetchall()
    conn.close()
    return 200, rows_to_list(rows)


# ---------- Orders ----------

@route("GET", r"^/api/orders$")
def list_orders(handler, match, body):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    conn.close()
    return 200, rows_to_list(rows)


@route("GET", r"^/api/orders/(?P<id>\d+)$")
def get_order(handler, match, body):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (match.group("id"),)).fetchone()
    conn.close()
    if not row:
        return 404, {"error": "order not found"}
    return 200, row_to_dict(row)


@route("POST", r"^/api/orders/(?P<id>\d+)/dispatch$")
def dispatch_order(handler, match, body):
    order_id = match.group("id")
    if "technician_id" not in body:
        return 400, {"error": "missing field: technician_id"}
    conn = get_conn()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return 404, {"error": "order not found"}
    tech = conn.execute("SELECT * FROM technicians WHERE id = ?", (body["technician_id"],)).fetchone()
    if not tech:
        conn.close()
        return 404, {"error": "technician not found"}
    cur = conn.execute(
        "INSERT INTO dispatches (order_id, technician_id, status) VALUES (?, ?, 'scheduled')",
        (order_id, body["technician_id"]),
    )
    conn.execute("UPDATE orders SET status = 'dispatched' WHERE id = ?", (order_id,))
    conn.commit()
    dispatch_id = cur.lastrowid
    row = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    conn.close()
    return 201, row_to_dict(row)


# ---------- Dispatches ----------

@route("GET", r"^/api/dispatches$")
def list_dispatches(handler, match, body):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM dispatches ORDER BY id DESC").fetchall()
    conn.close()
    return 200, rows_to_list(rows)


@route("POST", r"^/api/dispatches/(?P<id>\d+)/complete$")
def complete_dispatch(handler, match, body):
    dispatch_id = match.group("id")
    conn = get_conn()
    dispatch = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not dispatch:
        conn.close()
        return 404, {"error": "dispatch not found"}
    conn.execute(
        "UPDATE dispatches SET status = 'completed', completed_at = datetime('now'), notes = ? WHERE id = ?",
        (body.get("notes", ""), dispatch_id),
    )
    conn.execute(
        "UPDATE orders SET status = 'completed' WHERE id = ?", (dispatch["order_id"],)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    conn.close()
    return 200, row_to_dict(row)


# ---------- Invoices ----------

@route("POST", r"^/api/orders/(?P<id>\d+)/invoice$")
def create_invoice(handler, match, body):
    order_id = match.group("id")
    conn = get_conn()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return 404, {"error": "order not found"}
    if order["status"] != "completed":
        conn.close()
        return 400, {"error": "order must be completed before invoicing"}
    proposal = conn.execute("SELECT * FROM proposals WHERE id = ?", (order["proposal_id"],)).fetchone()
    cur = conn.execute(
        "INSERT INTO invoices (order_id, amount_cents, status) VALUES (?, ?, 'unpaid')",
        (order_id, proposal["amount_cents"]),
    )
    conn.execute("UPDATE orders SET status = 'invoiced' WHERE id = ?", (order_id,))
    conn.commit()
    invoice_id = cur.lastrowid
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    conn.close()
    return 201, row_to_dict(row)


@route("GET", r"^/api/invoices$")
def list_invoices(handler, match, body):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
    conn.close()
    return 200, rows_to_list(rows)


@route("GET", r"^/api/invoices/(?P<id>\d+)$")
def get_invoice(handler, match, body):
    conn = get_conn()
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (match.group("id"),)).fetchone()
    conn.close()
    if not row:
        return 404, {"error": "invoice not found"}
    return 200, row_to_dict(row)


# ---------- Payments ----------

@route("POST", r"^/api/invoices/(?P<id>\d+)/pay$")
def pay_invoice(handler, match, body):
    invoice_id = match.group("id")
    conn = get_conn()
    invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not invoice:
        conn.close()
        return 404, {"error": "invoice not found"}
    if invoice["status"] == "paid":
        conn.close()
        return 400, {"error": "invoice already paid"}
    amount = body.get("amount_cents", invoice["amount_cents"])
    method = body.get("method", "card")
    cur = conn.execute(
        "INSERT INTO payments (invoice_id, amount_cents, method) VALUES (?, ?, ?)",
        (invoice_id, amount, method),
    )
    conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (invoice_id,))
    conn.execute(
        "UPDATE orders SET status = 'paid' WHERE id = (SELECT order_id FROM invoices WHERE id = ?)",
        (invoice_id,),
    )
    conn.commit()
    payment_id = cur.lastrowid
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    conn.close()
    return 201, row_to_dict(row)


# ---------- Health check ----------

@route("GET", r"^/api/health$")
def health(handler, match, body):
    return 200, {"status": "ok"}


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _dispatch(self, method):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw_body = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON body"})
            return

        for route_method, pattern, fn in ROUTES:
            if route_method != method:
                continue
            m = pattern.match(path)
            if m:
                try:
                    status, payload = fn(self, m, body)
                except Exception as e:
                    self._send_json(500, {"error": str(e)})
                    return
                self._send_json(status, payload)
                return

        self._send_json(404, {"error": "no such route", "path": path, "method": method})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def log_message(self, fmt, *args):
        # Quieter default logging; keep method + path + status
        print(f"{self.address_string()} - {fmt % args}")


def main():
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Manifold Lite listening on 0.0.0.0:{PORT} (db: {DB_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
