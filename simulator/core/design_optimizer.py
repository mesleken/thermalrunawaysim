"""
Tasarım Çalışması Optimizatörü ve Kütle Ceza / Pareto Cephesi Motoru (DesignOptimizer)
Aşama 3: Batarya modülü kütle/hacim hesabı, Mass-Penalty İndeksi, çok amaçlı maliyet
fonksiyonu ve Kütle-Güvenlik Pareto Cephesi (Pareto Front & Knee Point) analizörü.
"""

from typing import Dict, Any, List, Tuple, Optional
import math
from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.constants import CellFormat


def calculate_module_mass(config, geom_builder: Optional[PackGeometryBuilder] = None) -> Dict[str, float]:
    """
    Simülasyon konfigürasyonundan batarya modülünün gerçekçi kütle dökümünü ve hacmini hesaplar.
    
    Bileşenler:
    - Hücreler (Jelly roll + çelik kovan)
    - Hücreler arası bariyer / separatör (Mika, aerojel vb. yoğunluklarına göre)
    - Hücreler arası dolgu / hava boşluğu (Potting epoxy, hava vb.)
    - Alt sıvı soğutma plakası ve kanallardaki soğutucu sıvı
    - Alüminyum yapısal modül muhafazası / kasa
    - Bakır bara (busbar) bağlantıları
    """
    if geom_builder is None:
        geom_builder = PackGeometryBuilder()

    rows = int(config.rows)
    cols = int(config.cols)
    total_cells = rows * cols
    cell_format = getattr(config, "cell_format", "18650")
    if hasattr(cell_format, "value"):
        cell_format = cell_format.value

    # 1. Hücre Boyut ve Kütlesi
    format_lookup_key = str(cell_format)
    if format_lookup_key in ("prismatic", CellFormat.PRISMATIC):
        format_lookup_key = "Prismatic_50Ah"
    elif format_lookup_key in ("pouch", CellFormat.POUCH):
        format_lookup_key = "Pouch_60Ah"

    cell_dim = geom_builder.CELL_DIMENSIONS.get(format_lookup_key, {
        "radius": 0.009, "height": 0.065, "mass": 0.046, "cp": 1050.0, "type": "cylindrical"
    })
    single_cell_mass = float(getattr(config, "cell_mass_kg", None) or cell_dim.get("mass", 0.046))
    total_cells_mass = total_cells * single_cell_mass

    # Hücre hacmi (Silindirik, Prizmatik ve Pouch ayrımı)
    geom_type = str(cell_dim.get("type", "cylindrical")).lower()
    is_planar = geom_type in ("prismatic", "pouch") or format_lookup_key in ("Prismatic_50Ah", "Pouch_60Ah")
    if is_planar:
        cell_w = float(cell_dim.get("width", cell_dim.get("length", 0.148)))
        cell_t = float(cell_dim.get("thickness", 0.026))
        cell_h = float(cell_dim.get("height", 0.095))
        single_cell_vol = cell_w * cell_t * cell_h
        cell_dx = cell_w
        cell_dy = cell_t
    else:
        radius = float(cell_dim.get("radius", 0.009))
        cell_h = float(cell_dim.get("height", 0.065))
        single_cell_vol = math.pi * (radius ** 2) * cell_h
        cell_dx = radius * 2.0
        cell_dy = radius * 2.0

    # 2. Modül Boyutları (Hücreler + Boşluklar)
    spacing_x = float(getattr(config, "spacing_x_mm", 2.0)) / 1000.0
    spacing_y = float(getattr(config, "spacing_y_mm", 2.0)) / 1000.0

    module_width = cols * cell_dx + (cols + 1) * spacing_x
    module_length = rows * cell_dy + (rows + 1) * spacing_y
    module_height = cell_h
    enclosure_box_vol = module_width * module_length * module_height

    # 3. Hücreler Arası Arayüz Sayısı ve Bariyer Kütlesi (X ve Y arayüz alanları ayrı ayrı hesaplanır)
    n_interfaces_x = rows * max(0, cols - 1)
    n_interfaces_y = cols * max(0, rows - 1)
    
    sep_mat_id = getattr(config, "separator_material_id", None)
    sep_thick_mm = float(getattr(config, "separator_thickness_mm", 0.0) or 0.0)
    sep_thick_m = sep_thick_mm / 1000.0

    barrier_mass = 0.0
    total_barrier_vol = 0.0

    if sep_mat_id and sep_thick_m > 0:
        mat_info = geom_builder.materials_lib.get(sep_mat_id, {})
        # Varsayılan yoğunluklar (kg/m3)
        density_map = {
            "aerogel_insulation": 160.0,
            "mica_sheet": 2100.0,
            "silicone_pad": 2400.0,
            "paraffin_pcm_pad": 900.0,
            "ceramic_fiber_paper": 210.0,
            "intumescent_coating": 1150.0,
            "air_gap": 1.2
        }
        rho_barrier = float(mat_info.get("density_kg_per_m3", density_map.get(sep_mat_id, 1000.0)))
        
        # X ve Y yönü komşu yüzey alanları
        if is_planar:
            area_x = cell_h * cell_dy  # Yan dar kenar komşuluğu (H * T)
            area_y = cell_h * cell_dx  # Ana geniş yüzey komşuluğu (H * W)
            total_barrier_area = (n_interfaces_x * area_x) + (n_interfaces_y * area_y)
        else:
            contact_area = cell_h * (cell_dx * 0.65)
            total_barrier_area = (n_interfaces_x + n_interfaces_y) * contact_area

        total_barrier_vol = total_barrier_area * sep_thick_m
        barrier_mass = total_barrier_vol * rho_barrier

    # 4. Boşluk / Dolgu Kütlesi
    total_cells_vol = total_cells * single_cell_vol
    gap_vol = max(0.0, enclosure_box_vol - total_cells_vol - total_barrier_vol)

    gap_mat_id = getattr(config, "gap_material_id", "air_gap")
    gap_info = geom_builder.materials_lib.get(gap_mat_id, {})
    rho_gap = float(gap_info.get("density_kg_per_m3", 1.2 if gap_mat_id == "air_gap" else 1200.0))
    gap_mass = gap_vol * rho_gap

    # 5. Soğutma Plakası ve Soğutucu Sıvı Kütlesi
    cooling_mass = 0.0
    active_cooling = getattr(config, "active_cooling_enabled", False)
    if active_cooling:
        plate_area = module_width * module_length
        plate_thickness = 0.003  # 3 mm taban plakası
        # %70 Alüminyum (2700 kg/m3), %30 Su/Glikol Karışımı (1050 kg/m3)
        effective_rho_cooling = 0.70 * 2700.0 + 0.30 * 1050.0  # ~2205 kg/m3
        cooling_mass = plate_area * plate_thickness * effective_rho_cooling

    # 6. Yapısal Kasa (Enclosure) ve Bara Kütlesi
    # 1.5 mm Alüminyum kasa sacı (4 yan duvar + üst kapak)
    casing_thickness = 0.0015
    casing_area = 2.0 * (module_width + module_length) * module_height + (module_width * module_length)
    enclosure_mass = casing_area * casing_thickness * 2700.0  # Alüminyum 6061

    # Bakır bara (Busbar) bağlantı kütlesi (~8 gram/hücre)
    busbar_mass = total_cells * 0.008

    # Toplam Kütle
    total_module_mass = (
        total_cells_mass +
        barrier_mass +
        gap_mass +
        cooling_mass +
        enclosure_mass +
        busbar_mass
    )

    total_module_vol_liters = (module_width * module_length * (module_height + (0.003 if active_cooling else 0.0))) * 1000.0

    return {
        "total_mass_kg": round(total_module_mass, 4),
        "cells_mass_kg": round(total_cells_mass, 4),
        "barrier_mass_kg": round(barrier_mass, 4),
        "gap_mass_kg": round(gap_mass, 4),
        "cooling_mass_kg": round(cooling_mass, 4),
        "enclosure_mass_kg": round(enclosure_mass, 4),
        "busbar_mass_kg": round(busbar_mass, 4),
        "module_volume_liters": round(total_module_vol_liters, 2),
        "module_width_mm": round(module_width * 1000.0, 1),
        "module_length_mm": round(module_length * 1000.0, 1),
        "module_height_mm": round(module_height * 1000.0, 1)
    }


class DesignOptimizationEngine:
    """
    Çok Amaçlı Tasarım Çalışması (Design Study) ve Pareto Optimizatörü.
    Kütle artışı ile termal kaçak güvenlik skoru arasındaki Pareto Cephesini (Trade-off) çözer.
    """

    @staticmethod
    def analyze_study(
        cases_data: List[Dict[str, Any]],
        w_safety: float = 0.6,
        w_mass: float = 0.4
    ) -> Dict[str, Any]:
        """
        Tasarım vakalarının kütle, risk ve sıcaklık metriklerini analiz eder.
        Pareto optimal tasarım kümesini (Pareto Front) ve Diz Noktasını (Knee Point) belirler.
        """
        if not cases_data:
            return {
                "cases": [],
                "pareto_front_indices": [],
                "knee_point_index": None,
                "baseline_mass_kg": 0.0,
                "summary": "Analiz edilecek vaka bulunamadı."
            }

        # 1. Baz kütle tespiti (ilk vaka veya minimum kütleli vaka)
        baseline_mass = cases_data[0].get("module_mass_kg", 1.0)
        if baseline_mass <= 0:
            baseline_mass = min(c.get("module_mass_kg", 1.0) for c in cases_data)
            if baseline_mass <= 0:
                baseline_mass = 1.0

        # Her vaka için kütle ceza indeksini (Mass Penalty %) hesapla
        for c in cases_data:
            m = c.get("module_mass_kg", baseline_mass)
            penalty_pct = ((m - baseline_mass) / baseline_mass) * 100.0
            c["mass_penalty_index_percent"] = round(penalty_pct, 1)

        # 2. Pareto Optimalitesi Tespiti (2 Boyutlu Min-Min Optimizasyon: Kütle vs Risk Skoru)
        n = len(cases_data)
        pareto_flags = [True] * n

        for i in range(n):
            mass_i = cases_data[i]["module_mass_kg"]
            risk_i = cases_data[i]["risk_score_100"]

            for j in range(n):
                if i == j:
                    continue
                mass_j = cases_data[j]["module_mass_kg"]
                risk_j = cases_data[j]["risk_score_100"]

                # j vakası i vakasını domine ediyor mu?
                # j vakası hem daha hafif (veya eşit) hem de daha az riskli (veya eşit)
                # ve en az bir kriterde kesinlikle daha üstün olmalı.
                if (mass_j <= mass_i and risk_j <= risk_i) and (mass_j < mass_i or risk_j < risk_i):
                    pareto_flags[i] = False
                    break

        pareto_indices = [idx for idx, flag in enumerate(pareto_flags) if flag]
        
        # Pareto cephesindeki elemanları kütleye göre sırala
        pareto_indices.sort(key=lambda idx: cases_data[idx]["module_mass_kg"])

        for idx, c in enumerate(cases_data):
            c["is_pareto_optimal"] = pareto_flags[idx]

        # 3. Diz Noktası (Knee Point / En İyi Denge) Seçimi
        # Kütle ve Risk skorunu [0, 1] aralığına normalize et
        masses = [c["module_mass_kg"] for c in cases_data]
        risks = [c["risk_score_100"] for c in cases_data]

        min_m, max_m = min(masses), max(masses)
        min_r, max_r = min(risks), max(risks)
        span_m = max(1e-4, max_m - min_m)
        span_r = max(1e-4, max_r - min_r)

        best_knee_idx = None
        min_distance_to_utopia = float("inf")

        for idx in pareto_indices:
            c = cases_data[idx]
            norm_m = (c["module_mass_kg"] - min_m) / span_m
            norm_r = (c["risk_score_100"] - min_r) / span_r

            # Ağırlıklı öklid mesafesi (Ideal Utopia noktası: (0, 0) = en hafif ve en güvenli)
            dist = math.sqrt(w_mass * (norm_m ** 2) + w_safety * (norm_r ** 2))
            c["utopia_distance"] = round(dist, 4)

            if dist < min_distance_to_utopia:
                min_distance_to_utopia = dist
                best_knee_idx = idx

        # Eğer Pareto kümesinde kimse kalmadıysa (olağandışı durum), ilkini seç
        if best_knee_idx is None:
            best_knee_idx = 0

        knee_case = cases_data[best_knee_idx]

        # 4. Özet Raporu Oluştur
        base_case = cases_data[0]
        delta_m = knee_case["module_mass_kg"] - base_case["module_mass_kg"]
        delta_r = base_case["risk_score_100"] - knee_case["risk_score_100"]

        summary = (
            f"Pareto Analizi: {len(pareto_indices)} vaka Pareto Cephesinde yer almaktadır. "
            f"Önerilen Diz Noktası (Knee Point): '{knee_case['case_name']}' "
            f"(Kütle: {knee_case['module_mass_kg']:.2f} kg, Risk: {knee_case['risk_score_100']}/100). "
        )
        if delta_m > 0 and delta_r > 0:
            summary += f"Baz tasarıma göre +{delta_m:.2f} kg ilave kütle maliyeti ile risk skoru {delta_r:.1f} puan düşürülmüştür."
        elif delta_m <= 0 and delta_r > 0:
            summary += f"Baz tasarımdan daha hafif veya eşit kütlede risk skoru {delta_r:.1f} puan düşürülmüştür."
        else:
            summary += f"Tasarım maksimum güvenlik/kütle oranını sağlamaktadır."

        return {
            "cases": cases_data,
            "pareto_front_indices": pareto_indices,
            "knee_point_index": best_knee_idx,
            "baseline_mass_kg": round(baseline_mass, 3),
            "summary": summary
        }

    @staticmethod
    def build_2d_grid_variations(
        base_request_dict: Dict[str, Any],
        param_x: str,
        values_x: List[Any],
        param_y: str,
        values_y: List[Any]
    ) -> List[Dict[str, Any]]:
        """2 Parametreli Izgara Taraması (2D Parametric Grid Sweep) için konfigürasyon matrisi üretir."""
        cases = []
        for vx in values_x:
            for vy in values_y:
                cfg = dict(base_request_dict)
                cfg[param_x] = vx
                cfg[param_y] = vy
                cfg["case_name"] = f"{param_x}={vx}_{param_y}={vy}"
                cfg["grid_coords"] = {"x_val": vx, "y_val": vy, "param_x": param_x, "param_y": param_y}
                cases.append(cfg)
        return cases

    @staticmethod
    def analyze_tornado_sensitivity(
        baseline_case: Dict[str, Any],
        variation_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        OAT (One-At-A-Time) Hassasiyet Çalışması Sonuçlarını Tornado Sıralamasına Dönüştürür.
        Her parametrenin tepe sıcaklık ve risk skoruna etkisini (Swing Range) hesaplar.
        """
        base_temp = baseline_case.get("peak_module_temp_C", 100.0)
        base_risk = baseline_case.get("risk_score_100", 50.0)

        # Parametre bazında grupla: param_name -> {"low": case, "high": case}
        param_groups: Dict[str, Dict[str, Any]] = {}
        for c in variation_cases:
            p_name = c.get("perturbed_param")
            direction = c.get("perturbation_direction", "high")
            if p_name:
                if p_name not in param_groups:
                    param_groups[p_name] = {}
                param_groups[p_name][direction] = c

        tornado_items = []
        for p_name, dirs in param_groups.items():
            low_case = dirs.get("low", baseline_case)
            high_case = dirs.get("high", baseline_case)

            t_low = low_case.get("peak_module_temp_C", base_temp)
            t_high = high_case.get("peak_module_temp_C", base_temp)
            temp_swing = abs(t_high - t_low)

            r_low = low_case.get("risk_score_100", base_risk)
            r_high = high_case.get("risk_score_100", base_risk)
            risk_swing = abs(r_high - r_low)

            tornado_items.append({
                "param_name": p_name,
                "temp_low_C": round(t_low, 2),
                "temp_high_C": round(t_high, 2),
                "temp_swing_C": round(temp_swing, 2),
                "delta_temp_low_C": round(t_low - base_temp, 2),
                "delta_temp_high_C": round(t_high - base_temp, 2),
                "risk_low": round(r_low, 1),
                "risk_high": round(r_high, 1),
                "risk_swing": round(risk_swing, 1)
            })

        # En yüksek sıcaklık etkisine göre sırala (Tornado Grafiği hiyerarşisi)
        tornado_items.sort(key=lambda x: x["temp_swing_C"], reverse=True)

        return {
            "baseline_peak_temp_C": round(base_temp, 2),
            "baseline_risk_score": round(base_risk, 1),
            "parameters_ranked": tornado_items,
            "most_sensitive_parameter": tornado_items[0]["param_name"] if tornado_items else None
        }
