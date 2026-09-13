"""
Kinetik Motor Birim Testleri
Arrhenius formülü doğrulaması, sınır koşulları ve ısı salınım testleri.
"""

import pytest
import math
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.constants import R_GAS, celsius_to_kelvin

def test_arrhenius_kinetics_library_loading():
    engine = ArrheniusKineticsEngine()
    assert "NMC_generic_v1" in engine.library
    assert "LFP_generic_v1" in engine.library
    assert "NMC811_high_energy_v1" in engine.library

    nmc = engine.get_params("NMC_generic_v1")
    assert nmc.Ea == 128500.0
    assert nmc.A == 2.5e12
    assert nmc.delta_H == 780000.0
    assert math.isclose(nmc.T_onset_K, celsius_to_kelvin(155.0), abs_tol=0.1)

def test_reaction_rate_boundaries():
    engine = ArrheniusKineticsEngine()
    nmc = engine.get_params("NMC_generic_v1")

    # Oda sıcaklığında (25°C = 298.15K) reaksiyon hızı pratikte 0 olmalıdır
    rate_room = engine.reaction_rate(alpha=0.0, T_K=298.15, params=nmc)
    assert rate_room < 1e-6

    # Kaçak sıcaklığında (220°C = 493.15K) reaksiyon hızı pozitif ve hızlı olmalıdır
    rate_runaway = engine.reaction_rate(alpha=0.05, T_K=493.15, params=nmc)
    assert rate_runaway > 0.01

    # Alpha >= 1.0 iken reaksiyon hızı kesinlikle 0 olmalıdır (reaktant tükendi)
    rate_exhausted = engine.reaction_rate(alpha=1.0, T_K=500.0, params=nmc)
    assert rate_exhausted == 0.0

def test_heat_generation_calculation():
    engine = ArrheniusKineticsEngine()
    nmc = engine.get_params("NMC_generic_v1")

    rate = 0.05  # 1/s
    cell_mass = 0.046 # kg
    q_dot = engine.heat_generation_rate(
        dalpha_dt=rate,
        cell_mass_kg=cell_mass,
        params=nmc,
        ohmic_power_W=2.0
    )
    # Beklenen kimyasal ısı: 0.046 kg * 0.58 (active_mass) * 780000 J/kg * 0.05 1/s = 1040.52 W
    # Toplam: 1040.52 + 2 = 1042.52 W
    expected = (0.046 * 0.58 * 780000.0 * 0.05) + 2.0
    assert math.isclose(q_dot, expected, rel_tol=1e-5)
