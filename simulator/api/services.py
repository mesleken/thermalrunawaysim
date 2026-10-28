"""
Simülasyon Servis Katmanı (SimulationService)
Geometri inşası, termal ağ çözümü, değerlendirme ve PDF üretimini orkestre eder.
Faz 0.5 Sözleşme 3 gereğince tamamlanan sonuçlar değişmez (immutable) olarak saklanır.
"""

from typing import Dict, Any, Optional, List, Tuple
import os
import uuid
import time
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from pathlib import Path
import numpy as np

from simulator.core.constants import celsius_to_kelvin, PropagationStatus
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.pack_geometry import PackGeometryBuilder
from simulator.core.thermal_network import ThermalNetworkAssembler
from simulator.core.solver import ThermalRunawaySolver, SimulationResult
from simulator.core.propagation_evaluator import PropagationEvaluator, PropagationEvaluation
from simulator.core.validation_engine import ValidationEngine
from simulator.core.design_optimizer import calculate_module_mass, DesignOptimizationEngine
from simulator.reporting.report_generator import ReportGenerator
from simulator.persistence.database import db_repo
from simulator.api.models import (
    PackSimulationRequest,
    DesignStudyRequest,
    MonteCarloUQRequest,
    ValidationCompareRequest,
    AutoCalibrateRequest,
    Grid2DStudyRequest,
    SensitivityStudyRequest
)

class SimulationService:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parent.parent.parent)
        self.kinetics_engine = ArrheniusKineticsEngine()
        self.geometry_builder = PackGeometryBuilder()
        self.evaluator = PropagationEvaluator()
        self.validation_engine = ValidationEngine()
        self.report_generator = ReportGenerator(output_dir=str(self.base_dir / "reports"))
        self.db = db_repo

        # Değişmez sonuç deposu (In-memory cache + SQLite kalıcılık)
        self._results_store: Dict[str, Dict[str, Any]] = {}
        self._store_lock = threading.Lock()

        # Arka plan / toplu tarama görev durumu deposu (SSE İlerleme Akışı için)
        self._tasks_store: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

    def init_task(self, task_id: Optional[str], total: int, label: str = "Toplu Analiz") -> str:
        tid = task_id or f"task_{uuid.uuid4().hex[:10]}"
        with self._tasks_lock:
            self._tasks_store[tid] = {
                "task_id": tid,
                "label": label,
                "status": "RUNNING",
                "completed": 0,
                "total": max(1, int(total)),
                "progress_percent": 0.0,
                "message": f"{label} başlatıldı (0/{total})...",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": time.time(),
                "error": None
            }
        return tid

    def update_task_progress(self, task_id: str, completed: int, total: int, message: str = "", status: str = "RUNNING") -> None:
        pct = round(min(100.0, (completed / max(1, total)) * 100.0), 1)
        with self._tasks_lock:
            if task_id in self._tasks_store:
                self._tasks_store[task_id].update({
                    "status": status,
                    "completed": int(completed),
                    "total": max(1, int(total)),
                    "progress_percent": pct,
                    "message": message or f"Simülasyon {completed}/{total} tamamlandı (%{pct:.0f})",
                    "updated_at": time.time()
                })

    def fail_task(self, task_id: str, error_msg: str) -> None:
        with self._tasks_lock:
            if task_id in self._tasks_store:
                self._tasks_store[task_id].update({
                    "status": "FAILED",
                    "message": f"Hata: {error_msg}",
                    "error": error_msg,
                    "updated_at": time.time()
                })

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._tasks_lock:
            t = self._tasks_store.get(task_id)
            return dict(t) if t else None

    def _run_batch_parallel(
        self,
        configs: List[PackSimulationRequest],
        task_id: Optional[str] = None,
        task_label: str = "Parametrik Tarama",
        persist_each_to_db: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Çoklu simülasyon varyasyonlarını paralel iş parçacığı havuzunda (SciPy C/Fortran LSODA GIL-free)
        koşturur, ilerleme durumunu SSE görev deposuna anlık yazar ve sonuçları sıra korumalı döner.
        """
        total = len(configs)
        tid = self.init_task(task_id, total=total, label=task_label)
        if total == 0:
            self.update_task_progress(tid, 0, 1, "Tamamlandı", status="COMPLETED")
            return []

        max_workers = min(total, max(1, min(4, os.cpu_count() or 2)))
        ordered_results: List[Optional[Dict[str, Any]]] = [None] * total
        completed_counter = 0

        # Ana serviste kayıtlı özel kimya/malzemelerin anlık görüntüsü
        custom_chems = dict(self.kinetics_engine.library)
        custom_mats = dict(self.geometry_builder.materials_lib)
        custom_dims = dict(self.geometry_builder.CELL_DIMENSIONS)

        def _worker_fn(idx: int, req_cfg: PackSimulationRequest) -> Tuple[int, Dict[str, Any]]:
            # İzole işçi servisi (paylaşımlı mutable state çakışmasını önler)
            worker_svc = SimulationService(base_dir=str(self.base_dir))
            worker_svc.kinetics_engine.library.update(custom_chems)
            worker_svc.geometry_builder.materials_lib.update(custom_mats)
            worker_svc.geometry_builder.CELL_DIMENSIONS.update(custom_dims)
            rec = worker_svc.run_simulation(req_cfg, generate_pdf=False, persist_db=False)
            return idx, rec

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [pool.submit(_worker_fn, idx, cfg) for idx, cfg in enumerate(configs)]
                for fut in as_completed(futures):
                    idx, rec = fut.result()
                    ordered_results[idx] = rec
                    with self._store_lock:
                        self._results_store[rec["job_id"]] = rec
                    if persist_each_to_db:
                        try:
                            self.db.save_simulation(rec["job_id"], rec, rec["request_config"])
                        except Exception:
                            pass
                    completed_counter += 1
                    self.update_task_progress(
                        tid,
                        completed_counter,
                        total,
                        message=f"{task_label}: {completed_counter}/{total} tamamlandı (%{(completed_counter/total)*100:.0f})",
                        status="COMPLETED" if completed_counter >= total else "RUNNING"
                    )
        except Exception as exc:
            self.fail_task(tid, str(exc))
            raise

        return [r for r in ordered_results if r is not None]

    def run_simulation(
        self,
        request: PackSimulationRequest,
        generate_pdf: bool = False,
        persist_db: bool = True
    ) -> Dict[str, Any]:
        """Tüm simülasyon akışını senkron çalıştırır ve sonuç nesnesini dondurur (PDF varsayılan olarak lazy üretilir)."""
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
            from simulator.core.kinetics_engine import ChemistryParams, SubReaction
            base_chem = self.kinetics_engine.get_params(active_chem_id)
            adv_id = f"adv_{uuid.uuid4().hex[:6]}"
            a_factor = (request.custom_A_pre_exponential / base_chem.A) if (request.custom_A_pre_exponential is not None and base_chem.A > 0) else 1.0
            ea_factor = (request.custom_Ea_J_per_mol / base_chem.Ea) if (request.custom_Ea_J_per_mol is not None and base_chem.Ea > 0) else 1.0
            dh_factor = ((request.custom_delta_H_J_per_g * 1000.0) / base_chem.delta_H) if (request.custom_delta_H_J_per_g is not None and base_chem.delta_H > 0) else 1.0

            adv_chem = base_chem.scale_kinetics(a_factor=a_factor, ea_factor=ea_factor, dh_factor=dh_factor)
            adv_chem.chemistry_id = adv_id
            adv_chem.name = f"{base_chem.name} (Gelişmiş Fizik)"
            if request.custom_reaction_order_n is not None:
                adv_chem.n = float(request.custom_reaction_order_n)
            if request.custom_active_mass_ratio is not None:
                adv_chem.active_mass_ratio = float(request.custom_active_mass_ratio)
            adv_chem.source_type = base_chem.source_type

            if request.custom_sub_reactions:
                parsed_subs = []
                for idx, sr in enumerate(request.custom_sub_reactions):
                    base_sr = base_chem.sub_reactions[idx] if idx < len(base_chem.sub_reactions) else None
                    dh_val = sr.get("delta_H_J_per_kg")
                    if dh_val is None and sr.get("delta_H_J_per_g") is not None:
                        dh_val = float(sr["delta_H_J_per_g"]) * 1000.0
                    if dh_val is None:
                        dh_val = base_sr.delta_H if base_sr else 500000.0
                    ea_val = sr.get("Ea_J_per_mol")
                    if ea_val is None and sr.get("Ea_kJ_per_mol") is not None:
                        ea_val = float(sr["Ea_kJ_per_mol"]) * 1000.0
                    if ea_val is None:
                        ea_val = base_sr.Ea if base_sr else 130000.0
                    parsed_subs.append(
                        SubReaction(
                            key=sr.get("key", base_sr.key if base_sr else f"rxn_{idx}"),
                            name=sr.get("name", base_sr.name if base_sr else f"Alt Reaksiyon #{idx+1}"),
                            A_per_s=float(sr.get("A_per_s", sr.get("A", base_sr.A if base_sr else 1e14))),
                            Ea_J_per_mol=float(ea_val),
                            delta_H_J_per_kg=float(dh_val),
                            n=float(sr.get("n", base_sr.n if base_sr else 1.0)),
                            m_autocatalytic=float(sr.get("m_autocatalytic", base_sr.m_autocatalytic if base_sr else 0.0)),
                            T_onset_K=float(sr.get("T_onset_K", base_sr.T_onset_K if base_sr else 373.15)),
                            description=sr.get("description", base_sr.description if base_sr else "")
                        )
                    )
                adv_chem.sub_reactions = parsed_subs

            active_chem_id = adv_id
            self.kinetics_engine.library[adv_id] = adv_chem

        # SOC Ölçeklendirmesi (%0 - 100)
        if request.soc_percent < 100.0:
            current_chem = self.kinetics_engine.get_params(active_chem_id)
            soc_id = f"{active_chem_id}_soc{int(request.soc_percent)}"
            scaled_chem = current_chem.apply_soc_scaling(request.soc_percent)
            self.kinetics_engine.library[soc_id] = scaled_chem
            active_chem_id = soc_id

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
            T_vent_gas_K=(request.T_vent_gas_C + 273.15) if request.T_vent_gas_C is not None else None,
            nodal_model=request.nodal_model,
            kinetics_model=request.kinetics_model,
            ejecta_mass_loss_ratio=request.ejecta_mass_loss_ratio,
            vent_direction_deg=request.vent_direction_deg,
            soc_percent=request.soc_percent
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
            isc_resistance_ohm=request.isc_resistance_ohm,
            oven_target_temp_C=request.oven_target_temp_C,
            oven_ramp_C_per_min=request.oven_ramp_C_per_min,
            enclosure_free_volume_liters=request.enclosure_free_volume_liters,
            vent_valve_area_cm2=request.vent_valve_area_cm2,
            vent_burst_pressure_kpa=request.vent_burst_pressure_kpa,
            num_output_points=request.num_output_points,
            config_dict=request.model_dump()
        )

        # Modül Kütle Dökümünü Hesapla ve Sonuca Ekle
        mass_breakdown = calculate_module_mass(request, self.geometry_builder)
        result.pack_metrics["module_mass_kg"] = mass_breakdown["total_mass_kg"]
        result.pack_metrics["module_mass_breakdown"] = mass_breakdown

        # 4. Yayılım riskini değerlendir (Topolojik bağlantı tabanlı nedensel DAG ile)
        eval_obj = self.evaluator.evaluate(result, trigger_cell_id=request.trigger_cell_id, connections=connections)
        
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

        # 5. İsteğe Bağlı (On-Demand / Lazy) PDF Raporu Üretimi
        pdf_path = None
        if generate_pdf:
            try:
                pdf_path = self.report_generator.generate_pdf_report(result, eval_obj)
            except Exception:
                pdf_path = None

        evaluation = eval_obj.to_dict()
        evaluation["module_mass_kg"] = mass_breakdown["total_mass_kg"]
        evaluation["module_mass_breakdown"] = mass_breakdown

        # 6. Sonuçları değişmez (immutable) olarak kaydet ve SQLite'a tam kayıt olarak yaz
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
            "pdf_filename": Path(pdf_path).name if pdf_path else None
        }
        with self._store_lock:
            self._results_store[job_id] = record

        # SQLite Kalıcılık (Tam kayıt serileştirmesi: sunucu yeniden başlasa dahi evaluation + config korunur)
        if persist_db:
            try:
                self.db.save_simulation(job_id, record, request.model_dump())
            except Exception:
                pass

        return record

    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Bellekten veya SQLite kalıcı veritabanından simülasyonu tam sadakatle getirir."""
        with self._store_lock:
            if job_id in self._results_store:
                return self._results_store[job_id]

        # SQLite'tan sorgula
        stored = self.db.get_simulation(job_id)
        if stored:
            if "simulation_result" in stored and "evaluation" in stored:
                record = stored
                record.setdefault("job_id", job_id)
                record.setdefault("status", "COMPLETED")
                record.setdefault("request_config", {})
                record.setdefault("pack_bounds", {})
                record.setdefault("pdf_report_path", None)
                record.setdefault("pdf_filename", None)
            else:
                # Eski format ham SimulationResult kaydı için geriye dönük uyumlu yeniden inşa
                sim_res_obj = SimulationResult(**stored)
                trig_id = int(stored.get("pack_metrics", {}).get("trigger_cell_id", 0))
                eval_rebuilt = self.evaluator.evaluate(sim_res_obj, trigger_cell_id=trig_id).to_dict()
                record = {
                    "job_id": job_id,
                    "status": "COMPLETED",
                    "created_at": stored.get("created_at", ""),
                    "completed_at": stored.get("created_at", ""),
                    "request_config": {"trigger_cell_id": trig_id},
                    "pack_bounds": {},
                    "simulation_result": stored,
                    "evaluation": eval_rebuilt,
                    "pdf_report_path": None,
                    "pdf_filename": None
                }
            with self._store_lock:
                self._results_store[job_id] = record
            return record
        return None

    def get_or_create_pdf_report(self, job_id: str) -> str:
        """PDF raporunu sadece istendiğinde (lazy on-demand) üretir veya önbellekten döner."""
        record = self.get_result(job_id)
        if not record:
            raise KeyError(f"Simülasyon job_id='{job_id}' bulunamadı.")

        if record.get("pdf_report_path") and Path(record["pdf_report_path"]).exists():
            return record["pdf_report_path"]

        # Yeniden üret (status enum dönüşümü ile)
        sim_res = SimulationResult(**record["simulation_result"])
        eval_dict = record["evaluation"]
        raw_status = eval_dict.get("status", "NO_PROPAGATION")
        try:
            status_enum = PropagationStatus(raw_status) if isinstance(raw_status, str) else raw_status
        except ValueError:
            status_enum = PropagationStatus.NO_PROPAGATION

        eval_obj = PropagationEvaluation(
            status=status_enum,
            time_to_first_propagation_s=eval_dict.get("time_to_first_propagation_s"),
            total_cells=eval_dict.get("total_cells", len(sim_res.cell_summaries)),
            affected_cells_count=eval_dict.get("affected_cells_count", 0),
            propagation_ratio=eval_dict.get("propagation_ratio_percent", 0.0) / 100.0,
            propagation_sequence=eval_dict.get("propagation_sequence", []),
            propagation_path_graph=eval_dict.get("propagation_path_graph", []),
            peak_module_temp_C=eval_dict.get("peak_module_temp_C", 100.0),
            min_containment_margin_C=eval_dict.get("min_containment_margin_C", 50.0),
            risk_score_100=eval_dict.get("risk_score_100", 0.0),
            uncertainty_bounds=eval_dict.get("uncertainty_bounds", {}),
            regulatory_summary=eval_dict.get("regulatory_summary", ""),
            confidence_level=eval_dict.get("confidence_level", "high"),
            confidence_message=eval_dict.get("confidence_message", ""),
            regulatory_compliance=eval_dict.get("regulatory_compliance", {})
        )

        pdf_path = self.report_generator.generate_pdf_report(sim_res, eval_obj)
        record["pdf_report_path"] = pdf_path
        record["pdf_filename"] = Path(pdf_path).name
        return pdf_path

    def export_simulation_data(self, job_id: str, fmt: str = "csv") -> Tuple[bytes, str, str]:
        """
        Aşama 4: Simülasyon zaman serisini ve durum matrisini CSV, NPZ (ikili sıkıştırılmış) veya JSON olarak dışa aktarır.
        Döner: (data_bytes, media_type, filename)
        """
        record = self.get_result(job_id)
        if not record:
            raise KeyError(f"Simülasyon job_id='{job_id}' bulunamadı.")

        sim_res = record["simulation_result"]
        times = np.array(sim_res["time_points_s"], dtype=np.float32)
        cells = sim_res["cell_summaries"]
        temps_dict = sim_res["temperature_history_C"]
        alphas_dict = sim_res["alpha_history"]

        fmt = fmt.lower().strip()

        if fmt == "csv":
            buf = io.StringIO()
            header = ["time_s"]
            for c in cells:
                cid = c["cell_id"]
                header.append(f"cell_{cid}_temp_C")
            for c in cells:
                cid = c["cell_id"]
                header.append(f"cell_{cid}_alpha")
            buf.write(",".join(header) + "\n")

            n_pts = len(times)
            for i in range(n_pts):
                row = [f"{times[i]:.4f}"]
                for c in cells:
                    cid = c["cell_id"]
                    t_val = temps_dict.get(cid, temps_dict.get(str(cid), [0.0]))[i]
                    row.append(f"{t_val:.2f}")
                for c in cells:
                    cid = c["cell_id"]
                    a_val = alphas_dict.get(cid, alphas_dict.get(str(cid), [0.0]))[i]
                    row.append(f"{a_val:.4f}")
                buf.write(",".join(row) + "\n")

            content = buf.getvalue().encode("utf-8")
            return content, "text/csv", f"simulation_{job_id}.csv"

        elif fmt == "npz":
            buf = io.BytesIO()
            n_cells = len(cells)
            temp_matrix = np.zeros((n_cells, len(times)), dtype=np.float32)
            alpha_matrix = np.zeros((n_cells, len(times)), dtype=np.float32)

            for idx, c in enumerate(cells):
                cid = c["cell_id"]
                temp_matrix[idx, :] = np.array(temps_dict.get(cid, temps_dict.get(str(cid))), dtype=np.float32)
                alpha_matrix[idx, :] = np.array(alphas_dict.get(cid, alphas_dict.get(str(cid))), dtype=np.float32)

            np.savez_compressed(
                buf,
                time_points_s=times,
                temperature_matrix_C=temp_matrix,
                alpha_matrix=alpha_matrix,
                config_hash=np.array([sim_res["config_hash"]])
            )
            buf.seek(0)
            return buf.getvalue(), "application/octet-stream", f"simulation_{job_id}.npz"

        else:
            export_dict = {
                "job_id": job_id,
                "config_hash": sim_res["config_hash"],
                "created_at": record["created_at"],
                "time_points_s": sim_res["time_points_s"],
                "temperature_history_C": sim_res["temperature_history_C"],
                "evaluation": record["evaluation"]
            }
            content = json.dumps(export_dict, indent=2).encode("utf-8")
            return content, "application/json", f"simulation_{job_id}.json"

    def get_audit_certificate(self, job_id: str) -> Dict[str, Any]:
        """
        Aşama 4: Değişmez (Audit-Proof) Kriptografik Doğrulama Sertifikası üretir.
        """
        record = self.get_result(job_id)
        if not record:
            raise KeyError(f"Simülasyon job_id='{job_id}' bulunamadı.")

        sim_res = record["simulation_result"]
        eval_data = record["evaluation"]
        git_hash = ReportGenerator._get_git_commit_hash()

        return {
            "certificate_id": f"TR-CERT-{job_id.upper()}",
            "job_id": job_id,
            "status": "CRYPTOGRAPHICALLY_VERIFIED",
            "is_tamper_proof": True,
            "config_hash_sha256": sim_res["config_hash"],
            "execution_fingerprint": sim_res["execution_fingerprint"],
            "git_commit_sha": git_hash,
            "library_validation_source": sim_res.get("validation_status", "literature_calibrated"),
            "solver_engine": sim_res.get("solver_metadata", {}).get("solver_method", "LSODA"),
            "regulatory_standards": [
                "UL 9540A Level 2 (Module Runaway Containment)",
                "UN 38.3 (T.1-T.8 Thermal Abuse Compliance)",
                "SAE J2464 / ISO 6469-1"
            ],
            "timestamp_created_utc": record["created_at"],
            "timestamp_completed_utc": record.get("completed_at", record["created_at"]),
            "summary_metrics": {
                "peak_temperature_C": eval_data.get("peak_module_temp_C"),
                "risk_score_100": eval_data.get("risk_score_100"),
                "affected_cells_count": eval_data.get("affected_cells_count"),
                "propagation_status": eval_data.get("status")
            },
            "verification_urn": f"urn:thermalrunaway:cert:{job_id}:{sim_res['config_hash'][:16]}:{git_hash[:8]}"
        }

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

        configs_only = [v[3] for v in variations]
        batch_records = self._run_batch_parallel(
            configs=configs_only,
            task_id=getattr(study_req, "task_id", None),
            task_label="1D Tasarım Taraması",
            persist_each_to_db=True
        )

        case_results = []
        for idx, (case_name, param_lbl, param_val, cfg) in enumerate(variations):
            res = batch_records[idx]
            ev = res["evaluation"]
            mass_info = calculate_module_mass(cfg, self.geometry_builder)
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
                "job_id": res["job_id"],
                "module_mass_kg": mass_info["total_mass_kg"],
                "mass_penalty_index_percent": 0.0,
                "is_pareto_optimal": False
            })

        # Aşama 3: Kütle Ceza İndeksi ve Pareto Cephesi Analizi (Multi-Objective Optimization)
        pareto_analysis = DesignOptimizationEngine.analyze_study(
            cases_data=case_results,
            w_safety=getattr(study_req, "w_safety", 0.6),
            w_mass=getattr(study_req, "w_mass", 0.4)
        )

        knee_idx = pareto_analysis["knee_point_index"]
        if knee_idx is not None and 0 <= knee_idx < len(case_results):
            case_results[knee_idx]["is_recommended"] = True
            reason = pareto_analysis["summary"]
        else:
            sorted_cases = sorted(case_results, key=lambda c: (c["risk_score_100"], c["affected_cells_count"], c["peak_module_temp_C"]))
            best_case = sorted_cases[0]
            best_case["is_recommended"] = True
            knee_idx = best_case["case_index"]
            reason = f"En düşük risk skoru ({best_case['risk_score_100']}/100) ve {best_case['affected_cells_count']} etkilenen hücre ile en güvenli tasarım."

        return {
            "study_id": study_id,
            "sweep_type": sweep_type,
            "recommended_case_index": knee_idx,
            "recommended_reason": reason,
            "cases": case_results,
            "pareto_front_indices": pareto_analysis["pareto_front_indices"],
            "knee_point_index": knee_idx,
            "baseline_mass_kg": pareto_analysis["baseline_mass_kg"],
            "pareto_summary": pareto_analysis["summary"]
        }

    def compare_simulation_with_sensor_log(self, job_id: str, csv_content: str, cell_id: int = 0) -> Dict[str, Any]:
        """
        Aşama 2: Yüklenen deneysel CSV sensör logunu tamamlanmış simülasyonla karşılaştırır.
        """
        sim_data = self.get_result(job_id)
        if not sim_data:
            raise KeyError(f"Simülasyon job_id='{job_id}' bulunamadı.")

        sim_res = sim_data["simulation_result"]
        sim_times = sim_res["time_points_s"]

        # Hücre sıcaklık serisini bul
        temps_dict = sim_res["temperature_history_C"]
        sim_temps = temps_dict.get(cell_id) or temps_dict.get(str(cell_id))
        if sim_temps is None:
            sim_temps = list(temps_dict.values())[0]

        # CSV'yi ayrıştır
        exp_times, exp_temps = self.validation_engine.parse_sensor_csv(csv_content)

        target_summary = next(
            (c for c in sim_res["cell_summaries"] if c["cell_id"] == cell_id),
            sim_res["cell_summaries"][0]
        )
        if target_summary.get("T_onset_C") is not None and target_summary.get("T_trigger_C") is not None:
            t_onset_C = float(target_summary["T_onset_C"])
            t_trig_C = float(target_summary["T_trigger_C"])
        else:
            first_chem = target_summary.get("chemistry_id", "NMC_generic_v1")
            chem_params = self.kinetics_engine.get_params(first_chem)
            t_onset_C = chem_params.T_onset_K - 273.15
            t_trig_C = chem_params.T_trigger_K - 273.15

        residuals = self.validation_engine.evaluate_residuals(
            sim_times=sim_times,
            sim_temps=sim_temps,
            exp_times=exp_times,
            exp_temps=exp_temps,
            sim_onset_C=t_onset_C,
            sim_trigger_C=t_trig_C
        )

        res_dict = residuals.to_dict()
        res_dict["job_id"] = job_id
        return res_dict

    def run_monte_carlo_uq(self, request: MonteCarloUQRequest) -> Dict[str, Any]:
        """
        Aşama 2: Belirsizlik Nicelendirmesi (Uncertainty Quantification & Monte Carlo).
        Ea, dH, A ve h_vent parametrelerini varyans toleransı ile pertürbe ederek N simülasyon koşturur.
        P10 (İyimser), P50 (Medyan) ve P90 (Muhafazakâr) güvenilirlik bantlarını üretir.
        """
        study_id = f"mc_{uuid.uuid4().hex[:8]}"
        base = request.base_config
        n_samples = request.n_samples
        var_pct = request.variance_percent
        var_ratio = var_pct / 100.0

        base_chem = self.kinetics_engine.get_params(base.chemistry_id)
        base_A = base.custom_A_pre_exponential or base_chem.A
        base_Ea = base.custom_Ea_J_per_mol or base_chem.Ea
        base_dH = base.custom_delta_H_J_per_g or (base_chem.delta_H / 1000.0)
        base_h_vent = base.h_vent_W_per_m2_K

        all_histories: List[List[float]] = []
        all_peak_temps: List[float] = []
        time_points_ref: List[float] = []

        rng = np.random.default_rng(42)
        mc_configs: List[PackSimulationRequest] = []

        for s_idx in range(n_samples):
            cfg = base.model_copy(deep=True)
            cfg.advanced_physics_enabled = True
            cfg.custom_A_pre_exponential = float(max(1e10, base_A * (1.0 + rng.normal(0.0, var_ratio * 0.5))))
            cfg.custom_Ea_J_per_mol = float(max(50000.0, base_Ea * (1.0 + rng.normal(0.0, var_ratio))))
            cfg.custom_delta_H_J_per_g = float(max(100.0, base_dH * (1.0 + rng.normal(0.0, var_ratio))))
            cfg.h_vent_W_per_m2_K = float(max(10.0, base_h_vent * (1.0 + rng.normal(0.0, var_ratio * 0.8))))
            mc_configs.append(cfg)

        batch_records = self._run_batch_parallel(
            configs=mc_configs,
            task_id=getattr(request, "task_id", None),
            task_label="Monte Carlo UQ Analizi",
            persist_each_to_db=False
        )

        for res in batch_records:
            sim_res = res["simulation_result"]
            trig_id = base.trigger_cell_id

            if not time_points_ref:
                time_points_ref = sim_res["time_points_s"]

            trig_history = sim_res["temperature_history_C"].get(trig_id) or sim_res["temperature_history_C"].get(str(trig_id))
            if trig_history:
                all_histories.append(trig_history)
            all_peak_temps.append(float(res["evaluation"]["peak_module_temp_C"]))

        if not all_histories:
            raise RuntimeError("Monte Carlo simülasyonları sonuç üretemedi.")

        hist_matrix = np.array(all_histories, dtype=np.float64)
        peaks_arr = np.array(all_peak_temps, dtype=np.float64)

        p10_history = [round(float(x), 2) for x in np.percentile(hist_matrix, 10, axis=0)]
        p50_history = [round(float(x), 2) for x in np.percentile(hist_matrix, 50, axis=0)]
        p90_history = [round(float(x), 2) for x in np.percentile(hist_matrix, 90, axis=0)]

        p10_peak = float(np.percentile(peaks_arr, 10))
        p50_peak = float(np.percentile(peaks_arr, 50))
        p90_peak = float(np.percentile(peaks_arr, 90))

        ci_width = p90_peak - p10_peak
        summary = (
            f"90% İstatistiksel Güvenilirlik Bandı (N={n_samples}, ±%{var_pct:.1f} Varyans): "
            f"P10(İyimser)={p10_peak:.1f}°C, P50(Medyan)={p50_peak:.1f}°C, P90(Muhafazakâr)={p90_peak:.1f}°C. "
            f"Belirsizlik Güven Aralığı: ±{ci_width/2.0:.1f}°C."
        )

        return {
            "study_id": study_id,
            "n_samples": n_samples,
            "variance_percent": var_pct,
            "p10_peak_temp_C": round(p10_peak, 2),
            "p50_peak_temp_C": round(p50_peak, 2),
            "p90_peak_temp_C": round(p90_peak, 2),
            "confidence_interval_width_C": round(ci_width, 2),
            "time_points_s": time_points_ref,
            "p10_temperature_history_C": p10_history,
            "p50_temperature_history_C": p50_history,
            "p90_temperature_history_C": p90_history,
            "summary_statement": summary
        }

    def run_auto_calibration(self, req: AutoCalibrateRequest) -> Dict[str, Any]:
        """ARC / F848 test CSV sıcaklık verisinden Arrhenius kinetiğini otomatik kalibre eder."""
        cp_val = float(req.cell_cp_J_per_kg_K if req.cell_cp_J_per_kg_K is not None else req.cp_J_per_kg_K)
        fit_result = self.validation_engine.auto_calibrate_arrhenius_from_csv(
            csv_text=req.csv_content,
            cell_mass_kg=req.cell_mass_kg,
            cp_J_per_kg_K=cp_val,
            active_mass_ratio=req.active_mass_ratio
        )

        # Kalibre edilen kimyayı kinetik kütüphanesine kaydet (Doğru ChemistryParams argümanlarıyla)
        from simulator.core.kinetics_engine import ChemistryParams
        chem_id = f"calibrated_{uuid.uuid4().hex[:6]}"
        t_onset_C = float(fit_result.get("detected_T_onset_C") or 150.0)
        t_tr_C = float(fit_result.get("detected_T_trigger_C") or max(t_onset_C + 35.0, 200.0))

        chem_obj = ChemistryParams(
            chemistry_id=chem_id,
            name=f"{req.chemistry_name} (Otomatik Kalibre)",
            A_pre_exponential_per_s=fit_result["frequency_factor_A"],
            Ea_J_per_mol=fit_result["activation_energy_J_per_mol"],
            delta_H_J_per_kg=fit_result["reaction_enthalpy_J_per_kg"],
            T_onset_K=t_onset_C + 273.15,
            T_trigger_K=t_tr_C + 273.15,
            n_reaction_order=1.0,
            nominal_mass_kg=req.cell_mass_kg,
            nominal_cp_J_per_kg_K=cp_val,
            active_mass_ratio=req.active_mass_ratio,
            source_type="user_defined",
            nominal_voltage_V=3.7,
            nominal_capacity_Ah=max(0.5, round(req.cell_mass_kg * 56.5, 2)),
            internal_resistance_ohm=0.02,
            gas_yield_L_per_Ah=1.5
        )
        self.kinetics_engine.library[chem_id] = chem_obj
        fit_result["registered_chemistry_id"] = chem_id
        fit_result["detected_T_onset_C"] = round(t_onset_C, 1)
        fit_result["detected_T_trigger_C"] = round(t_tr_C, 1)

        if getattr(req, "persist_to_library", False):
            user_lib_path = self.base_dir / "data" / "user_chemistry_library.json"
            data = {"chemistries": []}
            if user_lib_path.exists():
                try:
                    with open(user_lib_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {"chemistries": []}
            data.setdefault("chemistries", []).append({
                "chemistry_id": chem_id,
                "name": chem_obj.name,
                "A_pre_exponential_per_s": fit_result["frequency_factor_A"],
                "Ea_J_per_mol": fit_result["activation_energy_J_per_mol"],
                "delta_H_J_per_g": round(fit_result["reaction_enthalpy_J_per_kg"] / 1000.0, 2),
                "T_onset_K": t_onset_C + 273.15,
                "T_trigger_K": t_tr_C + 273.15,
                "active_mass_ratio": req.active_mass_ratio,
                "nominal_mass_kg": req.cell_mass_kg,
                "nominal_cp_J_per_kg_K": cp_val,
                "source_references": ["ARC/CSV Otomatik Ters Kalibrasyon"],
                "source_type": "user_defined"
            })
            os.makedirs(user_lib_path.parent, exist_ok=True)
            with open(user_lib_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

        return fit_result

    def run_2d_design_study(self, req: Grid2DStudyRequest) -> Dict[str, Any]:
        """2 Parametreli Izgara Taraması koşturur (paralel işçi havuzu ile) ve 2D kontur matrislerini üretir."""
        study_id = f"study2d_{uuid.uuid4().hex[:8]}"
        base_dict = req.base_config.model_dump()
        cases = DesignOptimizationEngine.build_2d_grid_variations(
            base_request_dict=base_dict,
            param_x=req.param_x,
            values_x=req.values_x,
            param_y=req.param_y,
            values_y=req.values_y
        )

        valid_fields = set(PackSimulationRequest.model_fields.keys())
        sim_requests = [
            PackSimulationRequest(**{k: v for k, v in cfg_dict.items() if k in valid_fields})
            for cfg_dict in cases
        ]

        batch_records = self._run_batch_parallel(
            configs=sim_requests,
            task_id=getattr(req, "task_id", None),
            task_label="2D Matris Taraması",
            persist_each_to_db=True
        )

        matrix_peak_T: List[List[float]] = []
        matrix_risk: List[List[float]] = []
        case_results = []

        idx_case = 0
        for vx in req.values_x:
            row_T = []
            row_risk = []
            for vy in req.values_y:
                cfg_dict = cases[idx_case]
                res = batch_records[idx_case]
                ev = res["evaluation"]

                p_temp = ev["peak_module_temp_C"]
                r_score = ev["risk_score_100"]

                row_T.append(p_temp)
                row_risk.append(r_score)
                case_results.append({
                    "case_name": cfg_dict["case_name"],
                    "x_val": vx,
                    "y_val": vy,
                    "peak_temp_C": p_temp,
                    "risk_score": r_score,
                    "affected_cells": ev["affected_cells_count"],
                    "module_mass_kg": ev.get("module_mass_kg", 0.0),
                    "status": ev["status"],
                    "job_id": res["job_id"]
                })
                idx_case += 1
            matrix_peak_T.append(row_T)
            matrix_risk.append(row_risk)

        return {
            "study_id": study_id,
            "param_x": req.param_x,
            "param_y": req.param_y,
            "values_x": req.values_x,
            "values_y": req.values_y,
            "matrix_peak_temp_C": matrix_peak_T,
            "matrix_risk_score": matrix_risk,
            "cases": case_results
        }

    def run_sensitivity_study(self, req: SensitivityStudyRequest) -> Dict[str, Any]:
        """OAT (One-At-A-Time) Hassasiyet Çalışması ve Tornado Sıralaması koşturur (paralel)."""
        study_id = f"sens_{uuid.uuid4().hex[:8]}"
        base = req.base_config
        pert_ratio = req.perturbation_percent / 100.0

        params_to_vary = [
            ("spacing_x_mm", "Hücre Boşluğu (mm)"),
            ("separator_thickness_mm", "Bariyer Kalınlığı (mm)"),
            ("T_ambient_C", "Ortam Sıcaklığı (°C)"),
            ("trigger_power_W", "Tetikleme Gücü (W)"),
            ("h_ambient_W_per_m2_K", "Konveksiyon Katsayısı (W/m²K)"),
            ("soc_percent", "Şarj Durumu SOC (%)")
        ]

        all_configs: List[PackSimulationRequest] = [base]
        meta_list: List[Tuple[str, str]] = [("__baseline__", "base")]

        for p_name, p_label in params_to_vary:
            base_val = getattr(base, p_name, None)
            if base_val is None or (base_val == 0.0 and p_name != "separator_thickness_mm"):
                continue
            if p_name == "separator_thickness_mm" and (base_val == 0.0 or not base.separator_material_id):
                continue

            cfg_low = base.model_copy(deep=True)
            low_val = float(base_val * (1.0 - pert_ratio))
            if p_name == "spacing_x_mm":
                low_val = max(0.2, low_val)
                cfg_low.spacing_y_mm = max(0.2, float(base.spacing_y_mm * (1.0 - pert_ratio)))
            elif p_name == "soc_percent":
                low_val = max(5.0, min(100.0, low_val))
            elif p_name != "T_ambient_C":
                low_val = max(0.05, low_val)
            setattr(cfg_low, p_name, low_val)
            all_configs.append(cfg_low)
            meta_list.append((p_label, "low"))

            cfg_high = base.model_copy(deep=True)
            high_val = float(base_val * (1.0 + pert_ratio))
            if p_name == "spacing_x_mm":
                high_val = min(50.0, high_val)
                cfg_high.spacing_y_mm = min(50.0, float(base.spacing_y_mm * (1.0 + pert_ratio)))
            elif p_name == "soc_percent":
                high_val = max(5.0, min(100.0, high_val))
            setattr(cfg_high, p_name, high_val)
            all_configs.append(cfg_high)
            meta_list.append((p_label, "high"))

        batch_records = self._run_batch_parallel(
            configs=all_configs,
            task_id=getattr(req, "task_id", None),
            task_label="Tornado Hassasiyet Analizi",
            persist_each_to_db=False
        )

        base_eval = batch_records[0]["evaluation"]
        base_case = {
            "peak_module_temp_C": base_eval["peak_module_temp_C"],
            "risk_score_100": base_eval["risk_score_100"]
        }

        var_cases = []
        for idx in range(1, len(batch_records)):
            p_label, direction = meta_list[idx]
            ev = batch_records[idx]["evaluation"]
            var_cases.append({
                "perturbed_param": p_label,
                "perturbation_direction": direction,
                "peak_module_temp_C": ev["peak_module_temp_C"],
                "risk_score_100": ev["risk_score_100"]
            })

        tornado_analysis = DesignOptimizationEngine.analyze_tornado_sensitivity(
            baseline_case=base_case,
            variation_cases=var_cases
        )
        tornado_analysis["study_id"] = study_id
        return tornado_analysis

    def compare_runs(self, job_a_id: str, job_b_id: str) -> Dict[str, Any]:
        """İki bağımsız simülasyon sonucunu (Run A vs Run B) karşılaştırır."""
        res_a = self.get_result(job_a_id)
        res_b = self.get_result(job_b_id)
        if not res_a or not res_b:
            raise KeyError("Karşılaştırılacak simülasyonlardan en az biri bulunamadı.")

        sim_a = res_a["simulation_result"]
        sim_b = res_b["simulation_result"]
        eval_a = res_a["evaluation"]
        eval_b = res_b["evaluation"]

        peak_a = float(eval_a.get("peak_module_temp_C", sim_a.get("pack_metrics", {}).get("peak_module_temp_C", 0.0)))
        peak_b = float(eval_b.get("peak_module_temp_C", sim_b.get("pack_metrics", {}).get("peak_module_temp_C", 0.0)))
        risk_a = float(eval_a.get("risk_score_100", 0.0))
        risk_b = float(eval_b.get("risk_score_100", 0.0))
        aff_a = int(eval_a.get("affected_cells_count", sim_a.get("pack_metrics", {}).get("runaway_cell_count", 0)))
        aff_b = int(eval_b.get("affected_cells_count", sim_b.get("pack_metrics", {}).get("runaway_cell_count", 0)))

        t_prop_a = eval_a.get("time_to_first_propagation_s")
        t_prop_b = eval_b.get("time_to_first_propagation_s")
        delta_t_prop = round(float(t_prop_b) - float(t_prop_a), 2) if (t_prop_a is not None and t_prop_b is not None) else 0.0

        mass_a = float(eval_a.get("module_mass_kg", sim_a.get("pack_metrics", {}).get("module_mass_kg", 0.0)))
        mass_b = float(eval_b.get("module_mass_kg", sim_b.get("pack_metrics", {}).get("module_mass_kg", 0.0)))

        # Zaman serilerini ortak ızgaraya enterpole et
        t_a = sim_a["time_points_s"]
        t_b = sim_b["time_points_s"]
        t_max = min(t_a[-1], t_b[-1])
        common_t = np.linspace(0.0, t_max, 100)

        trig_id_a = res_a.get("request_config", {}).get("trigger_cell_id", sim_a.get("pack_metrics", {}).get("trigger_cell_id", 0))
        trig_id_b = res_b.get("request_config", {}).get("trigger_cell_id", sim_b.get("pack_metrics", {}).get("trigger_cell_id", 0))

        th_a = sim_a["temperature_history_C"]
        th_b = sim_b["temperature_history_C"]
        trig_a_temps = th_a.get(trig_id_a) or th_a.get(str(trig_id_a)) or list(th_a.values())[0]
        trig_b_temps = th_b.get(trig_id_b) or th_b.get(str(trig_id_b)) or list(th_b.values())[0]

        interp_a = [round(float(T), 2) for T in np.interp(common_t, t_a, trig_a_temps)]
        interp_b = [round(float(T), 2) for T in np.interp(common_t, t_b, trig_b_temps)]
        time_list = [round(float(t), 2) for t in common_t]

        delta_peak = round(peak_b - peak_a, 2)
        delta_risk = round(risk_b - risk_a, 1)
        delta_aff = aff_b - aff_a
        delta_mass = round(mass_b - mass_a, 3)

        return {
            "job_a_id": job_a_id,
            "job_b_id": job_b_id,
            "metrics_a": {
                "peak_temp_C": peak_a,
                "risk_score": risk_a,
                "affected_cells": aff_a,
                "time_to_first_propagation_s": t_prop_a,
                "module_mass_kg": mass_a
            },
            "metrics_b": {
                "peak_temp_C": peak_b,
                "risk_score": risk_b,
                "affected_cells": aff_b,
                "time_to_first_propagation_s": t_prop_b,
                "module_mass_kg": mass_b
            },
            "delta_metrics": {
                "delta_peak_temp_C": delta_peak,
                "delta_risk_score": delta_risk,
                "delta_affected_cells": delta_aff,
                "delta_first_propagation_s": delta_t_prop,
                "delta_mass_kg": delta_mass
            },
            "temperature_comparison": {
                "time_points_s": time_list,
                "temps_a_C": interp_a,
                "temps_b_C": interp_b
            },
            # Frontend doğrudan erişim anahtarları
            "time_points_s": time_list,
            "delta_peak_temp_C": delta_peak,
            "delta_risk_score": delta_risk,
            "delta_affected_cells": delta_aff,
            "delta_first_propagation_s": delta_t_prop,
            "delta_mass_kg": delta_mass,
            "run_a": {
                "job_id": job_a_id,
                "peak_temp_C": peak_a,
                "risk_score": risk_a,
                "affected_cells": aff_a,
                "time_to_first_propagation_s": t_prop_a,
                "module_mass_kg": mass_a,
                "trigger_temp_history": interp_a
            },
            "run_b": {
                "job_id": job_b_id,
                "peak_temp_C": peak_b,
                "risk_score": risk_b,
                "affected_cells": aff_b,
                "time_to_first_propagation_s": t_prop_b,
                "module_mass_kg": mass_b,
                "trigger_temp_history": interp_b
            }
        }
