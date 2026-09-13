"""
Simülasyon Servis Katmanı (SimulationService)
Geometri inşası, termal ağ çözümü, değerlendirme ve PDF üretimini orkestre eder.
Faz 0.5 Sözleşme 3 gereğince tamamlanan sonuçlar değişmez (immutable) olarak saklanır.
"""

from typing import Dict, Any, Optional
import uuid
import time
from pathlib import Path

from simulator.core.constants import celsius_to_kelvin
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.thermal_network import ThermalNetworkAssembler
from simulator.core.solver import ThermalRunawaySolver, SimulationResult
from simulator.core.propagation_evaluator import PropagationEvaluator, PropagationEvaluation
from simulator.reporting.report_generator import ReportGenerator
from simulator.api.models import PackSimulationRequest, DesignStudyRequest

class SimulationService:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parent.parent.parent)
        self.kinetics_engine = ArrheniusKineticsEngine()
        self.geometry_builder = PackGeometryBuilder()
        self.evaluator = PropagationEvaluator()
        self.report_generator = ReportGenerator(output_dir=str(self.base_dir / "reports"))

        # Değişmez sonuç deposu (In-memory cache + disk raporu)
        self._results_store: Dict[str, Dict[str, Any]] = {}

    def run_simulation(self, request: PackSimulationRequest) -> Dict[str, Any]:
        """Tüm simülasyon akışını senkron çalıştırır ve sonuç nesnesini dondurur."""
        job_id = f"sim_{uuid.uuid4().hex[:10]}"
        start_time = time.strftime("%Y-%m-%d %H:%M:%S")

        # 0. Özel (Inline) Parametre Enjeksiyonu
        active_chem_id = request.chemistry_id
        if request.custom_chemistry_params:
            from simulator.core.kinetics_engine import ChemistryParams
            custom_data = dict(request.custom_chemistry_params)
            active_chem_id = custom_data.get("chemistry_id", f"custom_inline_{uuid.uuid4().hex[:6]}")
            custom_data["chemistry_id"] = active_chem_id
            custom_data["source_type"] = "user_defined"
            chem_obj = ChemistryParams.from_dict(custom_data, source_type="user_defined")
            self.kinetics_engine.library[active_chem_id] = chem_obj
        elif request.advanced_physics_enabled:
            from simulator.core.kinetics_engine import ChemistryParams
            base_chem = self.kinetics_engine.get_params(active_chem_id)
            adv_id = f"adv_{uuid.uuid4().hex[:6]}"
            adv_data = {
                "chemistry_id": adv_id,
                "name": f"{base_chem.name} (Gelişmiş Fizik)",
                "A_pre_exponential_per_s": request.custom_A_pre_exponential if request.custom_A_pre_exponential is not None else base_chem.A,
                "Ea_J_per_mol": request.custom_Ea_J_per_mol if request.custom_Ea_J_per_mol is not None else base_chem.Ea,
                "delta_H_J_per_kg": (request.custom_delta_H_J_per_g * 1000.0) if request.custom_delta_H_J_per_g is not None else base_chem.delta_H,
                "T_onset_K": base_chem.T_onset_K,
                "T_trigger_K": base_chem.T_trigger_K,
                "n_reaction_order": request.custom_reaction_order_n if request.custom_reaction_order_n is not None else base_chem.n,
                "active_mass_ratio": request.custom_active_mass_ratio if request.custom_active_mass_ratio is not None else base_chem.active_mass_ratio,
                "source_type": "user_defined"
            }
            active_chem_id = adv_id
            self.kinetics_engine.library[adv_id] = ChemistryParams.from_dict(adv_data, source_type="user_defined")

        active_sep_id = request.separator_material_id
        if request.custom_separator_params:
            custom_mat = dict(request.custom_separator_params)
            active_sep_id = custom_mat.get("material_id", f"mat_inline_{uuid.uuid4().hex[:6]}")
            custom_mat["material_id"] = active_sep_id
            custom_mat["source_type"] = "user_defined"
            self.geometry_builder.materials_lib[active_sep_id] = custom_mat

        active_gap_id = request.gap_material_id
        if request.custom_gap_params:
            custom_gap = dict(request.custom_gap_params)
            active_gap_id = custom_gap.get("material_id", f"gap_inline_{uuid.uuid4().hex[:6]}")
            custom_gap["material_id"] = active_gap_id
            custom_gap["source_type"] = "user_defined"
            self.geometry_builder.materials_lib[active_gap_id] = custom_gap

        # 1. Geometriyi inşa et
        T_amb_K = celsius_to_kelvin(request.T_ambient_C)
        cells, connections, pack_bounds = self.geometry_builder.build_pack(
            rows=request.rows,
            cols=request.cols,
            cell_format=request.cell_format,
            spacing_x_mm=request.spacing_x_mm,
            spacing_y_mm=request.spacing_y_mm,
            chemistry_id=active_chem_id,
            staggered=request.staggered,
            separator_material_id=active_sep_id,
            separator_thickness_mm=request.separator_thickness_mm,
            gap_material_id=active_gap_id,
            initial_temp_K=T_amb_K
        )

        # 2. Isıl ağı kur
        assembler = ThermalNetworkAssembler(
            cells=cells,
            connections=connections,
            materials_lib=self.geometry_builder.materials_lib,
            kinetics_engine=self.kinetics_engine,
            h_ambient_conv_W_per_m2_K=request.h_ambient_W_per_m2_K,
            T_ambient_K=T_amb_K,
            emissivity=request.surface_emissivity,
            busbar_conductance_W_per_K=request.busbar_conductance_W_per_K,
            active_cooling_enabled=request.active_cooling_enabled,
            h_cooling_plate_W_per_m2_K=request.h_cooling_plate_W_per_m2_K,
            T_coolant_K=celsius_to_kelvin(request.T_coolant_C),
            h_vent_W_per_m2_K=request.h_vent_W_per_m2_K,
            T_vent_gas_K=(request.T_vent_gas_C + 273.15) if request.T_vent_gas_C is not None else None
        )

        # 3. Diferansiyel denklemleri çöz
        solver = ThermalRunawaySolver(assembler)
        result = solver.solve(
            job_id=job_id,
            t_span=(0.0, request.simulation_time_s),
            trigger_cell_id=request.trigger_cell_id,
            trigger_method=request.trigger_method,
            trigger_power_W=request.trigger_power_W,
            trigger_duration_s=request.trigger_duration_s,
            trigger_initial_temp_C=request.trigger_initial_temp_C,
            num_output_points=request.num_output_points,
            config_dict=request.model_dump()
        )

        # 4. Yayılım riskini değerlendir
        eval_obj = self.evaluator.evaluate(result, trigger_cell_id=request.trigger_cell_id)
        
        # Seçilen kimyanın özelliklerini kontrol et
        chem_params = self.kinetics_engine.get_params(active_chem_id)

        # 4.1 Güven Etiketi / Uyarı Bayrağı
        is_dense = request.spacing_x_mm < 3.0 or request.spacing_y_mm < 3.0
        no_barrier = request.separator_material_id is None
        
        if chem_params.source_type == "user_defined":
            eval_obj.confidence_level = "low"
            eval_obj.confidence_message = "⚠️ SİMÜLASYON UYARISI: Bu simülasyon kullanıcı tarafından tanımlanmış, bağımsız doğrulanmamış (user_defined_unverified) özel kimya parametreleriyle çalıştırılmıştır."
        elif is_dense and no_barrier:
            eval_obj.confidence_level = "low"
            eval_obj.confidence_message = "⚠️ DİKKAT: Yarı-ampirik Ejecta-Konveksiyon gaz modeli devrede. Ancak bariyersiz dar boşluk (<3mm) nedeniyle gerçek fiziksel alev sıçramaları sonucu daha agresif yayılım olabilir."
        else:
            eval_obj.confidence_level = "high"
            eval_obj.confidence_message = "✅ Güvenilirlik: Yüksek (Kayıtlı literatür verisi, uygun aralık/bariyer)."

        # 5. PDF raporunu üret
        pdf_path = self.report_generator.generate_pdf_report(result, eval_obj)

        evaluation = eval_obj.to_dict()

        # 6. Sonuçları değişmez (immutable) olarak kaydet (Sözleşme 3)
        completed_at = time.strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "job_id": job_id,
            "status": "COMPLETED",
            "created_at": start_time,
            "completed_at": completed_at,
            "request_config": request.model_dump(),
            "pack_bounds": pack_bounds,
            "simulation_result": result.to_dict(),
            "evaluation": evaluation,
            "pdf_report_path": pdf_path,
            "pdf_filename": Path(pdf_path).name
        }
        self._results_store[job_id] = record
        return record

    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._results_store.get(job_id)

    def run_design_study(self, study_req: DesignStudyRequest) -> Dict[str, Any]:
        """Çoklu parametre taraması (Design Study / Sweep) gerçekleştirir ve karşılaştırmalı matris üretir."""
        study_id = f"study_{uuid.uuid4().hex[:8]}"
        base = study_req.base_config
        sweep_type = study_req.sweep_type

        variations = []
        if sweep_type == "spacing_sweep":
            vals = study_req.sweep_values or [1.5, 2.0, 2.5, 3.0]
            for v in vals:
                cfg = base.model_copy(deep=True)
                cfg.spacing_x_mm = float(v)
                cfg.spacing_y_mm = float(v)
                variations.append((f"{v} mm Boşluk", "Hücre Aralığı", f"{v} mm", cfg))
        elif sweep_type == "separator_sweep":
            cases_def = [
                ("Bariyersiz (Sadece Hava)", "Bariyer", "Yok", None, 0.0),
                ("Mika Plaka (0.5 mm)", "Bariyer", "Mika 0.5mm", "mica_sheet", 0.5),
                ("Mika Plaka (1.0 mm)", "Bariyer", "Mika 1.0mm", "mica_sheet", 1.0),
                ("Aerojel Kompozit (1.0 mm)", "Bariyer", "Aerojel 1.0mm", "aerogel_insulation", 1.0),
            ]
            for name, lbl, val_str, mat_id, thick in cases_def:
                cfg = base.model_copy(deep=True)
                cfg.separator_material_id = mat_id
                cfg.separator_thickness_mm = thick
                variations.append((name, lbl, val_str, cfg))
        elif sweep_type == "cooling_sweep":
            cases_def = [
                ("Pasif Doğal Konveksiyon", "Soğutma", "Kapalı", False, 0.0),
                ("Aktif Soğutma (h=400)", "Soğutma", "400 W/m²K", True, 400.0),
                ("Aktif Soğutma (h=800)", "Soğutma", "800 W/m²K", True, 800.0),
                ("Yoğun Sıvı Soğutma (h=1500)", "Soğutma", "1500 W/m²K", True, 1500.0),
            ]
            for name, lbl, val_str, enabled, h_val in cases_def:
                cfg = base.model_copy(deep=True)
                cfg.active_cooling_enabled = enabled
                cfg.h_cooling_plate_W_per_m2_K = h_val
                variations.append((name, lbl, val_str, cfg))
        else:
            raise ValueError(f"Bilinmeyen tarama tipi: {sweep_type}")

        case_results = []
        for idx, (case_name, param_lbl, param_val, cfg) in enumerate(variations):
            res = self.run_simulation(cfg)
            ev = res["evaluation"]
            case_results.append({
                "case_index": idx,
                "case_name": case_name,
                "param_label": param_lbl,
                "param_value": param_val,
                "peak_module_temp_C": ev["peak_module_temp_C"],
                "affected_cells_count": ev["affected_cells_count"],
                "total_cells": ev["total_cells"],
                "propagation_ratio_percent": ev["propagation_ratio_percent"],
                "time_to_first_propagation_s": ev["time_to_first_propagation_s"],
                "risk_score_100": ev["risk_score_100"],
                "status": ev["status"],
                "is_recommended": False,
                "job_id": res["job_id"]
            })

        # En güvenli tasarımı tespit et (Sıralama: 1. Risk skoru, 2. Etkilenen hücre, 3. Pik sıcaklık)
        sorted_cases = sorted(case_results, key=lambda c: (c["risk_score_100"], c["affected_cells_count"], c["peak_module_temp_C"]))
        best_case = sorted_cases[0]
        best_case["is_recommended"] = True

        reason = f"En düşük risk skoru ({best_case['risk_score_100']}/100) ve {best_case['affected_cells_count']} etkilenen hücre ile en güvenli tasarım."

        return {
            "study_id": study_id,
            "sweep_type": sweep_type,
            "recommended_case_index": best_case["case_index"],
            "recommended_reason": reason,
            "cases": case_results
        }
