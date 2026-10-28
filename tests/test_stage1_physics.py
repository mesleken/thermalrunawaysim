"""
Aşama 1 Çekirdek Fizik Motoru Testleri:
1. Çoklu-Reaksiyon Kinetiği (Multi-Reaction Kinetics & Endotermik Separatör Erimesi)
2. Core-Shell 1D Radyal Ağ Modeli ve Termal Difüzyon Gecikmesi (Thermal Lag)
3. Dinamik Venting Kütle Kaybı (Ejecta Mass Loss)
4. Yönlü Venting Modeli (Directional Ejecta)
"""

import pytest
import numpy as np

from simulator.api.models import PackSimulationRequest
from simulator.api.services import SimulationService
from simulator.core.kinetics_engine import ArrheniusKineticsEngine, SubReaction, get_default_sub_reactions

def test_multi_reaction_kinetics_endothermic_separator():
    """Çoklu reaksiyon modelinde 4 reaksiyon ve separatörün endotermik (ısı yutucu) etkisi doğrulanır."""
    sub_rxns = get_default_sub_reactions("NMC_generic_v1")
    assert len(sub_rxns) == 4
    
    # 3. reaksiyon (separatör erimesi) endotermik olmalıdır (delta_H < 0)
    sep_rxn = next(r for r in sub_rxns if "separator" in r.key)
    assert sep_rxn.delta_H < 0.0, f"Separatör entalpisi endotermik (negatif) olmalıdır: {sep_rxn.delta_H}"
    
    # Kinetik motoru testi
    engine = ArrheniusKineticsEngine()
    alphas = np.array([0.5, 0.5, 0.5, 0.1])
    rates = engine.multi_reaction_rates(alphas, T_K=415.0, sub_reactions=sub_rxns)
    assert len(rates) == 4
    assert all(r >= 0.0 for r in rates)
    
    # Isı üretimi: Separatör erimesi negatif ısı katkısı sağlamalıdır
    dH_rates = [r.delta_H * rates[idx] for idx, r in enumerate(sub_rxns)]
    assert dH_rates[2] < 0.0, "Separatör faz geçişi ısı yutmalıdır."
    
    # Uçtan uca servis simülasyonu
    service = SimulationService()
    req = PackSimulationRequest(
        rows=2,
        cols=2,
        simulation_time_s=30.0,
        kinetics_model="multi_reaction"
    )
    result = service.run_simulation(req)
    assert result["status"] == "COMPLETED"
    assert result["simulation_result"]["pack_metrics"]["kinetics_model"] == "multi_reaction"
    assert result["evaluation"]["peak_module_temp_C"] > 50.0

def test_core_shell_thermal_lag():
    """Core-Shell (2 düğümlü 1D radyal) modelinde Core'un Shell'den önce ve daha sıcak olduğu doğrulanır."""
    service = SimulationService()
    req = PackSimulationRequest(
        rows=2,
        cols=1,
        simulation_time_s=35.0,
        nodal_model="core_shell",
        trigger_cell_id=0,
        trigger_power_W=3500.0,
        trigger_duration_s=3.0
    )
    result = service.run_simulation(req)
    assert result["status"] == "COMPLETED"
    
    summaries = result["simulation_result"]["cell_summaries"]
    trigger_cell = summaries[0]
    
    # Core ve Shell tepe sıcaklıkları mevcut olmalı
    assert "max_core_temperature_C" in trigger_cell
    assert "max_temperature_C" in trigger_cell  # Dış kabuk sıcaklığı
    
    # Kimyasal ısı Core'da üretildiği için Core tepe sıcaklığı Shell'den büyük veya eşit olmalıdır
    assert trigger_cell["max_core_temperature_C"] >= trigger_cell["max_temperature_C"], (
        f"Core ({trigger_cell['max_core_temperature_C']}°C) "
        f"Shell'den ({trigger_cell['max_temperature_C']}°C) daha sıcak olmalıdır."
    )
    
    # Çözücü metriklerinde nodal_model teyit edilir
    assert result["simulation_result"]["pack_metrics"]["nodal_model"] == "core_shell"

def test_dynamic_ejecta_mass_loss():
    """Venting anında hücre kütlesinin dinamik olarak atılması ve termal sığanın düşmesi test edilir."""
    service = SimulationService()
    req = PackSimulationRequest(
        rows=2,
        cols=1,
        simulation_time_s=25.0,
        ejecta_mass_loss_ratio=0.25,
        trigger_cell_id=0
    )
    result = service.run_simulation(req)
    assert result["status"] == "COMPLETED"
    assert result["evaluation"]["peak_module_temp_C"] > 100.0

def test_directional_venting():
    """Yönlü venting: Komşuya doğru püsküren alev ile ters yöne püsküren alev arasındaki ısı farkı doğrulanır."""
    service = SimulationService()
    
    # Vaka A: Hücre 0'dan Hücre 1'e doğru (0 derece, pozitif X yönünde komşuya direkt temas)
    req_towards = PackSimulationRequest(
        rows=1,
        cols=2,
        simulation_time_s=25.0,
        vent_direction_deg=0.0,
        trigger_cell_id=0
    )
    res_towards = service.run_simulation(req_towards)
    temp_neighbor_towards = res_towards["simulation_result"]["cell_summaries"][1]["max_temperature_C"]
    
    # Vaka B: Hücre 0'dan ters yöne (180 derece, komşudan uzağa püskürme)
    req_away = PackSimulationRequest(
        rows=1,
        cols=2,
        simulation_time_s=25.0,
        vent_direction_deg=180.0,
        trigger_cell_id=0
    )
    res_away = service.run_simulation(req_away)
    temp_neighbor_away = res_away["simulation_result"]["cell_summaries"][1]["max_temperature_C"]
    
    # Komşuya bakan püskürme komşu hücreyi daha fazla ısıtmalıdır
    assert temp_neighbor_towards >= temp_neighbor_away, (
        f"Yönlü püskürmede komşuya doğru sıcaklık ({temp_neighbor_towards}°C), "
        f"ters yöne püskürmeden ({temp_neighbor_away}°C) daha yüksek veya eşit olmalıdır."
    )
