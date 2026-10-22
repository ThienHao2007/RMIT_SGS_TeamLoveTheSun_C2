import argparse
import os
import webbrowser
from pathlib import Path

import uvicorn

from scripts.gen_keys import create_jwt, generate_keys

ROOT = Path(__file__).resolve().parent

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

def main():
    parser = argparse.ArgumentParser(description="Launch the local API Guard demo and UI")
    parser.add_argument("--port", type=int, default=8000, help="local HTTP port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the UI in a browser")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    ui_dist = ROOT / "ui" / "dist"
    if not (ui_dist / "index.html").is_file() or not (ui_dist / "assets").is_dir():
        parser.exit(
            1,
            f"UI build missing or incomplete at {ui_dist}.\n"
            "Run the setup script, or run npm ci and npm run build in the ui folder.\n",
        )

    # Resolve defaults and relative overrides against the checkout, not the caller's cwd.
    for name, default in (
        ("QUORUM_KEYS_DIR", "keys"),
        ("QUORUM_DB_PATH", "quorum.db"),
        ("QUORUM_POLICY_PATH", "policy.json"),
    ):
        path = Path(os.environ.get(name, default))
        os.environ[name] = str((ROOT / path).resolve())
    keys_dir = Path(os.environ["QUORUM_KEYS_DIR"])

    print(f"\n{BOLD}{CYAN}{'=' * 65}")
    print("  QUORUM-GOVERNED API GUARD — LOCAL DEMO LAUNCHER")
    print(f"{'=' * 65}{RESET}\n")

    # Existing keypairs and database are retained; incomplete keypairs are not replaced.
    try:
        generate_keys(keys_dir)
        token_b = create_jwt("admin2", keys_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Cannot load demo credentials: {exc}\nExisting keys were not replaced.\n")

    print(f"{GREEN}Ed25519 demo credentials loaded; existing keys are retained.{RESET}")
    print(f"{GREEN}UI build found at {ui_dist}.{RESET}\n")
    print(f"{BOLD}ADMIN B LOGIN (use these credentials to approve requests in the UI):{RESET}")
    print(f"{YELLOW}Admin B token (expires after 60 minutes):{RESET}\n{token_b}\n")
    print(f"{YELLOW}Admin B private key file:{RESET} {keys_dir / 'admin2.pem'}\n")
    print("Local demo credentials only. Do not publish tokens or private keys.")

    url = f"http://127.0.0.1:{args.port}"
    print(f"\n{BOLD}{GREEN}Starting the server at: {url}{RESET}")
    print(f"  - UI:             {url}")
    print(f"  - API endpoints:  {url}/data, {url}/limits, ...")
    print(f"  - API docs:       {url}/docs")
    print(f"  - Database:       {os.environ['QUORUM_DB_PATH']} (retained)")
    print("\nPress CTRL+C to stop.\n")

    class LauncherServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            if self.started and not args.no_browser:
                try:
                    if not webbrowser.open(url):
                        print(f"Browser could not be opened automatically. Open {url} manually.")
                except Exception as exc:
                    print(f"Browser could not be opened: {exc}. Open {url} manually.")

    server = LauncherServer(
        uvicorn.Config("api.main:app", host="127.0.0.1", port=args.port, reload=False)
    )
    server.run()
    if not server.started:
        parser.exit(1, "Server did not start.\n")

if __name__ == "__main__":
    main()
