"""
Batarya Paketi Geometrisi ve Topoloji İnşa Edici (PackGeometryBuilder)
Silindirik ve prizmatik hücre dizilimlerini, komşuluk matrisini ve temas alanlarını hesaplar.
"""

from typing import List, Dict, Tuple, Any, Optional
import math
from pathlib import Path
import json

from simulator.core.constants import CellFormat, CYLINDRICAL_SPECS
from simulator.core.cell_model import CellModel, CellGeometry

class NeighborConnection:
    """İki komşu hücre arasındaki geometrik ve termal bağlantı bilgisi."""
    def __init__(
        self,
        cell_i_id: int,
        cell_j_id: int,
        center_distance_m: float,
        surface_gap_m: float,
        contact_area_m2: float,
        separator_material_id: Optional[str] = None,
        separator_thickness_m: float = 0.0,
        gap_material_id: str = "air_gap"
    ):
        self.cell_i_id = cell_i_id
        self.cell_j_id = cell_j_id
        self.center_distance_m = center_distance_m
        self.surface_gap_m = max(1e-6, surface_gap_m)
        self.contact_area_m2 = contact_area_m2
        self.separator_material_id = separator_material_id
        self.separator_thickness_m = separator_thickness_m
        self.gap_material_id = gap_material_id


class PackGeometryBuilder:
    """Hücre koordinatlarını, komşuluk ilişkilerini ve modül topolojisini kurar."""

    def __init__(self, materials_library_path: Optional[str] = None):
        # 1. Varsayılan (Built-in) Hücre Boyutları
        self.CELL_DIMENSIONS = {
            "18650": {"radius": 0.009, "height": 0.065, "mass": 0.046, "cp": 1050.0, "casing_thickness": 0.0003, "type": "cylindrical"},
            "21700": {"radius": 0.0105, "height": 0.070, "mass": 0.068, "cp": 1020.0, "casing_thickness": 0.0003, "type": "cylindrical"},
            "4680": {"radius": 0.023, "height": 0.080, "mass": 0.355, "cp": 1100.0, "casing_thickness": 0.0006, "type": "cylindrical"},
            "Prismatic_50Ah": {"width": 0.148, "thickness": 0.026, "height": 0.095, "mass": 1.15, "cp": 1150.0, "casing_thickness": 0.001, "type": "prismatic"}
        }
        
        base_dir = Path(__file__).resolve().parent.parent.parent
        user_formats_path = base_dir / "data" / "user_formats_library.json"
        if user_formats_path.exists():
            try:
                with open(user_formats_path, "r", encoding="utf-8") as f:
                    usr_formats = json.load(f)
                    for k, v in usr_formats.get("formats", {}).items():
                        self.CELL_DIMENSIONS[k] = v
            except Exception as e:
                print(f"Kullanıcı formatları yüklenirken hata: {e}")

        # 2. Malzeme Kütüphanesini Yükle
        if materials_library_path is None:
            materials_library_path = str(base_dir / "data" / "materials_library.json")
            
        self.materials_lib = {}
        if Path(materials_library_path).exists():
            with open(materials_library_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for mat in data.get("materials", []):
                    self.materials_lib[mat["material_id"]] = mat
                    
        user_mat_path = base_dir / "data" / "user_materials_library.json"
        if user_mat_path.exists():
            try:
                with open(user_mat_path, "r", encoding="utf-8") as f:
                    usr_mats = json.load(f)
                    for mat in usr_mats.get("materials", []):
                        self.materials_lib[mat["material_id"]] = mat
            except Exception as e:
                print(f"Kullanıcı malzemeleri yüklenirken hata: {e}")

    def build_pack(
        self,
        rows: int,
        cols: int,
        cell_format: str = "18650",
        spacing_x_mm: float = 2.0,
        spacing_y_mm: float = 2.0,
        chemistry_id: str = "NMC_generic_v1",
        cell_mass_kg: Optional[float] = None,
        cell_cp_J_per_kg_K: Optional[float] = None,
        staggered: bool = False,
        separator_material_id: Optional[str] = None,
        separator_thickness_mm: float = 0.0,
        gap_material_id: str = "air_gap",
        initial_temp_K: float = 298.15
    ) -> Tuple[List[CellModel], List[NeighborConnection], Dict[str, float]]:
        """
        Kullanıcı girdilerinden hücre listesi, komşuluk bağlantıları ve modül boyutlarını üretir.
        """
        spacing_x_m = float(spacing_x_mm) / 1000.0
        spacing_y_m = float(spacing_y_mm) / 1000.0
        sep_thickness_m = float(separator_thickness_mm) / 1000.0

        format_lookup_key = cell_format
        if cell_format in ["prismatic", CellFormat.PRISMATIC]:
            format_lookup_key = "Prismatic_50Ah"
            
        specs = self.CELL_DIMENSIONS.get(format_lookup_key, self.CELL_DIMENSIONS["18650"])
        sample_geom = CellGeometry(cell_format, specs=specs)
        
        dx_cell = sample_geom.length
        dy_cell = sample_geom.thickness if specs.get("type") == "prismatic" else sample_geom.diameter
        cell_height = sample_geom.height

        mass = cell_mass_kg or specs.get("mass", 0.046)
        cp = cell_cp_J_per_kg_K or specs.get("cp", 1050.0)

        cells: List[CellModel] = []
        cell_id = 0

        # Adım aralıkları (merkezden merkeze)
        pitch_x = dx_cell + spacing_x_m
        pitch_y = dy_cell + spacing_y_m

        for r in range(rows):
            # Staggered (üçgen/heksagonal) dizilim varsa tek sayılı satırları yarı adım kaydır
            row_offset_x = (pitch_x * 0.5) if (staggered and r % 2 == 1) else 0.0
            for c in range(cols):
                pos_x = c * pitch_x + row_offset_x + (dx_cell / 2.0)
                pos_y = r * pitch_y + (dy_cell / 2.0)

                geom = CellGeometry(cell_format, specs=specs)
                cell = CellModel(
                    cell_id=cell_id,
                    name=f"Cell_{r}_{c}",
                    chemistry_id=chemistry_id,
                    mass_kg=mass,
                    cp_J_per_kg_K=cp,
                    geometry=geom,
                    pos_x=pos_x,
                    pos_y=pos_y,
                    row_idx=r,
                    col_idx=c,
                    initial_temp_K=initial_temp_K
                )
                cells.append(cell)
                cell_id += 1

        # Komşuluk bağlantılarını hesapla — yön bazlı ortogonal komşuluk (Von Neumann)
        # Eski 1.45 * max(pitch) eşiği çapraz ve uzak hücreleri yanlışlıkla bağlıyordu.
        # Yeni yaklaşım: X ve Y eksenlerinde ayrı ayrı 1.1 * pitch eşiği uygular.
        threshold_x = 1.1 * pitch_x  # X yönünde doğrudan komşu mesafe sınırı
        threshold_y = 1.1 * pitch_y  # Y yönünde doğrudan komşu mesafe sınırı
        # Staggered dizilimde diagonal komşular yarı adım kaydırıldığından
        # biraz daha geniş bir eşik gerekir
        if staggered:
            staggered_diag_dist = math.hypot(pitch_x * 0.5, pitch_y)
            threshold_diag = 1.1 * staggered_diag_dist
        else:
            threshold_diag = 0.0  # Staggered değilse diagonal bağlantı yok

        connections: List[NeighborConnection] = []

        n_cells = len(cells)
        for i in range(n_cells):
            for j in range(i + 1, n_cells):
                ci = cells[i]
                cj = cells[j]
                dx = abs(ci.pos_x - cj.pos_x)
                dy = abs(ci.pos_y - cj.pos_y)
                dist = math.hypot(dx, dy)

                # Ortogonal komşu mu? (aynı satır veya aynı sütun)
                is_x_neighbor = (dx < threshold_x and dy < pitch_y * 0.3)
                is_y_neighbor = (dy < threshold_y and dx < pitch_x * 0.3)
                is_staggered_neighbor = staggered and (dist < threshold_diag)

                if not (is_x_neighbor or is_y_neighbor or is_staggered_neighbor):
                    continue

                # Yüzeyden yüzeye boşluk ve temas alanı hesapla
                if cell_format == CellFormat.PRISMATIC:
                    if dx > dy:
                        # X yönü komşusu — geniş yüz temas
                        surf_gap = max(1e-4, dx - dx_cell)
                        contact_area = ci.geometry.height * ci.geometry.thickness
                    else:
                        # Y yönü komşusu — dar yan yüz temas
                        surf_gap = max(1e-4, dy - dy_cell)
                        contact_area = ci.geometry.height * ci.geometry.length
                else:
                    surf_gap = max(1e-4, dist - dx_cell)
                    # Silindirik hücreler için etkin iletim alanı
                    contact_area = cell_height * (dx_cell * 0.65)

                conn = NeighborConnection(
                    cell_i_id=ci.cell_id,
                    cell_j_id=cj.cell_id,
                    center_distance_m=dist,
                    surface_gap_m=surf_gap,
                    contact_area_m2=contact_area,
                    separator_material_id=separator_material_id,
                    separator_thickness_m=sep_thickness_m,
                    gap_material_id=gap_material_id
                )
                connections.append(conn)

        # Modülün toplam geometrik boyutları
        min_x = min(c.pos_x - dx_cell/2 for c in cells)
        max_x = max(c.pos_x + dx_cell/2 for c in cells)
        min_y = min(c.pos_y - dy_cell/2 for c in cells)
        max_y = max(c.pos_y + dy_cell/2 for c in cells)

        pack_bounds = {
            "width_m": max_x - min_x,
            "length_m": max_y - min_y,
            "height_m": cell_height,
            "total_cells": len(cells)
        }

        return cells, connections, pack_bounds
