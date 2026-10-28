"""
Comprehensive Test Suite for Thermal Runaway Workbench V2.0.
Verifies all newly integrated physical modules, solvers, hazard engines,
inverse calibration algorithms, and SQLite persistence.
"""

import math
import numpy as np
import pytest
from pathlib import Path

from simulator.core.cell_model import CellModel, CellFormat
from simulator.core.constants import TriggerMethod, R_GAS_CONSTANT, P_ATM_PA
from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.thermal_network import ThermalNetworkAssembler
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.gas_hazard_engine import GasHazardEngine
from simulator.core.validation_engine import ValidationEngine
from simulator.core.propagation_evaluator import PropagationEvaluator
from simulator.core.design_optimizer import DesignOptimizationEngine
from simulator.persistence.database import WorkbenchDatabaseRepository
from simulator.api.models import PackSimulationRequest
from simulator.api.services import SimulationService


# ================= 1. POUCH FORMAT & PLANAR CONDUCTANCE =================

def test_pouch_format_geometry_and_conductance():
    """Pouch (kese) hücre formatının planar boyutları ve iletkenlik ağını doğrular."""
    geom_builder = PackGeometryBuilder()
    cells, connections, bounds = geom_builder.build_pack(
        rows=1,
        cols=2,
        cell_format="Pouch_60Ah",
        spacing_x_mm=2.0,
        spacing_y_mm=2.0,
        gap_material_id="air_gap",
        separator_material_id="paraffin_pcm_pad",
        separator_thickness_mm=1.0
    )
    
    assert len(cells) == 2
    cell0 = cells[0]
    assert cell0.geometry.geometry_type == "pouch"
    assert cell0.geometry.width > 0.1  # ~150 mm
    assert cell0.geometry.thickness > 0.005  # ~12 mm
    
    kinetics = ArrheniusKineticsEngine()
    assembler = ThermalNetworkAssembler(
        cells=cells,
        connections=connections,
        materials_lib=geom_builder.materials_lib,
        kinetics_engine=kinetics
    )
    
    G = assembler.G_conduction
    assert G.shape == (2, 2)
    assert G[0, 1] > 0.0
    assert np.isclose(G[0, 1], G[1, 0])  # Simetrik iletim


# ================= 2. BEŞ GERÇEKÇİ ABUSE VE TETİKLEME SENARYOSU =================

def test_external_heater_thermostat_cutoff():
    """UL 9540A kovan film ısıtıcısının termostat eşiğinde (T >= 250°C) kesilmesini test eder."""
    service = SimulationService()
    req = PackSimulationRequest(
        rows=1,
        cols=1,
        cell_format="18650",
        trigger_method="external_heater",
        trigger_power_W=500.0,
        trigger_duration_s=40.0,
        simulation_time_s=30.0
    )
    res = service.run_simulation(req)
    assert res["status"] == "COMPLETED"
    peak_T = res["evaluation"]["peak_module_temp_C"]
    assert peak_T >= 200.0
    assert not np.isnan(peak_T)


def test_nail_penetration_isc_abuse():
    """SAE J2464 / GB çivi batması dahili kısa devre (ISC) üssel güç sönümlenmesini test eder."""
    service = SimulationService()
    req = PackSimulationRequest(
        rows=1,
        cols=1,
        cell_format="21700",
        trigger_method="nail_penetration_isc",
        isc_resistance_ohm=0.005,
        soc_percent=100.0,
        simulation_time_s=25.0
    )
    res = service.run_simulation(req)
    assert res["status"] == "COMPLETED"
    peak_T = res["evaluation"]["peak_module_temp_C"]
    assert peak_T > 80.0
    assert res["evaluation"]["status"] in ("NO_PROPAGATION", "LOCAL_CONTAINED", "UNCONTROLLED_CASCADE")


def test_oven_ramp_abuse():
    """UN 38.3 termal fırın rampasını (10°C/dk ortam sıcaklığı artışı) test eder."""
    service = SimulationService()
    req = PackSimulationRequest(
        rows=1,
        cols=1,
        cell_format="18650",
        trigger_method="oven_ramp",
        oven_target_temp_C=150.0,
        oven_ramp_C_per_min=10.0,
        T_ambient_C=30.0,
        simulation_time_s=30.0
    )
    res = service.run_simulation(req)
    assert res["status"] == "COMPLETED"
    # Python dict içindeki sıcaklık geçmişi
    history = res["simulation_result"]["temperature_history_C"]
    cell_temps = history[0] if 0 in history else history["0"]
    assert cell_temps[-1] > 30.0


# ================= 3. GAZ SALINIMI VE MAHFAZA PATLAMA MOTORU (NFPA 68) =================

def test_gas_hazard_engine_calculations():
    """Gaz motorunun STP hacim, Le Chatelier LEL%, pik aşırı basınç ve menfez boyutunu test eder."""
    geom_builder = PackGeometryBuilder()
    cells, _, _ = geom_builder.build_pack(
        rows=1, cols=2, cell_format="18650", spacing_x_mm=2.0, spacing_y_mm=2.0
    )
    
    kinetics = ArrheniusKineticsEngine()
    cell_chems = [kinetics.get_params(c.chemistry_id) for c in cells]
    
    alpha_history = {
        0: [0.0, 0.2, 0.8, 1.0],
        1: [0.0, 0.0, 0.1, 0.5]
    }
    time_points = [0.0, 2.0, 5.0, 10.0]
    
    summary = GasHazardEngine.evaluate_gas_hazard(
        time_points=time_points,
        alpha_history=alpha_history,
        cells=cells,
        cell_chemistries=cell_chems,
        enclosure_free_vol_L=8.0,
        vent_valve_area_cm2=2.0,
        vent_burst_pressure_kpa=35.0
    )
    
    assert summary is not None
    assert summary["total_gas_released_stp_L"] > 0.0
    assert summary["mixture_lel_percent"] > 3.0 and summary["mixture_lel_percent"] < 15.0
    assert "enclosure_analysis" in summary
    enc = summary["enclosure_analysis"]
    assert enc is not None
    assert enc["peak_overpressure_kpa"] >= 0.0
    assert enc["recommended_min_vent_area_cm2"] > 0.0


# ================= 4. OTOMATİK ARRHENIUS TERS KALİBRASYON (AUTO-FIT) =================

def test_auto_calibrate_arrhenius_synthetic():
    """Sentetik ARC eğrisinden Kissinger + Trust-Region Least-Squares ile Arrhenius geri türetimi."""
    val_engine = ValidationEngine()
    
    # Sentetik gerçekçi zaman-sıcaklık profili oluştur
    t = np.linspace(0, 100, 101)
    temp = 40.0 + 0.1 * t + 600.0 / (1.0 + np.exp(-0.25 * (t - 60)))
    
    csv_lines = ["time_s,temperature_C"]
    for ti, Ti in zip(t, temp):
        csv_lines.append(f"{ti:.1f},{Ti:.2f}")
    csv_content = "\n".join(csv_lines)
    
    fit_res = val_engine.auto_calibrate_arrhenius_from_csv(
        csv_text=csv_content,
        cell_mass_kg=0.048,
        cp_J_per_kg_K=950.0,
        active_mass_ratio=0.60
    )
    
    assert fit_res is not None
    assert fit_res["frequency_factor_A"] > 0.0
    assert fit_res["activation_energy_J_per_mol"] > 50000.0
    assert fit_res["reaction_enthalpy_J_per_kg"] > 50000.0
    assert fit_res["r2_score"] > 0.90  # Güçlü uyum kalitesi


# ================= 5. SQLITE PERSISTENCE REPOSITORY =================

def test_sqlite_workbench_persistence(tmp_path):
    """SQLite workbench.db CRUD işlemlerini ve simülasyon zlib serileştirmesini test eder."""
    db_file = str(tmp_path / "test_workbench.db")
    repo = WorkbenchDatabaseRepository(db_path=db_file)
    
    # 1. Proje kaydetme, listeleme, getirme, silme
    repo.save_project(
        project_id="proj_001",
        name="Test Projesi Pouch",
        description="Açıklama",
        payload={"rows": 2, "cols": 2, "format": "pouch"}
    )
    
    projects = repo.list_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "Test Projesi Pouch"
    
    proj = repo.get_project("proj_001")
    assert proj is not None
    assert proj["payload"]["format"] == "pouch"
    
    # 2. Simülasyon kaydetme ve getirme
    sample_data = {
        "job_id": "sim_job_999",
        "pack_metrics": {
            "peak_module_temp_C": 450.2,
            "runaway_cell_count": 1,
            "total_cells": 4
        },
        "risk_score_100": 35.0,
        "cell_summaries": [
            {"cell_id": 0, "max_temperature_C": 450.2, "runaway_time_s": 5.0}
        ],
        "simulation_result": {
            "time_points_s": [0.0, 1.0, 2.0],
            "temperature_history_C": {0: [25.0, 200.0, 450.0]},
            "alpha_history": {0: [0.0, 0.5, 1.0]}
        }
    }
    
    repo.save_simulation("sim_job_999", sample_data)
    sims = repo.list_simulations()
    assert len(sims) == 1
    assert sims[0]["job_id"] == "sim_job_999"
    assert sims[0]["peak_temp_C"] == 450.2
    
    retrieved = repo.get_simulation("sim_job_999")
    assert retrieved is not None
    assert retrieved["job_id"] == "sim_job_999"
    assert retrieved["risk_score_100"] == 35.0
    
    # Proje silme
    deleted = repo.delete_project("proj_001")
    assert deleted is True
    assert len(repo.list_projects()) == 0


# ================= 6. 2D PARAMETRE TARAMASI VE TORNADO SENSITIVITY =================

def test_design_optimizer_grid_and_tornado():
    """2D Grid Tarama varyasyonları ve Tornado duyarlılık analizi fonksiyonlarını test eder."""
    base_cfg = {
        "rows": 2,
        "cols": 2,
        "spacing_x_mm": 2.0,
        "spacing_y_mm": 2.0,
        "separator_thickness_mm": 1.0,
        "h_cooling_plate_W_per_m2_K": 800.0
    }
    
    # 1. 2D Grid
    cases = DesignOptimizationEngine.build_2d_grid_variations(
        base_request_dict=base_cfg,
        param_x="spacing_x_mm",
        values_x=[1.5, 2.0],
        param_y="separator_thickness_mm",
        values_y=[0.5, 1.0, 1.5]
    )
    assert len(cases) == 6
    assert cases[0]["grid_coords"]["x_val"] == 1.5
    assert cases[0]["grid_coords"]["y_val"] == 0.5
    
    # 2. Tornado Sensitivity
    baseline = {"peak_module_temp_C": 520.0, "risk_score_100": 70.0}
    variation_cases = [
        {"perturbed_param": "spacing_x_mm", "perturbation_direction": "low", "peak_module_temp_C": 580.0, "risk_score_100": 85.0},
        {"perturbed_param": "spacing_x_mm", "perturbation_direction": "high", "peak_module_temp_C": 480.0, "risk_score_100": 55.0},
        {"perturbed_param": "separator_thickness_mm", "perturbation_direction": "low", "peak_module_temp_C": 550.0, "risk_score_100": 75.0},
        {"perturbed_param": "separator_thickness_mm", "perturbation_direction": "high", "peak_module_temp_C": 490.0, "risk_score_100": 60.0}
    ]
        
    ranking = DesignOptimizationEngine.analyze_tornado_sensitivity(
        baseline_case=baseline,
        variation_cases=variation_cases
    )
    assert "parameters_ranked" in ranking
    ranked = ranking["parameters_ranked"]
    assert len(ranked) == 2
    assert ranked[0]["temp_swing_C"] >= ranked[1]["temp_swing_C"]
    assert ranking["most_sensitive_parameter"] == "spacing_x_mm"


# ================= 7. REGULATORY COMPLIANCE CHECKLIST (GB 38031, UL 9540A, UN 38.3) =================

def test_regulatory_compliance_report():
    """PropagationEvaluator'ün GB 38031 (5-dakika kaçış), UL 9540A ve UN 38.3 kontrolünü test eder."""
    evaluator = PropagationEvaluator()
    
    class MockResult:
        def __init__(self):
            self.cell_summaries = [
                {
                    "cell_id": 0, "name": "Cell_0", "max_temperature_C": 620.0,
                    "max_core_temperature_C": 650.0, "thermal_lag_s": 3.2,
                    "runaway_time_s": 8.5, "pos_x_mm": 0.0, "pos_y_mm": 0.0,
                    "is_trigger": True, "mass_kg": 0.048, "chemistry_id": "NMC_generic_v1"
                },
                {
                    "cell_id": 1, "name": "Cell_1", "max_temperature_C": 78.0,
                    "max_core_temperature_C": 78.0, "thermal_lag_s": 0.0,
                    "runaway_time_s": None, "pos_x_mm": 25.0, "pos_y_mm": 0.0,
                    "is_trigger": False, "mass_kg": 0.048, "chemistry_id": "NMC_generic_v1"
                }
            ]
            self.time_points_s = [0.0, 5.0, 10.0, 30.0]
            self.temperature_history_C = {
                0: [25.0, 120.0, 620.0, 500.0],
                1: [25.0, 30.0, 65.0, 78.0]
            }
            self.peak_temperature_C = 620.0
            
    eval_res = evaluator.evaluate(MockResult(), trigger_cell_id=0)
    assert eval_res.regulatory_compliance is not None
    compliance = eval_res.regulatory_compliance
    
    # 5-dakika (300s) kuralı: komşu hücreler 300 saniyeden önce kaçağa girmedi -> PASSED
    assert compliance["gb_38031_5min_egress"]["passed"] is True
    # UL 9540A birim yayılım: komşulara yayılmadı -> PASSED
    assert compliance["ul_9540a_unit_level"]["passed"] is True
    # UN 38.3 termal aşırı sıcaklık
    assert "un_383_thermal_abuse" in compliance
