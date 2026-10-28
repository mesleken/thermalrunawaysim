"""
Hücre Modeli (CellModel)
Tek bir pil hücresinin fiziksel, geometrik, termal ve reaksiyon durumunu tutar.
Faz 0.5 Sözleşme 1 (Kelvin birimi, alpha [0,1], CellState) ile birebir uyumludur.
Aşama 1: Core-Shell (1D radyal iç jöle rulo ve dış kovan) düğüm desteği eklendi.
"""

from typing import Dict, Any, Optional
import math
from simulator.core.constants import CellState, CellFormat, CYLINDRICAL_SPECS, kelvin_to_celsius, celsius_to_kelvin

class CellGeometry:
    """Hücre geometrik boyutları, yüzey alanı ve Core-Shell iletim hesaplamaları."""
    def __init__(
        self,
        format_type: str,
        specs: Optional[Dict[str, Any]] = None,
        diameter: Optional[float] = None,
        height: Optional[float] = None,
        length: Optional[float] = None,
        width: Optional[float] = None,
        thickness: Optional[float] = None,
        casing_thickness_m: float = 0.0003  # 0.3 mm metalik dış gövde
    ):
        self.format_type = format_type
        self.casing_thickness_m = float(casing_thickness_m)

        # Geometri tipini güvenli normalize et
        format_str = str(format_type).lower()
        if specs and specs.get("type"):
            self.geometry_type = str(specs["type"]).lower()
        elif "pouch" in format_str:
            self.geometry_type = "pouch"
        elif "prismatic" in format_str or format_type == CellFormat.PRISMATIC:
            self.geometry_type = "prismatic"
        else:
            self.geometry_type = "cylindrical"

        if self.geometry_type in ("prismatic", "pouch"):
            self.length = length or (specs.get("length") if specs else None) or (specs.get("width", 0.148) if specs else 0.148)
            self.height = height or (specs.get("height", 0.098) if specs else 0.098)
            self.thickness = thickness or width or (specs.get("thickness", 0.027) if specs else 0.027)
            self.diameter = math.sqrt(self.length * self.thickness * 4.0 / math.pi)
            self.radius = self.diameter / 2.0
            self.width = self.length
        elif specs and self.geometry_type == "cylindrical":
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
    def volume(self) -> float:
        """Hücre toplam hacmi (m^3)."""
        if self.geometry_type in ("prismatic", "pouch"):
            return float(self.length * self.thickness * self.height)
        else:
            return float(math.pi * (self.radius ** 2) * self.height)

    @property
    def core_radius(self) -> float:
        """İç aktif jöle rulo (Core) yarıçapı (m)."""
        return max(0.001, self.radius - self.casing_thickness_m)

    @property
    def surface_area(self) -> float:
        """Toplam dış konveksiyonel yüzey alanı (m^2)."""
        if self.geometry_type in ("prismatic", "pouch"):
            return 2.0 * (self.length * self.height + self.length * self.thickness + self.height * self.thickness)
        else:
            # Silindirik: 2 * pi * r * h + 2 * pi * r^2
            lateral = 2.0 * math.pi * self.radius * self.height
            caps = 2.0 * math.pi * (self.radius ** 2)
            return lateral + caps

    @property
    def bottom_area(self) -> float:
        """Soğutma plakası ile temas eden taban alanı (m^2)."""
        if self.geometry_type in ("prismatic", "pouch"):
            return self.length * self.thickness
        else:
            return math.pi * (self.radius ** 2)

    @property
    def lateral_projected_area(self) -> float:
        """Komşu hücreye bakan yanal projeksiyon alanı (m^2)."""
        if self.geometry_type in ("prismatic", "pouch"):
            return self.height * self.length
        else:
            return self.diameter * self.height

    def get_core_shell_conductance(
        self,
        k_radial: float = 0.8,
        k_casing: float = 50.0,
        r_contact_m2K_W: float = 1.5e-4
    ) -> float:
        """
        Aşama 1 & V2: Forgez-Lin analitik hacimsel radyal iletim + temas + kovan direnci (W/K).
        Silindirik: R_cs = 1/(8*pi*k_r*H) + R_contact/(2*pi*R_in*H) + ln(R_out/R_in)/(2*pi*k_case*H)
        Prizmatik/Pouch: R_cs = (thickness/2)/(3*k_r*A_broad) + R_contact/A_broad + t_case/(k_case*A_broad)
        """
        if self.geometry_type in ("prismatic", "pouch"):
            a_broad = max(1e-6, 2.0 * self.length * self.height)
            r_core = (self.thickness * 0.5) / (3.0 * k_radial * a_broad)
            r_contact = r_contact_m2K_W / a_broad
            r_case = self.casing_thickness_m / (k_casing * a_broad)
            return 1.0 / max(1e-5, r_core + r_contact + r_case)
        else:
            h = max(1e-4, self.height)
            r_in = self.core_radius
            r_core = 1.0 / (8.0 * math.pi * k_radial * h)
            r_contact = r_contact_m2K_W / (2.0 * math.pi * r_in * h)
            r_case = math.log(max(1.0001, self.radius / r_in)) / (2.0 * math.pi * k_casing * h)
            return 1.0 / max(1e-5, r_core + r_contact + r_case)


class CellModel:
    """Tekil pil hücresi modeli (Tek Düğümlü veya Core-Shell 2 Düğümlü)."""
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

        # Core-Shell Kütle ve Isıl Sığa Dağılımı (Enerji Korunumu ile)
        if self.geometry.geometry_type == "pouch":
            self.core_mass_fraction = 0.92  # Kese hücrede aktif jöle oranı (~%92)
            self.shell_mass_fraction = 0.08  # İnce Al-lamine kılıf (~%8)
            self.shell_cp = 900.0   # J/kg.K (Alüminyum polimer kılıf)
        else:
            self.core_mass_fraction = 0.82  # Silindirik/Prizmatik aktif rulo (~%82)
            self.shell_mass_fraction = 0.18  # Metalik çelik/Al kovan (~%18)
            self.shell_cp = 500.0   # J/kg.K (Kovan)

        self.core_mass = self.mass * self.core_mass_fraction
        self.shell_mass = self.mass * self.shell_mass_fraction

        # Isıl sığa korunumu: m_core * core_cp + m_shell * shell_cp == m * cp
        # Böylece adiyabatik modda Lumped ve Core-Shell tepe sıcaklıkları tam örtüşür
        self.core_cp = max(600.0, (self.cp - (self.shell_mass_fraction * self.shell_cp)) / self.core_mass_fraction)

        # Durum değişkenleri (Kelvin ve boyutsuz alpha)
        self._T_K = float(initial_temp_K)
        self.T_core_K = float(initial_temp_K)
        self.T_shell_K = float(initial_temp_K)
        self._alpha = 0.0
        self.state = CellState.NORMAL

        # Tetiklenme ve olay kayıtları
        self.onset_time: Optional[float] = None
        self.runaway_time: Optional[float] = None
        self.max_temperature_K = float(initial_temp_K)
        self.max_core_temp_K = float(initial_temp_K)
        self.max_shell_temp_K = float(initial_temp_K)
        self.thermal_lag_s: float = 0.0

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
            "format_type": self.geometry.format_type,
            "geometry_type": self.geometry.geometry_type,
            "mass_kg": self.mass,
            "cp_J_per_kg_K": self.cp,
            "pos_x_mm": round(self.pos_x * 1000.0, 2),
            "pos_y_mm": round(self.pos_y * 1000.0, 2),
            "row_idx": self.row_idx,
            "col_idx": self.col_idx,
            "temperature_C": round(self.temperature_C, 2),
            "temperature_K": round(self.temperature_K, 2),
            "max_temperature_C": round(kelvin_to_celsius(self.max_temperature_K), 2),
            "max_core_temp_C": round(kelvin_to_celsius(self.max_core_temp_K), 2),
            "max_shell_temp_C": round(kelvin_to_celsius(self.max_shell_temp_K), 2),
            "thermal_lag_s": round(self.thermal_lag_s, 3),
            "alpha": round(self.alpha, 4),
            "state": self.state.value,
            "onset_time_s": self.onset_time,
            "runaway_time_s": self.runaway_time
        }
