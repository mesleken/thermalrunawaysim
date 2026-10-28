"""
Kurumsal SQLite Kalıcılık Katmanı (Database Persistence)
Simülasyon sonuçlarını, konfigürasyon özetlerini ve kullanıcı projelerini
data/workbench.db üzerinde WAL (Write-Ahead Logging) modunda sıkıştırarak (zlib) saklar.
"""

from typing import Dict, Any, List, Optional
import os
import sqlite3
import json
import zlib
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "workbench.db")

class DatabaseRepository:
    """Simülasyon ve Proje Yönetimi için SQLite Veritabanı Deposu."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Tabloları ve indeksleri oluşturur."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS simulations (
                    job_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    config_hash TEXT,
                    execution_fingerprint TEXT,
                    status TEXT,
                    n_cells INTEGER,
                    peak_temp_C REAL,
                    affected_cells INTEGER,
                    risk_score REAL,
                    result_blob BLOB,
                    metadata_json TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sim_created ON simulations(created_at DESC);")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    payload_json TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_proj_updated ON projects(updated_at DESC);")

    def save_simulation(self, job_id: str, result_dict: Dict[str, Any], config_dict: Optional[Dict[str, Any]] = None) -> None:
        """Simülasyon kaydını (tam servis kaydı veya ham sonuç sözlüğü) zlib ile sıkıştırıp kaydeder."""
        if "simulation_result" in result_dict and isinstance(result_dict["simulation_result"], dict) and "pack_metrics" in result_dict["simulation_result"]:
            sim_part = result_dict["simulation_result"]
        else:
            sim_part = result_dict

        eval_part = result_dict.get("evaluation") or result_dict.get("propagation_evaluation") or {}
        pack_metrics = sim_part.get("pack_metrics") or result_dict.get("pack_metrics") or {}
        cell_summaries = sim_part.get("cell_summaries") or result_dict.get("cell_summaries") or []

        peak_temp = eval_part.get("peak_module_temp_C")
        if peak_temp is None:
            peak_temp = pack_metrics.get("peak_module_temp_C", 0.0)

        affected = eval_part.get("affected_cells_count")
        if affected is None:
            affected = pack_metrics.get("runaway_cell_count", 0)

        n_cells = eval_part.get("total_cells")
        if n_cells is None:
            n_cells = pack_metrics.get("total_cells", len(cell_summaries))

        cfg_hash = sim_part.get("config_hash") or result_dict.get("config_hash", "")
        fingerprint = sim_part.get("execution_fingerprint") or result_dict.get("execution_fingerprint", "")

        risk_score = eval_part.get("risk_score_100")
        if risk_score is None:
            risk_score = result_dict.get("risk_score_100", 0.0)

        eff_config = config_dict or result_dict.get("request_config") or {}
        meta = {
            "config": eff_config,
            "validation_status": sim_part.get("validation_status", "literature_calibrated"),
            "solver_metadata": sim_part.get("solver_metadata", {})
        }

        raw_bytes = json.dumps(result_dict).encode("utf-8")
        compressed_blob = zlib.compress(raw_bytes, level=6)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO simulations 
                (job_id, config_hash, execution_fingerprint, status, n_cells, peak_temp_C, affected_cells, risk_score, result_blob, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                cfg_hash,
                fingerprint,
                result_dict.get("status", "COMPLETED"),
                int(n_cells),
                float(peak_temp),
                int(affected),
                float(risk_score),
                compressed_blob,
                json.dumps(meta)
            ))

    def get_simulation(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Sıkıştırılmış simülasyon sonucunu çözer ve döner."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT result_blob FROM simulations WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row or not row["result_blob"]:
                return None
            try:
                decompressed = zlib.decompress(row["result_blob"])
                return json.loads(decompressed.decode("utf-8"))
            except Exception:
                return None

    def list_simulations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Kayıtlı simülasyonların özet listesini döner."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT job_id, created_at, status, n_cells, peak_temp_C, affected_cells, risk_score, metadata_json
                FROM simulations
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                meta = {}
                if r["metadata_json"]:
                    try:
                        meta = json.loads(r["metadata_json"])
                    except Exception:
                        pass
                n_cells_val = int(r["n_cells"] or 0)
                peak_t_val = float(r["peak_temp_C"] or 0.0)
                results.append({
                    "job_id": r["job_id"],
                    "created_at": r["created_at"],
                    "status": r["status"],
                    "n_cells": n_cells_val,
                    "cell_count": n_cells_val,
                    "peak_temp_C": peak_t_val,
                    "max_temperature_C": peak_t_val,
                    "affected_cells": int(r["affected_cells"] or 0),
                    "risk_score": float(r["risk_score"] or 0.0),
                    "config": meta.get("config", {})
                })
            return results

    def delete_simulation(self, job_id: str) -> bool:
        """Simülasyon kaydını siler."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM simulations WHERE job_id = ?", (job_id,))
            return cursor.rowcount > 0

    def save_project(self, project_id: str, name: str, description: str, payload: Dict[str, Any]) -> None:
        """Kullanıcının batarya modülü tasarım projesini kaydeder."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO projects (project_id, name, description, updated_at, payload_json)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (project_id, name, description, json.dumps(payload)))

    def list_projects(self) -> List[Dict[str, Any]]:
        """Kayıtlı projeleri konfigürasyonlarıyla birlikte listeler."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT project_id, name, description, updated_at, payload_json FROM projects ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r["payload_json"]) if r["payload_json"] else {}
                except Exception:
                    payload = {}
                out.append({
                    "project_id": r["project_id"],
                    "name": r["name"],
                    "description": r["description"],
                    "updated_at": r["updated_at"],
                    "created_at": r["updated_at"],
                    "payload": payload,
                    "config_payload": payload
                })
            return out

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Projeyi yükler."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT project_id, name, description, updated_at, payload_json FROM projects WHERE project_id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
            res["payload"] = payload
            res["config_payload"] = payload
            res["created_at"] = res.get("updated_at")
            del res["payload_json"]
            return res

    def delete_project(self, project_id: str) -> bool:
        """Projeyi siler."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            return cursor.rowcount > 0

# Tekil örnek ve Takma ad
WorkbenchDatabaseRepository = DatabaseRepository
db_repo = DatabaseRepository()
