import base64
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import uvicorn
from cryptography.hazmat.primitives import serialization

from scripts.gen_keys import create_jwt, generate_keys

ROOT = Path(__file__).resolve().parent
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def step(title):
    print(f"\n{BOLD}{CYAN}{title}{RESET}")


def ok(message):
    print(f"  {GREEN}{message}{RESET}")


def info(message):
    print(f"  {YELLOW}{message}{RESET}")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


@contextmanager
def demo_environment(keys_dir, policy_file, db_file):
    values = {
        "QUORUM_KEYS_DIR": str(keys_dir),
        "QUORUM_POLICY_PATH": str(policy_file),
        "QUORUM_DB_PATH": str(db_file),
    }
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextmanager
def demo_server():
    # Bind once and pass the same socket to Uvicorn: no port-selection race,
    # and no possibility of probing an unrelated service on port 8000.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                "api.main:app", host="127.0.0.1", port=port,
                log_level="warning", access_log=False, timeout_graceful_shutdown=5,
            )
        )
        errors = []

        def serve():
            try:
                server.run(sockets=[listener])
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=serve, name="quorum-demo-server")
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not thread.is_alive():
                    detail = str(errors[0]) if errors else "server exited before startup"
                    raise RuntimeError(f"Demo server failed to start: {detail}")
                if time.monotonic() >= deadline:
                    raise RuntimeError("Demo server did not start within 15 seconds")
                time.sleep(0.05)
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            # Stop the server before restoring the environment or removing files.
            thread.join()


def api(base, method, path, token=None, body=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = Request(f"{base}{path}", data=data, headers=headers, method=method)
    # Local demo traffic must not be sent through a configured HTTP proxy.
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        with exc:
            content = exc.read().decode("utf-8")
            try:
                return exc.code, json.loads(content)
            except ValueError:
                return exc.code, {"raw": content}


def sign(keys_dir, admin, message):
    private_key = serialization.load_pem_private_key(
        (keys_dir / f"{admin}.pem").read_bytes(), None
    )
    return base64.urlsafe_b64encode(private_key.sign(message)).decode().rstrip("=")


def run_steps(base, keys_dir, policy_file, token_a, token_b):
    step("3. Read public data without administrator credentials")
    status, result = api(base, "GET", "/data")
    require(status == 200 and result == {"data": "public"}, f"Public request failed: {status} {result}")
    ok(f"HTTP 200: {result}")

    step("4. Admin 1 requests a limit of 1000")
    status, result = api(base, "POST", "/limits", token_a, {"value": 1000})
    require(
        status == 429 and result.get("error") == "Quorum required" and result.get("request_id"),
        f"Expected a pending request (HTTP 429), received: {status} {result}",
    )
    request_id = result["request_id"]
    ok(f"HTTP 429: request {request_id} awaits another administrator")

    step("5. Admin 1 attempts to approve their own request")
    status, pending = api(base, "GET", "/quorum/pending", token_b)
    require(status == 200 and isinstance(pending, list), f"Cannot list pending requests: {status} {pending}")
    item = next((item for item in pending if item["id"] == request_id), None)
    require(item is not None, "The newly queued request is missing")
    encoded = item["approval_payload"]
    message = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    status, result = api(
        base, "POST", "/quorum/approve", token_a,
        {"request_id": request_id, "signature": sign(keys_dir, "admin1", message)},
    )
    require(status == 403, f"Expected self-approval to be rejected: {status} {result}")
    ok(f"HTTP 403: {result.get('detail')}")

    step("6. Admin 2 signs the approval payload with Ed25519")
    info(f"Pending request from {item['admin']} for {item['endpoint']}")
    status, result = api(
        base, "POST", "/quorum/approve", token_b,
        {"request_id": request_id, "signature": sign(keys_dir, "admin2", message)},
    )
    require(
        status == 200 and result.get("status") == "approved",
        f"Second-administrator approval failed: {status} {result}",
    )
    ok("HTTP 200: the authenticated request was approved by a different administrator")

    step("7. Admin 1 repeats the approved request")
    status, result = api(base, "POST", "/limits", token_a, {"value": 1000})
    require(
        status == 200 and result.get("result") == "limit set to 1000",
        f"Expected the approved result: {status} {result}",
    )
    ok(f"HTTP 200: {result['result']}")

    step("8. Modify only the temporary policy file outside the approval flow")
    tampered = json.loads(policy_file.read_text(encoding="utf-8"))
    tampered["limits"]["value"] = 999999
    policy_file.write_text(json.dumps(tampered), encoding="utf-8")
    status, result = api(base, "GET", "/policy")
    require(
        status == 403 and result.get("error") == "policy immutable without quorum",
        f"Expected policy-file tampering to be detected: {status} {result}",
    )
    ok("HTTP 403: the changed policy does not match its stored SHA-256 digest")
    info("This check does not protect against an attacker who can also rewrite the database.")


def main():
    print(f"{BOLD}{'=' * 65}")
    print("  QUORUM-GOVERNED API GUARD — ISOLATED LOCAL DEMO")
    print(f"{'=' * 65}{RESET}")
    info("Local Ed25519 identities and two-administrator approval; not a live TideCloak integration.")
    # The API reads its store configuration at import time. Refuse a reused
    # interpreter rather than accidentally operating on an already-loaded store.
    require("api.main" not in sys.modules and "api.quorum" not in sys.modules,
            "Run demo.py in a fresh Python process; the API has already been imported")
    with tempfile.TemporaryDirectory(prefix="quorum-demo-") as directory:
        temporary = Path(directory).resolve()
        keys_dir = temporary / "keys"
        policy_file = temporary / "policy.json"
        db_file = temporary / "quorum.db"
        step("1. Generate disposable administrator keypairs and JWTs")
        generate_keys(keys_dir)
        token_a = create_jwt("admin1", keys_dir)
        token_b = create_jwt("admin2", keys_dir)
        shutil.copyfile(ROOT / "policy.json", policy_file)
        ok("Repository keys, database, and policy will not be modified")

        step("2. Start a dedicated loopback server with a temporary database and policy")
        with demo_environment(keys_dir, policy_file, db_file), demo_server() as base:
            ok(f"Demo server started at {base}")
            run_steps(base, keys_dir, policy_file, token_a, token_b)

    print(f"\n{BOLD}{GREEN}All demonstrated request checks passed.{RESET}")
    print("Demo server stopped and temporary keys, policy, and database removed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nDemo interrupted; its context managers clean up temporary resources.")
        sys.exit(130)
    except Exception as exc:
        print(f"\n{RED}Demo failed: {exc}{RESET}", file=sys.stderr)
        sys.exit(1)
