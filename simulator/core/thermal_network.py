"""
Isıl Ağ Montajcısı (ThermalNetworkAssembler)
Hücreler arası iletim, busbar termal köprüsü, yüzeyler arası karşılıklı radyasyon,
ortam konveksiyonu ve aktif soğutma plakası sınır şartlarını diferansiyel denklem seti olarak kurar.
Aşama 1: Core-Shell (1D radyal iç jöle rulo ve dış kovan), Yönlü Venting, Dinamik Kütle Kaybı
ve Çoklu-Reaksiyon Kinetiği (4 kademe) tam entegre edilmiştir.
"""

from typing import List, Dict, Any, Optional, Tuple
import math
import numpy as np

from simulator.core.constants import STEFAN_BOLTZMANN, KELVIN_ZERO_C, celsius_to_kelvin
from simulator.core.cell_model import CellModel
from simulator.core.pack_geometry import NeighborConnection
from simulator.core.kinetics_engine import ArrheniusKineticsEngine, ChemistryParams

class ThermalNetworkAssembler:
    """Tüm hücreler için ısıl direnç ve radyasyon ağını kurar ve ODE sağ taraf fonksiyonunu üretir."""

    def __init__(
        self,
        cells: List[CellModel],
        connections: List[NeighborConnection],
        materials_lib: Dict[str, Dict[str, Any]],
        kinetics_engine: ArrheniusKineticsEngine,
        h_ambient_conv_W_per_m2_K: float = 10.0,
        T_ambient_K: float = 298.15,
        emissivity: float = 0.85,
        busbar_conductance_W_per_K: float = 0.60,
        active_cooling_enabled: bool = False,
        h_cooling_plate_W_per_m2_K: float = 800.0,
        T_coolant_K: float = 298.15,
        contact_resistance_K_per_W: float = 0.05,
        h_vent_W_per_m2_K: float = 100.0,
        T_vent_gas_K: Optional[float] = None,
        nodal_model: str = "lumped",                 # "lumped" (1-düğüm) veya "core_shell" (2-düğüm 1D radyal)
        kinetics_model: str = "single_step",         # "single_step" veya "multi_reaction" (4-kademe)
        ejecta_mass_loss_ratio: float = 0.0,        # Venting kütle kaybı oranı (0.0 - 0.40)
        vent_direction_deg: Optional[float] = None, # Yönlü venting açısı (derece, None ise her yöne)
        soc_percent: float = 100.0                   # Hücre Şarj Seviyesi (SOC %)
    ):
        self.cells = cells
        self.connections = connections
        self.materials_lib = materials_lib
        self.kinetics_engine = kinetics_engine
        self.n_cells = len(cells)

        self.h_ambient = float(h_ambient_conv_W_per_m2_K)
        self.T_ambient_K = float(T_ambient_K)
        self.emissivity = float(emissivity)
        self.busbar_conductance = float(busbar_conductance_W_per_K)

        self.active_cooling_enabled = active_cooling_enabled
        self.h_cooling = float(h_cooling_plate_W_per_m2_K)
        self.T_coolant_K = float(T_coolant_K)
        self.contact_resistance = float(contact_resistance_K_per_W)
        self.h_vent = float(h_vent_W_per_m2_K)
        self.T_vent_gas_K = float(T_vent_gas_K) if T_vent_gas_K is not None else None

        # Model Yapılandırmaları
        self.nodal_model = nodal_model.lower()
        self.kinetics_model = kinetics_model.lower()
        self.ejecta_mass_loss_ratio = float(ejecta_mass_loss_ratio)
        self.vent_direction_deg = float(vent_direction_deg) if vent_direction_deg is not None else None
        self.soc_percent = max(0.0, min(100.0, float(soc_percent)))

        # Hücre kütle ve cp dizileri (Lumped model için)
        self.masses = np.array([c.mass for c in cells], dtype=np.float64)
        self.cps = np.array([c.cp for c in cells], dtype=np.float64)
        self.thermal_capacities = self.masses * self.cps

        # Core-Shell Termal Özellikleri (2-düğüm modeli için)
        self.core_masses = np.array([c.core_mass for c in cells], dtype=np.float64)
        self.shell_masses = np.array([c.shell_mass for c in cells], dtype=np.float64)
        self.core_cps = np.array([c.core_cp for c in cells], dtype=np.float64)
        self.shell_cps = np.array([c.shell_cp for c in cells], dtype=np.float64)
        self.G_core_shell = np.array([c.geometry.get_core_shell_conductance() for c in cells], dtype=np.float64)

        # Yüzey ve taban alanları
        self.surface_areas = np.array([c.geometry.surface_area for c in cells], dtype=np.float64)
        self.bottom_areas = np.array([c.geometry.bottom_area for c in cells], dtype=np.float64)

        # Komşularla paylaşılan ve dış ortama bakan yüzey alanları
        self.facing_areas = np.zeros(self.n_cells, dtype=np.float64)
        for conn in self.connections:
            self.facing_areas[conn.cell_i_id] += conn.contact_area_m2
            self.facing_areas[conn.cell_j_id] += conn.contact_area_m2

        self.exposed_areas = np.maximum(0.0005, self.surface_areas - self.facing_areas)

        # Bağlantı ve bariyer analizlerini önbelleğe al
        self._init_connection_properties()

        # Temel iletkenlik matrisini kur (G_matrix: W/K)
        self.G_conduction = self._build_conduction_conductance_matrix()

        # Her hücrenin kimya parametrelerini önbelleğe al
        self.cell_chemistries: List[ChemistryParams] = [
            self.kinetics_engine.get_params(c.chemistry_id) for c in cells
        ]

    def _get_material_k(self, material_id: Optional[str], default_k: float = 0.026) -> float:
        if not material_id or material_id not in self.materials_lib:
            return default_k
        return float(self.materials_lib[material_id].get("k_thermal_W_per_m_K", default_k))

    def _init_connection_properties(self) -> None:
        """PCM ve termal bariyer bozunma parametrelerini hazırlar."""
        self.conn_data: List[Dict[str, Any]] = []
        self.cell_pcm_buffers: Dict[int, List[Dict[str, float]]] = {i: [] for i in range(self.n_cells)}

        k_casing = self._get_material_k("aluminum_6061", 167.0)
        t_casing = 0.0003

        for conn in self.connections:
            i = conn.cell_i_id
            j = conn.cell_j_id
            A = conn.contact_area_m2
            R_casing = 2.0 * (t_casing / (k_casing * A))

            has_sep = bool(conn.separator_material_id and conn.separator_thickness_m > 0)
            sep_mat = self.materials_lib.get(conn.separator_material_id, {}) if has_sep else {}

            if has_sep:
                k_sep = float(sep_mat.get("k_thermal_W_per_m_K", 0.02))
                R_sep = conn.separator_thickness_m / (k_sep * A)
                max_svc_C = sep_mat.get("max_service_temp_C")
                degrade_T_K = celsius_to_kelvin(float(max_svc_C)) if max_svc_C is not None else None
            else:
                R_sep = 0.0
                degrade_T_K = None

            gap_dist = max(1e-5, conn.surface_gap_m - conn.separator_thickness_m)
            k_gap = self._get_material_k(conn.gap_material_id, 0.026)
            R_gap = gap_dist / (k_gap * A)

            R_total = R_casing + R_sep + R_gap
            cond_base = 1.0 / max(1e-5, R_total)
            if not has_sep:
                cond_base += self.busbar_conductance

            # Bozunmuş bariyer iletkenliği (Separatör eridiğinde / delindiğinde)
            R_degraded = R_casing + R_gap
            cond_degraded = (1.0 / max(1e-5, R_degraded)) + self.busbar_conductance

            c_info = {
                "i": i,
                "j": j,
                "area": A,
                "has_sep": has_sep,
                "cond_base": cond_base,
                "cond_degraded": cond_degraded,
                "degrade_T_K": degrade_T_K
            }
            self.conn_data.append(c_info)

            # PCM Faz Değişim Kontrolü (Separatör ve/veya Dolgu Malzemesi)
            sep_latent = float(sep_mat.get("latent_heat_J_per_kg", 0.0)) if has_sep else 0.0
            if sep_latent > 0.0:
                density = float(sep_mat.get("density_kg_per_m3", 900.0))
                m_pcm = density * A * conn.separator_thickness_m
                t_melt_C = float(sep_mat.get("melting_temp_C", 50.0))
                t_range = float(sep_mat.get("melting_range_K", 6.0))
                pcm_spec = {
                    "mass_kg": m_pcm,
                    "latent_heat_J_per_kg": sep_latent,
                    "T_melt_K": celsius_to_kelvin(t_melt_C),
                    "sigma_K": max(0.5, t_range / 2.355)
                }
                self.cell_pcm_buffers[i].append(pcm_spec)
                self.cell_pcm_buffers[j].append(pcm_spec)

            gap_mat = self.materials_lib.get(conn.gap_material_id, {}) if conn.gap_material_id else {}
            gap_latent = float(gap_mat.get("latent_heat_J_per_kg", 0.0))
            if gap_latent > 0.0:
                density = float(gap_mat.get("density_kg_per_m3", 900.0))
                m_pcm = density * A * gap_dist
                t_melt_C = float(gap_mat.get("melting_temp_C", 50.0))
                t_range = float(gap_mat.get("melting_range_K", 6.0))
                pcm_spec = {
                    "mass_kg": m_pcm,
                    "latent_heat_J_per_kg": gap_latent,
                    "T_melt_K": celsius_to_kelvin(t_melt_C),
                    "sigma_K": max(0.5, t_range / 2.355)
                }
                self.cell_pcm_buffers[i].append(pcm_spec)
                self.cell_pcm_buffers[j].append(pcm_spec)

    def _build_conduction_conductance_matrix(self) -> np.ndarray:
        """Komşu hücreler arasındaki nominal iletkenlik matrisini üretir."""
        G = np.zeros((self.n_cells, self.n_cells), dtype=np.float64)
        for c in self.conn_data:
            i, j, cond = c["i"], c["j"], c["cond_base"]
            G[i, j] += cond
            G[j, i] += cond
        return G

    def _compute_network_flows(
        self,
        t: float,
        state_vector: np.ndarray,
        trigger_cell_id: Optional[int] = None,
        trigger_power_W: float = 0.0,
        trigger_duration_s: float = 5.0,
        ohmic_power_W: float = 0.0,
        trigger_method: str = "thermal_pulse",
        isc_resistance_ohm: float = 0.05,
        oven_target_temp_C: Optional[float] = None,
        oven_ramp_C_per_min: float = 5.0
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray]]:
        """
        Tüm termal ve kinetik akıları hesaplayan çekirdek fonksiyon.
        Diferansiyeller ve ayrıntılı ısı bileşenleri (W) döner.
        """
        N = self.n_cells
        is_core_shell = (self.nodal_model == "core_shell")
        is_multi_rxn = (self.kinetics_model == "multi_reaction")

        # 1. Sıcaklıkları ayrıştır
        if is_core_shell:
            temps_core = np.maximum(50.0, state_vector[:N])
            temps_shell = np.maximum(50.0, state_vector[N:2*N])
            temps_surface = temps_shell
            rxn_offset = 2 * N
        else:
            temps_core = np.maximum(50.0, state_vector[:N])
            temps_shell = temps_core
            temps_surface = temps_core
            rxn_offset = N

        # 2. Reaksiyon ilerleme değişkenlerini ayrıştır
        if is_multi_rxn:
            alphas_raw = np.clip(state_vector[rxn_offset : rxn_offset + 4*N], 0.0, 1.0)
            alphas_sub = alphas_raw.reshape((N, 4))
            alphas_effective = alphas_sub[:, 3]
            dalpha_dt = np.zeros((N, 4), dtype=np.float64)
        else:
            alphas = np.clip(state_vector[rxn_offset : rxn_offset + N], 0.0, 1.0)
            alphas_effective = alphas
            dalpha_dt = np.zeros(N, dtype=np.float64)

        # 3. Dinamik Ejecta Kütle Kaybı ve Termal Sığa Azalması
        if self.ejecta_mass_loss_ratio > 0.0:
            mass_factors = np.maximum(0.5, 1.0 - (self.ejecta_mass_loss_ratio * alphas_effective))
        else:
            mass_factors = np.ones(N, dtype=np.float64)

        effective_thermal_capacities = self.thermal_capacities * mass_factors
        effective_core_capacities = (self.core_masses * self.core_cps) * mass_factors
        shell_capacities = self.shell_masses * self.shell_cps.copy()

        # PCM İlave Isıl Sığa (Apparent Heat Capacity) Hesabı
        for i in range(N):
            pcm_list = self.cell_pcm_buffers.get(i, [])
            if pcm_list:
                t_surf = temps_surface[i]
                extra_cp = 0.0
                for pcm in pcm_list:
                    # 0.5 * m_pcm paylaşımlı tampon kütlesi
                    m_half = 0.5 * pcm["mass_kg"]
                    diff = t_surf - pcm["T_melt_K"]
                    sig = pcm["sigma_K"]
                    gauss = math.exp(-0.5 * (diff / sig) ** 2) / (sig * math.sqrt(2.0 * math.pi))
                    extra_cp += m_half * pcm["latent_heat_J_per_kg"] * gauss
                effective_thermal_capacities[i] += extra_cp
                shell_capacities[i] += extra_cp

        # 4. Kinetik Reaksiyon Hızları ve Kimyasal Isı Üretimi
        # Not: Başlangıç reaktif kütlesi (initial mass) kullanılır; mass_factors ile küçültülmez.
        q_chem = np.zeros(N, dtype=np.float64)
        q_vap = np.zeros(N, dtype=np.float64)
        q_ext_core = np.zeros(N, dtype=np.float64)
        q_ext_shell = np.zeros(N, dtype=np.float64)

        # 5 Farklı Tetikleme Modu Isı Girişi
        if trigger_cell_id is not None and 0 <= trigger_cell_id < N:
            chem_trig = self.cell_chemistries[trigger_cell_id]
            if trigger_method == "thermal_pulse":
                if t <= trigger_duration_s:
                    q_ext_core[trigger_cell_id] = trigger_power_W
            elif trigger_method == "external_heater":
                # UL 9540A: Yüzey ısıtma ceketi, T_trigger'a ulaşınca termostatla kesilir
                if t <= trigger_duration_s and temps_surface[trigger_cell_id] < chem_trig.T_trigger_K:
                    q_ext_shell[trigger_cell_id] = trigger_power_W
            elif trigger_method == "nail_penetration_isc":
                # Çivi batması: Dahili kısa devre (ISC), SOC bağımlı OCV ve depolanan elektrik enerjisi korunumu
                v_nom = float(getattr(chem_trig, "nominal_voltage", getattr(chem_trig, "nominal_voltage_V", 3.7)))
                s_soc = max(0.05, min(1.0, self.soc_percent / 100.0))
                v_ocv = v_nom * (0.85 + 0.15 * s_soc)
                r_isc = max(1e-4, isc_resistance_ohm)
                p_isc_0 = (v_ocv ** 2) / r_isc

                base_cap_ah = float(getattr(chem_trig, "nominal_capacity_Ah", 2.6))
                ref_mass_kg = max(0.01, float(getattr(chem_trig, "nominal_mass", 0.046)))
                eff_cap_ah = base_cap_ah * (self.masses[trigger_cell_id] / ref_mass_kg)
                stored_elec_J = 3600.0 * eff_cap_ah * v_ocv * s_soc

                tau_energy_limit = stored_elec_J / max(1.0, p_isc_0)
                tau_isc = max(0.1, min(10.0, tau_energy_limit))
                q_ext_core[trigger_cell_id] = p_isc_0 * math.exp(-t / tau_isc)

        # Reaksiyon hızları (Saf kimyasal ısı üretimi q_chem, dış tetikleme q_ext_core'dan ayrı tutulur)
        for i in range(N):
            chem = self.cell_chemistries[i]
            m0 = self.masses[i]

            if is_multi_rxn:
                rates = self.kinetics_engine.multi_reaction_rates(alphas_sub[i], temps_core[i], chem.sub_reactions)
                dalpha_dt[i] = rates
                q_chem[i] = self.kinetics_engine.multi_heat_generation_rate(
                    rates, m0, chem.sub_reactions, chem.active_mass_ratio, ohmic_power_W, 0.0
                )
                eff_rate = rates[3]
            else:
                rate = self.kinetics_engine.reaction_rate(alphas[i], temps_core[i], chem)
                dalpha_dt[i] = rate
                q_chem[i] = self.kinetics_engine.heat_generation_rate(
                    rate, m0, chem, ohmic_power_W, 0.0
                )
                eff_rate = rate

            # Elektrolit buharlaşması endotermik ısı yutumu (Vaporization Heat Sink: 400 kJ/kg)
            if self.ejecta_mass_loss_ratio > 0.0 and alphas_effective[i] > 0.05 and eff_rate > 0.0:
                delta_h_vap = 4.0e5
                q_vap[i] = m0 * self.ejecta_mass_loss_ratio * delta_h_vap * eff_rate

        # 5. İletim Akısı (Termal bariyer aşırı sıcaklık bozunması - sürekli geçişli)
        q_cond_net = np.zeros(N, dtype=np.float64)
        for c in self.conn_data:
            i, j = c["i"], c["j"]
            t_i, t_j = temps_surface[i], temps_surface[j]
            degrade_T = c["degrade_T_K"]

            if degrade_T is not None and max(t_i, t_j) > degrade_T:
                breach_cond = min(1.0, (max(t_i, t_j) - degrade_T) / 30.0)
                cond = c["cond_base"] + breach_cond * (c["cond_degraded"] - c["cond_base"])
            else:
                cond = c["cond_base"]

            q_flow = cond * (t_i - t_j)
            q_cond_net[i] += q_flow
            q_cond_net[j] -= q_flow

        # 6. Radyasyon ve Aktif Zarflı Yönlü Venting (Bariyer eridiğinde/delindiğinde sızıntı dahil)
        temps_clamped = np.maximum(50.0, temps_surface)
        temps_pow4 = temps_clamped ** 4.0
        q_rad_net = np.zeros(N, dtype=np.float64)
        q_vent_net = np.zeros(N, dtype=np.float64)

        eps_eff = self.emissivity / (2.0 - self.emissivity)

        for c in self.conn_data:
            i = c["i"]
            j = c["j"]
            A = c["area"]
            has_sep = c["has_sep"]
            degrade_T = c["degrade_T_K"]

            if not has_sep:
                shield_transmittance = 1.0
            elif degrade_T is not None and max(temps_surface[i], temps_surface[j]) > degrade_T:
                shield_transmittance = min(0.85, (max(temps_surface[i], temps_surface[j]) - degrade_T) / 120.0)
            else:
                shield_transmittance = 0.0

            if shield_transmittance > 0.0:
                # Radyasyon akısı
                q_rad_ij = shield_transmittance * STEFAN_BOLTZMANN * eps_eff * A * (temps_pow4[i] - temps_pow4[j])
                q_rad_net[i] += q_rad_ij
                q_rad_net[j] -= q_rad_ij

                # Yön faktörleri
                dir_factor_ij = 1.0
                dir_factor_ji = 1.0
                if self.vent_direction_deg is not None:
                    ci = self.cells[i]
                    cj = self.cells[j]
                    angle_ij_deg = math.degrees(math.atan2(cj.pos_y - ci.pos_y, cj.pos_x - ci.pos_x)) % 360.0
                    angle_ji_deg = (angle_ij_deg + 180.0) % 360.0

                    diff_ij = abs(angle_ij_deg - self.vent_direction_deg)
                    if diff_ij > 180.0:
                        diff_ij = 360.0 - diff_ij
                    diff_ji = abs(angle_ji_deg - self.vent_direction_deg)
                    if diff_ji > 180.0:
                        diff_ji = 360.0 - diff_ji

                    dir_factor_ij = max(0.1, math.cos(math.radians(diff_ij)))
                    dir_factor_ji = max(0.1, math.cos(math.radians(diff_ji)))

                chem_i = self.cell_chemistries[i]
                chem_j = self.cell_chemistries[j]

                # Hücre i -> j Aktif Venting Zarfı (0.05 < alpha < 0.98 arasında tepe yapar ve biter)
                if temps_core[i] >= chem_i.T_trigger_K and (0.05 <= alphas_effective[i] < 0.98):
                    alpha_norm_i = (alphas_effective[i] - 0.05) / 0.93
                    phi_vent_i = max(0.0, 4.0 * alpha_norm_i * (1.0 - alpha_norm_i))
                    T_vent_i = self.T_vent_gas_K if self.T_vent_gas_K is not None else (1273.15 if "NMC" in chem_i.chemistry_id else 623.15)
                    q_vent_ij = shield_transmittance * (self.h_vent * dir_factor_ij * phi_vent_i) * A * (T_vent_i - temps_surface[j])
                    if q_vent_ij > 0:
                        q_vent_net[j] += q_vent_ij

                # Hücre j -> i Aktif Venting Zarfı
                if temps_core[j] >= chem_j.T_trigger_K and (0.05 <= alphas_effective[j] < 0.98):
                    alpha_norm_j = (alphas_effective[j] - 0.05) / 0.93
                    phi_vent_j = max(0.0, 4.0 * alpha_norm_j * (1.0 - alpha_norm_j))
                    T_vent_j = self.T_vent_gas_K if self.T_vent_gas_K is not None else (1273.15 if "NMC" in chem_j.chemistry_id else 623.15)
                    q_vent_ji = shield_transmittance * (self.h_vent * dir_factor_ji * phi_vent_j) * A * (T_vent_j - temps_surface[i])
                    if q_vent_ji > 0:
                        q_vent_net[i] += q_vent_ji

        # 7 & 8. Fırın Testi (Oven Ramp) veya Sabit Ortam Sıcaklığı
        if trigger_method == "oven_ramp" and oven_target_temp_C is not None:
            t_target_K = celsius_to_kelvin(oven_target_temp_C)
            ramp_k_per_s = oven_ramp_C_per_min / 60.0
            current_T_amb_K = min(self.T_ambient_K + ramp_k_per_s * t, t_target_K)
        else:
            current_T_amb_K = self.T_ambient_K

        # Ortama konveksiyon
        q_conv = self.h_ambient * self.exposed_areas * (temps_surface - current_T_amb_K)

        # Dış çevreye radyasyon
        q_rad_ambient = STEFAN_BOLTZMANN * self.emissivity * self.exposed_areas * (temps_pow4 - current_T_amb_K**4)

        # 9. Taban Soğutma Plakası Isı Çekişi
        q_cooling = np.zeros(N, dtype=np.float64)
        if self.active_cooling_enabled:
            effective_cooling_G = 1.0 / ((1.0 / (self.h_cooling * self.bottom_areas)) + self.contact_resistance)
            q_cooling = effective_cooling_G * (temps_surface - self.T_coolant_K)

        # 10. Enerji Dengesi Diferansiyelleri (dT/dt)
        q_cs = np.zeros(N, dtype=np.float64)
        if is_core_shell:
            q_cs = self.G_core_shell * (temps_core - temps_shell)
            dT_core_dt = (q_chem + q_ext_core - q_vap - q_cs) / effective_core_capacities
            net_shell_heat = q_cs + q_ext_shell - q_cond_net - q_rad_net + q_vent_net - q_conv - q_rad_ambient - q_cooling
            dT_shell_dt = net_shell_heat / shell_capacities
            dT_dt = np.concatenate([dT_core_dt, dT_shell_dt])
        else:
            net_heat = q_chem + q_ext_core - q_vap + q_ext_shell - q_cond_net - q_rad_net + q_vent_net - q_conv - q_rad_ambient - q_cooling
            dT_dt = net_heat / effective_thermal_capacities

        flux_breakdown = {
            "q_chem": q_chem,
            "q_abuse": q_ext_core + q_ext_shell,
            "q_vap": q_vap,
            "q_cond": q_cond_net,
            "q_rad": q_rad_net,
            "q_vent": q_vent_net,
            "q_conv": q_conv,
            "q_rad_ambient": q_rad_ambient,
            "q_cool": q_cooling,
            "q_cs": q_cs,
            "q_ext_core": q_ext_core,
            "q_ext_shell": q_ext_shell,
            "T_ambient_current_K": current_T_amb_K
        }

        return dT_dt, dalpha_dt, flux_breakdown

    def compute_derivatives(
        self,
        t: float,
        state_vector: np.ndarray,
        trigger_cell_id: Optional[int] = None,
        trigger_power_W: float = 0.0,
        trigger_duration_s: float = 5.0,
        ohmic_power_W: float = 0.0,
        trigger_method: str = "thermal_pulse",
        isc_resistance_ohm: float = 0.05,
        oven_target_temp_C: Optional[float] = None,
        oven_ramp_C_per_min: float = 5.0
    ) -> np.ndarray:
        """
        ODE Sağ taraf fonksiyonu f(t, y).
        solve_ivp entegrasyonu için türev vektörünü döner.
        """
        dT_dt, dalpha_dt, _ = self._compute_network_flows(
            t=t,
            state_vector=state_vector,
            trigger_cell_id=trigger_cell_id,
            trigger_power_W=trigger_power_W,
            trigger_duration_s=trigger_duration_s,
            ohmic_power_W=ohmic_power_W,
            trigger_method=trigger_method,
            isc_resistance_ohm=isc_resistance_ohm,
            oven_target_temp_C=oven_target_temp_C,
            oven_ramp_C_per_min=oven_ramp_C_per_min
        )
        return np.concatenate([dT_dt, dalpha_dt.flatten()])

    def evaluate_heat_flows(
        self,
        t: float,
        state_vector: np.ndarray,
        trigger_cell_id: Optional[int] = None,
        trigger_power_W: float = 0.0,
        trigger_duration_s: float = 5.0,
        ohmic_power_W: float = 0.0,
        trigger_method: str = "thermal_pulse",
        isc_resistance_ohm: float = 0.05,
        oven_target_temp_C: Optional[float] = None,
        oven_ramp_C_per_min: float = 5.0
    ) -> Dict[str, np.ndarray]:
        """Grafik tablosu ve analizler için bileşen bazlı ısı akılarını döner."""
        _, _, breakdown = self._compute_network_flows(
            t=t,
            state_vector=state_vector,
            trigger_cell_id=trigger_cell_id,
            trigger_power_W=trigger_power_W,
            trigger_duration_s=trigger_duration_s,
            ohmic_power_W=ohmic_power_W,
            trigger_method=trigger_method,
            isc_resistance_ohm=isc_resistance_ohm,
            oven_target_temp_C=oven_target_temp_C,
            oven_ramp_C_per_min=oven_ramp_C_per_min
        )
        return breakdown
