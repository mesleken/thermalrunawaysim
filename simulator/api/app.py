"""
FastAPI Ana Uygulaması (App)
REST API Endpoint'leri ve Statik Web Dashboard Dağıtımı.
"""

from typing import Dict, Any, Optional
import os
from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from simulator.api.models import (
    PackSimulationRequest, CustomChemistryRequest, CustomMaterialRequest,
    CustomFormatRequest, DesignStudyRequest
)
from simulator.api.services import SimulationService
from simulator.core.kinetics_engine import ArrheniusKineticsEngine

app = FastAPI(
    title="Pil Paketi Termal Kaçak Simülatörü API",
    version="1.0.0",
    description="UL 9540A / UN 38.3 Ön-Tarama ve Termal Kaçak Yayılım Simülasyon Motoru."
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
        "version": "1.0.0",
        "validation_status": "literature_calibrated"
    }

@app.get("/api/chemistry/library")
def get_chemistry_library():
    """Tüm yerleşik (built_in) ve özel (user_defined) kimyaları detaylı parametreleriyle döndürür."""
    # En güncel kütüphaneyi almak için motoru tazeleyelim
    service.kinetics_engine = ArrheniusKineticsEngine()
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
        
    return {"status": "success", "material_id": mat_id}

@app.get("/api/formats/library")
def get_formats_library():
    from simulator.core.pack_geometry import PackGeometryBuilder
    builder = PackGeometryBuilder()
    return builder.CELL_DIMENSIONS

from simulator.api.models import CustomFormatRequest

@app.post("/api/formats/custom")
def add_custom_format(req: CustomFormatRequest):
    import json
    from pathlib import Path
    
    base_dir = Path(__file__).resolve().parent.parent.parent
    user_lib_path = base_dir / "data" / "user_formats_library.json"
    
    data = {"formats": {}}
    if user_lib_path.exists():
        with open(user_lib_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
    fid = req.format_name
    new_fmt = {
        "radius": req.radius_mm / 1000.0,
        "height": req.height_mm / 1000.0,
        "mass": req.mass_kg,
        "casing_thickness": req.casing_thickness_mm / 1000.0,
        "cp": 1050.0, # Default
        "type": "cylindrical",
        "source_type": "user_defined"
    }
    
    data["formats"][fid] = new_fmt
    with open(user_lib_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    return {"status": "success", "format_id": fid}

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
            "cases": study_result["cases"]
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tasarım çalışması hatası: {str(e)}")

@app.get("/api/simulations")
def list_simulations():
    """Önceki simülasyonların özet listesini döndürür."""
    results = []
    for job_id, record in service._results_store.items():
        results.append({
            "job_id": job_id,
            "status": record.get("status"),
            "created_at": record.get("created_at"),
            "risk_score": record.get("evaluation", {}).get("risk_score_100")
        })
    return {"simulations": results}

@app.get("/api/simulations/{job_id}/results")
def get_simulation_results(job_id: str):
    """Belirli bir simülasyonun tam zaman serisi ve değerlendirme sonucunu getirir."""
    record = service.get_result(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"İş ID '{job_id}' bulunamadı.")
    return record

@app.get("/api/simulations/{job_id}/report")
def download_pdf_report(job_id: str):
    """Üretilen mühendislik değerlendirme PDF raporunu indirir."""
    record = service.get_result(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"İş ID '{job_id}' bulunamadı.")
    pdf_path = record.get("pdf_report_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF rapor dosyası bulunamadı.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=record.get("pdf_filename", f"Report_{job_id}.pdf")
    )

@app.get("/")
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h2>Pil Paketi Termal Kaçak Simülatörü API Aktif</h2><p><a href='/docs'>Swagger API Dokümantasyonu</a></p>")
