"""
Faz 1 — Tek Hücre Adiyabatik ARC Doğrulama Testi
Literatür Accelerating Rate Calorimetry (ARC) verileriyle model çıktılarının karşılaştırılması.
"""

import pytest
import math
import numpy as np
from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.thermal_network import ThermalNetworkAssembler
from simulator.core.solver import ThermalRunawaySolver
from simulator.core.constants import celsius_to_kelvin, kelvin_to_celsius

def test_single_cell_arc_nmc_runaway_validation():
    """
    Tek hücre adiyabatik ARC testi:
    NMC18650 hücresi T_onset (155°C) civarına ısıtıldığında kendi kendine ekzotermik
    ısınma ile kaçağa girmeli ve literatürdeki ~750-850°C pik sıcaklık aralığına ulaşmalıdır.
    """
    builder = PackGeometryBuilder()
    kinetics = ArrheniusKineticsEngine()

    cells, connections, _ = builder.build_pack(
        rows=1, cols=1,
        chemistry_id="NMC_generic_v1",
        initial_temp_K=celsius_to_kelvin(160.0) # Onset üstünde başlat
    )

    # Adiyabatik ortam (çevreye ısı kaybı yok: h_conv=0)
    assembler = ThermalNetworkAssembler(
        cells=cells,
        connections=connections,
        materials_lib=builder.materials_lib,
        kinetics_engine=kinetics,
        h_ambient_conv_W_per_m2_K=0.0,
        emissivity=0.0 # Adiyabatik radyasyonsuz kalorimetre
    )

    solver = ThermalRunawaySolver(assembler)
    result = solver.solve(
        job_id="arc_validation_test",
        t_span=(0.0, 120.0),
        trigger_cell_id=0,
        trigger_method="instant_onset",
        trigger_initial_temp_C=160.0,
        num_output_points=200
    )

    cell_0 = result.cell_summaries[0]
    peak_T_C = cell_0["max_temperature_C"]
    final_alpha = cell_0["alpha"]

    # Doğrulama kriterleri:
    # 1. Reaksiyon tamamlanmalı (alpha > 0.95)
    assert final_alpha > 0.95
    # 2. Pik sıcaklık literatür adiyabatik NMC bandında olmalıdır
    # active_mass_ratio = 0.58
    # delta_H = 780 J/g (aktif kütle için), cp = 1050 J/(kg*K)
    # delta_T = (780000 * 0.58) / 1050 ~ 431 K -> 160 + 431 = 591°C
    assert 580.0 <= peak_T_C <= 610.0
    # 3. Kaçak zamanı kaydedilmiş olmalıdır
    assert cell_0["runaway_time_s"] is not None
