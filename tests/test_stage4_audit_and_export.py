"""
Aşama 4: Kriptografik Denetlenebilirlik, Audit Sertifikası ve Veri Dışa Aktarma Testleri
"""

import io
import numpy as np
import pytest
from fastapi.testclient import TestClient
from simulator.api.app import app

client = TestClient(app)

def test_audit_certificate_endpoint_and_pdf_qr():
    # 1. Simülasyon Koştur
    payload = {
        "rows": 2,
        "cols": 2,
        "cell_format": "18650",
        "spacing_x_mm": 2.0,
        "spacing_y_mm": 2.0,
        "simulation_time_s": 20.0,
        "trigger_cell_id": 0
    }
    res_run = client.post("/api/simulations/run", json=payload)
    assert res_run.status_code == 200
    run_data = res_run.json()
    job_id = run_data["job_id"]

    # 2. PDF Raporu İndir (QR ve Kriptografik Bölüm İçerir)
    res_pdf = client.get(f"/api/simulations/{job_id}/report")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert len(res_pdf.content) > 3000

    # 3. Kriptografik Denetim Sertifikasını Sorgula
    res_cert = client.get(f"/api/simulations/{job_id}/audit-certificate")
    assert res_cert.status_code == 200
    cert = res_cert.json()

    assert cert["job_id"] == job_id
    assert cert["certificate_id"].startswith("TR-CERT-")
    assert cert["status"] == "CRYPTOGRAPHICALLY_VERIFIED"
    assert cert["is_tamper_proof"] is True
    assert len(cert["config_hash_sha256"]) == 64
    assert len(cert["git_commit_sha"]) >= 8
    assert "UL 9540A Level 2" in cert["regulatory_standards"][0]
    assert cert["verification_urn"].startswith("urn:thermalrunaway:cert:")


def test_simulation_data_export_csv():
    payload = {
        "rows": 2,
        "cols": 2,
        "simulation_time_s": 15.0
    }
    res_run = client.post("/api/simulations/run", json=payload)
    job_id = res_run.json()["job_id"]

    res_csv = client.get(f"/api/simulations/{job_id}/export?format=csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    text = res_csv.text
    lines = text.strip().split("\n")
    assert len(lines) > 5
    header = lines[0]
    assert "time_s" in header
    assert "cell_0_temp_C" in header
    assert "cell_0_alpha" in header


def test_simulation_data_export_binary_npz():
    payload = {
        "rows": 2,
        "cols": 2,
        "simulation_time_s": 15.0
    }
    res_run = client.post("/api/simulations/run", json=payload)
    job_id = res_run.json()["job_id"]

    res_npz = client.get(f"/api/simulations/{job_id}/export?format=npz")
    assert res_npz.status_code == 200
    assert "application/octet-stream" in res_npz.headers["content-type"]
    
    # İkili arşivi numpy ile doğrula
    buf = io.BytesIO(res_npz.content)
    with np.load(buf) as npz_data:
        assert "time_points_s" in npz_data
        assert "temperature_matrix_C" in npz_data
        assert "alpha_matrix" in npz_data
        assert npz_data["temperature_matrix_C"].shape[0] == 4  # 4 cells
        assert npz_data["temperature_matrix_C"].shape[1] == len(npz_data["time_points_s"])
