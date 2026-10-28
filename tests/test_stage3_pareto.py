"""
Aşama 3: Kütle Ceza İndeksi ve Pareto Cephesi Analizörü Birim Testleri
"""

import pytest
from simulator.core.design_optimizer import calculate_module_mass, DesignOptimizationEngine
from simulator.api.models import PackSimulationRequest, DesignStudyRequest
from simulator.api.services import SimulationService


def test_calculate_module_mass_physical_consistency():
    # 1. Baz durum: Bariyersiz 2x2 silindirik 18650
    base_cfg = PackSimulationRequest(
        rows=2,
        cols=2,
        cell_format="18650",
        spacing_x_mm=2.0,
        spacing_y_mm=2.0,
        active_cooling_enabled=False
    )
    m_base = calculate_module_mass(base_cfg)
    assert m_base["total_mass_kg"] > 0.15  # 4 * 46g + enclosure
    assert m_base["barrier_mass_kg"] == 0.0

    # 2. Mika Bariyer (Yoğunluk 2100 kg/m3, 1.0 mm)
    mica_cfg = base_cfg.model_copy(deep=True)
    mica_cfg.separator_material_id = "mica_sheet"
    mica_cfg.separator_thickness_mm = 1.0
    m_mica = calculate_module_mass(mica_cfg)
    assert m_mica["barrier_mass_kg"] > 0.0
    assert m_mica["total_mass_kg"] > m_base["total_mass_kg"]

    # 3. Aerojel Bariyer (Yoğunluk 160 kg/m3, 1.0 mm)
    aerogel_cfg = base_cfg.model_copy(deep=True)
    aerogel_cfg.separator_material_id = "aerogel_insulation"
    aerogel_cfg.separator_thickness_mm = 1.0
    m_aero = calculate_module_mass(aerogel_cfg)
    assert m_aero["barrier_mass_kg"] > 0.0
    # Aerojel mikadan belirgin derecede hafif olmalıdır (160 vs 2100 kg/m3)
    assert m_aero["barrier_mass_kg"] < m_mica["barrier_mass_kg"]
    assert m_aero["total_mass_kg"] < m_mica["total_mass_kg"]

    # 4. Aktif Soğutma Plakası İlavesi
    cooling_cfg = base_cfg.model_copy(deep=True)
    cooling_cfg.active_cooling_enabled = True
    m_cooling = calculate_module_mass(cooling_cfg)
    assert m_cooling["cooling_mass_kg"] > 0.0
    assert m_cooling["total_mass_kg"] > m_base["total_mass_kg"]


def test_pareto_dominance_and_knee_point_algorithm():
    # Sentetik 4 vaka:
    # Vaka 0: Çok hafif ama çok riskli (Baz) -> Kütle: 5.0 kg, Risk: 90
    # Vaka 1: Ağır ve orta riskli -> Kütle: 6.5 kg, Risk: 40 (Vaka 2 tarafından domine edilir!)
    # Vaka 2: Vaka 1'den hem daha hafif hem daha güvenli -> Kütle: 5.4 kg, Risk: 20
    # Vaka 3: En güvenli ama en ağır -> Kütle: 7.0 kg, Risk: 10
    cases_mock = [
        {"case_index": 0, "case_name": "Baz Durum", "module_mass_kg": 5.0, "risk_score_100": 90.0},
        {"case_index": 1, "case_name": "Ağır Sub-optimal", "module_mass_kg": 6.5, "risk_score_100": 40.0},
        {"case_index": 2, "case_name": "Aerojel Optimum", "module_mass_kg": 5.4, "risk_score_100": 20.0},
        {"case_index": 3, "case_name": "Ultra Güvenli Ağır", "module_mass_kg": 7.0, "risk_score_100": 10.0},
    ]

    res = DesignOptimizationEngine.analyze_study(cases_mock, w_safety=0.6, w_mass=0.4)

    # Vaka 1, Vaka 2 tarafından domine edilmiştir (5.4 < 6.5 ve 20 < 40)
    assert cases_mock[1]["is_pareto_optimal"] is False
    # Vaka 0, 2, 3 Pareto cephesindedir
    assert cases_mock[0]["is_pareto_optimal"] is True
    assert cases_mock[2]["is_pareto_optimal"] is True
    assert cases_mock[3]["is_pareto_optimal"] is True

    assert res["pareto_front_indices"] == [0, 2, 3]
    # Knee point, kütle artışı ve risk düşüşü dengesi en iyi olan Vaka 2 olmalıdır
    assert res["knee_point_index"] == 2
    assert "Baz Durum" in res["summary"] or "Aerojel Optimum" in res["summary"]


def test_design_study_service_pareto_output():
    service = SimulationService()
    base_req = PackSimulationRequest(
        rows=2,
        cols=2,
        simulation_time_s=25.0
    )
    study_req = DesignStudyRequest(
        sweep_type="separator_sweep",
        base_config=base_req,
        w_safety=0.7,
        w_mass=0.3
    )
    study_res = service.run_design_study(study_req)

    assert "pareto_front_indices" in study_res
    assert len(study_res["pareto_front_indices"]) >= 1
    assert "knee_point_index" in study_res
    assert study_res["knee_point_index"] is not None
    assert "baseline_mass_kg" in study_res
    assert study_res["baseline_mass_kg"] > 0.0

    # Her vakanın kütle ve ceza metrikleri kontrolü
    for c in study_res["cases"]:
        assert "module_mass_kg" in c
        assert c["module_mass_kg"] > 0.0
        assert "mass_penalty_index_percent" in c
        assert "is_pareto_optimal" in c

    rec_case = study_res["cases"][study_res["recommended_case_index"]]
    assert rec_case["is_recommended"] is True
    assert rec_case["is_pareto_optimal"] is True
