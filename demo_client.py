#!/usr/bin/env python3
"""
Exercises the full Manifold Lite flow against a running server:
  create proposal -> sign -> dispatch -> complete -> invoice -> pay

Usage:
  python3 server.py &         # start the server in one terminal
  python3 demo_client.py       # run this in another

Set BASE_URL to point at a deployed instance instead of localhost:
  BASE_URL=https://manifold-lite.onrender.com python3 demo_client.py
"""

import json
import os
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


def call(method, path, body=None):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def step(label, method, path, body=None):
    status, payload = call(method, path, body)
    print(f"[{status}] {label}")
    print(json.dumps(payload, indent=2))
    print()
    return payload


def main():
    print(f"Running demo flow against {BASE_URL}\n")

    proposal = step(
        "Create proposal", "POST", "/api/proposals",
        {
            "customer_name": "Jordan Park",
            "customer_address": "77 Maple Ave",
            "description": "Install ductless mini-split, 2 zones",
            "amount_cents": 620000,
        },
    )
    proposal_id = proposal["id"]

    order = step("Sign proposal (creates order)", "POST", f"/api/proposals/{proposal_id}/sign")
    order_id = order["id"]

    technicians = step("List technicians", "GET", "/api/technicians")
    tech_id = technicians[0]["id"]

    dispatch = step(
        "Dispatch order to technician", "POST", f"/api/orders/{order_id}/dispatch",
        {"technician_id": tech_id},
    )
    dispatch_id = dispatch["id"]

    step(
        "Complete field work", "POST", f"/api/dispatches/{dispatch_id}/complete",
        {"notes": "Installed both indoor units, tested airflow, customer signed off."},
    )

    invoice = step("Generate invoice", "POST", f"/api/orders/{order_id}/invoice")
    invoice_id = invoice["id"]

    step("Record payment", "POST", f"/api/invoices/{invoice_id}/pay", {"method": "card"})

    final_order = step("Final order state", "GET", f"/api/orders/{order_id}")
    print(f"Flow complete. Final order status: {final_order['status']}")


if __name__ == "__main__":
    main()
