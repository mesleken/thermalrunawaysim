"""
Kinetik Motoru (ArrheniusKineticsEngine)
Hücre içerisindeki ekzotermik reaksiyon hızını ve ısı üretimini hesaplar.
Faz 0 parametre kütüphanesi ve Faz 0.5 Sözleşme 1'e tam uyumlu.
"""

from typing import Dict, Any, Optional
import json
from pathlib import Path
import math
import numpy as np

from simulator.core.constants import R_GAS, KELVIN_ZERO_C

class ChemistryParams:
    """Tekil bir hücre kimyasına ait Arrhenius kinetik ve termal parametreleri."""
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
        uncertainty: Optional[Dict[str, Any]] = None,
        source_references: Optional[list] = None,
        source_type: str = "built_in"
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
        self.uncertainty = uncertainty or {}
        self.source_references = source_references or []
        self.source_type = source_type

    @classmethod
    def from_dict(cls, data: Dict[str, Any], source_type: str = "built_in") -> "ChemistryParams":
        return cls(
            chemistry_id=data["chemistry_id"],
            name=data.get("name", data["chemistry_id"]),
            A_pre_exponential_per_s=data.get("A_pre_exponential_per_s", 3.0e14),
            Ea_J_per_mol=data.get("Ea_J_per_mol") or (data.get("Ea_kJ_per_mol", 130.0) * 1000.0) or 130000.0,
            delta_H_J_per_kg=data.get("delta_H_J_per_kg") or (data.get("delta_H_J_per_g", 500.0) * 1000.0),
            T_onset_K=data.get("T_onset_K") or (data.get("T_onset_C", 155.0) + KELVIN_ZERO_C),
            T_trigger_K=data.get("T_trigger_K") or (data.get("T_trigger_C", 200.0) + KELVIN_ZERO_C),
            n_reaction_order=data.get("n_reaction_order", 1.0),
            nominal_mass_kg=data.get("nominal_mass_kg", 0.046),
            nominal_cp_J_per_kg_K=data.get("nominal_cp_J_per_kg_K", 1050.0),
            active_mass_ratio=data.get("active_mass_ratio", 0.55),
            uncertainty=data.get("uncertainty", {}),
            source_references=data.get("source_references", []),
            source_type=data.get("source_type", source_type)
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
        Reaksiyon ilerleme hızı: d(alpha)/dt = A * exp(-Ea / (R * T)) * (1 - alpha)^n
        Sayısal taşmaları ve negatif reaksiyon hızlarını önlemek için güvenli sınırlandırma uygulanır.
        """
        if alpha >= 1.0 or T_K <= 0.0:
            return 0.0

        # Kalan reaktant konsantrasyonu terimi: (1 - alpha)^n
        reactant_term = max(0.0, 1.0 - alpha) ** params.n
        if reactant_term <= 1e-12:
            return 0.0

        # Arrhenius üslü terimi: exp(-Ea / (R * T))
        exponent = -params.Ea / (R_GAS * T_K)
        # Sayısal alt taşmayı önleme: -80'in altı efektif 0'dır
        if exponent < -80.0:
            return 0.0
        # Sayısal üst taşmayı önleme
        if exponent > 0.0:
            exponent = 0.0

        dalpha_dt = params.A * math.exp(exponent) * reactant_term
        return max(0.0, float(dalpha_dt))

    def heat_generation_rate(
        self,
        dalpha_dt: float,
        cell_mass_kg: float,
        params: ChemistryParams,
        ohmic_power_W: float = 0.0,
        external_trigger_power_W: float = 0.0
    ) -> float:
        """
        Toplam ısı üretim gücü Q_dot (Watt = J/s):
        Q_dot = m_cell * active_mass_ratio * delta_H * (dalpha/dt) + Q_ohmic + Q_external
        """
        active_mass = cell_mass_kg * getattr(params, "active_mass_ratio", 0.55)
        q_chemical = active_mass * params.delta_H * dalpha_dt
        return float(q_chemical + ohmic_power_W + external_trigger_power_W)
