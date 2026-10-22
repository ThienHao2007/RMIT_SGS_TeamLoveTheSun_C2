# QUORUM — TeamLoveTheSun

**Campus:** RMIT_SGS · **Challenge:** C2 · **Integration mode:** Plan C (simulated TideCloak integration)

## Project overview

QUORUM is an API approval dashboard that prevents one administrator from independently executing sensitive operational changes.

### 1. Vision & originality

We propose a practical two-person approval workflow for API limits and security policies, making privileged changes visible and reviewable instead of trusting a single administrator session.

### 2. Trust constraint insight

An administrator credential often grants both the ability to request a change and the power to execute it. A stolen credential or mistaken action can therefore affect everyone. Separating proposal from approval introduces a second accountable decision before execution.

### 3. Value & impact

Small platform teams can review production-like changes without building a separate approval system. For example, raising an API limit from 100 to 1,000 remains pending until another administrator approves the exact request.

### 4. Why TideCloak matters

This submission follows the event's permitted Plan C: TideCloak identity and governance integration is simulated locally with Ed25519 JWTs and signed approvals. The repository includes Raziel MCP configuration for development guidance, not a live TideCloak connection. TideCloak is the intended identity and distributed-authority layer; this prototype does not claim its production security guarantees.

### 5. Prototype & storytelling

The FastAPI backend and React dashboard demonstrate proposal, distinct-administrator approval, execution, policy version history, persistent audit events, administrator fingerprints, and policy-file integrity checks. Judges should observe that the requester cannot approve their own request, then switch to the second administrator and confirm the state change and audit trail.

## Setup

### Requirements

- Python **3.12 or newer**; Node.js **22.12 or newer** with npm.
- Internet access for initial dependency installation.
- A current Chrome/Edge browser for Web Crypto Ed25519 signing. Use `http://localhost` or `http://127.0.0.1`, not an insecure remote HTTP origin.
- These instructions run a local hackathon demo, not a production deployment.

### Windows PowerShell

Open a terminal in the repository root:

```powershell
.\setup.bat
.\.venv\Scripts\python.exe run.py
```

### macOS / Linux

```bash
bash setup.sh
.venv/bin/python run.py
```

Setup creates `.venv`, installs Python dependencies, runs `npm ci` and the UI production build, and generates missing demo keys. It does not reset existing keys or the database. The launcher serves the built UI and API together at **http://127.0.0.1:8000** and opens a browser.

If port 8000 is occupied:

```powershell
.\.venv\Scripts\python.exe run.py --port 8002 --no-browser
```

Then open **http://127.0.0.1:8002**. On macOS/Linux replace the interpreter with `.venv/bin/python`.

### Administrator credentials

Generate short-lived JWTs from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/gen_keys.py --tokens
```

For Admin A use `admin1`; for Admin B use `admin2`:

1. Open the administrator settings in the dashboard.
2. Paste only the JWT value into the JWT field — **not** the `admin1=` / `admin2=` prefix and not a private key. A JWT has three dot-separated parts.
3. Paste the matching `keys/admin1.pem` or `keys/admin2.pem` private key's Base64 body into the PKCS8 Ed25519 field. Omit the `BEGIN PRIVATE KEY` / `END PRIVATE KEY` lines and whitespace.
4. Save. Switch both fields when switching administrators; do not mix their credentials.

Tokens expire after one hour by default; rerun `--tokens` to issue fresh tokens without changing existing keys. The UI stores these demo credentials in browser `localStorage`. Never use production credentials here. Do not commit keys, tokens, `.env`, or the SQLite database, and do not show them in recordings.

### Interactive demonstration

1. Configure Admin A, open **Policies**, change `limits.value` in the JSON editor, and submit for approval. The API queues it rather than executing it immediately (HTTP 429 is intentional for pending quorum).
2. Open **Pending approvals** and inspect the proposal. An approval from the requesting administrator is rejected.
3. Configure Admin B, select the same proposal, and sign/approve it.
4. Return to **Policies** and inspect the changed JSON and new policy version. Overview reports the version and integrity status; its operational limit is a separate setting changed through `POST /limits`, demonstrated by `demo.py`.
5. Open **Audit** to inspect actual persisted events, then **Administrators** to inspect the two public-key fingerprints. This view is an inventory, not administrator provisioning.

An already-approved identical request may reuse its cached result; choose a new value for a fresh demonstration. Use a disposable checkout for policy-tamper experiments rather than editing a working demo's policy file.

### Automated HTTP demonstration

```powershell
.\.venv\Scripts\python.exe demo.py
```

This starts its own server on an OS-assigned local port with temporary keys, policy, and database. It demonstrates the public route, queued sensitive request, approval, execution, and policy-tamper rejection without overwriting the interactive demo's state.

### Development and checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix ui run lint
npm --prefix ui run build
```

For a Vite development server, run the backend on port 8000 and `npm --prefix ui run dev` in a second terminal. The Vite proxy routes API requests to that backend.

## Architecture and implemented boundaries

- **FastAPI:** JWT verification, sensitive-request guard, signed approval validation, protected dashboard endpoints.
- **React / Vite:** Overview, pending requests, policy editor/history, audit pagination, administrator inventory.
- **SQLite:** pending requests, approved results, policy version metadata, and audit events.
- **Policy integrity:** a SHA-256 digest of canonical JSON is compared with the recorded policy root. This is a single digest, not a full Merkle tree.
- **Two-person authorization:** one authenticated proposer and one distinct administrator's signed approval. This is not two cryptographic operation signatures or threshold cryptography.

The local server generates/holds demo keys. A machine owner who can alter both the database and policy file is outside the protection offered here; the audit database is not immutable. Live TideCloak authentication, distributed key custody, production provisioning, and deployment hardening are not implemented. See [TideCloak integration disclosure](docs/TIDECLOAK.md).

## Submission files

- [Submission video](demo/TeamLoveTheSun_RMIT_SGS_C2.mp4) — local credential scenes redacted; lightly accelerated and compressed from the team's recording. Download the MP4 if GitHub does not preview it.
- [Vietnamese submission checklist](SUBMISSION.md).
- [Two-minute demo recording guide](docs/DEMO_SCRIPT.md).

The video shows the recorded prototype; the repository also contains safe setup/launcher improvements made when preparing this submission.

## Official references

- [Tide Unlocked challenge and Plan C guidance](https://tide.org/unlocked/#challenge)
- [TideCloak](https://tide.org/tidecloak)
- [Official submission form](https://forms.gle/HRHYjnqB86j1LFS97)

This project is submitted by **TeamLoveTheSun**, **RMIT_SGS**, **C2**. No live TideCloak deployment is claimed.
