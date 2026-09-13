"""
Isıl Ağ Montaj Birim Testleri
İletkenlik matrisi simetrisi, enerji dengesi türevleri ve sınır şartları.
"""

import pytest
import numpy as np
from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.thermal_network import ThermalNetworkAssembler

def test_conductance_matrix_symmetry():
    builder = PackGeometryBuilder()
    kinetics = ArrheniusKineticsEngine()
    cells, connections, _ = builder.build_pack(
        rows=2, cols=2, spacing_x_mm=2.0, spacing_y_mm=2.0
    )

    assembler = ThermalNetworkAssembler(
        cells=cells,
        connections=connections,
        materials_lib=builder.materials_lib,
        kinetics_engine=kinetics
    )

    G = assembler.G_conduction
    # G matrisi kare ve simetrik olmalıdır: G_ij = G_ji
    assert G.shape == (4, 4)
    assert np.allclose(G, G.T, atol=1e-9)

def test_energy_balance_isolated_equilibrium():
    """Tüm hücreler ortam sıcaklığında ve reaksiyon yokken türevler 0'a yakın olmalıdır."""
    builder = PackGeometryBuilder()
    kinetics = ArrheniusKineticsEngine()
    cells, connections, _ = builder.build_pack(
        rows=2, cols=2, spacing_x_mm=2.0, spacing_y_mm=2.0
    )

    assembler = ThermalNetworkAssembler(
        cells=cells,
        connections=connections,
        materials_lib=builder.materials_lib,
        kinetics_engine=kinetics,
        T_ambient_K=298.15
    )

    # State: [298.15, 298.15, 298.15, 298.15, 0, 0, 0, 0]
    state = np.array([298.15, 298.15, 298.15, 298.15, 0.0, 0.0, 0.0, 0.0])
    derivatives = assembler.compute_derivatives(t=0.0, state_vector=state)

    dT_dt = derivatives[:4]
    dalpha_dt = derivatives[4:]

    # Oda sıcaklığında ısı transferi ve kimyasal üretim neredeyse 0 olmalıdır
    assert np.all(np.abs(dT_dt) < 1e-3)
    assert np.all(np.abs(dalpha_dt) < 1e-6)
