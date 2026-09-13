"""
Geometri ve Topoloji Birim Testleri
PackGeometryBuilder, komşuluk ilişkileri ve boyut hesaplamaları.
"""

import pytest
import math
from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.constants import CellFormat

def test_cylindrical_pack_builder_grid():
    builder = PackGeometryBuilder()
    cells, connections, bounds = builder.build_pack(
        rows=2,
        cols=3,
        cell_format=CellFormat.CYLINDRICAL_18650,
        spacing_x_mm=2.0,
        spacing_y_mm=2.0,
        staggered=False
    )
    assert len(cells) == 6
    assert bounds["total_cells"] == 6

    # 2x3 bir ızgarada 4 kenar komşusu (yatay 4, dikey 3) toplam en az 7 bağlantı olmalıdır
    assert len(connections) >= 7

    # Hücre merkez mesafeleri: 18mm çap + 2mm aralık = 20mm = 0.020 m
    for conn in connections:
        assert conn.center_distance_m >= 0.019
        assert conn.contact_area_m2 > 0.0

def test_prismatic_pack_builder():
    builder = PackGeometryBuilder()
    cells, connections, bounds = builder.build_pack(
        rows=1,
        cols=4,
        cell_format=CellFormat.PRISMATIC,
        spacing_x_mm=3.0,
        spacing_y_mm=3.0
    )
    assert len(cells) == 4
    assert len(connections) == 3 # 1D 4 prizmatik hücre = 3 arayüz bağlantısı
    for c in cells:
        assert c.geometry.format_type == CellFormat.PRISMATIC
        assert c.mass > 1.0 # Prizmatik LFP kütlesi ~1.15 kg
