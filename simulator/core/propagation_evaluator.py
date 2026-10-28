"""
Yayılım Değerlendirici ve Risk Analizörü (PropagationEvaluator)
Simülasyon sonuçlarını tarayarak termal kaçak yayılım grafiğini, yayılma hızını,
çok boyutlu risk vektörünü ve UL 9540A ön-değerlendirmesini üretir.
Faz 0.5 Sözleşme 4 ve Sözleşme 5'e tam uyumludur.
"""

from typing import Dict, Any, List, Optional
import math
import numpy as np
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
        confidence_message: str = "",
        regulatory_compliance: Optional[Dict[str, Any]] = None
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
        self.regulatory_compliance = regulatory_compliance or {}

    def to_dict(self) -> Dict[str, Any]:
        status_str = self.status.value if hasattr(self.status, "value") else str(self.status)
        return {
            "status": status_str,
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
            "confidence_message": self.confidence_message,
            "regulatory_compliance": self.regulatory_compliance
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

    def evaluate(
        self,
        result: SimulationResult,
        trigger_cell_id: int,
        connections: Optional[List[Any]] = None
    ) -> PropagationEvaluation:
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

        # Fiziksel komşuluk haritası (connections mevcutsa gerçek topoloji ve temas alanı ağırlığı)
        adjacency: Dict[int, Dict[int, float]] = {}
        if connections:
            for conn in connections:
                u = getattr(conn, "cell_i_id", None)
                v = getattr(conn, "cell_j_id", None)
                if u is not None and v is not None:
                    area = float(getattr(conn, "contact_area_m2", 1e-3))
                    gap = max(1e-5, float(getattr(conn, "surface_gap_m", 2e-3)))
                    weight = area / gap
                    adjacency.setdefault(u, {})[v] = adjacency.get(u, {}).get(v, 0.0) + weight
                    adjacency.setdefault(v, {})[u] = adjacency.get(v, {}).get(u, 0.0) + weight

        time_pts = np.array(getattr(result, "time_points_s", []), dtype=np.float64)
        temp_hist = getattr(result, "temperature_history_C", {}) or {}

        def _get_temp_series(cid: int) -> Optional[np.ndarray]:
            arr = temp_hist.get(cid)
            if arr is None:
                arr = temp_hist.get(str(cid))
            return np.array(arr, dtype=np.float64) if arr is not None else None

        # Nedensel Yayılım Grafiği (Causal Directed Propagation DAG - Isı Akısı & Komşuluk Tabanlı)
        path_graph: List[Dict[str, Any]] = []

        for i, target in enumerate(runaway_cells):
            t_cid = target["cell_id"]
            if t_cid == trigger_cell_id or i == 0:
                continue

            t_tr_target = float(target["runaway_time_s"])
            prior_cells = [c for c in runaway_cells[:i] if float(c["runaway_time_s"]) <= t_tr_target]
            if not prior_cells:
                prior_cells = runaway_cells[:i]

            best_source = None
            target_x = float(target.get("pos_x_mm", target.get("pos_x", 0.0)))
            target_y = float(target.get("pos_y_mm", target.get("pos_y", 0.0)))
            t_series_target = _get_temp_series(t_cid)

            # 1. Öncelik: Gerçek topolojik komşular arasında kümülatif ısı transferi integrali en yüksek ebeveyn
            direct_neighbors = adjacency.get(t_cid, {})
            prior_direct = [c for c in prior_cells if c["cell_id"] in direct_neighbors]

            if prior_direct and len(time_pts) > 1 and t_series_target is not None:
                best_heat_score = -1.0
                mask = time_pts <= (t_tr_target + 1e-6)
                t_sub = time_pts[mask] if np.sum(mask) >= 2 else time_pts[:2]
                target_sub = t_series_target[:len(t_sub)]

                for cand in prior_direct:
                    u_cid = cand["cell_id"]
                    u_series = _get_temp_series(u_cid)
                    g_weight = direct_neighbors[u_cid]
                    if u_series is not None:
                        u_sub = u_series[:len(t_sub)]
                        delta_T_pos = np.maximum(0.0, u_sub - target_sub)
                        heat_integral = float(np.trapezoid(delta_T_pos, t_sub)) * g_weight
                    else:
                        heat_integral = g_weight
                    if heat_integral > best_heat_score:
                        best_heat_score = heat_integral
                        best_source = cand

            # 2. Yedek (Fallback): Uzaysal Öklid mesafesi (pos_x_mm, pos_y_mm) ve sıcaklık sürüşü
            if best_source is None:
                min_dist = float("inf")
                for cand in prior_cells:
                    cx = float(cand.get("pos_x_mm", cand.get("pos_x", 0.0)))
                    cy = float(cand.get("pos_y_mm", cand.get("pos_y", 0.0)))
                    dist = math.hypot(cx - target_x, cy - target_y)
                    if dist < min_dist - 1e-6:
                        min_dist = dist
                        best_source = cand
                    elif abs(dist - min_dist) <= 1e-6:
                        if best_source is None or cand["runaway_time_s"] > best_source["runaway_time_s"]:
                            best_source = cand

            if best_source is not None:
                dt = target["runaway_time_s"] - best_source["runaway_time_s"]
                path_graph.append({
                    "from_cell_id": best_source["cell_id"],
                    "from_cell_name": best_source["name"],
                    "to_cell_id": target["cell_id"],
                    "to_cell_name": target["name"],
                    "delta_t_s": round(max(0.0, dt), 3)
                })

        # Komşu hücrelerin termal güvenlik marjı (Containment Margin - Dinamik T_onset_C)
        non_trigger_cells = [c for c in cells if c["cell_id"] != trigger_cell_id]
        if non_trigger_cells:
            margins = []
            for c in non_trigger_cells:
                if c.get("T_onset_C") is not None:
                    onset = float(c["T_onset_C"])
                else:
                    onset = _CHEMISTRY_ONSET_C.get(c.get("chemistry_id", ""), _DEFAULT_ONSET_C)
                margins.append(onset - c["max_temperature_C"])
            min_margin = min(margins)
        else:
            min_margin = 0.0

        peak_temp = max(c["max_temperature_C"] for c in cells)

        # Regülasyon Uyumluluk Değerlendirmesi
        gb_38031_pass = bool(affected_count <= 1 or (time_to_first_prop is not None and time_to_first_prop >= 300.0))
        ul_9540a_pass = bool(affected_count <= 1)
        un_383_pass = bool(peak_temp <= 170.0 and affected_count == 0)

        regulatory_compliance = {
            "gb_38031_5min_egress": {
                "standard": "GB 38031-2020 / ECE R100.03",
                "passed": gb_38031_pass,
                "required_seconds": 300.0,
                "actual_first_propagation_s": time_to_first_prop,
                "egress_margin_s": round(time_to_first_prop - 300.0, 1) if time_to_first_prop is not None else None,
                "verdict": "UYGUN (>=5 dk yolcu tahliye süresi korundu)" if gb_38031_pass else "UYGUN DEĞİL (Yayılım 300s altında gerçekleşti)"
            },
            "ul_9540a_unit_level": {
                "standard": "UL 9540A Unit Level",
                "passed": ul_9540a_pass,
                "verdict": "UYGUN (Tetikleyici hücreyle sınırlandırıldı)" if ul_9540a_pass else "RİSKLİ (Hücreler arası yayılım gerçekleşti)"
            },
            "un_383_thermal_abuse": {
                "standard": "UN 38.3.4.2 Termal Fırın Testi",
                "passed": un_383_pass,
                "verdict": "UYGUN (Tepe sıcaklık tehlikeli eşiğin altında)" if un_383_pass else "BİLGİ (Kaçak reaksiyonu veya yüksek tepe sıcaklığı)"
            }
        }

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
            regulatory_summary=reg_summary,
            regulatory_compliance=regulatory_compliance
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
