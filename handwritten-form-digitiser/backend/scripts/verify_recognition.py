"""Live verification script demonstrating OCR engine discovery, mock/tesseract recognition, and error resilience."""

import io
import subprocess
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import httpx
import numpy as np

PORT = 8009
BASE_URL = f"http://127.0.0.1:{PORT}"


def create_demo_form(width=800, height=1000) -> bytes:
    """Generate in-memory synthetic form matching devanagari_synthetic_v1 coordinates."""
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
    cv2.rectangle(canvas, (20, 20), (width - 20, height - 20), (0, 0, 0), 2)
    cv2.putText(canvas, "DEVANAGARI APPLICATION FORM", (50, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    # Field 1: applicant_name [0.10, 0.22, 0.85, 0.32] -> (80, 220) to (680, 320)
    cv2.rectangle(canvas, (80, 220), (680, 320), (0, 0, 0), 2)
    cv2.putText(canvas, "Applicant Name:", (85, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1)
    cv2.putText(canvas, "Rakesh Kumar Sharma", (100, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (15, 15, 15), 2)

    # Field 2: submission_date [0.55, 0.38, 0.90, 0.48] -> (440, 380) to (720, 480)
    cv2.rectangle(canvas, (440, 380), (720, 480), (0, 0, 0), 2)
    cv2.putText(canvas, "Submission Date:", (445, 370), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1)
    cv2.putText(canvas, "15/08/2026", (460, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (15, 15, 15), 2)

    # Field 3: declared_amount [0.10, 0.54, 0.60, 0.64] -> (80, 540) to (480, 640)
    cv2.rectangle(canvas, (80, 540), (480, 640), (0, 0, 0), 2)
    cv2.putText(canvas, "Declared Amount (INR):", (85, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1)
    cv2.putText(canvas, "25,000", (100, 600), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (15, 15, 15), 2)

    success, encoded = cv2.imencode(".png", canvas)
    assert success
    return encoded.tobytes()


def main():
    print(f"[*] Starting live Uvicorn server on port {PORT} for Phase 04 verification...")
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
        client = httpx.Client(base_url=BASE_URL, timeout=10.0)
        started = False
        for _ in range(25):
            try:
                r = client.get("/api/health")
                if r.status_code == 200:
                    started = True
                    break
            except Exception:
                time.sleep(0.4)

        if not started:
            print("[FAIL] Server failed to start within timeout.")
            sys.exit(1)

        print("[OK] Server online and healthy.")

        # 1. Discover registered OCR engines
        print("\n--- 1. Testing GET /api/recognize/engines ---")
        engines_res = client.get("/api/recognize/engines")
        assert engines_res.status_code == 200, f"Expected 200, got {engines_res.status_code}"
        engines_data = engines_res.json()["data"]
        print(f"Registered OCR engines: {len(engines_data)}")
        for eng in engines_data:
            print(f"  - [{eng['engine_id']}] {eng['display_name']} | Available: {eng['is_available']} | Scripts: {eng['supported_scripts']}")

        # 2. Test End-to-End Recognition with Mock Engine
        print("\n--- 2. Testing POST /api/recognize (engine_id=mock) ---")
        demo_image = create_demo_form()
        rec_res = client.post(
            "/api/recognize",
            data={
                "template_id": "devanagari_synthetic_v1",
                "engine_id": "mock",
                "strategy": "hybrid",
            },
            files={"file": ("synthetic_form.png", io.BytesIO(demo_image), "image/png")},
        )
        assert rec_res.status_code == 200, f"Expected 200, got {rec_res.status_code}: {rec_res.text}"
        rec_body = rec_res.json()["data"]
        print(f"Template ID: {rec_body['template_id']}")
        print(f"Engine: {rec_body['engine_id']}")
        print(f"Total Inference Time: {rec_body['total_inference_time_ms']:.2f} ms")
        print(f"Recognized Fields ({len(rec_body['fields'])}):")
        for fid, fval in rec_body["fields"].items():
            repr_text = fval['text'].encode('unicode_escape').decode('ascii') if sys.platform == 'win32' else fval['text']
            print(f"  - {fid}: text={repr_text} | status={fval['status']} | conf={fval['confidence']:.2f} | time={fval['inference_time_ms']:.2f}ms")

        # 3. Test Recognition with Tesseract Engine (clean handling if not installed)
        print("\n--- 3. Testing POST /api/recognize (engine_id=tesseract) ---")
        tess_res = client.post(
            "/api/recognize",
            data={
                "template_id": "devanagari_synthetic_v1",
                "engine_id": "tesseract",
                "strategy": "fixed",
            },
            files={"file": ("synthetic_form.png", io.BytesIO(demo_image), "image/png")},
        )
        assert tess_res.status_code == 200, f"Expected 200, got {tess_res.status_code}: {tess_res.text}"
        tess_body = tess_res.json()["data"]
        print(f"Tesseract engine response: {tess_body['engine_id']}")
        for fid, fval in tess_body["fields"].items():
            print(f"  - {fid}: status={fval['status']} | warnings={fval.get('warnings', [])}")

        # 4. Test Error Handling (Corrupted File)
        print("\n--- 4. Testing POST /api/recognize with corrupt image payload ---")
        corrupt_res = client.post(
            "/api/recognize",
            data={"engine_id": "mock"},
            files={"file": ("corrupt.png", io.BytesIO(b"garbage_data_not_an_image"), "image/png")},
        )
        assert corrupt_res.status_code == 400, f"Expected 400, got {corrupt_res.status_code}"
        err = corrupt_res.json()["error"]
        print(f"[OK] Corrupt upload rejected cleanly: code={err['code']}, message={err['message']}")

        print("\n=======================================================")
        print("ALL LIVE VERIFICATION CHECKS PASSED SUCCESSFULLY!")
        print("=======================================================")

    finally:
        print("[*] Terminating Uvicorn process...")
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
