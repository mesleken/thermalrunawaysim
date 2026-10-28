"""
FastAPI Ana Uygulaması (App)
REST API Endpoint'leri ve Statik Web Dashboard Dağıtımı.
"""

from typing import Dict, Any, Optional
import os
import asyncio
from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from simulator.api.models import (
    PackSimulationRequest, CustomChemistryRequest, CustomMaterialRequest,
    CustomFormatRequest, DesignStudyRequest, ValidationCompareRequest, MonteCarloUQRequest,
    AutoCalibrateRequest, Grid2DStudyRequest, SensitivityStudyRequest, ProjectSaveRequest
)
from simulator.api.services import SimulationService
from simulator.core.kinetics_engine import ArrheniusKineticsEngine
from simulator.core.pack_geometry import PackGeometryBuilder

app = FastAPI(
    title="Pil Paketi Termal Kaçak Simülatörü API",
    version="2.0.0",
    description="UL 9540A / UN 38.3 / GB 38031 Ön-Tarama ve Termal Kaçak Yayılım CAE Simülasyon Motoru V2.0."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = SimulationService()

# Statik web dizini
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "validation_status": "literature_calibrated"
    }

@app.get("/api/chemistry/library")
def get_chemistry_library():
    """Tüm yerleşik (built_in) ve özel (user_defined) kimyaları detaylı parametreleriyle döndürür."""
    # En güncel kütüphaneyi almak için motoru tazeleyelim (oturum içi kalibre kimyaları koruyarak)
    in_mem_calibrated = {
        k: v for k, v in service.kinetics_engine.library.items() if k.startswith("calibrated_")
    }
    service.kinetics_engine = ArrheniusKineticsEngine()
    service.kinetics_engine.library.update(in_mem_calibrated)
    chemistries = []
    for cid, chem in service.kinetics_engine.library.items():
        chemistries.append({
            "chemistry_id": cid,
            "name": chem.name,
            "T_onset_K": chem.T_onset_K,
            "T_onset_C": round(chem.T_onset_K - 273.15, 1),
            "T_trigger_K": chem.T_trigger_K,
            "T_trigger_C": round(chem.T_trigger_K - 273.15, 1),
            "A_pre_exponential_per_s": chem.A,
            "Ea_J_per_mol": chem.Ea,
            "Ea_kJ_per_mol": round(chem.Ea / 1000.0, 1),
            "delta_H_J_per_kg": chem.delta_H,
            "delta_H_J_per_g": round(chem.delta_H / 1000.0, 1),
            "active_mass_ratio": round(getattr(chem, "active_mass_ratio", 0.58), 3),
            "nominal_cp_J_per_kg_K": getattr(chem, "nominal_cp", 1050.0),
            "nominal_mass_kg": getattr(chem, "nominal_mass", 0.046),
            "nominal_voltage_V": getattr(chem, "nominal_voltage", 3.7),
            "nominal_capacity_Ah": getattr(chem, "nominal_capacity_Ah", 2.6),
            "gas_yield_L_per_Ah": getattr(chem, "gas_yield_L_per_Ah", 1.5),
            "sub_reactions": [sr.to_dict() for sr in getattr(chem, "sub_reactions", [])],
            "source_type": chem.source_type,
            "source_references": getattr(chem, "source_references", [])
        })
    return {"chemistries": chemistries}

from simulator.api.models import CustomChemistryRequest

@app.post("/api/chemistry/custom")
def add_custom_chemistry(req: CustomChemistryRequest):
    import uuid
    import json
    from pathlib import Path
    
    base_dir = Path(__file__).resolve().parent.parent.parent
    user_lib_path = base_dir / "data" / "user_chemistry_library.json"
    
    data = {"chemistries": []}
    if user_lib_path.exists():
        with open(user_lib_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
    chem_id = f"user_def_{uuid.uuid4().hex[:6]}"
    
    new_chem = {
        "chemistry_id": chem_id,
        "name": req.name,
        "A_pre_exponential_per_s": req.A_pre_exponential_per_s,
        "Ea_J_per_mol": req.Ea_J_per_mol,
        "delta_H_J_per_g": req.delta_H_J_per_g,
        "T_onset_K": req.T_onset_C + 273.15,
        "T_trigger_K": req.T_trigger_C + 273.15,
        "active_mass_ratio": req.active_mass_ratio,
        "source_references": req.source_references,
        "source_type": "user_defined"
    }
    
    data["chemistries"].append(new_chem)
    with open(user_lib_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    # Motoru yenile
    service.kinetics_engine = ArrheniusKineticsEngine()
    return {"status": "success", "chemistry_id": chem_id, "message": "Özel kimya başarıyla kaydedildi."}

@app.get("/api/materials/library")
def get_materials_library():
    """Tüm yerleşik ve özel malzemeleri döndürür."""
    # service.geometry_builder.materials_lib artık iki json'u da okuyor
    # Güncel versiyonunu alalım
    from simulator.core.pack_geometry import PackGeometryBuilder
    builder = PackGeometryBuilder()
    return builder.materials_lib

@app.post("/api/materials/custom")
def add_custom_material(req: CustomMaterialRequest):
    import uuid
    import json
    from pathlib import Path
    
    base_dir = Path(__file__).resolve().parent.parent.parent
    user_lib_path = base_dir / "data" / "user_materials_library.json"
    
    data = {"materials": []}
    if user_lib_path.exists():
        with open(user_lib_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
    mat_id = f"mat_{uuid.uuid4().hex[:6]}"
    
    new_mat = {
        "material_id": mat_id,
        "name": req.name,
        "density_kg_per_m3": req.density_kg_per_m3,
        "cp_J_per_kg_K": req.cp_J_per_kg_K,
        "k_thermal_W_per_m_K": req.k_thermal_W_per_m_K,
        "source_type": "user_defined"
    }
    
    data["materials"].append(new_mat)
    with open(user_lib_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    service.geometry_builder = PackGeometryBuilder()
    return {"status": "success", "material_id": mat_id}

@app.get("/api/formats/library")
def get_formats_library():
    builder = PackGeometryBuilder()
    service.geometry_builder = builder
    return builder.CELL_DIMENSIONS

from simulator.api.models import CustomFormatRequest

@app.post("/api/formats/custom")
def add_custom_format(req: CustomFormatRequest):
    base_dir = Path(__file__).resolve().parent.parent.parent
    user_lib_path = base_dir / "data" / "user_formats_library.json"

    data = {"formats": {}}
    if user_lib_path.exists():
        with open(user_lib_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    fid = req.format_name.strip()
    ftype = (req.format_type or "cylindrical").lower().strip()
    if ftype not in ("cylindrical", "prismatic", "pouch"):
        ftype = "cylindrical"

    if ftype in ("prismatic", "pouch"):
        w_mm = req.width_mm if (req.width_mm is not None and req.width_mm > 0) else 148.0
        t_mm = req.thickness_mm if (req.thickness_mm is not None and req.thickness_mm > 0) else (12.0 if ftype == "pouch" else 26.0)
        new_fmt = {
            "width": float(w_mm) / 1000.0,
            "thickness": float(t_mm) / 1000.0,
            "height": float(req.height_mm) / 1000.0,
            "mass": float(req.mass_kg),
            "casing_thickness": float(req.casing_thickness_mm) / 1000.0,
            "cp": float(req.cp_J_per_kg_K),
            "type": ftype,
            "source_type": "user_defined"
        }
    else:
        r_mm = req.radius_mm if (req.radius_mm is not None and req.radius_mm > 0) else 9.0
        new_fmt = {
            "radius": float(r_mm) / 1000.0,
            "height": float(req.height_mm) / 1000.0,
            "mass": float(req.mass_kg),
            "casing_thickness": float(req.casing_thickness_mm) / 1000.0,
            "cp": float(req.cp_J_per_kg_K),
            "type": "cylindrical",
            "source_type": "user_defined"
        }

    data.setdefault("formats", {})[fid] = new_fmt
    with open(user_lib_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    service.geometry_builder = PackGeometryBuilder()
    return {"status": "success", "format_id": fid, "format": new_fmt}

@app.delete("/api/chemistry/custom/{chemistry_id}")
def delete_custom_chemistry(chemistry_id: str):
    import json
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent.parent
    user_lib_path = base_dir / "data" / "user_chemistry_library.json"
    if not user_lib_path.exists():
        raise HTTPException(status_code=404, detail="Özel kimya kütüphanesi bulunamadı.")
    with open(user_lib_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    initial_len = len(data.get("chemistries", []))
    data["chemistries"] = [c for c in data.get("chemistries", []) if c.get("chemistry_id") != chemistry_id]
    if len(data["chemistries"]) == initial_len:
        raise HTTPException(status_code=404, detail=f"'{chemistry_id}' bulunamadı.")
    with open(user_lib_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    service.kinetics_engine = ArrheniusKineticsEngine()
    return {"status": "success", "message": f"{chemistry_id} silindi."}

@app.delete("/api/materials/custom/{material_id}")
def delete_custom_material(material_id: str):
    import json
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent.parent
    user_lib_path = base_dir / "data" / "user_materials_library.json"
    if not user_lib_path.exists():
        raise HTTPException(status_code=404, detail="Özel malzeme kütüphanesi bulunamadı.")
    with open(user_lib_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    initial_len = len(data.get("materials", []))
    data["materials"] = [m for m in data.get("materials", []) if m.get("material_id") != material_id]
    if len(data["materials"]) == initial_len:
        raise HTTPException(status_code=404, detail=f"'{material_id}' bulunamadı.")
    with open(user_lib_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return {"status": "success", "message": f"{material_id} silindi."}

@app.delete("/api/formats/custom/{format_id}")
def delete_custom_format(format_id: str):
    import json
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent.parent
    user_lib_path = base_dir / "data" / "user_formats_library.json"
    if not user_lib_path.exists():
        raise HTTPException(status_code=404, detail="Özel format kütüphanesi bulunamadı.")
    with open(user_lib_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if format_id not in data.get("formats", {}):
        raise HTTPException(status_code=404, detail=f"'{format_id}' bulunamadı.")
    del data["formats"][format_id]
    with open(user_lib_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return {"status": "success", "message": f"{format_id} silindi."}

@app.get("/api/library/summary")
def get_library_summary():
    """Tüm yerleşik ve özel kütüphane bileşenlerini toplu özet olarak döner."""
    chem_lib = get_chemistry_library()["chemistries"]
    from simulator.core.pack_geometry import PackGeometryBuilder
    builder = PackGeometryBuilder()
    return {
        "chemistries": chem_lib,
        "materials": builder.materials_lib,
        "formats": builder.CELL_DIMENSIONS
    }

@app.post("/api/simulations/run")
def run_simulation(request: PackSimulationRequest):
    """Yeni bir simülasyon çalıştırır, değişmez (immutable) sonuçları üretir ve kaydeder."""
    try:
        record = service.run_simulation(request)
        return {
            "success": True,
            "job_id": record["job_id"],
            "status": record["status"],
            "created_at": record["created_at"],
            "pack_bounds": record["pack_bounds"],
            "evaluation": record["evaluation"],
            "config_hash": record["simulation_result"]["config_hash"],
            "execution_fingerprint": record["simulation_result"]["execution_fingerprint"],
            "pdf_filename": record["pdf_filename"]
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simülasyon hatası: {str(e)}")

@app.post("/api/simulations/design-study")
def run_design_study(request: DesignStudyRequest):
    """Çoklu parametre taraması (Design Study / Spacing & Barrier Sweep) gerçekleştirir."""
    try:
        study_result = service.run_design_study(request)
        return {
            "success": True,
            "study_id": study_result["study_id"],
            "sweep_type": study_result["sweep_type"],
            "recommended_case_index": study_result["recommended_case_index"],
            "recommended_reason": study_result["recommended_reason"],
            "cases": study_result["cases"],
            "pareto_front_indices": study_result.get("pareto_front_indices", []),
            "knee_point_index": study_result.get("knee_point_index"),
            "baseline_mass_kg": study_result.get("baseline_mass_kg", 0.0),
            "pareto_summary": study_result.get("pareto_summary", "")
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tasarım çalışması hatası: {str(e)}")

@app.post("/api/validation/compare")
def compare_validation(request: ValidationCompareRequest):
    """Aşama 2: Deneysel CSV sensör logunu tamamlanmış bir simülasyonla karşılaştırır."""
    try:
        return service.compare_simulation_with_sensor_log(
            job_id=request.job_id,
            csv_content=request.csv_content,
            cell_id=request.cell_id
        )
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validasyon hatası: {str(e)}")

@app.post("/api/simulations/monte-carlo-uq")
def run_monte_carlo(request: MonteCarloUQRequest):
    """Aşama 2: Belirsizlik Nicelendirmesi (Monte Carlo UQ: P10, P50, P90) simülasyonu koşturur."""
    try:
        return service.run_monte_carlo_uq(request)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Monte Carlo UQ hatası: {str(e)}")

@app.post("/api/validation/auto-calibrate")
def auto_calibrate_kinetics(request: AutoCalibrateRequest):
    """ARC/F848 test CSV sıcaklık eğrisinden Arrhenius parametrelerini (A, Ea, delta_H) ters optimizasyonla türetir."""
    try:
        return service.run_auto_calibration(request)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Otomatik kalibrasyon hatası: {str(e)}")

@app.post("/api/simulations/design-study-2d")
def run_design_study_2d(request: Grid2DStudyRequest):
    """2 Parametreli Izgara Taraması koşturur ve 2D kontur matrisini döner."""
    try:
        return service.run_2d_design_study(request)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"2D Tasarım çalışması hatası: {str(e)}")

@app.post("/api/simulations/sensitivity")
def run_sensitivity(request: SensitivityStudyRequest):
    """OAT (One-At-A-Time) Hassasiyet ve Tornado Sıralaması analizi koşturur."""
    try:
        return service.run_sensitivity_study(request)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hassasiyet analizi hatası: {str(e)}")

@app.get("/api/simulations/compare")
def compare_simulations(job_a: str, job_b: str):
    """İki simülasyonun (Run A vs Run B) sıcaklık, yayılım ve kütle metriklerini karşılaştırır."""
    try:
        return service.compare_runs(job_a, job_b)
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Karşılaştırma hatası: {str(e)}")

@app.get("/api/tasks/{task_id}")
def get_task_progress(task_id: str):
    """Toplu tarama / Monte Carlo görevinin anlık ilerleme durumunu döndürür."""
    status = service.get_task_status(task_id)
    if not status:
        return {
            "task_id": task_id,
            "status": "PENDING",
            "completed": 0,
            "total": 1,
            "progress_percent": 0.0,
            "message": "Görev kuyrukta bekleniyor..."
        }
    return status


@app.get("/api/tasks/{task_id}/stream")
async def stream_task_progress(task_id: str):
    """Server-Sent Events (SSE) ile istemciye canlı ilerleme yüzdesi akışı sağlar."""
    async def event_generator():
        last_sent = None
        wait_ticks = 0
        while wait_ticks < 600:  # Max ~120 saniye zaman aşımı
            status = service.get_task_status(task_id)
            if status is None:
                payload = {
                    "task_id": task_id,
                    "status": "PENDING",
                    "completed": 0,
                    "total": 1,
                    "progress_percent": 0.0,
                    "message": "Paralel işçi havuzu hazırlanıyor..."
                }
            else:
                payload = status

            serialized = json.dumps(payload, ensure_ascii=False)
            if serialized != last_sent:
                yield f"data: {serialized}\n\n"
                last_sent = serialized

            if status and status.get("status") in ("COMPLETED", "FAILED"):
                break

            wait_ticks += 1
            await asyncio.sleep(0.2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/presets")
def get_industrial_presets():
    """Endüstriyel OEM, ESS ve laboratuvar test ön-ayarlarını (6 Standart Preset) döndürür."""
    return {
        "presets": [
            {
                "preset_id": "tesla_model3_cylindrical",
                "name": "Tesla Model 3 / Y (21700 NMC811 Silindirik Modül)",
                "description": "3x8 dizilim, 21700 yüksek enerjili NMC811 hücreler, 2.0 mm boşluk, taban sıvı soğutma, mika separatör.",
                "config": {
                    "rows": 3,
                    "cols": 8,
                    "cell_format": "21700",
                    "chemistry_id": "NMC811_high_energy_v1",
                    "spacing_x_mm": 2.0,
                    "spacing_y_mm": 2.0,
                    "separator_material_id": "mica_sheet",
                    "separator_thickness_mm": 0.5,
                    "gap_material_id": "air_gap",
                    "active_cooling_enabled": True,
                    "h_cooling_plate_W_per_m2_K": 1000.0,
                    "trigger_cell_id": 0,
                    "trigger_method": "thermal_pulse",
                    "trigger_power_W": 2500.0,
                    "trigger_duration_s": 3.0,
                    "soc_percent": 100.0,
                    "advanced_physics_enabled": True,
                    "nodal_model": "core_shell",
                    "kinetics_model": "multi_reaction",
                    "ejecta_mass_loss_ratio": 0.15
                }
            },
            {
                "preset_id": "byd_blade_prismatic_lfp",
                "name": "BYD Blade / LFP Prizmatik Güvenlik Paketi",
                "description": "1x6 prizmatik LFP hücre dizilimi, çivi batması (ISC) testi, aerojel yalıtım ve yüksek yayılım direnci.",
                "config": {
                    "rows": 1,
                    "cols": 6,
                    "cell_format": "Prismatic_50Ah",
                    "chemistry_id": "LFP_generic_v1",
                    "spacing_x_mm": 1.5,
                    "spacing_y_mm": 1.5,
                    "separator_material_id": "aerogel_insulation",
                    "separator_thickness_mm": 1.0,
                    "gap_material_id": "air_gap",
                    "active_cooling_enabled": True,
                    "h_cooling_plate_W_per_m2_K": 600.0,
                    "trigger_cell_id": 0,
                    "trigger_method": "nail_penetration_isc",
                    "isc_resistance_ohm": 0.015,
                    "soc_percent": 100.0,
                    "advanced_physics_enabled": True,
                    "nodal_model": "core_shell",
                    "kinetics_model": "single_step",
                    "ejecta_mass_loss_ratio": 0.05
                }
            },
            {
                "preset_id": "ctc_4680_structural_pack",
                "name": "4680 Yapısal Batarya Paketi (Cell-to-Chassis CTC)",
                "description": "3x4 büyük çaplı 4680 NCA silindirik hücreler, heksagonal dizilim, epoksi potting dolgu ve taban soğutma.",
                "config": {
                    "rows": 3,
                    "cols": 4,
                    "cell_format": "4680",
                    "chemistry_id": "NCA_high_power_v1",
                    "spacing_x_mm": 2.5,
                    "spacing_y_mm": 2.5,
                    "staggered": True,
                    "separator_material_id": "ceramic_fiber_paper",
                    "separator_thickness_mm": 1.0,
                    "gap_material_id": "epoxy_potting",
                    "active_cooling_enabled": True,
                    "h_cooling_plate_W_per_m2_K": 1200.0,
                    "trigger_cell_id": 0,
                    "trigger_method": "thermal_pulse",
                    "trigger_power_W": 4500.0,
                    "trigger_duration_s": 4.0,
                    "soc_percent": 100.0,
                    "advanced_physics_enabled": True,
                    "nodal_model": "core_shell",
                    "kinetics_model": "multi_reaction",
                    "ejecta_mass_loss_ratio": 0.18
                }
            },
            {
                "preset_id": "vw_meb_pouch_nmc",
                "name": "VW MEB Platformu (Pouch 60Ah NMC Kese Modül)",
                "description": "2x4 Pouch 60Ah (kese) hücre formatı, UL 9540A film ısıtıcı testi ve 1.2 mm aerojel mat separatör.",
                "config": {
                    "rows": 2,
                    "cols": 4,
                    "cell_format": "Pouch_60Ah",
                    "chemistry_id": "NMC_generic_v1",
                    "spacing_x_mm": 2.5,
                    "spacing_y_mm": 2.0,
                    "separator_material_id": "aerogel_insulation",
                    "separator_thickness_mm": 1.2,
                    "gap_material_id": "air_gap",
                    "active_cooling_enabled": True,
                    "h_cooling_plate_W_per_m2_K": 800.0,
                    "trigger_cell_id": 0,
                    "trigger_method": "external_heater",
                    "trigger_power_W": 2200.0,
                    "trigger_duration_s": 12.0,
                    "soc_percent": 100.0,
                    "advanced_physics_enabled": True,
                    "nodal_model": "core_shell",
                    "kinetics_model": "multi_reaction",
                    "ejecta_mass_loss_ratio": 0.12
                }
            },
            {
                "preset_id": "ess_naion_pcm_rack",
                "name": "Şebeke Depolama (ESS) Sodyum-İyon PCM Tamponlu Raf",
                "description": "3x3 modül, Na-Ion katmanlı katot kimyası, parafin PCM matı ile 52°C gizli ısı termal tamponu.",
                "config": {
                    "rows": 3,
                    "cols": 3,
                    "cell_format": "21700",
                    "chemistry_id": "NaIon_layered_v1",
                    "spacing_x_mm": 3.0,
                    "spacing_y_mm": 3.0,
                    "separator_material_id": "paraffin_pcm_pad",
                    "separator_thickness_mm": 1.5,
                    "gap_material_id": "air_gap",
                    "active_cooling_enabled": False,
                    "trigger_cell_id": 0,
                    "trigger_method": "thermal_pulse",
                    "trigger_power_W": 2000.0,
                    "trigger_duration_s": 4.0,
                    "soc_percent": 100.0,
                    "advanced_physics_enabled": True,
                    "nodal_model": "core_shell",
                    "kinetics_model": "single_step",
                    "ejecta_mass_loss_ratio": 0.08
                }
            },
            {
                "preset_id": "single_cell_arc_un383",
                "name": "Tek Hücre ARC & UN 38.3 (%30 SOC Fırın Testi)",
                "description": "1x1 tekil 18650 NMC hücre, %30 nakliye şarj durumunda (SOC) 5°C/dk UN 38.3 termal fırın rampa testi.",
                "config": {
                    "rows": 1,
                    "cols": 1,
                    "cell_format": "18650",
                    "chemistry_id": "NMC_generic_v1",
                    "spacing_x_mm": 2.0,
                    "spacing_y_mm": 2.0,
                    "separator_material_id": None,
                    "separator_thickness_mm": 0.0,
                    "gap_material_id": "air_gap",
                    "active_cooling_enabled": False,
                    "trigger_cell_id": 0,
                    "trigger_method": "oven_ramp",
                    "oven_target_temp_C": 165.0,
                    "oven_ramp_C_per_min": 5.0,
                    "soc_percent": 30.0,
                    "simulation_time_s": 180.0,
                    "advanced_physics_enabled": True,
                    "nodal_model": "core_shell",
                    "kinetics_model": "multi_reaction",
                    "ejecta_mass_loss_ratio": 0.05
                }
            }
        ]
    }

# ================= Proje Yönetimi Endpoint'leri =================

@app.get("/api/projects")
def list_projects():
    """SQLite veritabanındaki kayıtlı projeleri listeler."""
    return {"projects": service.db.list_projects()}

@app.post("/api/projects")
def save_project(req: ProjectSaveRequest):
    """Proje tasarımını SQLite veritabanına kaydeder."""
    import uuid
    p_id = req.project_id or f"proj_{uuid.uuid4().hex[:8]}"
    service.db.save_project(p_id, req.name, req.description or "", req.payload)
    return {"status": "success", "project_id": p_id, "message": "Proje başarıyla kaydedildi."}

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    """Kayıtlı projeyi SQLite'tan yükler."""
    proj = service.db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")
    return proj

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    """Projeyi siler."""
    deleted = service.db.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Silinecek proje bulunamadı.")
    return {"status": "success", "message": "Proje silindi."}

@app.get("/api/simulations")
def list_simulations():
    """Kayıtlı simülasyonların özet listesini döndürür."""
    # SQLite'tan listele
    return {"simulations": service.db.list_simulations(limit=50)}

@app.get("/api/simulations/{job_id}/results")
def get_simulation_results(job_id: str):
    """Belirli bir simülasyonun tam zaman serisi ve değerlendirme sonucunu getirir."""
    record = service.get_result(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"İş ID '{job_id}' bulunamadı.")
    return record

@app.get("/api/simulations/{job_id}/report")
def download_pdf_report(job_id: str):
    """İsteğe bağlı (lazy on-demand) PDF raporunu oluşturur veya önbellekten döner."""
    try:
        pdf_path = service.get_or_create_pdf_report(job_id)
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail="PDF rapor dosyası oluşturulamadı.")
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"Report_{job_id}.pdf"
        )
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF rapor hatası: {str(e)}")

@app.get("/api/simulations/{job_id}/audit-certificate")
def get_audit_certificate(job_id: str):
    """Aşama 4: Değişmez Kriptografik Denetim ve Doğrulama Sertifikası (Audit-Proof Certificate) döner."""
    try:
        return service.get_audit_certificate(job_id)
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sertifika üretimi hatası: {str(e)}")

@app.get("/api/simulations/{job_id}/export")
def export_simulation_data(job_id: str, format: str = "csv"):
    """
    Aşama 4: Simülasyon serilerini CSV, sıkıştırılmış ikili NPZ (.npz) veya JSON olarak dışa aktarır.
    """
    try:
        content, media_type, filename = service.export_simulation_data(job_id, fmt=format)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dışa aktarma hatası: {str(e)}")

@app.get("/")
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h2>Pil Paketi Termal Kaçak Simülatörü API Aktif</h2><p><a href='/docs'>Swagger API Dokümantasyonu</a></p>")
