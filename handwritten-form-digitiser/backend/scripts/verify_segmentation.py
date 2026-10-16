"""Live verification script demonstrating field detection, segmentation, and crop extraction."""

import io
import subprocess
import sys
import time
import cv2
import httpx
import numpy as np

PORT = 8008
BASE_URL = f"http://127.0.0.1:{PORT}"


def create_demo_form(width=800, height=1000) -> bytes:
    """Generate in-memory synthetic form matching devanagari_synthetic_v1 coordinates."""
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
    cv2.rectangle(canvas, (20, 20), (width - 20, height - 20), (0, 0, 0), 2)
    cv2.putText(canvas, "DEVANAGARI APPLICATION FORM", (50, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    # Field 1: applicant_name [0.10, 0.22, 0.85, 0.32] -> (80, 220) to (680, 320)
    cv2.rectangle(canvas, (80, 220), (680, 320), (0, 0, 0), 2)
    cv2.putText(canvas, "Applicant Name:", (85, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1)
    cv2.putText(canvas, "Rakesh Kumar Sharma", (100, 280), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.9, (15, 15, 15), 2)

    # Field 2: submission_date [0.55, 0.38, 0.90, 0.48] -> (440, 380) to (720, 480)
    cv2.rectangle(canvas, (440, 380), (720, 480), (0, 0, 0), 2)
    cv2.putText(canvas, "Submission Date:", (445, 370), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1)
    cv2.putText(canvas, "15/08/2026", (460, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (15, 15, 15), 2)

    # Field 3: declared_amount [0.10, 0.54, 0.60, 0.64] -> (80, 540) to (480, 640)
    cv2.rectangle(canvas, (80, 540), (480, 640), (0, 0, 0), 2)
    cv2.putText(canvas, "Declared Amount (INR):", (85, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1)
    cv2.putText(canvas, "25,000", (100, 600), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (15, 15, 15), 2)

    success, encoded = cv2.imencode(".jpg", canvas)
    assert success
    return encoded.tobytes()


def main():
    print(f"[*] Starting live Uvicorn server on port {PORT} for Phase 03 verification...")
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
            print("[!] Server failed to start.")
            return 1

        print("[+] Live server ready.\n")

        # 1. Verify GET /api/templates
        tmpl_resp = client.get("/api/templates")
        print(f"[*] GET /api/templates -> Status: {tmpl_resp.status_code}")
        assert tmpl_resp.status_code == 200
        templates = tmpl_resp.json()["data"]
        print(f"    Available templates ({len(templates)}): {[t['template_id'] for t in templates]}")

        # 2. Verify POST /api/segment
        form_bytes = create_demo_form(width=800, height=1000)
        files = {"file": ("demo_form.jpg", io.BytesIO(form_bytes), "image/jpeg")}
        data = {"template_id": "devanagari_synthetic_v1", "strategy": "hybrid"}

        seg_resp = client.post("/api/segment", files=files, data=data)
        print(f"\n[*] POST /api/segment -> Status: {seg_resp.status_code}")
        assert seg_resp.status_code == 200
        body = seg_resp.json()
        assert body["success"] is True

        payload = body["data"]
        print(f"    Status: {payload['status']}")
        print(f"    Template: {payload['template_name']} ({payload['template_id']})")
        print(f"    Total Processing Time: {payload['processing_time_ms']}ms")
        print(f"    Annotated Full Preview URL: {payload['annotated_preview']['data_url'][:45]}... (width={payload['annotated_preview']['width']}px)")

        print("\n--- Detected & Segmented Fields Demonstration ---")
        for fid, field in payload["fields"].items():
            box = field["bounding_box"]
            crop_prev = field["crop_preview"]
            print(f"    > Field: '{field['field_name']}' ({field['field_id']})")
            print(f"      Type: {field['field_type']}")
            print(f"      Status: {field['status']} (Method: {field['detection_method']}, Confidence: {field['confidence']})")
            print(f"      Bounding Box: [x1={box['x1']}, y1={box['y1']}, x2={box['x2']}, y2={box['y2']}] -> {box['width']}x{box['height']}px")
            if crop_prev:
                print(f"      Crop Preview: {crop_prev['preview_data_url'][:45]}... ({crop_prev['width']}x{crop_prev['height']}px)")
            if field["warnings"]:
                print(f"      Warnings: {field['warnings']}")
            print()

        # 3. Test Invalid Template Rejection
        bad_files = {"file": ("demo_form.jpg", io.BytesIO(form_bytes), "image/jpeg")}
        bad_data = {"template_id": "nonexistent_template"}
        bad_resp = client.post("/api/segment", files=bad_files, data=bad_data)
        print(f"[*] POST /api/segment (Invalid Template) -> Status: {bad_resp.status_code}")
        assert bad_resp.status_code == 404
        assert bad_resp.json()["error"]["code"] == "TEMPLATE_NOT_FOUND"
        print(f"    Cleanly rejected: {bad_resp.json()['error']['message']}")

        print("\n[+] All Phase 03 live server verifications PASSED with 100% compliance!")
        return 0
    finally:
        print("\n[*] Terminating Uvicorn server...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[+] Server terminated.")


if __name__ == "__main__":
    sys.exit(main())
