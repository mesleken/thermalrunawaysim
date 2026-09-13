"""
API ve Raporlama Uçtan Uca Entegrasyon Testleri
FastAPI endpoint'leri, simülasyon servisi ve PDF dosya çıktısı doğrulaması.
"""

import pytest
import os
from fastapi.testclient import TestClient
from simulator.api.app import app

client = TestClient(app)

def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["validation_status"] == "literature_calibrated"

def test_api_chemistry_library():
    res = client.get("/api/chemistry/library")
    assert res.status_code == 200
    data = res.json()
    assert "chemistries" in data
    ids = [c["chemistry_id"] for c in data["chemistries"]]
    assert "NMC_generic_v1" in ids
    assert "LFP_generic_v1" in ids

def test_api_simulation_run_and_report_download():
    # 2x2 küçük modül simülasyonu çalıştır
    payload = {
        "rows": 2,
        "cols": 2,
        "cell_format": "18650",
        "spacing_x_mm": 2.0,
        "spacing_y_mm": 2.0,
        "chemistry_id": "NMC_generic_v1",
        "simulation_time_s": 30.0,
        "trigger_cell_id": 0,
        "trigger_power_W": 1200.0,
        "trigger_duration_s": 2.0,
        "num_output_points": 50
    }

    res = client.post("/api/simulations/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    job_id = data["job_id"]
    assert "config_hash" in data
    assert "execution_fingerprint" in data

    # Sonuçları sorgula
    res_get = client.get(f"/api/simulations/{job_id}/results")
    assert res_get.status_code == 200
    full_data = res_get.json()
    assert full_data["status"] == "COMPLETED"
    assert len(full_data["simulation_result"]["cell_summaries"]) == 4

    # PDF rapor indirme testi
    res_pdf = client.get(f"/api/simulations/{job_id}/report")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert len(res_pdf.content) > 1000 # Gerçek geçerli PDF verisi
