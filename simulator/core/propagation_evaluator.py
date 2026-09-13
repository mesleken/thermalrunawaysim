"""
Yayılım Değerlendirici ve Risk Analizörü (PropagationEvaluator)
Simülasyon sonuçlarını tarayarak termal kaçak yayılım grafiğini, yayılma hızını,
çok boyutlu risk vektörünü ve UL 9540A ön-değerlendirmesini üretir.
Faz 0.5 Sözleşme 4 ve Sözleşme 5'e tam uyumludur.
"""

from typing import Dict, Any, List, Optional
from simulator.core.constants import PropagationStatus
from simulator.core.solver import SimulationResult

class PropagationEvaluation:
    """Termal kaçak yayılım değerlendirme raporu veri yapısı."""
    def __init__(
        self,
        status: PropagationStatus,
        time_to_first_propagation_s: Optional[float],
        total_cells: int,
        affected_cells_count: int,
        propagation_ratio: float,
        propagation_sequence: List[Dict[str, Any]],
        propagation_path_graph: List[Dict[str, Any]],
        peak_module_temp_C: float,
        min_containment_margin_C: float,
        risk_score_100: float,
        uncertainty_bounds: Dict[str, Any],
        regulatory_summary: str,
        confidence_level: str = "high",
        confidence_message: str = ""
    ):
        self.status = status
        self.time_to_first_propagation_s = time_to_first_propagation_s
        self.total_cells = total_cells
        self.affected_cells_count = affected_cells_count
        self.propagation_ratio = propagation_ratio
        self.propagation_sequence = propagation_sequence
        self.propagation_path_graph = propagation_path_graph
        self.peak_module_temp_C = peak_module_temp_C
        self.min_containment_margin_C = min_containment_margin_C
        self.risk_score_100 = risk_score_100
        self.uncertainty_bounds = uncertainty_bounds
        self.regulatory_summary = regulatory_summary
        self.confidence_level = confidence_level
        self.confidence_message = confidence_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "time_to_first_propagation_s": self.time_to_first_propagation_s,
            "total_cells": self.total_cells,
            "affected_cells_count": self.affected_cells_count,
            "propagation_ratio_percent": round(self.propagation_ratio * 100.0, 1),
            "propagation_sequence": self.propagation_sequence,
            "propagation_path_graph": self.propagation_path_graph,
            "peak_module_temp_C": round(self.peak_module_temp_C, 2),
            "min_containment_margin_C": round(self.min_containment_margin_C, 2),
            "risk_score_100": round(self.risk_score_100, 1),
            "uncertainty_bounds": self.uncertainty_bounds,
            "regulatory_summary": self.regulatory_summary,
            "confidence_level": self.confidence_level,
            "confidence_message": self.confidence_message
        }


# Chemistry onset temperatures for containment margin calculation
_CHEMISTRY_ONSET_C = {
    "NMC_generic_v1": 155.0,
    "NMC811_high_energy_v1": 138.0,
    "LFP_generic_v1": 215.0,
}
_DEFAULT_ONSET_C = 155.0


class PropagationEvaluator:
    """Zaman serisi ve hücre olaylarını analiz eden değerlendirici motor."""

    def evaluate(self, result: SimulationResult, trigger_cell_id: int) -> PropagationEvaluation:
        cells = result.cell_summaries
        total_cells = len(cells)

        # Kaçağa giren hücreleri runaway_time sırasına göre sırala
        runaway_cells = [
            c for c in cells if c.get("runaway_time_s") is not None
        ]
        runaway_cells.sort(key=lambda x: x["runaway_time_s"])

        affected_count = len(runaway_cells)
        propagation_ratio = affected_count / max(1, total_cells)

        # Yayılım sırası listesi
        sequence: List[Dict[str, Any]] = []
        for rank, c in enumerate(runaway_cells):
            sequence.append({
                "order": rank + 1,
                "cell_id": c["cell_id"],
                "name": c["name"],
                "runaway_time_s": c["runaway_time_s"],
                "max_temperature_C": c["max_temperature_C"],
                "is_trigger": (c["cell_id"] == trigger_cell_id)
            })

        # İlk komşuya yayılma süresi (trigger cell haricindeki ilk hücrenin zamanı)
        neighbor_runaways = [c for c in runaway_cells if c["cell_id"] != trigger_cell_id]
        if len(neighbor_runaways) > 0:
            time_to_first_prop = neighbor_runaways[0]["runaway_time_s"]
        else:
            time_to_first_prop = None

        # Yayılım grafiği (Directed Propagation Graph)
        path_graph: List[Dict[str, Any]] = []
        for i in range(len(runaway_cells) - 1):
            source = runaway_cells[i]
            target = runaway_cells[i + 1]
            dt = target["runaway_time_s"] - source["runaway_time_s"]
            path_graph.append({
                "from_cell_id": source["cell_id"],
                "from_cell_name": source["name"],
                "to_cell_id": target["cell_id"],
                "to_cell_name": target["name"],
                "delta_t_s": round(dt, 3)
            })

        # Komşu hücrelerin termal güvenlik marjı (Containment Margin)
        # Use the actual onset temp for each cell's chemistry
        non_trigger_cells = [c for c in cells if c["cell_id"] != trigger_cell_id]
        if non_trigger_cells:
            margins = []
            for c in non_trigger_cells:
                onset = _CHEMISTRY_ONSET_C.get(c.get("chemistry_id", ""), _DEFAULT_ONSET_C)
                margins.append(onset - c["max_temperature_C"])
            min_margin = min(margins)
        else:
            min_margin = 0.0

        peak_temp = max(c["max_temperature_C"] for c in cells)

        # Calculate risk score dynamically based on actual metrics (0-100)
        risk_score = self._calculate_risk_score(
            affected_count=affected_count,
            total_cells=total_cells,
            propagation_ratio=propagation_ratio,
            min_margin=min_margin,
            peak_temp=peak_temp,
            time_to_first_prop=time_to_first_prop
        )

        # Sınıflandırma
        if affected_count <= 1:
            status = PropagationStatus.NO_PROPAGATION
            reg_summary = (
                "BAŞARILI ÖN-TARAMA: Termal kaçak tetikleyici hücreyle sınırlı kalmıştır (Single-Cell Containment). "
                "Komşu hücreler termal kaçak onset sıcaklığına ulaşmamıştır (UL 9540A Seviye 2 kriteri hedefleriyle uyumlu)."
            )
        elif affected_count <= 2 or propagation_ratio < 0.35:
            status = PropagationStatus.LOCAL_CONTAINED
            reg_summary = (
                "KISMEN YAYILIM: Termal kaçak doğrudan temas eden komşu hücreye sıçramış, ancak modül geneline yayılmadan durdurulmuştur. "
                "Separatör kalınlığının veya hücre aralığının artırılması önerilir."
            )
        else:
            status = PropagationStatus.UNCONTROLLED_CASCADE
            reg_summary = (
                "KRİTİK RİSK: Modül genelinde kontrolsüz zincirleme termal kaçak yayılımı (Thermal Runaway Cascade) gerçekleşmiştir. "
                "Tasarım UL 9540A ön-taramasından geçemez. Acil termal bariyer (aerojel/mika) ve aktif soğutma revizyonu gereklidir."
            )

        uncertainty_bounds = {
            "temperature_uncertainty_C": 10.0,
            "propagation_time_uncertainty_percent": 12.0,
            "confidence_band_desc": "Literatür ARC/DSC varyansına dayalı ±10°C sıcaklık ve ±12% yayılım süresi belirsizlik bandı."
        }

        return PropagationEvaluation(
            status=status,
            time_to_first_propagation_s=time_to_first_prop,
            total_cells=total_cells,
            affected_cells_count=affected_count,
            propagation_ratio=propagation_ratio,
            propagation_sequence=sequence,
            propagation_path_graph=path_graph,
            peak_module_temp_C=peak_temp,
            min_containment_margin_C=min_margin,
            risk_score_100=risk_score,
            uncertainty_bounds=uncertainty_bounds,
            regulatory_summary=reg_summary
        )

    def _calculate_risk_score(
        self,
        affected_count: int,
        total_cells: int,
        propagation_ratio: float,
        min_margin: float,
        peak_temp: float,
        time_to_first_prop: Optional[float]
    ) -> float:
        """
        Çok boyutlu risk skoru hesaplayıcı.
        Etkilenen hücre oranı, güvenlik marjı, pik sıcaklık ve yayılım hızı
        bileşenlerinin ağırlıklı ortalamasıdır.
        """
        score = 0.0

        # Component 1: Propagation ratio (0-35 pts)
        score += propagation_ratio * 35.0

        # Component 2: Containment margin (0-25 pts)
        # Negative margin = worse. +50°C margin = 0 risk. -100°C margin = 25 risk.
        if min_margin >= 50.0:
            margin_score = 0.0
        elif min_margin <= -100.0:
            margin_score = 25.0
        else:
            margin_score = 25.0 * (1.0 - (min_margin + 100.0) / 150.0)
        score += max(0.0, min(25.0, margin_score))

        # Component 3: Peak temperature severity (0-20 pts)
        if peak_temp <= 200.0:
            temp_score = 0.0
        elif peak_temp >= 900.0:
            temp_score = 20.0
        else:
            temp_score = 20.0 * (peak_temp - 200.0) / 700.0
        score += max(0.0, min(20.0, temp_score))

        # Component 4: Speed of propagation (0-20 pts)
        if time_to_first_prop is None:
            speed_score = 0.0  # No propagation
        elif time_to_first_prop <= 5.0:
            speed_score = 20.0  # Very fast = very dangerous
        elif time_to_first_prop >= 60.0:
            speed_score = 5.0  # Slow propagation = moderate concern
        else:
            speed_score = 20.0 - 15.0 * (time_to_first_prop - 5.0) / 55.0
        score += max(0.0, min(20.0, speed_score))

        return round(max(0.0, min(100.0, score)), 1)
