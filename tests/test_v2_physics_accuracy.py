"""
V2.0 Fiziksel Doğruluk, Enerji Korunumu ve Çok-Kademeli Kinetik Test Paketi.
Core-Shell Forgez-Lin radyal direnci, adiyabatik enerji korunumu, aktif venting penceresi,
4-kademeli ardışık reaksiyon sırası, SOC ölçeklemesi (endotermik separatör değişmezliği),
Prizmatik/Pouch yönlü iletkenliği, PCM gizli ısı tamponu, bariyer termal bozunması ve
ISC elektriksel enerji korunumunu doğrular.
"""

import numpy as np
import pytest

from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.thermal_network import ThermalNetworkAssembler
from simulator.api.models import PackSimulationRequest
from simulator.api.services import SimulationService


def test_core_shell_adiabatic_energy_conservation_and_thermal_lag():
    """
    Adiyabatik (h_amb=0, emissivity=0, ejecta=0) tek hücrede Lumped ile Core-Shell
    modellerinin toplam ısıl sığa korunumunu (eşdeğer son denge sıcaklığı) ve
    Core-Shell Forgez-Lin radyal direncinin gerçekçi termal gecikme ürettiğini doğrular.
    """
    service = SimulationService()
    common_kwargs = dict(
        rows=1,
        cols=1,
        cell_format="21700",
        chemistry_id="NMC_generic_v1",
        h_ambient_W_per_m2_K=0.0,
        surface_emissivity=0.0,
        active_cooling_enabled=False,
        trigger_method="instant_onset",
        trigger_initial_temp_C=225.0,
        simulation_time_s=60.0,
        num_output_points=200,
        advanced_physics_enabled=True,
        kinetics_model="single_step",
        ejecta_mass_loss_ratio=0.0
    )

    res_lumped = service.run_simulation(
        PackSimulationRequest(**common_kwargs, nodal_model="lumped"),
        persist_db=False
    )
    res_cs = service.run_simulation(
        PackSimulationRequest(**common_kwargs, nodal_model="core_shell"),
        persist_db=False
    )

    t_lumped_end = res_lumped["simulation_result"]["temperature_history_C"][0][-1]
    t_shell_hist = np.array(res_cs["simulation_result"]["temperature_history_C"][0])
    t_core_hist = np.array(res_cs["simulation_result"]["core_temperature_history_C"][0])

    # 1. Radyal termal gecikme: Kaçak esnasında T_core, T_shell'den anlamlı derecede yüksek olmalı
    peak_core_shell_diff = float(np.max(t_core_hist - t_shell_hist))
    assert peak_core_shell_diff > 25.0, f"Core-Shell radyal gradyanı yetersiz: {peak_core_shell_diff:.2f} °C"

    # 2. Adiyabatik enerji korunumu: Reaksiyon tamamlandığında ve iç denge kurulduğunda
    # Lumped ve Core-Shell son denge sıcaklıkları birebir örtüşmelidir (< 1.5°C fark)
    assert abs(t_shell_hist[-1] - t_core_hist[-1]) < 1.0
    assert abs(t_shell_hist[-1] - t_lumped_end) < 1.5, (
        f"Adiyabatik enerji korunumu sapması: Lumped={t_lumped_end:.2f}°C vs CoreShell={t_shell_hist[-1]:.2f}°C"
    )


def test_active_venting_window_cuts_off_ghost_heating_after_burnout():
    """
    Ejecta kütle kaybı ve aktif venting penceresinin alpha >= 0.98 sonrasında
    komşu hücreye hayalet gaz jeti ısıtmasını (q_vent) sıfırladığını doğrular.
    """
    service = SimulationService()
    req = PackSimulationRequest(
        rows=1,
        cols=2,
        cell_format="18650",
        spacing_x_mm=6.0,
        spacing_y_mm=6.0,
        separator_material_id=None,
        separator_thickness_mm=0.0,
        chemistry_id="NMC811_high_energy_v1",
        trigger_cell_id=0,
        trigger_method="instant_onset",
        trigger_initial_temp_C=240.0,
        simulation_time_s=45.0,
        num_output_points=180,
        advanced_physics_enabled=True,
        nodal_model="lumped",
        kinetics_model="single_step",
        ejecta_mass_loss_ratio=0.18,
        h_vent_W_per_m2_K=250.0
    )
    res = service.run_simulation(req, persist_db=False)
    sim = res["simulation_result"]
    alpha_0 = np.array(sim["alpha_history"][0])
    q_vent_1 = np.array(sim["heat_flux_history_W"]["q_vent"][1])

    # Aktif venting sırasında (0.1 < alpha_0 < 0.9) komşu hücre #1 pozitif gaz jeti ısısı almalı
    active_mask = (alpha_0 > 0.10) & (alpha_0 < 0.90)
    if np.any(active_mask):
        assert np.max(q_vent_1[active_mask]) > 0.0

    # Hücre #0 tamamen tükendikten sonra (alpha_0 >= 0.985 ve komşu henüz kaçağa girmemişken)
    alpha_1 = np.array(sim["alpha_history"][1])
    burned_no_neighbor_vent = (alpha_0 >= 0.985) & (alpha_1 < 0.05)
    assert np.any(burned_no_neighbor_vent), "Test penceresinde tükenmiş durum gözlenmedi"
    assert np.allclose(q_vent_1[burned_no_neighbor_vent], 0.0, atol=1e-6), (
        "Hücre tükendikten (alpha >= 0.98) sonra hayalet gaz ısıtması devam ediyor!"
    )


def test_four_stage_kinetics_strict_temperature_ordering_and_soc_invariance():
    """
    1. 4-kademeli kinetikte kademeli sıcaklık taramasında reaksiyon aktivasyon sırasının
       T(SEI) < T(Anode) < T(Separator) < T(Cathode) olduğunu doğrular.
    2. SOC ölçeklemesinde (%25 vs %100) ekzotermik entalpilerin tek sefer ölçeklendiğini
       ve endotermik separatör erimesinin (delta_H < 0) SOC'den bağımsız kaldığını doğrular.
    """
    engine = ArrheniusKineticsEngine()
    for chem_id in ["NMC_generic_v1", "NMC811_high_energy_v1", "LFP_generic_v1"]:
        chem_100 = engine.get_params(chem_id)
        chem_25 = chem_100.apply_soc_scaling(25.0)

        # Tek-kademeli entalpi beklenen ölçekleme faktörü: 0.25 + 0.75 * (0.25^1.15)
        expected_factor = 0.25 + 0.75 * (0.25 ** 1.15)
        assert np.isclose(chem_25.delta_H / chem_100.delta_H, expected_factor, rtol=1e-5)

        for sr_100, sr_25 in zip(chem_100.sub_reactions, chem_25.sub_reactions):
            if sr_100.delta_H < 0:
                # Endotermik PE/PP separatör erimesi SOC'ye bağlı değişmemeli!
                assert np.isclose(sr_25.delta_H, sr_100.delta_H, rtol=1e-9)
                assert np.isclose(sr_25.Ea, sr_100.Ea, rtol=1e-9)
            else:
                # Ekzotermik alt reaksiyonlar çift ölçeklenmemeli, tam expected_factor kadar ölçeklenmeli!
                assert np.isclose(sr_25.delta_H / sr_100.delta_H, expected_factor, rtol=1e-5)

    # Kademeli fırın/ARC rampa simülasyonunda 4 alt reaksiyonun yarı-dönüşüm (alpha_k >= 0.25) sırası
    service = SimulationService()
    req = PackSimulationRequest(
        rows=1,
        cols=1,
        cell_format="18650",
        chemistry_id="NMC811_high_energy_v1",
        trigger_method="thermal_pulse",
        trigger_power_W=140.0,
        trigger_duration_s=90.0,
        h_ambient_W_per_m2_K=0.0,
        surface_emissivity=0.0,
        simulation_time_s=90.0,
        num_output_points=400,
        advanced_physics_enabled=True,
        nodal_model="lumped",
        kinetics_model="multi_reaction"
    )
    res = service.run_simulation(req, persist_db=False)
    sim = res["simulation_result"]
    temps = np.array(sim["temperature_history_C"][0])
    subs = sim["sub_alpha_history"][0]

    def temp_at_threshold(alpha_list, thresh=0.01):
        arr = np.array(alpha_list)
        idxs = np.where(arr >= thresh)[0]
        assert len(idxs) > 0, "Alt reaksiyon eşiğe ulaşmadı"
        return float(temps[idxs[0]])

    t_sei = temp_at_threshold(subs["SEI"], thresh=0.01)
    t_sep = temp_at_threshold(subs["separator"], thresh=0.01)
    t_cat = temp_at_threshold(subs["cathode"], thresh=0.01)

    # 4 alt reaksiyonun teorik onset sıcaklık sıralaması: SEI < Anode < Separator < Cathode
    sub_map = {sr.key: sr for sr in chem_100.sub_reactions}
    assert sub_map["sei_decomposition"].T_onset_K < sub_map["anode_electrolyte"].T_onset_K < sub_map["separator_melting"].T_onset_K <= sub_map["cathode_decomposition"].T_onset_K

    # Simülasyon aktivasyon sırası: Erken SEI çözünmesi < Separatör erimesi < Katot termal kaçağı
    assert t_sei < t_sep < t_cat, (
        f"Fiziksel reaksiyon sırası ihlali: T_SEI={t_sei:.1f}°C, T_sep={t_sep:.1f}°C, T_cat={t_cat:.1f}°C"
    )
    assert 120.0 <= t_sep <= 160.0, (
        f"Separatör erime sıcaklığı fizik dışı bölgede: T_sep={t_sep:.1f}°C, T_cat={t_cat:.1f}°C"
    )


def test_soc_20_vs_100_runaway_severity():
    """%20 SOC'deki hücrenin %100 SOC'ye kıyasla çok daha düşük tepe sıcaklık ürettiğini doğrular."""
    service = SimulationService()
    base = dict(
        rows=1,
        cols=1,
        cell_format="21700",
        chemistry_id="NMC811_high_energy_v1",
        trigger_method="thermal_pulse",
        trigger_power_W=3500.0,
        trigger_duration_s=4.0,
        simulation_time_s=40.0
    )
    res_100 = service.run_simulation(PackSimulationRequest(**base, soc_percent=100.0), persist_db=False)
    res_20 = service.run_simulation(PackSimulationRequest(**base, soc_percent=20.0), persist_db=False)

    peak_100 = res_100["evaluation"]["peak_module_temp_C"]
    peak_20 = res_20["evaluation"]["peak_module_temp_C"]
    assert peak_20 < peak_100 - 150.0, f"SOC etkisi yetersiz: SOC100={peak_100:.1f}°C vs SOC20={peak_20:.1f}°C"


def test_prismatic_and_pouch_directional_contact_areas_and_pcm_buffering():
    """
    1. Prizmatik ve Pouch hücrelerde Y istifleme yönündeki geniş yüzey iletkenliğinin (G_y),
       X yan kenar iletkenliğinden (G_x) anlamlı derecede büyük olduğunu doğrular.
    2. Parafin PCM dolgunun (gizli ısı L_f=185 kJ/kg @ 52°C) komşu hücre ısınmasını tamponladığını doğrular.
    """
    builder = PackGeometryBuilder()
    kinetics = ArrheniusKineticsEngine()

    for fmt in ["Prismatic_50Ah", "Pouch_60Ah"]:
        cells, conns, _ = builder.build_pack(
            rows=2,
            cols=2,
            cell_format=fmt,
            spacing_x_mm=2.0,
            spacing_y_mm=2.0,
            gap_material_id="air_gap"
        )
        net = ThermalNetworkAssembler(
            cells, conns, builder.materials_lib, kinetics, busbar_conductance_W_per_K=0.0
        )
        # Hücre 0 (0,0) -> Hücre 1 (0,1) X komşusu (dar kenar); Hücre 0 (0,0) -> Hücre 2 (1,0) Y komşusu (geniş yüz)
        g_x = net.G_conduction[0, 1]
        g_y = net.G_conduction[0, 2]
        assert g_y > g_x * 4.0, f"{fmt} için Y geniş yüzey iletkenliği ({g_y:.4f}) X dar kenardan ({g_x:.4f}) büyük olmalı!"

    # PCM gizli ısı tamponlama testi (52°C erime bölgesinden geçişte komşu hücre sıcaklığı daha düşük kalmalı)
    service = SimulationService()
    common_cfg = dict(
        rows=1,
        cols=2,
        cell_format="21700",
        spacing_x_mm=2.5,
        spacing_y_mm=2.5,
        chemistry_id="NMC_generic_v1",
        trigger_cell_id=0,
        trigger_method="thermal_pulse",
        trigger_power_W=650.0,
        trigger_duration_s=12.0,
        simulation_time_s=40.0
    )
    # Aynı ısıl iletkenliğe (k=1.2 W/mK, rho=920, cp=2100) sahip ancak gizli ısısız referans dolgu vs gerçek PCM
    no_latent_gap = {
        "name": "Sensible_Only_Pad",
        "k_thermal_W_per_m_K": 1.2,
        "density_kg_per_m3": 920.0,
        "cp_J_per_kg_K": 2100.0,
        "latent_heat_J_per_kg": 0.0
    }
    res_sensible = service.run_simulation(
        PackSimulationRequest(**common_cfg, custom_gap_params=no_latent_gap),
        persist_db=False
    )
    res_pcm = service.run_simulation(
        PackSimulationRequest(**common_cfg, gap_material_id="paraffin_pcm_pad"),
        persist_db=False
    )

    t1_sensible_max = max(res_sensible["simulation_result"]["temperature_history_C"][1])
    t1_pcm_max = max(res_pcm["simulation_result"]["temperature_history_C"][1])
    assert t1_pcm_max < t1_sensible_max - 1.5, (
        f"PCM gizli ısı tamponu komşu sıcaklığını düşürmedi: PCM={t1_pcm_max:.2f}°C vs Sensible={t1_sensible_max:.2f}°C"
    )


def test_barrier_thermal_degradation_and_isc_energy_conservation():
    """
    1. Düşük servis sıcaklıklı bariyerin (max_service_temp_C=180°C) kaçak sırasında bozunarak
       yüksek servis sıcaklıklı bariyere (1100°C) kıyasla komşu hücreye çok daha fazla ısı geçirdiğini doğrular.
    2. Nail Penetration ISC modunda toplam entegre elektriksel kısa devre enerjisinin (q_abuse)
       hücrenin depolanan elektrik enerjisini (E_elec = 3600 * C_Ah * V_nom * s) aşmadığını doğrular.
    """
    service = SimulationService()
    low_temp_barrier = {
        "name": "Polymer_Foam_LowTemp",
        "k_thermal_W_per_m_K": 0.03,
        "density_kg_per_m3": 150.0,
        "cp_J_per_kg_K": 1200.0,
        "max_service_temp_C": 160.0
    }
    high_temp_barrier = {
        "name": "Ceramic_Barrier_HighTemp",
        "k_thermal_W_per_m_K": 0.03,
        "density_kg_per_m3": 150.0,
        "cp_J_per_kg_K": 1200.0,
        "max_service_temp_C": 1150.0
    }
    barrier_cfg = dict(
        rows=1,
        cols=2,
        cell_format="18650",
        spacing_x_mm=1.5,
        spacing_y_mm=1.5,
        separator_thickness_mm=1.0,
        chemistry_id="NMC811_high_energy_v1",
        trigger_cell_id=0,
        trigger_method="instant_onset",
        trigger_initial_temp_C=250.0,
        simulation_time_s=45.0,
        advanced_physics_enabled=True,
        h_vent_W_per_m2_K=180.0
    )
    res_degraded = service.run_simulation(
        PackSimulationRequest(**barrier_cfg, custom_separator_params=low_temp_barrier),
        persist_db=False
    )
    res_intact = service.run_simulation(
        PackSimulationRequest(**barrier_cfg, custom_separator_params=high_temp_barrier),
        persist_db=False
    )
    t_neighbor_degraded = max(res_degraded["simulation_result"]["temperature_history_C"][1])
    t_neighbor_intact = max(res_intact["simulation_result"]["temperature_history_C"][1])
    assert t_neighbor_degraded > t_neighbor_intact + 25.0, (
        f"Bariyer bozunma fiziği etkisiz: Bozunmuş={t_neighbor_degraded:.1f}°C vs Sağlam={t_neighbor_intact:.1f}°C"
    )

    # ISC Elektriksel enerji korunumu ve q_chem / q_abuse ayrımı
    req_isc = PackSimulationRequest(
        rows=1,
        cols=1,
        cell_format="18650",
        chemistry_id="LFP_generic_v1",
        trigger_method="nail_penetration_isc",
        isc_resistance_ohm=0.002,  # Çok düşük R_isc -> yüksek anlık güç, tau_isc enerji sınırlayıcı devreye girmeli!
        soc_percent=50.0,
        simulation_time_s=25.0,
        num_output_points=250
    )
    res_isc = service.run_simulation(req_isc, persist_db=False)
    sim_isc = res_isc["simulation_result"]
    times = np.array(sim_isc["time_points_s"])
    q_abuse = np.array(sim_isc["heat_flux_history_W"]["q_abuse"][0])
    q_chem = np.array(sim_isc["heat_flux_history_W"]["q_chem"][0])

    assert np.max(q_abuse) > 100.0
    # LFP @ 50% SOC için E_elec <= 3600 * C_scaled * 3.2 * 0.50 (~15-20 kJ)
    integrated_isc_J = float(np.trapezoid(q_abuse, times))
    chem = ArrheniusKineticsEngine().get_params("LFP_generic_v1")
    cell_mass = sim_isc["cell_summaries"][0]["mass_kg"]
    cap_scaled = chem.nominal_capacity_Ah * (cell_mass / max(0.01, chem.nominal_mass))
    e_elec_max_J = 3600.0 * cap_scaled * chem.nominal_voltage * 0.50

    assert integrated_isc_J <= e_elec_max_J * 1.05, (
        f"ISC enerjisi depolanan elektrik enerjisini aştı: {integrated_isc_J:.1f} J > {e_elec_max_J:.1f} J"
    )
    # Başlangıç anında (t=0, T=25°C) kimyasal ısı sıfıra yakınken q_abuse pozitif olmalı (ayrım doğrulaması)
    assert q_chem[0] < 1e-3 and q_abuse[0] > 100.0
