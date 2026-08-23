import os
import sys
import time
import urllib.request
import subprocess
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"


def is_server_running(url="http://localhost:3000"):
    try:
        with urllib.request.urlopen(url, timeout=2) as res:
            return res.status in (200, 304)
    except Exception:
        return False


def main():
    server_process = None
    if not is_server_running():
        print("[*] Starting Next.js frontend server on port 3000...")
        server_process = subprocess.Popen(
            ["bun", "run", "start"],
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )

        ready = False
        for i in range(20):
            time.sleep(1)
            if is_server_running():
                ready = True
                print(f"[+] Next.js server ready at http://localhost:3000 (after {i+1}s)")
                break

        if not ready:
            print("[!] Production server not ready, trying bun run dev...")
            if server_process:
                server_process.kill()
            server_process = subprocess.Popen(
                ["bun", "run", "dev"],
                cwd=str(FRONTEND_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
            )
            for i in range(25):
                time.sleep(1)
                if is_server_running():
                    ready = True
                    print(f"[+] Next.js dev server ready at http://localhost:3000 (after {i+1}s)")
                    break

        if not ready:
            print("[-] Failed to start Next.js frontend server.")
            if server_process:
                server_process.kill()
            sys.exit(1)
    else:
        print("[+] Frontend server already running at http://localhost:3000")

    # Run pytest
    print("\n[+] Executing Selenium End-to-End Test Suite...")
    pytest_args = [
        "uv",
        "run",
        "--with",
        "selenium",
        "--with",
        "pytest",
        "pytest",
        "-v",
        "-c",
        str(ROOT_DIR / "tests_selenium" / "pytest.ini"),
        str(ROOT_DIR / "tests_selenium"),
    ]

    try:
        result = subprocess.run(pytest_args, cwd=str(ROOT_DIR))
        exit_code = result.returncode
    finally:
        if server_process:
            print("\n[*] Stopping Next.js test server process...")
            server_process.terminate()
            try:
                server_process.wait(timeout=3)
            except Exception:
                server_process.kill()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
