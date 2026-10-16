"""Live verification script demonstrating Phase 05 field validation, calendar checks, and review flags."""

import subprocess
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import httpx

PORT = 8010
BASE_URL = f"http://127.0.0.1:{PORT}"


def main():
    print(f"[*] Starting live Uvicorn server on port {PORT} for Phase 05 verification...")
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

        # 1. Test Valid Devanagari Form Entry
        print("\n--- 1. Testing POST /api/validate (Valid Devanagari Fields) ---")
        valid_payload = {
            "template_id": "devanagari_synthetic_v1",
            "engine_id": "crnn",
            "fields": {
                "applicant_name": {
                    "field_id": "applicant_name",
                    "field_type": "NAME",
                    "raw_text": "राकेश कुमार शर्मा",
                    "confidence": 0.94,
                    "is_confidence_calibrated": True,
                },
                "submission_date": {
                    "field_id": "submission_date",
                    "field_type": "DATE",
                    "raw_text": "१५/०८/२०२४",
                    "confidence": 0.96,
                    "is_confidence_calibrated": True,
                },
                "declared_amount": {
                    "field_id": "declared_amount",
                    "field_type": "AMOUNT",
                    "raw_text": "२५,०००",
                    "confidence": 0.92,
                    "is_confidence_calibrated": True,
                },
            },
        }
        res = client.post("/api/validate", json=valid_payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()["data"]
        print(f"Total Fields: {data['total_fields']} | Valid: {data['valid_fields']} | Review Required: {data['review_required_fields']}")
        print(f"Document Requires Review: {data['document_requires_review']}")
        for fid, fval in data["fields"].items():
            repr_raw = fval['raw_text'].encode('unicode_escape').decode('ascii') if sys.platform == 'win32' else fval['raw_text']
            repr_norm = fval['normalized_text'].encode('unicode_escape').decode('ascii') if (fval['normalized_text'] and sys.platform == 'win32') else fval['normalized_text']
            print(f"  - [{fid}] Status: {fval['validation_status']} | Raw: '{repr_raw}' -> Normalized: '{repr_norm}'")

        assert data["valid_fields"] == 3
        assert data["document_requires_review"] is False

        # 2. Test Invalid Form Entries (Numeric in Name, Non-Leap Year Feb 29, Digit Confusion in Amount)
        print("\n--- 2. Testing POST /api/validate (Flagged Suspicious Entries) ---")
        suspicious_payload = {
            "template_id": "devanagari_synthetic_v1",
            "fields": {
                "applicant_name": {
                    "field_id": "applicant_name",
                    "field_type": "NAME",
                    "raw_text": "राम123",  # Digits inside name
                    "confidence": 0.90,
                    "is_confidence_calibrated": True,
                },
                "submission_date": {
                    "field_id": "submission_date",
                    "field_type": "DATE",
                    "raw_text": "29/02/2023",  # 2023 is non-leap year!
                    "confidence": 0.90,
                    "is_confidence_calibrated": True,
                },
                "declared_amount": {
                    "field_id": "declared_amount",
                    "field_type": "AMOUNT",
                    "raw_text": "25O00",  # 'O' instead of '0'
                    "confidence": 0.90,
                    "is_confidence_calibrated": True,
                },
            },
        }
        res2 = client.post("/api/validate", json=suspicious_payload)
        assert res2.status_code == 200
        data2 = res2.json()["data"]
        print(f"Total Fields: {data2['total_fields']} | Valid: {data2['valid_fields']} | Review Required: {data2['review_required_fields']}")
        print(f"Document Requires Review: {data2['document_requires_review']}")
        for fid, fval in data2["fields"].items():
            print(f"  - [{fid}] Status: {fval['validation_status']} | Review Required: {fval['requires_review']}")
            print(f"    Raw Text Preserved: '{fval['raw_text']}'")
            print(f"    Warning Codes: {fval['warning_codes']}")
            print(f"    Reasons: {fval['review_reasons']}")

        assert data2["document_requires_review"] is True
        assert data2["review_required_fields"] == 3
        # Crucial invariant: raw_text is never modified or deleted
        assert data2["fields"]["applicant_name"]["raw_text"] == "राम123"
        assert data2["fields"]["submission_date"]["raw_text"] == "29/02/2023"
        assert data2["fields"]["declared_amount"]["raw_text"] == "25O00"

        # 3. Test Valid Zero Preservation vs Empty
        print("\n--- 3. Testing Valid Zero Preservation vs Empty Amount ---")
        zero_res = client.post(
            "/api/validate/field",
            json={
                "field_id": "declared_amount",
                "field_type": "AMOUNT",
                "raw_text": "०.००",
                "confidence": 0.95,
                "is_confidence_calibrated": True,
            },
        )
        assert zero_res.status_code == 200
        zdata = zero_res.json()["data"]
        print(f"Zero Input '०.००' -> Status: {zdata['validation_status']}, Normalized: '{zdata['normalized_text']}', Parsed: {zdata['parsed_value']}")
        assert zdata["validation_status"] == "VALID"
        assert zdata["normalized_text"] == "0.00"

        print("\n=======================================================")
        print("ALL LIVE VALIDATION CHECKS PASSED SUCCESSFULLY!")
        print("=======================================================")

    finally:
        print("[*] Terminating Uvicorn process...")
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
