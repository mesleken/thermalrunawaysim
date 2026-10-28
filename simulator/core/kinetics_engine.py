"""
Kinetik Motoru (ArrheniusKineticsEngine)
Hücre içerisindeki ekzotermik reaksiyon hızını ve ısı üretimini hesaplar.
Hem klasik tek-adımlı Arrhenius kinetiğini hem de Aşama 1 Çoklu-Reaksiyon Kinetiğini
(SEI ayrışması, Anot-elektrolit, Separatör erimesi [endotermik], Katot bozunumu) destekler.
"""

from typing import Dict, Any, Optional, List
import json
from pathlib import Path
import math
import numpy as np

from simulator.core.constants import R_GAS, KELVIN_ZERO_C


class SubReaction:
    """Tekil bir alt reaksiyon modeli (Aşama 1 Çoklu-Reaksiyon Kinetiği)."""
    def __init__(
        self,
        key: str,
        name: str,
        A_per_s: float,
        Ea_J_per_mol: float,
        delta_H_J_per_kg: float,  # Negatif değer = Endotermik ısı yutumu (örn. separatör erimesi)
        n: float = 1.0,
        m_autocatalytic: float = 0.0,
        T_onset_K: float = 273.15,
        description: str = ""
    ):
        self.key = key
        self.name = name
        self.A = float(A_per_s)
        self.Ea = float(Ea_J_per_mol)
        self.delta_H = float(delta_H_J_per_kg)
        self.n = float(n)
        self.m_autocatalytic = float(m_autocatalytic)
        self.T_onset_K = float(T_onset_K)
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "A_per_s": self.A,
            "Ea_J_per_mol": self.Ea,
            "delta_H_J_per_kg": self.delta_H,
            "delta_H_J_per_g": self.delta_H / 1000.0,
            "n": self.n,
            "m_autocatalytic": self.m_autocatalytic,
            "T_onset_K": self.T_onset_K,
            "T_onset_C": self.T_onset_K - KELVIN_ZERO_C,
            "description": self.description
        }


def get_default_sub_reactions(chemistry_id: str) -> List[SubReaction]:
    """
    Literatür (Hatchard-Dahn / Kim-Sharifi ROM) bazlı 4 kademeli alt reaksiyon seti:
    1. SEI tabakası ayrışması (ekzotermik)
    2. Anot-elektrolit reaksiyonu (ekzotermik)
    3. Separatör erimesi (ENDOTERMİK: delta_H < 0, ısı yutar ve kaçağı geciktirir!)
    4. Katot bozunumu ve oksijen salınımı (şiddetli ekzotermik, otakatalitik)
    """
    chem_upper = chemistry_id.upper()
    is_lfp = "LFP" in chem_upper or "LMFP" in chem_upper
    is_811 = "811" in chem_upper
    is_nca = "NCA" in chem_upper
    is_na = "NAION" in chem_upper or "SODIUM" in chem_upper

    if is_lfp:
        is_lmfp = "LMFP" in chem_upper
        dH_cat = 4.4e5 if is_lmfp else 3.2e5
        Ea_cat = 158000.0 if is_lmfp else 165000.0
        A_cat = 3.5e13 if is_lmfp else 1.5e13
        return [
            SubReaction(
                key="sei_decomposition",
                name="SEI Tabakası Ayrışması",
                A_per_s=1.2e15,
                Ea_J_per_mol=135000.0,
                delta_H_J_per_kg=2.0e5,  # 200 J/g
                n=1.0,
                m_autocatalytic=0.0,
                T_onset_K=363.15,  # 90°C
                description="Katı elektrolit arayüzünün ilk termal parçalanması"
            ),
            SubReaction(
                key="anode_electrolyte",
                name="Anot-Elektrolit Reaksiyonu",
                A_per_s=2.0e13,
                Ea_J_per_mol=135000.0,
                delta_H_J_per_kg=4.5e5,  # 450 J/g
                n=1.0,
                m_autocatalytic=0.0,
                T_onset_K=398.15,  # 125°C
                description="Lityumlu karbon anotu ile solvent etkileşimi"
            ),
            SubReaction(
                key="separator_melting",
                name="Separatör Erimesi (Endotermik Faz Geçişi)",
                A_per_s=1.5e16,
                Ea_J_per_mol=138000.0,
                delta_H_J_per_kg=-4.8e4,  # -48 J/g (PE/PP Endotermik erime gizli ısısı)
                n=1.0,
                m_autocatalytic=0.0,
                T_onset_K=405.15,  # 132°C
                description="PE/PP membran erirken faz değişimiyle ısı emer (Soğuma etkisi)"
            ),
            SubReaction(
                key="cathode_decomposition",
                name="Katot Bozunumu (Fosfat Kafes)",
                A_per_s=A_cat,
                Ea_J_per_mol=Ea_cat,
                delta_H_J_per_kg=dH_cat,  # 320-440 J/g
                n=1.0,
                m_autocatalytic=0.5,
                T_onset_K=483.15 if is_lmfp else 493.15,  # 210°C / 220°C
                description="Fosfat kristal yapısının yüksek sıcaklıkta kararlı bozunumu"
            )
        ]
    else:
        # NMC / NMC811 / NCA / Standart Li-ion / Na-ion
        if is_811:
            A_cat = 3.5e14
            Ea_cat = 142000.0
            dH_cat = 7.5e5
            T_cat_onset = 428.15  # 155°C
        elif is_nca:
            A_cat = 4.0e14
            Ea_cat = 138000.0
            dH_cat = 7.8e5
            T_cat_onset = 418.15  # 145°C
        elif is_na:
            A_cat = 1.8e14
            Ea_cat = 145000.0
            dH_cat = 4.8e5
            T_cat_onset = 453.15  # 180°C
        else:
            A_cat = 2.5e14
            Ea_cat = 145000.0
            dH_cat = 6.2e5
            T_cat_onset = 448.15  # 175°C

        return [
            SubReaction(
                key="sei_decomposition",
                name="SEI Tabakası Ayrışması",
                A_per_s=1.66e15,
                Ea_J_per_mol=135000.0,
                delta_H_J_per_kg=2.57e5,  # 257 J/g
                n=1.0,
                m_autocatalytic=0.0,
                T_onset_K=353.15,  # 80°C
                description="SEI metastable tabakasının ilk ekzotermik çözünmesi"
            ),
            SubReaction(
                key="anode_electrolyte",
                name="Anot-Elektrolit Reaksiyonu",
                A_per_s=2.5e13,
                Ea_J_per_mol=135000.0,
                delta_H_J_per_kg=8.5e5,  # 850 J/g
                n=1.0,
                m_autocatalytic=0.0,
                T_onset_K=393.15,  # 120°C
                description="Çıplak lityumlu grafit ile organik solvent yanması"
            ),
            SubReaction(
                key="separator_melting",
                name="Separatör Erimesi (Endotermik Faz Değişimi)",
                A_per_s=1.5e16,
                Ea_J_per_mol=138000.0,
                delta_H_J_per_kg=-4.8e4,  # -48 J/g (PE/PP Endotermik faz değişimi: Kaçağı geciktirir)
                n=1.0,
                m_autocatalytic=0.0,
                T_onset_K=403.15,  # 130°C
                description="Polimer membran faz değişimi sırasında çevre ısısını soğurur"
            ),
            SubReaction(
                key="cathode_decomposition",
                name="Katot Bozunumu ve Oksijen Salınımı",
                A_per_s=A_cat,
                Ea_J_per_mol=Ea_cat,
                delta_H_J_per_kg=dH_cat,  # 620-780 J/g
                n=1.0,
                m_autocatalytic=0.75,
                T_onset_K=T_cat_onset,
                description="Metal oksit kafes çökmesi ve oksijen salınımıyla şiddetli alevlenme"
            )
        ]


class ChemistryParams:
    """Tekil bir hücre kimyasına ait Arrhenius kinetik, elektriksel ve termal parametreleri."""
    def __init__(
        self,
        chemistry_id: str,
        name: str,
        A_pre_exponential_per_s: float,
        Ea_J_per_mol: float,
        delta_H_J_per_kg: float,
        T_onset_K: float,
        T_trigger_K: float,
        n_reaction_order: float = 1.0,
        nominal_mass_kg: float = 0.046,
        nominal_cp_J_per_kg_K: float = 1050.0,
        active_mass_ratio: float = 0.55,
        nominal_voltage_V: float = 3.7,
        nominal_capacity_Ah: float = 2.6,
        internal_resistance_ohm: float = 0.02,
        gas_yield_L_per_Ah: float = 1.75,
        gas_fractions: Optional[Dict[str, float]] = None,
        uncertainty: Optional[Dict[str, Any]] = None,
        source_references: Optional[list] = None,
        source_type: str = "built_in",
        sub_reactions: Optional[List[SubReaction]] = None
    ):
        self.chemistry_id = chemistry_id
        self.name = name
        self.A = float(A_pre_exponential_per_s)
        self.Ea = float(Ea_J_per_mol)
        self.delta_H = float(delta_H_J_per_kg)
        self.T_onset_K = float(T_onset_K)
        self.T_trigger_K = float(T_trigger_K)
        self.n = float(n_reaction_order)
        self.nominal_mass = float(nominal_mass_kg)
        self.nominal_cp = float(nominal_cp_J_per_kg_K)
        self.active_mass_ratio = float(active_mass_ratio)
        self.nominal_voltage = float(nominal_voltage_V)
        self.nominal_capacity_Ah = float(nominal_capacity_Ah)
        self.internal_resistance_ohm = float(internal_resistance_ohm)
        self.gas_yield_L_per_Ah = float(gas_yield_L_per_Ah)
        self.gas_fractions = gas_fractions or {"CO2": 0.40, "CO": 0.25, "H2": 0.25, "CH4": 0.06, "C2H4": 0.04}
        self.uncertainty = uncertainty or {}
        self.source_references = source_references or []
        self.source_type = source_type
        self.sub_reactions = sub_reactions if sub_reactions is not None else get_default_sub_reactions(chemistry_id)

    def scale_kinetics(self, a_factor: float = 1.0, ea_factor: float = 1.0, dh_factor: float = 1.0) -> "ChemistryParams":
        """Monte Carlo ve Gelişmiş Fizik için ekzotermik reaksiyonları ölçekleyen kopya üretir."""
        new_sub = [
            SubReaction(
                key=sr.key,
                name=sr.name,
                A_per_s=(sr.A * a_factor) if sr.delta_H > 0 else sr.A,
                Ea_J_per_mol=(sr.Ea * ea_factor) if sr.delta_H > 0 else sr.Ea,
                delta_H_J_per_kg=(sr.delta_H * dh_factor) if sr.delta_H > 0 else sr.delta_H,
                n=sr.n,
                m_autocatalytic=sr.m_autocatalytic,
                T_onset_K=sr.T_onset_K,
                description=sr.description
            )
            for sr in self.sub_reactions
        ]
        return ChemistryParams(
            chemistry_id=self.chemistry_id,
            name=self.name,
            A_pre_exponential_per_s=self.A * a_factor,
            Ea_J_per_mol=self.Ea * ea_factor,
            delta_H_J_per_kg=self.delta_H * dh_factor,
            T_onset_K=self.T_onset_K,
            T_trigger_K=self.T_trigger_K,
            n_reaction_order=self.n,
            nominal_mass_kg=self.nominal_mass,
            nominal_cp_J_per_kg_K=self.nominal_cp,
            active_mass_ratio=self.active_mass_ratio,
            nominal_voltage_V=self.nominal_voltage,
            nominal_capacity_Ah=self.nominal_capacity_Ah,
            internal_resistance_ohm=self.internal_resistance_ohm,
            gas_yield_L_per_Ah=self.gas_yield_L_per_Ah,
            gas_fractions=dict(self.gas_fractions),
            uncertainty=self.uncertainty,
            source_references=self.source_references,
            source_type=self.source_type,
            sub_reactions=new_sub
        )

    def apply_soc_scaling(self, soc_percent: float = 100.0) -> "ChemistryParams":
        """
        Şarj Durumu (SOC %0-100) etkisi:
        - Düşük SOC'de aktif lityum miktarı azaldığı için ekzotermik reaksiyon entalpisi düşer:
          eta_dH = 0.25 + 0.75 * (SOC/100)^1.15
        - Endotermik separatör erimesi (delta_H < 0) fiziksel faz geçişi olduğundan SOC'den bağımsız kalır.
        - Aktivasyon bariyeri yükselir: delta_Ea = 4500 * (1 - SOC/100)
        - Onset ve trigger sıcaklıkları ötelenir
        """
        s = max(0.0, min(1.0, float(soc_percent) / 100.0))
        dh_factor = 0.25 + 0.75 * (s ** 1.15)
        ea_shift = 4500.0 * (1.0 - s)
        onset_shift_K = 18.0 * (1.0 - s)

        # scale_kinetics zaten hem tek-kademeli delta_H'ı hem de ekzotermik (sr.delta_H > 0) alt reaksiyonları
        # tek sefer ölçekler ve endotermik separatörü korur. Çift ölçekleme yapılmaz!
        scaled = self.scale_kinetics(dh_factor=dh_factor)
        scaled.Ea += ea_shift
        scaled.T_onset_K += onset_shift_K
        scaled.T_trigger_K += onset_shift_K

        for sr in scaled.sub_reactions:
            if sr.delta_H > 0:
                sr.Ea += ea_shift
                sr.T_onset_K += onset_shift_K

        return scaled

    @classmethod
    def from_dict(cls, data: Dict[str, Any], source_type: str = "built_in") -> "ChemistryParams":
        chem_id = data["chemistry_id"]
        sub_rxns = None
        if "sub_reactions" in data and isinstance(data["sub_reactions"], list):
            sub_rxns = []
            for idx, sr in enumerate(data["sub_reactions"]):
                if isinstance(sr, SubReaction):
                    sub_rxns.append(sr)
                elif isinstance(sr, dict):
                    dh_val = sr.get("delta_H_J_per_kg")
                    if dh_val is None and sr.get("delta_H_J_per_g") is not None:
                        dh_val = float(sr["delta_H_J_per_g"]) * 1000.0
                    if dh_val is None:
                        dh_val = 500000.0
                    ea_val = sr.get("Ea_J_per_mol")
                    if ea_val is None and sr.get("Ea_kJ_per_mol") is not None:
                        ea_val = float(sr["Ea_kJ_per_mol"]) * 1000.0
                    if ea_val is None:
                        ea_val = 130000.0
                    sub_rxns.append(
                        SubReaction(
                            key=sr.get("key", f"rxn_{idx}"),
                            name=sr.get("name", "Alt Reaksiyon"),
                            A_per_s=float(sr.get("A_per_s", sr.get("A", 1e14))),
                            Ea_J_per_mol=float(ea_val),
                            delta_H_J_per_kg=float(dh_val),
                            n=float(sr.get("n", 1.0)),
                            m_autocatalytic=float(sr.get("m_autocatalytic", 0.0)),
                            T_onset_K=float(sr.get("T_onset_K", (sr["T_onset_C"] + KELVIN_ZERO_C) if "T_onset_C" in sr else 373.15)),
                            description=sr.get("description", "")
                        )
                    )

        return cls(
            chemistry_id=chem_id,
            name=data.get("name", chem_id),
            A_pre_exponential_per_s=data.get("A_pre_exponential_per_s", 3.0e14),
            Ea_J_per_mol=data.get("Ea_J_per_mol") or (data.get("Ea_kJ_per_mol", 130.0) * 1000.0) or 130000.0,
            delta_H_J_per_kg=data.get("delta_H_J_per_kg") or (data.get("delta_H_J_per_g", 500.0) * 1000.0),
            T_onset_K=data.get("T_onset_K") or (data.get("T_onset_C", 155.0) + KELVIN_ZERO_C),
            T_trigger_K=data.get("T_trigger_K") or (data.get("T_trigger_C", 200.0) + KELVIN_ZERO_C),
            n_reaction_order=data.get("n_reaction_order", 1.0),
            nominal_mass_kg=data.get("nominal_mass_kg", 0.046),
            nominal_cp_J_per_kg_K=data.get("nominal_cp_J_per_kg_K", 1050.0),
            active_mass_ratio=data.get("active_mass_ratio", 0.55),
            nominal_voltage_V=data.get("nominal_voltage_V", 3.7),
            nominal_capacity_Ah=data.get("nominal_capacity_Ah", 2.6),
            internal_resistance_ohm=data.get("internal_resistance_ohm", 0.02),
            gas_yield_L_per_Ah=data.get("gas_yield_L_per_Ah", 1.75),
            gas_fractions=data.get("gas_fractions"),
            uncertainty=data.get("uncertainty", {}),
            source_references=data.get("source_references", []),
            source_type=data.get("source_type", source_type),
            sub_reactions=sub_rxns
        )


class ArrheniusKineticsEngine:
    """Arrhenius bozunma ve ekzotermik reaksiyon ısı motoru."""

    def __init__(self, library_path: Optional[str] = None):
        self.library: Dict[str, ChemistryParams] = {}
        
        base_dir = Path(__file__).resolve().parent.parent.parent
        main_lib = base_dir / "data" / "chemistry_library.json"
        user_lib = base_dir / "data" / "user_chemistry_library.json"
        
        if library_path is not None:
            if Path(library_path).exists():
                self.load_library(library_path, source_type="user_defined")
        else:
            if main_lib.exists():
                self.load_library(str(main_lib), source_type="built_in")
            if user_lib.exists():
                self.load_library(str(user_lib), source_type="user_defined")

    def load_library(self, path: str, source_type: str = "built_in"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for item in data.get("chemistries", []):
                params = ChemistryParams.from_dict(item, source_type=source_type)
                self.library[params.chemistry_id] = params
        except Exception as e:
            print(f"UYARI: {path} kütüphanesi yüklenemedi: {e}")

    def get_params(self, chemistry_id: str) -> ChemistryParams:
        if chemistry_id not in self.library:
            raise KeyError(f"Kimya ID '{chemistry_id}' kütüphanede bulunamadı. Mevcut: {list(self.library.keys())}")
        return self.library[chemistry_id]

    def reaction_rate(self, alpha: float, T_K: float, params: ChemistryParams) -> float:
        """
        Tek adımlı reaksiyon ilerleme hızı: d(alpha)/dt = A * exp(-Ea / (R * T)) * (1 - alpha)^n
        Sayısal taşmaları ve negatif reaksiyon hızlarını önlemek için güvenli sınırlandırma uygulanır.
        """
        if alpha >= 1.0 or T_K <= 0.0:
            return 0.0

        reactant_term = max(0.0, 1.0 - alpha) ** params.n
        if reactant_term <= 1e-12:
            return 0.0

        exponent = -params.Ea / (R_GAS * T_K)
        if exponent < -80.0:
            return 0.0
        if exponent > 0.0:
            exponent = 0.0

        dalpha_dt = params.A * math.exp(exponent) * reactant_term
        return max(0.0, float(dalpha_dt))

    def multi_reaction_rates(
        self,
        alphas: np.ndarray,
        T_K: float,
        sub_reactions: List[SubReaction]
    ) -> np.ndarray:
        """
        Aşama 1 Çoklu Reaksiyon Kinetiği:
        Her k alt reaksiyonu için d(alpha_k)/dt türevlerini hesaplar.
        """
        rates = np.zeros(len(sub_reactions), dtype=np.float64)
        if T_K <= 0.0:
            return rates

        for k, rxn in enumerate(sub_reactions):
            alpha_k = float(alphas[k])
            if alpha_k >= 1.0:
                rates[k] = 0.0
                continue

            reactant_term = max(0.0, 1.0 - alpha_k) ** rxn.n
            if reactant_term <= 1e-12:
                rates[k] = 0.0
                continue

            if rxn.m_autocatalytic > 0.0:
                cat_term = max(0.015, alpha_k) ** rxn.m_autocatalytic
            else:
                cat_term = 1.0

            # Endotermik faz geçişi (PE/PP separatör erimesi) için pürüzsüz erime eşiği kapısı (smooth sigmoid gate):
            # Erime sıcaklığının (T_onset_K ~130-135°C) altında erken faz geçişini önler ve Jacobian sürekliliğini korur.
            onset_gate = 1.0
            if rxn.delta_H < 0.0 and rxn.T_onset_K > 300.0:
                z = (T_K - rxn.T_onset_K) / 2.5
                if z < -20.0:
                    rates[k] = 0.0
                    continue
                elif z < 20.0:
                    onset_gate = 1.0 / (1.0 + math.exp(-z))

            exponent = -rxn.Ea / (R_GAS * T_K)
            if exponent < -80.0:
                rates[k] = 0.0
            elif exponent > 0.0:
                rates[k] = rxn.A * reactant_term * cat_term * onset_gate
            else:
                rates[k] = rxn.A * math.exp(exponent) * reactant_term * cat_term * onset_gate

        return rates

    def heat_generation_rate(
        self,
        dalpha_dt: float,
        cell_mass_kg: float,
        params: ChemistryParams,
        ohmic_power_W: float = 0.0,
        external_trigger_power_W: float = 0.0
    ) -> float:
        """
        Tek adımlı toplam ısı üretim gücü Q_dot (Watt = J/s):
        Q_dot = m_cell * active_mass_ratio * delta_H * (dalpha/dt) + Q_ohmic + Q_external
        """
        active_mass = cell_mass_kg * getattr(params, "active_mass_ratio", 0.55)
        q_chemical = active_mass * params.delta_H * dalpha_dt
        return float(q_chemical + ohmic_power_W + external_trigger_power_W)

    def multi_heat_generation_rate(
        self,
        dalpha_dt_array: np.ndarray,
        cell_mass_kg: float,
        sub_reactions: List[SubReaction],
        active_mass_ratio: float = 0.55,
        ohmic_power_W: float = 0.0,
        external_trigger_power_W: float = 0.0
    ) -> float:
        """
        Aşama 1 Çoklu Reaksiyon Isı Üretimi:
        Q_chem = m_active * sum_k (delta_H_k * dalpha_k/dt)
        Not: Separatör erimesinde delta_H_k negatif olduğundan sistemden ısı emer (endotermik soğuma).
        """
        active_mass = cell_mass_kg * active_mass_ratio
        q_chemical = 0.0
        for k, rxn in enumerate(sub_reactions):
            q_chemical += active_mass * rxn.delta_H * float(dalpha_dt_array[k])

        return float(q_chemical + ohmic_power_W + external_trigger_power_W)
