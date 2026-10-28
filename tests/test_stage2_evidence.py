"""
Aşama 2 Kanıt ve Validasyon Motoru (Evidence Engine) Testleri:
1. CSV sensör logu ayrıştırma (parse_sensor_csv)
2. Kalıntı hata (Residual RMSE, Onset, Peak) ve Validasyon Skoru hesabı
3. Monte Carlo Belirsizlik Analizi (P10, P50, P90 bantları)
4. REST API uç noktaları (/api/validation/compare, /api/simulations/monte-carlo-uq)
"""

import pytest
import numpy as np
from fastapi.testclient import TestClient

from simulator.core.validation_engine import ValidationEngine
from simulator.api.models import PackSimulationRequest, MonteCarloUQRequest, ValidationCompareRequest
from simulator.api.services import SimulationService
from simulator.api.app import app

client = TestClient(app)

def test_validation_engine_csv_parser():
    """CSV sensör logunun virgül ve noktalı virgül ayrımıyla hatasız okunduğu test edilir."""
    csv_sample_comma = """time_s,temperature_C
0.0, 25.0
5.0, 45.2
10.0, 110.5
15.0, 280.0
20.0, 750.4
25.0, 620.1
"""
    times, temps = ValidationEngine.parse_sensor_csv(csv_sample_comma)
    assert len(times) == 6
    assert len(temps) == 6
    assert times[0] == 0.0 and times[-1] == 25.0
    assert temps[0] == 25.0 and temps[4] == 750.4

    # Noktalı virgül formatı
    csv_sample_semi = """Zaman (s);Sicaklik (C)
0,0; 24,5
5,0; 50,0
10,0; 210,0
15,0; 650,0
"""
    times_semi, temps_semi = ValidationEngine.parse_sensor_csv(csv_sample_semi)
    assert len(times_semi) == 4
    assert temps_semi[2] == 210.0

def test_validation_residuals_and_confidence_score():
    """Simülasyon eğrisi ile deneysel sensör eğrisi karşılaştırılır ve güven skoru doğrulanır."""
    engine = ValidationEngine()
    
    # 0'dan 30'a simülasyon eğrisi
    sim_times = list(np.linspace(0.0, 30.0, 50))
    sim_temps = [25.0 + (700.0 / (1.0 + np.exp(-(t - 12.0) / 1.5))) for t in sim_times]
    
    # Benzer deneysel veri
    exp_times = np.linspace(0.0, 30.0, 40)
    exp_temps = np.array([25.0 + (680.0 / (1.0 + np.exp(-(t - 12.2) / 1.6))) for t in exp_times])
    
    res = engine.evaluate_residuals(
        sim_times=sim_times,
        sim_temps=sim_temps,
        exp_times=exp_times,
        exp_temps=exp_temps,
        sim_onset_C=155.0,
        sim_trigger_C=210.0
    )
    
    assert res.validation_score_percent >= 70.0, f"Skor yüksek olmalı: {res.validation_score_percent}"
    assert res.rmse_C > 0.0
    assert res.confidence_status in ["HIGH_CONFIDENCE_PASS", "MODERATE_MARGINAL"]
    assert len(res.aligned_time_points) == 100

def test_monte_carlo_uncertainty_quantification():
    """Monte Carlo belirsizlik analizi: P10 <= P50 <= P90 sıralaması ve tolerans bandı test edilir."""
    service = SimulationService()
    req = PackSimulationRequest(
        rows=2,
        cols=1,
        simulation_time_s=20.0
    )
    mc_req = MonteCarloUQRequest(
        base_config=req,
        n_samples=5,
        variance_percent=5.0
    )
    mc_res = service.run_monte_carlo_uq(mc_req)
    
    assert mc_res["n_samples"] == 5
    assert mc_res["p10_peak_temp_C"] <= mc_res["p50_peak_temp_C"] <= mc_res["p90_peak_temp_C"]
    assert mc_res["confidence_interval_width_C"] >= 0.0
    assert len(mc_res["p10_temperature_history_C"]) == len(mc_res["time_points_s"])

def test_validation_api_endpoints():
    """FastAPI /api/validation/compare ve /api/simulations/monte-carlo-uq uç noktaları test edilir."""
    # 1. Simülasyon koştur
    sim_res = client.post("/api/simulations/run", json={
        "rows": 2,
        "cols": 1,
        "simulation_time_s": 20.0
    })
    assert sim_res.status_code == 200
    job_id = sim_res.json()["job_id"]
    
    # 2. Sensör CSV karşılaştırması yap
    csv_text = """time_s,temperature_C
0.0, 25.0
5.0, 35.0
10.0, 80.0
15.0, 350.0
20.0, 600.0
"""
    val_res = client.post("/api/validation/compare", json={
        "job_id": job_id,
        "csv_content": csv_text,
        "cell_id": 0
    })
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert "validation_score_percent" in val_data
    assert "rmse_C" in val_data
    assert val_data["job_id"] == job_id
    
    # 3. Monte Carlo UQ uç noktası
    mc_res = client.post("/api/simulations/monte-carlo-uq", json={
        "base_config": {
            "rows": 2,
            "cols": 1,
            "simulation_time_s": 20.0
        },
        "n_samples": 5,
        "variance_percent": 4.0
    })
    assert mc_res.status_code == 200
    mc_data = mc_res.json()
    assert "p10_peak_temp_C" in mc_data
    assert "p90_peak_temp_C" in mc_data
    assert mc_data["p10_peak_temp_C"] <= mc_data["p90_peak_temp_C"]
