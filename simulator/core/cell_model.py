"""
Hücre Modeli (CellModel)
Tek bir pil hücresinin fiziksel, geometrik, termal ve reaksiyon durumunu tutar.
Faz 0.5 Sözleşme 1 (Kelvin birimi, alpha [0,1], CellState) ile birebir uyumludur.
"""

from typing import Dict, Any, Optional
import math
from simulator.core.constants import CellState, CellFormat, CYLINDRICAL_SPECS, kelvin_to_celsius, celsius_to_kelvin

class CellGeometry:
    """Hücre geometrik boyutları ve yüzey alanı hesaplamaları."""
    def __init__(
        self,
        format_type: str,
        specs: Optional[Dict[str, Any]] = None,
        diameter: Optional[float] = None,
        height: Optional[float] = None,
        length: Optional[float] = None,
        width: Optional[float] = None,
        thickness: Optional[float] = None
    ):
        self.format_type = format_type
        if specs and specs.get("type") == "prismatic":
            self.length = length or specs.get("width", 0.148)
            self.height = height or specs.get("height", 0.098)
            self.thickness = thickness or width or specs.get("thickness", 0.027)
            self.diameter = math.sqrt(self.length * self.thickness * 4.0 / math.pi)
            self.radius = self.diameter / 2.0
        elif specs: # Cylindrical
            self.diameter = diameter or (specs.get("radius", 0.009) * 2.0)
            self.height = height or specs.get("height", 0.065)
            self.radius = self.diameter / 2.0
            self.length = self.diameter
            self.width = self.diameter
            self.thickness = self.diameter
        else:
            # Fallback
            self.diameter = diameter or 0.018
            self.height = height or 0.065
            self.radius = self.diameter / 2.0
            self.length = self.diameter
            self.width = self.diameter
            self.thickness = self.diameter

    @property
    def surface_area(self) -> float:
        """Toplam dış konveksiyonel yüzey alanı (m^2)."""
        if self.format_type == CellFormat.PRISMATIC:
            return 2.0 * (self.length * self.height + self.length * self.thickness + self.height * self.thickness)
        else:
            # Silindirik: 2 * pi * r * h + 2 * pi * r^2
            lateral = 2.0 * math.pi * self.radius * self.height
            caps = 2.0 * math.pi * (self.radius ** 2)
            return lateral + caps

    @property
    def bottom_area(self) -> float:
        """Soğutma plakası ile temas eden taban alanı (m^2)."""
        if self.format_type == CellFormat.PRISMATIC:
            return self.length * self.thickness
        else:
            return math.pi * (self.radius ** 2)

    @property
    def lateral_projected_area(self) -> float:
        """Komşu hücreye bakan yanal projeksiyon alanı (m^2)."""
        if self.format_type == CellFormat.PRISMATIC:
            return self.height * self.length
        else:
            return self.diameter * self.height


class CellModel:
    """Tekil pil hücresi modeli."""
    def __init__(
        self,
        cell_id: int,
        name: str,
        chemistry_id: str,
        mass_kg: float,
        cp_J_per_kg_K: float,
        geometry: CellGeometry,
        pos_x: float,
        pos_y: float,
        row_idx: int = 0,
        col_idx: int = 0,
        initial_temp_K: float = 298.15
    ):
        self.cell_id = cell_id
        self.name = name
        self.chemistry_id = chemistry_id
        self.mass = float(mass_kg)
        self.cp = float(cp_J_per_kg_K)
        self.geometry = geometry
        self.pos_x = float(pos_x)  # Metre cinsinden x konumu
        self.pos_y = float(pos_y)  # Metre cinsinden y konumu
        self.row_idx = row_idx
        self.col_idx = col_idx

        # Durum değişkenleri (Kelvin ve boyutsuz alpha)
        self._T_K = float(initial_temp_K)
        self._alpha = 0.0
        self.state = CellState.NORMAL

        # Tetiklenme ve olay kayıtları
        self.onset_time: Optional[float] = None
        self.runaway_time: Optional[float] = None
        self.max_temperature_K = float(initial_temp_K)

    @property
    def temperature_K(self) -> float:
        return self._T_K

    @temperature_K.setter
    def temperature_K(self, val: float):
        self._T_K = float(val)
        if self._T_K > self.max_temperature_K:
            self.max_temperature_K = self._T_K

    @property
    def temperature_C(self) -> float:
        return kelvin_to_celsius(self._T_K)

    @property
    def alpha(self) -> float:
        return self._alpha

    @alpha.setter
    def alpha(self, val: float):
        self._alpha = max(0.0, min(1.0, float(val)))

    def update_state(self, current_time: float, T_onset_K: float, T_trigger_K: float, dT_dt: float = 0.0):
        """Hücrenin termal kaçak durumunu günceller."""
        if self.alpha >= 0.99:
            self.state = CellState.BURNED_OUT
            return

        if self._T_K >= T_trigger_K or dT_dt >= 1.0:
            if self.state != CellState.RUNAWAY:
                self.state = CellState.RUNAWAY
                if self.runaway_time is None:
                    self.runaway_time = current_time
        elif self._T_K >= T_onset_K:
            if self.state == CellState.NORMAL:
                self.state = CellState.ONSET
                if self.onset_time is None:
                    self.onset_time = current_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "name": self.name,
            "chemistry_id": self.chemistry_id,
            "mass_kg": self.mass,
            "cp_J_per_kg_K": self.cp,
            "pos_x_mm": round(self.pos_x * 1000.0, 2),
            "pos_y_mm": round(self.pos_y * 1000.0, 2),
            "row_idx": self.row_idx,
            "col_idx": self.col_idx,
            "temperature_C": round(self.temperature_C, 2),
            "temperature_K": round(self.temperature_K, 2),
            "max_temperature_C": round(kelvin_to_celsius(self.max_temperature_K), 2),
            "alpha": round(self.alpha, 4),
            "state": self.state.value,
            "onset_time_s": self.onset_time,
            "runaway_time_s": self.runaway_time
        }
