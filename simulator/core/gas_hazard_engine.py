"""
Gaz Tehlike ve Havalandırma Boyutlandırma Motoru (GasHazardEngine)
Termal kaçak esnasında hücrelerden salınan toksik ve yanıcı gazların miktarını,
Le Chatelier alt patlama sınırını (LEL %), mahfaza içi aşırı basınç profilini (ΔP)
ve NFPA 68 / NFPA 855 standartlarına göre güvenli tahliye valfi alanını hesaplar.
"""

from typing import Dict, Any, List, Optional
import math
import numpy as np

from simulator.core.constants import P_ATM_PA, MOLAR_VOL_STP_L, R_GAS_CONSTANT, KELVIN_ZERO_C
from simulator.core.cell_model import CellModel
from simulator.core.kinetics_engine import ChemistryParams

# Saf gazların havadaki Alt Patlama Sınırları (LEL - Lower Explosive Limit, % hacimce)
PURE_LEL_PERCENT = {
    "H2": 4.0,
    "CO": 12.5,
    "CH4": 5.0,
    "C2H4": 2.7,
    "C2H6": 3.0,
    "C3H8": 2.1
}

class GasHazardEngine:
    """Termal kaçak gaz salınımı ve patlama riski analitiği."""

    @staticmethod
    def calculate_le_chatelier_lel(gas_fractions: Dict[str, float]) -> float:
        """
        Le Chatelier karışım kuralı ile yanıcı gaz karışımının LEL değerini hesaplar:
        LEL_mix = (sum_flammable x_i) / sum_flammable (x_i / LEL_i)
        """
        total_flammable_frac = 0.0
        weighted_denominator = 0.0

        for gas, frac in gas_fractions.items():
            if gas in PURE_LEL_PERCENT and frac > 0.0:
                lel_pure = PURE_LEL_PERCENT[gas]
                total_flammable_frac += frac
                weighted_denominator += frac / lel_pure

        if weighted_denominator > 0.0:
            return round(total_flammable_frac / weighted_denominator, 2)
        return 5.0  # Varsayılan emniyetli ortalama LEL (% vol)

    @classmethod
    def evaluate_gas_hazard(
        cls,
        time_points: List[float],
        alpha_history: Dict[int, List[float]],
        cells: List[CellModel],
        cell_chemistries: List[ChemistryParams],
        enclosure_free_vol_L: Optional[float] = None,
        vent_valve_area_cm2: float = 2.0,
        vent_burst_pressure_kpa: float = 35.0,
        soc_percent: float = 100.0,
        enclosure_volume_auto_estimated: bool = False
    ) -> Dict[str, Any]:
        """
        Simülasyon sonuçlarına göre zamana bağlı gaz hacmi, konsantrasyonu ve basınç birikimini hesaplar.
        """
        n_steps = len(time_points)
        n_cells = len(cells)

        # Şarj Durumu (SOC %) gaz verim çarpanı: SOC=100%'de 1.0, düşük SOC'de azalan gaz üretimi
        s_soc = max(0.0, min(1.0, float(soc_percent) / 100.0))
        eta_soc = 0.35 + 0.65 * (s_soc ** 1.1)

        # 1. Hücre başı gaz verimi (L/Ah * Efektif Ah * eta_SOC)
        cell_max_gas_L: List[float] = []
        cell_gas_fractions: List[Dict[str, float]] = []

        for i in range(n_cells):
            chem = cell_chemistries[i]
            base_cap_ah = float(getattr(chem, "nominal_capacity_Ah", 5.0))
            ref_mass_kg = max(0.01, float(getattr(chem, "nominal_mass", 0.046)))
            cell_mass_kg = float(getattr(cells[i], "mass", ref_mass_kg))
            eff_cap_ah = base_cap_ah * (cell_mass_kg / ref_mass_kg)

            yield_l_per_ah = float(getattr(chem, "gas_yield_L_per_Ah", 1.5))
            fractions = getattr(chem, "gas_fractions", {
                "CO2": 0.40, "CO": 0.28, "H2": 0.18, "CH4": 0.09, "C2H4": 0.05
            })
            cell_max_gas_L.append(eff_cap_ah * yield_l_per_ah * eta_soc)
            cell_gas_fractions.append(fractions)

        # 2. Zamana bağlı kümülatif gaz salınımı V_gas(t) [L STP]
        total_gas_stp_L = np.zeros(n_steps, dtype=np.float64)
        species_totals_L: Dict[str, float] = {}

        for i in range(n_cells):
            alphas = np.array(alpha_history.get(i, alpha_history.get(str(i), [0.0] * n_steps)), dtype=np.float64)
            cell_gas = alphas * cell_max_gas_L[i]
            total_gas_stp_L += cell_gas

            final_alpha = alphas[-1] if len(alphas) > 0 else 0.0
            cell_final_gas = final_alpha * cell_max_gas_L[i]
            for gas, frac in cell_gas_fractions[i].items():
                species_totals_L[gas] = species_totals_L.get(gas, 0.0) + cell_final_gas * frac

        final_total_gas_L = float(total_gas_stp_L[-1]) if n_steps > 0 else 0.0

        # Karışım tür oranları
        species_fractions: Dict[str, float] = {}
        if final_total_gas_L > 1e-4:
            for gas, vol in species_totals_L.items():
                species_fractions[gas] = round(vol / final_total_gas_L, 4)
        else:
            species_fractions = cell_gas_fractions[0] if cell_gas_fractions else {}

        # Karışım LEL hesabı
        lel_mix_percent = cls.calculate_le_chatelier_lel(species_fractions)

        # 3. Anlık gaz salınım hızı dV/dt (L/s)
        gas_generation_rate_L_per_s = np.zeros(n_steps, dtype=np.float64)
        for s in range(1, n_steps):
            dt = max(1e-4, time_points[s] - time_points[s-1])
            gas_generation_rate_L_per_s[s] = max(0.0, (total_gas_stp_L[s] - total_gas_stp_L[s-1]) / dt)

        peak_vent_rate_L_s = float(np.max(gas_generation_rate_L_per_s))

        # 4. Mahfaza hacmi ve patlama konsantrasyonu analizi
        enclosure_analysis: Optional[Dict[str, Any]] = None
        min_recommended_vent_cm2 = 0.0

        if enclosure_free_vol_L is not None and enclosure_free_vol_L > 0.0:
            free_vol_m3 = enclosure_free_vol_L * 1e-3
            # Havadaki toplam gaz konsantrasyonu (% hacim)
            gas_conc_pct = (total_gas_stp_L / enclosure_free_vol_L) * 100.0

            # Karışımdaki toplam yanıcı gaz fraksiyonu
            flammable_species_sum = sum(
                frac for gas, frac in species_fractions.items() if gas in PURE_LEL_PERCENT
            )
            flammable_conc_pct = gas_conc_pct * flammable_species_sum

            # LEL yüzdesi (% LEL)
            lel_ratio_pct = (flammable_conc_pct / max(0.1, lel_mix_percent)) * 100.0
            peak_lel_ratio = float(np.max(lel_ratio_pct))

            # 5. Basınç Birikimi Analitiği (Aşırı Basınç - Overpressure transient ΔP kPa)
            # Standart orifis tahliyesi: Q_out = Cd * A * sqrt(2 * delta_P / rho_gas)
            delta_p_kpa = np.zeros(n_steps, dtype=np.float64)
            a_vent_m2 = max(1e-6, vent_valve_area_cm2 * 1e-4)
            cd = 0.62  # Orifis debi katsayısı
            t_gas_k = 473.15  # 200°C ortalama menfez gaz sıcaklığı
            rho_gas = 1.0     # kg/m3 menfez gaz yoğunluğu
            current_p_kpa = 0.0
            vent_activated = False

            for s in range(1, n_steps):
                dt = max(1e-4, time_points[s] - time_points[s-1])
                # Gaz giriş debisi m3/s (enclosure sıcaklığında)
                vol_rate_m3_s = (gas_generation_rate_L_per_s[s] * 1e-3) * (t_gas_k / 298.15)

                # Valf açılma kontrolü (Patlama diski açıldıktan sonra açık kalır)
                if current_p_kpa >= vent_burst_pressure_kpa:
                    vent_activated = True

                if vent_activated:
                    dp_pa = max(0.0, current_p_kpa * 1000.0)
                    outflow_m3_s = cd * a_vent_m2 * math.sqrt(2.0 * dp_pa / rho_gas)
                else:
                    outflow_m3_s = 0.0

                net_dn_dt = (vol_rate_m3_s - outflow_m3_s)
                # dP/dt = (P_atm / V_free) * dV_net
                dp_dt_kpa = (P_ATM_PA * 1e-3 / free_vol_m3) * net_dn_dt
                current_p_kpa = max(0.0, current_p_kpa + dp_dt_kpa * dt)
                delta_p_kpa[s] = current_p_kpa

            peak_overpressure_kpa = float(np.max(delta_p_kpa))

            # NFPA 68 bazlı emniyetli minimum tahliye alanı (cm2)
            # Hedef: Azami aşırı basıncın 50 kPa'yı aşmaması
            target_p_pa = 50000.0
            peak_flow_m3_s = (peak_vent_rate_L_s * 1e-3) * (t_gas_k / 298.15)
            if peak_flow_m3_s > 0:
                required_a_m2 = peak_flow_m3_s / (cd * math.sqrt(2.0 * target_p_pa / rho_gas))
                min_recommended_vent_cm2 = round(required_a_m2 * 1e4, 2)
            else:
                min_recommended_vent_cm2 = 1.0

            enclosure_analysis = {
                "enclosure_free_vol_L": round(float(enclosure_free_vol_L), 2),
                "enclosure_volume_auto_estimated": bool(enclosure_volume_auto_estimated),
                "peak_gas_conc_percent": round(float(np.max(gas_conc_pct)), 2),
                "peak_lel_ratio_percent": round(peak_lel_ratio, 1),
                "is_explosive_atmosphere": bool(peak_lel_ratio >= 100.0),
                "vent_valve_area_cm2": vent_valve_area_cm2,
                "vent_burst_pressure_kpa": vent_burst_pressure_kpa,
                "vent_activated": vent_activated,
                "peak_overpressure_kpa": round(peak_overpressure_kpa, 2),
                "recommended_min_vent_area_cm2": max(1.0, min_recommended_vent_cm2),
                "overpressure_history_kpa": [round(float(p), 2) for p in delta_p_kpa],
                "lel_ratio_history_percent": [round(float(r), 1) for r in lel_ratio_pct]
            }

        return {
            "total_gas_released_stp_L": round(final_total_gas_L, 2),
            "peak_gas_rate_L_per_s": round(peak_vent_rate_L_s, 2),
            "mixture_lel_percent": lel_mix_percent,
            "soc_gas_yield_factor": round(eta_soc, 3),
            "species_totals_L": {g: round(v, 2) for g, v in species_totals_L.items()},
            "species_fractions": species_fractions,
            "gas_volume_history_L": [round(float(v), 2) for v in total_gas_stp_L],
            "gas_rate_history_L_s": [round(float(r), 2) for r in gas_generation_rate_L_per_s],
            "enclosure_analysis": enclosure_analysis
        }
