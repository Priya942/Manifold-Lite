# Manifold Lite

A real (not simulated) backend for the Manifold HVAC demo flow:
**proposal → sign → order → dispatch → field completion → invoice → payment**

Stdlib-only Python: `http.server` + `sqlite3`. No external dependencies,
no framework, nothing to `pip install`.

## Files

- `schema.sql` — table definitions
- `server.py` — the HTTP API server (also serves `demo.html` at `/`)
- `seed.py` — creates the DB and inserts sample technicians + proposals
- `demo_client.py` — script that walks the full flow end-to-end against a running server
- `demo.html` — browser-based live demo UI; walks proposal → sign → dispatch → complete → invoice → pay against the real API
- `README.md` — this file

## Run it locally

```bash
python3 seed.py        # creates manifold.db with sample data
python3 server.py       # starts the server on http://localhost:8000
```

In another terminal:

```bash
python3 demo_client.py  # runs the full flow and prints each step's response
```

## API summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/proposals` | Create a proposal |
| GET | `/api/proposals` | List proposals |
| GET | `/api/proposals/{id}` | Get one proposal |
| POST | `/api/proposals/{id}/sign` | Sign proposal → creates an order |
| POST | `/api/technicians` | Create a technician |
| GET | `/api/technicians` | List technicians |
| GET | `/api/orders` | List orders |
| GET | `/api/orders/{id}` | Get one order |
| POST | `/api/orders/{id}/dispatch` | Assign a technician to the order |
| GET | `/api/dispatches` | List dispatches |
| POST | `/api/dispatches/{id}/complete` | Mark field work done |
| POST | `/api/orders/{id}/invoice` | Generate invoice (order must be completed) |
| GET | `/api/invoices` | List invoices |
| GET | `/api/invoices/{id}` | Get one invoice |
| POST | `/api/invoices/{id}/pay` | Record payment (order must be invoiced) |
| GET | `/api/health` | Health check |

All bodies and responses are JSON. CORS is wide open (`*`) so the demo
frontend can call it directly from a browser.

## Deploying to Render.com

1. **Push this folder to a Git repo** (GitHub or GitLab):
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Manifold Lite backend"
   git remote add origin https://github.com/<you>/manifold-lite.git
   git branch -M main
   git push -u origin main
   ```

2. **Create a new Web Service on Render**
   - Dashboard → New + → Web Service → connect the repo
   - Environment: Python 3
   - Build Command: `python seed.py`
   - Start Command: `python server.py`
   - Instance type: Free is fine for a demo

3. **Storage note:** Render's default disk is ephemeral — the SQLite
   file is wiped on every redeploy/restart. That's fine for a demo that
   re-seeds on each deploy. If you want data to persist across restarts,
   add a Render **Disk**, mount it (e.g. at `/data`), and set the
   `MANIFOLD_DB_PATH` environment variable to `/data/manifold.db`.

4. **Deploy** and note the URL Render gives you, e.g.
   `https://manifold-lite.onrender.com`. Verify with:
   ```bash
   curl https://manifold-lite.onrender.com/api/health
   ```

5. **Open the demo** — just visit the Render URL itself in a browser
   (e.g. `https://manifold-lite.onrender.com`). `server.py` serves
   `demo.html` at `/`, and the page auto-connects to its own origin,
   so there's nothing to configure — no separate file, no URL to paste.

The server already reads the `PORT` environment variable and binds to
`0.0.0.0`, both of which Render requires — no code changes needed to deploy.
