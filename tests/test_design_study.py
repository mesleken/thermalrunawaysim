"""
Tasarım Çalışması (Design Study) ve Gelişmiş Fizik Testleri
"""

from simulator.api.models import PackSimulationRequest, DesignStudyRequest
from simulator.api.services import SimulationService

def test_advanced_physics_injection():
    service = SimulationService()
    req = PackSimulationRequest(
        rows=2,
        cols=2,
        simulation_time_s=25.0,
        advanced_physics_enabled=True,
        custom_A_pre_exponential=5.0e12,
        custom_Ea_J_per_mol=125000.0,
        custom_reaction_order_n=1.2,
        custom_delta_H_J_per_g=850.0,
        h_vent_W_per_m2_K=150.0,
        T_vent_gas_C=900.0,
        surface_emissivity=0.90
    )
    result = service.run_simulation(req)
    assert result["status"] == "COMPLETED"
    assert "evaluation" in result
    assert result["evaluation"]["peak_module_temp_C"] > 50.0

def test_spacing_design_study():
    service = SimulationService()
    base_req = PackSimulationRequest(
        rows=2,
        cols=2,
        simulation_time_s=25.0
    )
    study_req = DesignStudyRequest(
        sweep_type="spacing_sweep",
        base_config=base_req,
        sweep_values=[1.5, 3.5]
    )
    res = service.run_design_study(study_req)
    assert res["sweep_type"] == "spacing_sweep"
    assert len(res["cases"]) == 2
    assert any(c["is_recommended"] for c in res["cases"])
    # 3.5mm spacing should have lower or equal peak temperature or risk score than 1.5mm
    case_15 = next(c for c in res["cases"] if "1.5" in c["case_name"])
    case_35 = next(c for c in res["cases"] if "3.5" in c["case_name"])
    assert case_35["risk_score_100"] <= case_15["risk_score_100"]

def test_separator_design_study():
    service = SimulationService()
    base_req = PackSimulationRequest(
        rows=2,
        cols=2,
        simulation_time_s=25.0
    )
    study_req = DesignStudyRequest(
        sweep_type="separator_sweep",
        base_config=base_req
    )
    res = service.run_design_study(study_req)
    assert res["sweep_type"] == "separator_sweep"
    assert len(res["cases"]) == 4
    assert any(c["is_recommended"] for c in res["cases"])
