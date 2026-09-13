"""
Isıl Ağ Montajcısı (ThermalNetworkAssembler)
Hücreler arası iletim, busbar termal köprüsü, yüzeyler arası karşılıklı radyasyon,
ortam konveksiyonu ve aktif soğutma plakası sınır şartlarını diferansiyel denklem seti olarak kurar.
Faz 0.5 Sözleşme 1 ve 2'ye tam uyumludur.
"""

from typing import List, Dict, Any, Optional
import math
import numpy as np

from simulator.core.constants import STEFAN_BOLTZMANN, KELVIN_ZERO_C
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
        T_vent_gas_K: Optional[float] = None
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

        # Hücre kütle ve cp dizileri
        self.masses = np.array([c.mass for c in cells], dtype=np.float64)
        self.cps = np.array([c.cp for c in cells], dtype=np.float64)
        self.thermal_capacities = self.masses * self.cps

        # Yüzey ve taban alanları
        self.surface_areas = np.array([c.geometry.surface_area for c in cells], dtype=np.float64)
        self.bottom_areas = np.array([c.geometry.bottom_area for c in cells], dtype=np.float64)

        # Komşularla paylaşılan ve dış ortama bakan yüzey alanları
        self.facing_areas = np.zeros(self.n_cells, dtype=np.float64)
        for conn in self.connections:
            self.facing_areas[conn.cell_i_id] += conn.contact_area_m2
            self.facing_areas[conn.cell_j_id] += conn.contact_area_m2

        self.exposed_areas = np.maximum(0.0005, self.surface_areas - self.facing_areas)

        # İletkenlik matrisini kur (G_matrix: W/K)
        self.G_conduction = self._build_conduction_conductance_matrix()

        # Her hücrenin kimya parametrelerini önbelleğe al
        self.cell_chemistries: List[ChemistryParams] = [
            self.kinetics_engine.get_params(c.chemistry_id) for c in cells
        ]

    def _get_material_k(self, material_id: Optional[str], default_k: float = 0.026) -> float:
        if not material_id or material_id not in self.materials_lib:
            return default_k
        return float(self.materials_lib[material_id].get("k_thermal_W_per_m_K", default_k))

    def _build_conduction_conductance_matrix(self) -> np.ndarray:
        """
        Komşu hücreler arasındaki seri ısıl direnç ve metalik busbar köprüsünü kurar.
        R_total = R_casing_i + R_separator + R_gap + R_casing_j
        G_total = (1 / R_total) + G_busbar (yalıtımsız ise)
        """
        G = np.zeros((self.n_cells, self.n_cells), dtype=np.float64)
        k_casing = self._get_material_k("aluminum_6061", 167.0)
        t_casing = 0.0003  # 0.3 mm alüminyum/çelik hücre gövdesi

        for conn in self.connections:
            i = conn.cell_i_id
            j = conn.cell_j_id
            A = conn.contact_area_m2

            # Hücre kabuk direnci
            R_casing = 2.0 * (t_casing / (k_casing * A))

            # Separatör direnci
            has_insulating_separator = (conn.separator_material_id and conn.separator_thickness_m > 0)
            if has_insulating_separator:
                k_sep = self._get_material_k(conn.separator_material_id, 0.02)
                R_sep = conn.separator_thickness_m / (k_sep * A)
            else:
                R_sep = 0.0

            # Boşluk (hava / dolgu) direnci
            gap_dist = max(1e-5, conn.surface_gap_m - conn.separator_thickness_m)
            k_gap = self._get_material_k(conn.gap_material_id, 0.026)
            R_gap = gap_dist / (k_gap * A)

            R_total = R_casing + R_sep + R_gap
            conductance = 1.0 / max(1e-5, R_total)

            # Busbar / metalik interconnect termal köprüsü:
            # Separatör varsa busbar köprüsü termal olarak yalıtılmış sayılır
            if not has_insulating_separator:
                conductance += self.busbar_conductance

            G[i, j] += conductance
            G[j, i] += conductance

        return G

    def compute_derivatives(
        self,
        t: float,
        state_vector: np.ndarray,
        trigger_cell_id: Optional[int] = None,
        trigger_power_W: float = 0.0,
        trigger_duration_s: float = 5.0,
        ohmic_power_W: float = 0.0
    ) -> np.ndarray:
        """
        ODE Sağ taraf fonksiyonu f(t, y):
        state_vector: [T_0, T_1, ..., T_{n-1}, alpha_0, alpha_1, ..., alpha_{n-1}]
        Döndürür: [dT_0/dt, ..., dT_{n-1}/dt, dalpha_0/dt, ..., dalpha_{n-1}/dt]
        """
        N = self.n_cells
        temps = np.maximum(50.0, state_vector[:N])  # Prevent non-physical negative temps
        alphas = np.clip(state_vector[N:2*N], 0.0, 1.0)  # Clamp alpha to [0, 1]

        dT_dt = np.zeros(N, dtype=np.float64)
        dalpha_dt = np.zeros(N, dtype=np.float64)

        # 1. Kinetik reaksiyon hızları ve kimyasal ısı üretimi
        q_gen = np.zeros(N, dtype=np.float64)
        for i in range(N):
            chem = self.cell_chemistries[i]
            rate = self.kinetics_engine.reaction_rate(alphas[i], temps[i], chem)
            dalpha_dt[i] = rate

            # Tetikleyici hücre için harici ısı darbesi kontrolü
            ext_pwr = 0.0
            if trigger_cell_id is not None and i == trigger_cell_id and t <= trigger_duration_s:
                ext_pwr = trigger_power_W

            q_gen[i] = self.kinetics_engine.heat_generation_rate(
                rate, self.masses[i], chem, ohmic_power_W, ext_pwr
            )

        # 2. Hücreler arası iletim ısı akısı: Q_cond_i = sum_j G_ij * (T_i - T_j)
        G_diag = np.sum(self.G_conduction, axis=1)
        q_cond_net = (G_diag * temps) - (self.G_conduction @ temps)

        # 3. Hücreler arası karşılıklı radyasyon ve Yarı-Ampirik Venting
        temps_clamped = np.maximum(50.0, temps)
        temps_pow4 = temps_clamped ** 4.0
        q_rad_intercell = np.zeros(N, dtype=np.float64)
        q_vent_intercell = np.zeros(N, dtype=np.float64) # Yarı-ampirik sıcak gaz enerjisi

        # Efektif yayılım çarpanı
        eps_eff = self.emissivity / (2.0 - self.emissivity)

        for conn in self.connections:
            # Opak separatör yoksa iki hücre arasında doğrudan etkileşim gerçekleşir
            if not (conn.separator_material_id and conn.separator_thickness_m > 0):
                i = conn.cell_i_id
                j = conn.cell_j_id
                A = conn.contact_area_m2
                q_rad_ij = STEFAN_BOLTZMANN * eps_eff * A * (temps_pow4[i] - temps_pow4[j])
                q_rad_intercell[i] += q_rad_ij
                q_rad_intercell[j] -= q_rad_ij
                
                # Yarı-Ampirik Venting / Ejecta Gaz Konveksiyonu
                chem_i = self.cell_chemistries[i]
                chem_j = self.cell_chemistries[j]
                h_vent = self.h_vent
                
                # Hücre i yanıyorsa, j'yi sıcak gazla kavurur
                if temps[i] >= chem_i.T_trigger_K and alphas[i] > 0.05:
                    T_vent_i = self.T_vent_gas_K if self.T_vent_gas_K is not None else (1273.15 if "NMC" in chem_i.chemistry_id else 623.15)
                    q_vent_ij = h_vent * A * (T_vent_i - temps[j])
                    if q_vent_ij > 0:
                        q_vent_intercell[j] += q_vent_ij
                        
                # Hücre j yanıyorsa, i'yi sıcak gazla kavurur
                if temps[j] >= chem_j.T_trigger_K and alphas[j] > 0.05:
                    T_vent_j = self.T_vent_gas_K if self.T_vent_gas_K is not None else (1273.15 if "NMC" in chem_j.chemistry_id else 623.15)
                    q_vent_ji = h_vent * A * (T_vent_j - temps[i])
                    if q_vent_ji > 0:
                        q_vent_intercell[i] += q_vent_ji

        # 4. Ortama konveksiyon: Yalnızca dışa bakan (exposed) yüzeylerden
        # İçteki hücreler komşuları tarafından sarıldığından açık havadaki gibi soğuyamaz
        q_conv = self.h_ambient * self.exposed_areas * (temps - self.T_ambient_K)

        # 5. Dış çevreye radyasyon (yalnızca dışa bakan maruz yüzeylerden)
        q_rad_ambient = STEFAN_BOLTZMANN * self.emissivity * self.exposed_areas * (temps_pow4 - self.T_ambient_K**4)

        # 6. Taban soğutma plakası aktif ısı çekişi: Q_cool = h_cool * A_bottom * (T - T_cool)
        q_cooling = np.zeros(N, dtype=np.float64)
        if self.active_cooling_enabled:
            effective_cooling_G = 1.0 / ((1.0 / (self.h_cooling * self.bottom_areas)) + self.contact_resistance)
            q_cooling = effective_cooling_G * (temps - self.T_coolant_K)

        # Toplam enerji dengesi:
        # m * cp * dT/dt = Q_gen - Q_cond - Q_rad_intercell + Q_vent_intercell - Q_conv - Q_rad_ambient - Q_cooling
        net_heat = q_gen - q_cond_net - q_rad_intercell + q_vent_intercell - q_conv - q_rad_ambient - q_cooling
        dT_dt = net_heat / self.thermal_capacities

        return np.concatenate([dT_dt, dalpha_dt])
