"""Live verification script for image upload validation and preprocessing."""

import io
import subprocess
import sys
import time
import cv2
import httpx
import numpy as np

PORT = 8008
BASE_URL = f"http://127.0.0.1:{PORT}"


def make_test_form(width=600, height=800, angle=4.0) -> bytes:
    """Generate in-memory synthetic form image with printed guide lines."""
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
    cv2.rectangle(canvas, (30, 30), (width - 30, height - 30), (0, 0, 0), 2)
    cv2.line(canvas, (30, 90), (width - 30, 90), (0, 0, 0), 2)
    cv2.putText(canvas, "SAMPLE APPLICATION FORM", (50, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    for y in range(160, height - 60, 90):
        cv2.line(canvas, (50, y), (width - 50, y), (20, 20, 20), 2)
        # Simulated handwriting strokes
        pts = np.array([[70, y - 25], [120, y - 45], [180, y - 20], [240, y - 35], [300, y - 20]], np.int32)
        cv2.polylines(canvas, [pts.reshape((-1, 1, 2))], False, (10, 10, 10), 2)

    if abs(angle) > 0.01:
        center = (width / 2.0, height / 2.0)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos_val = abs(rot_mat[0, 0])
        sin_val = abs(rot_mat[0, 1])
        new_w = int((height * sin_val) + (width * cos_val))
        new_h = int((height * cos_val) + (width * sin_val))
        rot_mat[0, 2] += (new_w / 2.0) - center[0]
        rot_mat[1, 2] += (new_h / 2.0) - center[1]
        canvas = cv2.warpAffine(canvas, rot_mat, (new_w, new_h), borderValue=(255, 255, 255))

    success, encoded = cv2.imencode(".jpg", canvas)
    assert success
    return encoded.tobytes()


def main():
    print(f"[*] Starting live Uvicorn server on port {PORT} for Phase 02 verification...")
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

        print("[+] Live server ready.")

        # 1. Valid Form Preprocessing Test
        img_bytes = make_test_form(width=600, height=800, angle=4.0)
        files = {"file": ("application_form.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        resp = client.post("/api/preprocess", files=files)
        print(f"[*] POST /api/preprocess (Valid Form) -> Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        print(f"    Filename: {data['filename']}")
        print(f"    Applied Steps: {', '.join(data['applied_steps'])}")
        print(f"    Skew Angle Detected: {data['metadata']['skew_angle_detected']}° (Corrected: {data['metadata']['skew_correction_applied']})")
        print(f"    Duration: {data['metadata']['processing_time_ms']}ms")
        print(f"    Preview Format: {data['preview']['format']} ({data['preview']['width']}x{data['preview']['height']}px, data_url size: {len(data['preview']['data_url'])} chars)")

        # 2. Corrupt Image Test
        corrupt_files = {"file": ("corrupt.jpg", io.BytesIO(b"\xff\xd8\xffnot-an-image"), "image/jpeg")}
        resp_corrupt = client.post("/api/preprocess", files=corrupt_files)
        print(f"[*] POST /api/preprocess (Corrupt Image) -> Status: {resp_corrupt.status_code}")
        assert resp_corrupt.status_code == 400
        assert resp_corrupt.json()["error"]["code"] == "INVALID_IMAGE_DATA"
        print(f"    Rejected cleanly with code: {resp_corrupt.json()['error']['code']}")

        # 3. Empty File Test
        empty_files = {"file": ("empty.png", io.BytesIO(b""), "image/png")}
        resp_empty = client.post("/api/preprocess", files=empty_files)
        print(f"[*] POST /api/preprocess (Empty File) -> Status: {resp_empty.status_code}")
        assert resp_empty.status_code == 400
        assert resp_empty.json()["error"]["code"] == "EMPTY_FILE"
        print(f"    Rejected cleanly with code: {resp_empty.json()['error']['code']}")

        # 4. Unsupported Format Test
        txt_files = {"file": ("form_notes.txt", io.BytesIO(b"Some text"), "text/plain")}
        resp_txt = client.post("/api/preprocess", files=txt_files)
        print(f"[*] POST /api/preprocess (Unsupported Format) -> Status: {resp_txt.status_code}")
        assert resp_txt.status_code == 400
        assert resp_txt.json()["error"]["code"] == "UNSUPPORTED_FORMAT"
        print(f"    Rejected cleanly with code: {resp_txt.json()['error']['code']}")

        # 5. Undersized Image Test
        tiny_canvas = np.ones((50, 50, 3), dtype=np.uint8) * 255
        _, tiny_enc = cv2.imencode(".jpg", tiny_canvas)
        tiny_files = {"file": ("icon.jpg", io.BytesIO(tiny_enc.tobytes()), "image/jpeg")}
        resp_tiny = client.post("/api/preprocess", files=tiny_files)
        print(f"[*] POST /api/preprocess (Undersized Image 50x50) -> Status: {resp_tiny.status_code}")
        assert resp_tiny.status_code == 422
        assert resp_tiny.json()["error"]["code"] == "INVALID_DIMENSIONS"
        print(f"    Rejected cleanly with code: {resp_tiny.json()['error']['code']}")

        print("\n[+] All live server verification tests PASSED with 100% compliance!")
        return 0
    finally:
        print("[*] Terminating Uvicorn server...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[+] Server terminated.")


if __name__ == "__main__":
    sys.exit(main())
