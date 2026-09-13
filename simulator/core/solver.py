"""
Termal Kaçak Çözücü Motoru (ThermalRunawaySolver)
scipy.integrate.solve_ivp ile adaptif, sertlik (stiff) algılamalı diferansiyel denklem çözümü.
Faz 0.5 Sözleşme 2 ve Sözleşme 3'e (Config Hash & Execution Fingerprint) tam uyumludur.
"""

from typing import Dict, Any, List, Optional, Tuple
import sys
import hashlib
import json
import time
import numpy as np
from scipy.integrate import solve_ivp

from simulator.core.constants import (
    SOLVER_DEFAULT_RTOL,
    SOLVER_DEFAULT_ATOL,
    SOLVER_DEFAULT_MAX_STEP,
    SOLVER_DEFAULT_FIRST_STEP,
    SOLVER_METHOD,
    CellState,
    celsius_to_kelvin,
    kelvin_to_celsius
)
from simulator.core.cell_model import CellModel
from simulator.core.thermal_network import ThermalNetworkAssembler

class SimulationResult:
    """Simülasyon Çıktı Nesnesi (Faz 0.5 Sözleşme 3 uyarınca değiştirilemez/immutable)."""
    def __init__(
        self,
        job_id: str,
        config_hash: str,
        execution_fingerprint: str,
        time_points_s: List[float],
        temperature_history_C: Dict[int, List[float]],
        alpha_history: Dict[int, List[float]],
        cell_summaries: List[Dict[str, Any]],
        pack_metrics: Dict[str, Any],
        validation_status: str = "literature_calibrated",
        solver_metadata: Optional[Dict[str, Any]] = None
    ):
        self.job_id = job_id
        self.config_hash = config_hash
        self.execution_fingerprint = execution_fingerprint
        self.time_points_s = time_points_s
        self.temperature_history_C = temperature_history_C
        self.alpha_history = alpha_history
        self.cell_summaries = cell_summaries
        self.pack_metrics = pack_metrics
        self.validation_status = validation_status
        self.solver_metadata = solver_metadata or {}
        self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "config_hash": self.config_hash,
            "execution_fingerprint": self.execution_fingerprint,
            "validation_status": self.validation_status,
            "created_at": self.created_at,
            "time_points_s": self.time_points_s,
            "temperature_history_C": self.temperature_history_C,
            "alpha_history": self.alpha_history,
            "cell_summaries": self.cell_summaries,
            "pack_metrics": self.pack_metrics,
            "solver_metadata": self.solver_metadata
        }


class ThermalRunawaySolver:
    """SciPy tabanlı sayısal simülasyon orkestratörü."""

    def __init__(self, assembler: ThermalNetworkAssembler):
        self.assembler = assembler
        self.cells = assembler.cells
        self.n_cells = len(self.cells)

    @staticmethod
    def generate_config_hash(config_dict: Dict[str, Any]) -> str:
        """Deterministik SHA-256 Configuration Hash (Sözleşme 3)."""
        clean_json = json.dumps(config_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(clean_json.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_execution_fingerprint(library_version: str = "1.0.0") -> str:
        """Sözleşme 3 gereği solver ve kütüphane versiyon parmak izi."""
        py_ver = f"py{sys.version_info.major}{sys.version_info.minor}"
        raw = f"scipy_{solve_ivp.__module__}_lib_{library_version}_{py_ver}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def solve(
        self,
        job_id: str,
        t_span: Tuple[float, float] = (0.0, 120.0),
        trigger_cell_id: int = 0,
        trigger_method: str = "thermal_pulse", # "thermal_pulse" veya "instant_onset"
        trigger_power_W: float = 1200.0,
        trigger_duration_s: float = 3.0,
        trigger_initial_temp_C: Optional[float] = None,
        num_output_points: int = 300,
        rtol: float = SOLVER_DEFAULT_RTOL,
        atol: float = SOLVER_DEFAULT_ATOL,
        max_step: float = SOLVER_DEFAULT_MAX_STEP,
        method: str = SOLVER_METHOD,
        config_dict: Optional[Dict[str, Any]] = None
    ) -> SimulationResult:
        """
        Simülasyonu çalıştırır ve zamana bağlı çözüm matrisini üretir.
        """
        start_wall_time = time.perf_counter()

        # Validate trigger_cell_id
        if trigger_cell_id < 0 or trigger_cell_id >= self.n_cells:
            raise ValueError(
                f"trigger_cell_id={trigger_cell_id} geçersiz. "
                f"Geçerli aralık: 0 - {self.n_cells - 1}"
            )

        N = self.n_cells

        # Başlangıç koşulları vektörü: [T_0, ..., T_{N-1}, alpha_0, ..., alpha_{N-1}]
        y0_temp = np.array([c.temperature_K for c in self.cells], dtype=np.float64)
        y0_alpha = np.array([c.alpha for c in self.cells], dtype=np.float64)

        # Eğer anlık başlangıç sıcaklığı (instant_onset) istenmişse:
        if trigger_method == "instant_onset" and trigger_initial_temp_C is not None:
            y0_temp[trigger_cell_id] = celsius_to_kelvin(trigger_initial_temp_C)
            applied_trigger_power = 0.0
        else:
            applied_trigger_power = trigger_power_W

        y0 = np.concatenate([y0_temp, y0_alpha])

        # Zaman ızgarası (çıktı için eşit aralıklı noktalar)
        t_eval = np.linspace(t_span[0], t_span[1], num_output_points)

        # ODE sağ taraf fonksiyonu
        def rhs(t, y):
            return self.assembler.compute_derivatives(
                t=t,
                state_vector=y,
                trigger_cell_id=trigger_cell_id,
                trigger_power_W=applied_trigger_power,
                trigger_duration_s=trigger_duration_s
            )

        # Güvenlik Kesintisi (Termination Event): Herhangi bir hücre 1500°C'yi (1773.15 K) aşarsa
        # çözücüyü (solver) sonsuz adım küçültme (step shrinking) kilitlenmesinden korumak için durdur.
        def max_temp_event(t, y):
            max_T = np.max(y[:N])
            return 1773.15 - max_T
        max_temp_event.terminal = True
        max_temp_event.direction = -1

        # solve_ivp çağrısı (LSODA / Radau sertlik algılamalı)
        sol = solve_ivp(
            fun=rhs,
            t_span=t_span,
            y0=y0,
            t_eval=t_eval,
            method=method,
            events=[max_temp_event],
            rtol=rtol,
            atol=atol,
            max_step=max_step,
            first_step=SOLVER_DEFAULT_FIRST_STEP
        )

        solve_duration_s = time.perf_counter() - start_wall_time

        if not sol.success:
            raise RuntimeError(f"Sayısal çözücü yakınsamadı: {sol.message}")

        # Çözüm verilerini ayrıştır
        time_points = [round(float(t), 4) for t in sol.t]
        temps_matrix = sol.y[:N, :]    # Şekil: (N, n_steps), Kelvin
        alphas_matrix = sol.y[N:2*N, :] # Şekil: (N, n_steps)

        # Sıcaklık geçmişini °C olarak sakla (Sözleşme 1 & 3: kullanıcı sunumu)
        temp_history_C: Dict[int, List[float]] = {}
        alpha_history: Dict[int, List[float]] = {}

        for i in range(N):
            temp_history_C[i] = [round(kelvin_to_celsius(float(T_k)), 2) for T_k in temps_matrix[i, :]]
            alpha_history[i] = [round(float(a), 4) for a in alphas_matrix[i, :]]

        # Hücre durumlarını ve olay zamanlarını tespit et
        cell_summaries: List[Dict[str, Any]] = []
        for i in range(N):
            cell = self.cells[i]
            chem = self.assembler.cell_chemistries[i]
            T_array_K = temps_matrix[i, :]
            alpha_array = alphas_matrix[i, :]

            # Max sıcaklık
            max_T_K = float(np.max(T_array_K))
            max_T_C = kelvin_to_celsius(max_T_K)
            cell.max_temperature_K = max_T_K

            # Onset zamanı (ilk T >= T_onset)
            onset_indices = np.where(T_array_K >= chem.T_onset_K)[0]
            if len(onset_indices) > 0:
                cell.onset_time = float(time_points[onset_indices[0]])
            else:
                cell.onset_time = None

            # Runaway zamanı (ilk T >= T_trigger veya alpha >= 0.05)
            runaway_indices = np.where((T_array_K >= chem.T_trigger_K) | (alpha_array >= 0.05))[0]
            if len(runaway_indices) > 0:
                cell.runaway_time = float(time_points[runaway_indices[0]])
                if alpha_array[-1] >= 0.99:
                    cell.state = CellState.BURNED_OUT
                else:
                    cell.state = CellState.RUNAWAY
            elif cell.onset_time is not None:
                cell.state = CellState.ONSET
            else:
                cell.state = CellState.NORMAL

            cell.temperature_K = float(T_array_K[-1])
            cell.alpha = float(alpha_array[-1])

            summary = cell.to_dict()
            summary["max_temperature_C"] = round(max_T_C, 2)
            cell_summaries.append(summary)

        # Modül seviyesi metrikler
        peak_pack_temp_C = max(s["max_temperature_C"] for s in cell_summaries)
        runaway_cells = [s for s in cell_summaries if s["runaway_time_s"] is not None]

        pack_metrics = {
            "total_cells": N,
            "runaway_cell_count": len(runaway_cells),
            "peak_module_temp_C": round(peak_pack_temp_C, 2),
            "solve_duration_wall_s": round(solve_duration_s, 3),
            "n_function_evaluations": sol.nfev,
            "trigger_cell_id": trigger_cell_id
        }

        cfg_hash = self.generate_config_hash(config_dict or {"job_id": job_id, "n_cells": N})
        fingerprint = self.generate_execution_fingerprint()

        return SimulationResult(
            job_id=job_id,
            config_hash=cfg_hash,
            execution_fingerprint=fingerprint,
            time_points_s=time_points,
            temperature_history_C=temp_history_C,
            alpha_history=alpha_history,
            cell_summaries=cell_summaries,
            pack_metrics=pack_metrics,
            validation_status="literature_calibrated",
            solver_metadata={
                "solver_method": method,
                "rtol": rtol,
                "atol": atol,
                "total_steps": len(time_points),
                "nfev": sol.nfev
            }
        )
