"""
V2.0 SQLite Kalıcılık (Sunucu Yeniden Başlatma Round-Trip), Tembel (On-Demand) PDF Üretimi,
Proje CRUD, Run A/B Kıyaslama, 2D Grid Sweep, Tornado Duyarlılık, 6 Endüstriyel Preset ve
Canlı SSE İlerleme Akışı Test Paketi.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from simulator.api.app import app
from simulator.api.models import PackSimulationRequest
from simulator.api.services import SimulationService
from simulator.persistence.database import DatabaseRepository


def test_sqlite_server_restart_roundtrip_compare_and_lazy_pdf(tmp_path):
    """
    Simüle edilmiş sunucu yeniden başlatmasında (bellek önbelleği sıfırlanmış yeni SimulationService):
    1. SQLite'tan tam kaydın (simulation_result + evaluation + request_config) kayıpsız yüklendiğini,
    2. İki geçmiş koşunun (Run A vs Run B) yeniden başlatma sonrasında dahi kıyaslanabildiğini,
    3. Başlangıçta diskte üretilmeyen PDF raporunun talep anında (lazy on-demand) hatasız üretildiğini doğrular.
    """
    db_file = str(tmp_path / "restart_test.db")

    # Oturum 1: İki farklı simülasyon çalıştır (generate_pdf=False varsayılan)
    svc_session1 = SimulationService()
    svc_session1.db = DatabaseRepository(db_path=db_file)
    svc_session1.report_generator.output_dir = str(tmp_path / "reports")
    Path(svc_session1.report_generator.output_dir).mkdir(parents=True, exist_ok=True)

    req_a = PackSimulationRequest(
        rows=1, cols=2, cell_format="18650", spacing_x_mm=1.5,
        separator_material_id=None, separator_thickness_mm=0.0,
        trigger_method="instant_onset", trigger_initial_temp_C=240.0,
        simulation_time_s=25.0, num_output_points=60
    )
    req_b = req_a.model_copy(update={
        "spacing_x_mm": 3.5,
        "separator_material_id": "aerogel_insulation",
        "separator_thickness_mm": 1.5
    })

    rec_a = svc_session1.run_simulation(req_a)
    rec_b = svc_session1.run_simulation(req_b)

    # Tembel PDF doğrulaması: Henüz rapor çağrılmadığı için pdf_report_path None olmalı
    assert rec_a["pdf_report_path"] is None
    assert rec_b["pdf_report_path"] is None

    # Oturum 2: Sunucu yeniden başladı (_results_store tamamen boş!)
    svc_session2 = SimulationService()
    svc_session2.db = DatabaseRepository(db_path=db_file)
    svc_session2.report_generator.output_dir = str(tmp_path / "reports")
    assert len(svc_session2._results_store) == 0

    loaded_a = svc_session2.get_result(rec_a["job_id"])
    assert loaded_a is not None
    assert loaded_a["evaluation"]["peak_module_temp_C"] == rec_a["evaluation"]["peak_module_temp_C"]
    assert loaded_a["request_config"]["spacing_x_mm"] == 1.5

    # Run A vs Run B karşılaştırması SQLite kayıtlarından sorunsuz çalışmalı
    comp = svc_session2.compare_runs(rec_a["job_id"], rec_b["job_id"])
    assert comp["job_a_id"] == rec_a["job_id"]
    assert comp["job_b_id"] == rec_b["job_id"]
    assert "delta_peak_temp_C" in comp
    assert "delta_mass_kg" in comp
    assert len(comp["run_a"]["trigger_temp_history"]) == 100

    # Lazy PDF üretimi SQLite'tan yüklenen kayıt üzerinde hatasız çalışmalı
    pdf_path = svc_session2.get_or_create_pdf_report(rec_a["job_id"])
    assert Path(pdf_path).exists()
    assert Path(pdf_path).stat().st_size > 5000


def test_api_projects_crud_compare_2d_grid_tornado_and_sse():
    """
    FastAPI uç noktalarını uçtan uca doğrular:
    - /api/projects (POST, GET, list, DELETE)
    - /api/simulations/design-study-2d + /api/tasks/{task_id}/stream (SSE)
    - /api/simulations/sensitivity (Tornado OAT sıralaması)
    - /api/simulations/compare
    """
    client = TestClient(app)

    # 1. Proje Kaydet / Listele / Getir / Sil
    proj_payload = {
        "name": "Test_4680_Paket_Rev1",
        "description": "Otomatik birim testi projesi",
        "payload": {"rows": 2, "cols": 3, "cell_format": "4680", "chemistry_id": "NCA_high_power_v1"}
    }
    res_save = client.post("/api/projects", json=proj_payload)
    assert res_save.status_code == 200
    proj_id = res_save.json()["project_id"]

    res_list = client.get("/api/projects")
    assert res_list.status_code == 200
    projects = res_list.json()["projects"]
    matching = [p for p in projects if p["project_id"] == proj_id]
    assert len(matching) == 1
    assert matching[0]["config_payload"]["cell_format"] == "4680"

    res_get = client.get(f"/api/projects/{proj_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Test_4680_Paket_Rev1"

    res_del = client.delete(f"/api/projects/{proj_id}")
    assert res_del.status_code == 200

    # 2. 2D Parametrik Izgara Taraması + Canlı SSE Görev Takibi
    task_id = "test_sse_grid_2d_001"
    grid_req = {
        "base_config": {
            "rows": 1,
            "cols": 2,
            "cell_format": "18650",
            "chemistry_id": "NMC_generic_v1",
            "separator_material_id": "mica_sheet",
            "trigger_method": "instant_onset",
            "trigger_initial_temp_C": 235.0,
            "simulation_time_s": 20.0,
            "num_output_points": 50
        },
        "param_x": "spacing_x_mm",
        "values_x": [1.5, 3.0],
        "param_y": "separator_thickness_mm",
        "values_y": [0.5, 1.5],
        "task_id": task_id
    }
    res_2d = client.post("/api/simulations/design-study-2d", json=grid_req)
    assert res_2d.status_code == 200
    data_2d = res_2d.json()
    assert len(data_2d["matrix_peak_temp_C"]) == 2
    assert len(data_2d["matrix_risk_score"][0]) == 2
    assert len(data_2d["cases"]) == 4

    # Görev ilerleme durumu COMPLETED (%100) olmalı ve SSE stream gerçek event döndürmeli
    res_task = client.get(f"/api/tasks/{task_id}")
    assert res_task.status_code == 200
    assert res_task.json()["status"] == "COMPLETED"
    assert res_task.json()["progress_percent"] == 100.0

    with client.stream("GET", f"/api/tasks/{task_id}/stream") as sse_resp:
        assert sse_resp.status_code == 200
        lines = [line for line in sse_resp.iter_lines() if line.startswith("data: ")]
        assert len(lines) >= 1
        event_obj = json.loads(lines[-1][len("data: "):])
        assert event_obj["status"] == "COMPLETED"
        assert event_obj["completed"] == 4

    # 3. 2D taramadaki iki uç vakayı /api/simulations/compare üzerinden kıyasla
    job_a = data_2d["cases"][0]["job_id"]
    job_b = data_2d["cases"][-1]["job_id"]
    res_cmp = client.get(f"/api/simulations/compare?job_a={job_a}&job_b={job_b}")
    assert res_cmp.status_code == 200
    cmp_json = res_cmp.json()
    assert "delta_metrics" in cmp_json
    assert "run_a" in cmp_json and "run_b" in cmp_json

    # 4. Tornado OAT Hassasiyet Analizi
    sens_req = {
        "base_config": grid_req["base_config"],
        "perturbation_percent": 20.0,
        "task_id": "test_sse_tornado_001"
    }
    res_sens = client.post("/api/simulations/sensitivity", json=sens_req)
    assert res_sens.status_code == 200
    sens_data = res_sens.json()
    assert len(sens_data["parameters_ranked"]) >= 4
    # Tornado listesi azalan temp_swing_C sırasıyla dizilmiş olmalı
    swings = [item["temp_swing_C"] for item in sens_data["parameters_ranked"]]
    assert swings == sorted(swings, reverse=True)


def test_all_six_industrial_presets_and_custom_sub_reactions():
    """
    1. /api/presets uç noktasındaki 6 endüstriyel şablonun tamamının geçerli olduğunu ve
       çözücüden hatasız geçtiğini doğrular.
    2. custom_sub_reactions ile gönderilen 4-kademeli özel kinetik tablosunun hatasız
       enjekte edilip çalıştığını doğrular.
    """
    client = TestClient(app)
    res_presets = client.get("/api/presets")
    assert res_presets.status_code == 200
    presets = res_presets.json()["presets"]
    assert len(presets) == 6

    for preset in presets:
        cfg = dict(preset["config"])
        # Test hızı için çıkış adımını ve süreyi makul tutarak tüm 6 şablonu gerçek çözücüde doğrula
        cfg["simulation_time_s"] = min(float(cfg.get("simulation_time_s", 20.0)), 15.0)
        cfg["num_output_points"] = 50
        res_run = client.post("/api/simulations/run", json=cfg)
        assert res_run.status_code == 200, f"Preset '{preset['preset_id']}' başarısız: {res_run.text}"
        assert res_run.json()["success"] is True

    # Özel 4-kademeli alt reaksiyon enjeksiyonu testi
    custom_multi_payload = {
        "rows": 1,
        "cols": 1,
        "cell_format": "21700",
        "chemistry_id": "NMC811_high_energy_v1",
        "trigger_method": "instant_onset",
        "trigger_initial_temp_C": 230.0,
        "simulation_time_s": 20.0,
        "num_output_points": 50,
        "advanced_physics_enabled": True,
        "nodal_model": "core_shell",
        "kinetics_model": "multi_reaction",
        "custom_sub_reactions": [
            {"key": "sei_decomposition", "name": "SEI", "A_per_s": 1.67e15, "Ea_J_per_mol": 135000.0, "delta_H_J_per_kg": 257000.0, "n": 1.0, "m_autocatalytic": 0.0, "T_onset_K": 353.15},
            {"key": "anode_electrolyte", "name": "Anot", "A_per_s": 2.5e13, "Ea_J_per_mol": 135000.0, "delta_H_J_per_kg": 850000.0, "n": 1.0, "m_autocatalytic": 0.0, "T_onset_K": 393.15},
            {"key": "separator_melting", "name": "Separator", "A_per_s": 1.5e16, "Ea_J_per_mol": 138000.0, "delta_H_J_per_kg": -48000.0, "n": 1.0, "m_autocatalytic": 0.0, "T_onset_K": 403.15},
            {"key": "cathode_decomposition", "name": "Katot", "A_per_s": 1.8e13, "Ea_J_per_mol": 139000.0, "delta_H_J_per_kg": 780000.0, "n": 1.0, "m_autocatalytic": 0.75, "T_onset_K": 433.15}
        ]
    }
    res_custom_multi = client.post("/api/simulations/run", json=custom_multi_payload)
    assert res_custom_multi.status_code == 200
    job_id = res_custom_multi.json()["job_id"]
    res_full = client.get(f"/api/simulations/{job_id}/results")
    assert res_full.status_code == 200
    assert "SEI" in res_full.json()["simulation_result"]["sub_alpha_history"]["0"]
