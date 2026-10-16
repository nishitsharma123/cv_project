"""Standalone live server verification script."""

import subprocess
import sys
import time
import httpx

PORT = 8008
BASE_URL = f"http://127.0.0.1:{PORT}"


def main():
    print(f"[*] Starting live Uvicorn server on port {PORT}...")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        cwd=".",
    )

    try:
        # Wait up to 10 seconds for server startup
        client = httpx.Client(base_url=BASE_URL, timeout=5.0)
        started = False
        for i in range(20):
            try:
                r = client.get("/api/health")
                if r.status_code == 200:
                    started = True
                    break
            except Exception:
                time.sleep(0.5)

        if not started:
            print("[!] Failed to connect to server within timeout.")
            return 1

        print("[+] Server started successfully.")

        # 1. Test GET /api/health
        health_resp = client.get("/api/health")
        print(f"[*] GET /api/health -> Status: {health_resp.status_code}")
        print(f"    Body: {health_resp.text}")
        assert health_resp.status_code == 200, f"Expected 200, got {health_resp.status_code}"
        assert health_resp.json()["success"] is True
        assert health_resp.json()["data"]["status"] == "HEALTHY"

        # 2. Test GET /api/nonexistent
        nf_resp = client.get("/api/nonexistent")
        print(f"[*] GET /api/nonexistent -> Status: {nf_resp.status_code}")
        print(f"    Body: {nf_resp.text}")
        assert nf_resp.status_code == 404, f"Expected 404, got {nf_resp.status_code}"
        assert nf_resp.json()["success"] is False
        assert nf_resp.json()["error"]["code"] == "NOT_FOUND"

        # 3. Test GET /docs
        docs_resp = client.get("/docs")
        print(f"[*] GET /docs -> Status: {docs_resp.status_code}")
        assert docs_resp.status_code == 200, f"Expected 200, got {docs_resp.status_code}"

        print("[+] All live server verifications passed successfully!")
        return 0
    finally:
        print("[*] Stopping live Uvicorn server...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[+] Uvicorn server terminated.")


if __name__ == "__main__":
    sys.exit(main())
