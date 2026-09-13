"""
Faz 2 & Faz 5 — İki Hücreli ve Çok Hücreli Termal Kaçak Yayılım Testleri
Bariyersiz yayılım vs Aerojel yalıtımlı koruma (UL 9540A tek hücre sınırlama) doğrulaması.
"""

import pytest
from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.thermal_network import ThermalNetworkAssembler
from simulator.core.solver import ThermalRunawaySolver
from simulator.core.propagation_evaluator import PropagationEvaluator
from simulator.core.constants import PropagationStatus

def test_two_cell_propagation_uninsulated():
    """
    Yalıtımsız, dar aralıklı (1 mm) 2 hücreli sistem:
    Hücre 0 termal kaçağa girdiğinde yüksek iletim ve radyasyon sebebiyle Hücre 1'e yayılmalıdır.
    """
    builder = PackGeometryBuilder()
    kinetics = ArrheniusKineticsEngine()

    cells, connections, _ = builder.build_pack(
        rows=1, cols=2,
        spacing_x_mm=1.0,
        chemistry_id="NMC_generic_v1",
        separator_material_id=None
    )

    assembler = ThermalNetworkAssembler(
        cells=cells,
        connections=connections,
        materials_lib=builder.materials_lib,
        kinetics_engine=kinetics,
        h_ambient_conv_W_per_m2_K=5.0,
        busbar_conductance_W_per_K=0.60
    )

    solver = ThermalRunawaySolver(assembler)
    result = solver.solve(
        job_id="test_uninsulated_2cell",
        t_span=(0.0, 45.0),
        trigger_cell_id=0,
        trigger_power_W=3500.0,
        trigger_duration_s=3.0,
        num_output_points=120
    )

    evaluator = PropagationEvaluator()
    evaluation = evaluator.evaluate(result, trigger_cell_id=0)

    # İki hücre de kaçağa girmelidir
    assert evaluation.affected_cells_count == 2
    assert evaluation.time_to_first_propagation_s is not None
    assert evaluation.time_to_first_propagation_s > 0.0
    assert result.cell_summaries[0]["max_temperature_C"] > 650.0
    assert result.cell_summaries[1]["max_temperature_C"] > 500.0

def test_two_cell_containment_with_aerogel():
    """
    2.5 mm Silika Aerojel bariyerli 2 hücreli sistem:
    Hücre 0 kaçağa girer ancak düşük iletkenlik (0.018 W/mK) ve bloke edilen radyasyon
    sayesinde Hücre 1 korunmalı ve NO_PROPAGATION (UL 9540A Tek Hücre Sınırlaması) sağlanmalıdır.
    """
    builder = PackGeometryBuilder()
    kinetics = ArrheniusKineticsEngine()

    cells, connections, _ = builder.build_pack(
        rows=1, cols=2,
        spacing_x_mm=3.0,
        chemistry_id="NMC_generic_v1",
        separator_material_id="aerogel_insulation",
        separator_thickness_mm=2.5
    )

    assembler = ThermalNetworkAssembler(
        cells=cells,
        connections=connections,
        materials_lib=builder.materials_lib,
        kinetics_engine=kinetics,
        h_ambient_conv_W_per_m2_K=10.0
    )

    solver = ThermalRunawaySolver(assembler)
    result = solver.solve(
        job_id="test_aerogel_2cell",
        t_span=(0.0, 45.0),
        trigger_cell_id=0,
        trigger_power_W=3500.0,
        trigger_duration_s=3.0,
        num_output_points=120
    )

    evaluator = PropagationEvaluator()
    evaluation = evaluator.evaluate(result, trigger_cell_id=0)

    # Hücre 1 kaçağa girmemeli, yayılım engellenmeli
    assert evaluation.status == PropagationStatus.NO_PROPAGATION
    assert evaluation.affected_cells_count == 1
    assert evaluation.time_to_first_propagation_s is None
    # Hücre 0 yandı, ama Hücre 1 pik sıcaklığı onset'in (155°C) altında kaldı
    assert result.cell_summaries[0]["max_temperature_C"] > 650.0
    assert result.cell_summaries[1]["max_temperature_C"] < 155.0
