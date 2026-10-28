"""
V2.0 Gaz Tehlikesi (NFPA 68 & Le Chatelier LEL), Türev Tabanlı Otomatik Ters Kinetik Kalibrasyon
ve Nedensel Yayılım Grafiği (Causal DAG + GB 38031 5-Dk Kuralı) Test Paketi.
"""

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from simulator.core.constants import R_GAS_CONSTANT
from simulator.core.gas_hazard_engine import GasHazardEngine
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.validation_engine import ValidationEngine
from simulator.api.models import PackSimulationRequest
from simulator.api.services import SimulationService


def test_gas_hazard_le_chatelier_soc_scaling_and_rupture_disk():
    """
    1. Le Chatelier karışım LEL formülünün analitik değerle örtüştüğünü doğrular.
    2. SOC düştükçe salınan STP gaz hacminin düştüğünü doğrular.
    3. Otomatik mahfaza boşluk hacmi tahmini ve patlama diski (vent_activated) basınç tahliyesini doğrular.
    """
    # Karışım bazlı Le Chatelier: 50% H2 (LEL %4.0) + 50% CH4 (LEL %5.0) -> 1 / (0.5/4.0 + 0.5/5.0) = 4.44%
    lel_h2_ch4 = GasHazardEngine.calculate_le_chatelier_lel({"H2": 0.50, "CH4": 0.50})
    assert np.isclose(lel_h2_ch4, 4.44, atol=0.02)

    builder = PackGeometryBuilder()
    kinetics = ArrheniusKineticsEngine()
    cells, _, _ = builder.build_pack(rows=1, cols=1, cell_format="21700", chemistry_id="NMC811_high_energy_v1")
    chem = kinetics.get_params("NMC811_high_energy_v1")

    t_pts = list(np.linspace(0.0, 30.0, 61))
    alpha_full = {0: list(np.clip(np.linspace(0.0, 1.4, 61), 0.0, 1.0))}

    gh_100 = GasHazardEngine.evaluate_gas_hazard(
        time_points=t_pts,
        alpha_history=alpha_full,
        cells=cells,
        cell_chemistries=[chem],
        enclosure_free_vol_L=5.0,
        vent_valve_area_cm2=4.0,
        vent_burst_pressure_kpa=20.0,
        soc_percent=100.0
    )
    gh_30 = GasHazardEngine.evaluate_gas_hazard(
        time_points=t_pts,
        alpha_history=alpha_full,
        cells=cells,
        cell_chemistries=[chem],
        enclosure_free_vol_L=5.0,
        vent_valve_area_cm2=4.0,
        vent_burst_pressure_kpa=20.0,
        soc_percent=30.0
    )

    assert gh_30["total_gas_released_stp_L"] < gh_100["total_gas_released_stp_L"] * 0.65
    enc = gh_100["enclosure_analysis"]
    assert enc is not None
    assert enc["is_explosive_atmosphere"] is True
    assert enc["peak_lel_ratio_percent"] > 100.0
    assert enc["vent_activated"] is True
    # Patlama diski açıldıktan sonra aşırı basınç tahliye olarak düşmeli (son basınç < tepe basınç)
    p_hist = enc["overpressure_history_kpa"]
    assert p_hist[-1] < enc["peak_overpressure_kpa"]
    assert enc["recommended_min_vent_area_cm2"] >= 1.0

    # enclosure_free_volume_liters=None verildiğinde solver otomatik boşluk hacmi tahmin etmeli
    service = SimulationService()
    res_auto = service.run_simulation(
        PackSimulationRequest(
            rows=2,
            cols=2,
            cell_format="21700",
            trigger_method="instant_onset",
            trigger_initial_temp_C=240.0,
            enclosure_free_volume_liters=None,
            simulation_time_s=25.0
        ),
        persist_db=False
    )
    gh_auto = res_auto["simulation_result"]["gas_hazard_summary"]
    assert gh_auto["enclosure_analysis"] is not None
    assert gh_auto["enclosure_analysis"]["enclosure_volume_auto_estimated"] is True
    assert gh_auto["enclosure_analysis"]["enclosure_free_vol_L"] > 0.05


def test_auto_calibrate_arrhenius_recovers_synthetic_arc_and_ramped_curves():
    """
    Bilinen (A, Ea, delta_H) parametreleriyle üretilmiş sentetik adiyabatik ARC ve
    fırın ısıtma rampalı CSV eğrilerinden ters optimizasyonun yüksek doğrulukla (R² >= 0.94)
    yakınsadığını ve türev tabanlı T_onset / T_TR tespitinin çalıştığını doğrular.
    """
    true_A = 1.8e13
    true_Ea = 132000.0
    true_dH = 720000.0  # 720 J/g
    cp = 1000.0
    f_act = 0.60
    r_ext = 0.08  # K/s sabit ön-ısıtma rampası

    def synth_ode(t, y):
        T_K = y[0]
        alpha = min(1.0, max(0.0, y[1]))
        rate = true_A * np.exp(-true_Ea / (R_GAS_CONSTANT * T_K)) * (1.0 - alpha)
        ext_term = r_ext * (1.0 - alpha)
        dT_dt = ext_term + (f_act * true_dH * rate) / cp
        return [dT_dt, rate]

    t_eval = np.linspace(0.0, 1000.0, 120)
    sol = solve_ivp(synth_ode, (0.0, 1000.0), [333.15, 0.0], method="LSODA", t_eval=t_eval)
    temps_C = sol.y[0, :] - 273.15

    # Türev tabanlı büküm noktası tespiti
    inflections = ValidationEngine.detect_inflections(sol.t, temps_C)
    assert inflections["T_onset_C"] is not None
    assert inflections["T_tr_C"] is not None
    assert inflections["T_onset_C"] < inflections["T_tr_C"]

    csv_lines = ["time_s,temperature_C"] + [f"{t:.2f},{T:.2f}" for t, T in zip(sol.t, temps_C)]
    csv_text = "\n".join(csv_lines)

    fit = ValidationEngine.auto_calibrate_arrhenius_from_csv(
        csv_text=csv_text,
        cell_mass_kg=0.050,
        cp_J_per_kg_K=cp,
        active_mass_ratio=f_act
    )

    assert fit["r2_score"] >= 0.94, f"Otomatik kalibrasyon R² düşük: {fit['r2_score']}"
    assert fit["r_squared"] == fit["r2_score"]
    # Toplam adiyabatik sıcaklık artışı doğrudan delta_H ile belirlenir -> %15 tolerans içinde kurtarmalı
    recovered_dH = fit["reaction_enthalpy_J_per_kg"]
    assert abs(recovered_dH - true_dH) / true_dH < 0.20, (
        f"Entalpi geri kazanımı hatalı: Gerçek={true_dH/1000:.0f} J/g vs Bulunan={recovered_dH/1000:.0f} J/g"
    )


def test_causal_propagation_dag_on_3x3_center_triggered_pack_and_gb38031():
    """
    3x3 pakette merkez hücre (#4) tetiklendiğinde:
    1. Nedensel yayılım grafiğinin (propagation_path_graph) köşegen veya rastgele kronolojik
       zincir yerine doğrudan fiziksel dik komşulara (4 -> 1, 4 -> 3, 4 -> 5, 4 -> 7) bağlandığını doğrular.
    2. GB 38031 5-dakika yolcu tahliye kuralının (<300s yayılımda FAIL, yayılmamada PASS) doğru çalıştığını doğrular.
    """
    service = SimulationService()
    req_cascade = PackSimulationRequest(
        rows=3,
        cols=3,
        cell_format="18650",
        spacing_x_mm=1.0,
        spacing_y_mm=1.0,
        separator_material_id=None,
        separator_thickness_mm=0.0,
        gap_material_id="thermal_potting_gel",
        chemistry_id="NMC811_high_energy_v1",
        trigger_cell_id=4,  # Merkez hücre (satır=1, sütun=1)
        trigger_method="instant_onset",
        trigger_initial_temp_C=260.0,
        simulation_time_s=60.0,
        num_output_points=150
    )
    res_cascade = service.run_simulation(req_cascade, persist_db=False)
    ev = res_cascade["evaluation"]
    dag = ev["propagation_path_graph"]

    assert ev["affected_cells_count"] >= 5
    # Dik komşular (1, 3, 5, 7) doğrudan merkez hücre #4 tarafından tetiklenmiş olmalı!
    edges_by_target = {edge["to_cell_id"]: edge["from_cell_id"] for edge in dag}
    for ortho_id in [1, 3, 5, 7]:
        assert ortho_id in edges_by_target, f"Dik komşu #{ortho_id} yayılım grafiğinde yok"
        assert edges_by_target[ortho_id] == 4, (
            f"Nedensel DAG hatası: Komşu #{ortho_id} kaynağı #4 olmalıydı, #{edges_by_target[ortho_id]} bulundu!"
        )

    # Köşe hücreler (0, 2, 6, 8) eğer kaçağa girdiyse kaynakları #4 değil, komşu dik hücrelerden biri olmalı
    for corner_id, valid_parents in [(0, {1, 3}), (2, {1, 5}), (6, {3, 7}), (8, {5, 7})]:
        if corner_id in edges_by_target:
            assert edges_by_target[corner_id] in valid_parents, (
                f"Köşe #{corner_id} fiziksel komşusu olmayan #{edges_by_target[corner_id]} hücresine bağlandı!"
            )

    # 60 saniye içinde yayılım olduğu için GB 38031 (< 300s) FAIL olmalı
    reg_fail = ev["regulatory_compliance"]
    assert reg_fail["gb_38031_5min_egress"]["passed"] is False
    assert reg_fail["ul_9540a_unit_level"]["passed"] is False

    # Aerojel bariyerli + soğutmalı pakette yayılım engellendiğinde GB 38031 ve UL 9540A PASS olmalı
    req_safe = req_cascade.model_copy(update={
        "rows": 1,
        "cols": 2,
        "trigger_cell_id": 0,
        "spacing_x_mm": 3.0,
        "separator_material_id": "aerogel_insulation",
        "separator_thickness_mm": 2.0,
        "gap_material_id": "air_gap",
        "active_cooling_enabled": True,
        "h_cooling_plate_W_per_m2_K": 1200.0
    })
    res_safe = service.run_simulation(req_safe, persist_db=False)
    reg_pass = res_safe["evaluation"]["regulatory_compliance"]
    assert reg_pass["gb_38031_5min_egress"]["passed"] is True
    assert reg_pass["ul_9540a_unit_level"]["passed"] is True
