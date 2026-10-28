"""
Termal Kaçak Çözücü Motoru (ThermalRunawaySolver)
scipy.integrate.solve_ivp ile adaptif, sertlik (stiff) algılamalı diferansiyel denklem çözümü.
Faz 0.5 Sözleşme 2 ve Sözleşme 3'e (Config Hash & Execution Fingerprint) tam uyumludur.
Aşama 1: Core-Shell (2 düğüm) ve Çoklu-Reaksiyon Kinetiği durum vektörü çözümü desteklenir.
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
        solver_metadata: Optional[Dict[str, Any]] = None,
        core_temperature_history_C: Optional[Dict[int, List[float]]] = None,
        sub_alpha_history: Optional[Dict[int, Dict[str, List[float]]]] = None,
        heat_flux_history_W: Optional[Dict[str, Dict[int, List[float]]]] = None,
        gas_hazard_summary: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None
    ):
        def _normalize_cell_map(d: Optional[Dict[Any, Any]]) -> Dict[int, Any]:
            if not d:
                return {}
            return {int(k): v for k, v in d.items()}

        self.job_id = job_id
        self.config_hash = config_hash
        self.execution_fingerprint = execution_fingerprint
        self.time_points_s = time_points_s
        self.temperature_history_C = _normalize_cell_map(temperature_history_C)
        self.core_temperature_history_C = _normalize_cell_map(core_temperature_history_C)
        self.sub_alpha_history = _normalize_cell_map(sub_alpha_history) if sub_alpha_history is not None else None
        self.heat_flux_history_W = (
            {fk: _normalize_cell_map(cmap) for fk, cmap in heat_flux_history_W.items()}
            if heat_flux_history_W is not None else None
        )
        self.gas_hazard_summary = gas_hazard_summary
        self.alpha_history = _normalize_cell_map(alpha_history)
        self.cell_summaries = cell_summaries
        self.pack_metrics = pack_metrics
        self.validation_status = validation_status
        self.solver_metadata = solver_metadata or {}
        self.created_at = created_at or time.strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "config_hash": self.config_hash,
            "execution_fingerprint": self.execution_fingerprint,
            "validation_status": self.validation_status,
            "created_at": self.created_at,
            "time_points_s": self.time_points_s,
            "temperature_history_C": self.temperature_history_C,
            "core_temperature_history_C": self.core_temperature_history_C,
            "sub_alpha_history": self.sub_alpha_history,
            "heat_flux_history_W": self.heat_flux_history_W,
            "gas_hazard_summary": self.gas_hazard_summary,
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
        trigger_method: str = "thermal_pulse", # "thermal_pulse", "external_heater", "nail_penetration_isc", "oven_ramp", "instant_onset"
        trigger_power_W: float = 1200.0,
        trigger_duration_s: float = 3.0,
        trigger_initial_temp_C: Optional[float] = None,
        isc_resistance_ohm: float = 0.05,
        oven_target_temp_C: Optional[float] = None,
        oven_ramp_C_per_min: float = 5.0,
        enclosure_free_volume_liters: Optional[float] = None,
        vent_valve_area_cm2: float = 2.0,
        vent_burst_pressure_kpa: float = 35.0,
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

        if trigger_cell_id < 0 or trigger_cell_id >= self.n_cells:
            raise ValueError(
                f"trigger_cell_id={trigger_cell_id} geçersiz. "
                f"Geçerli aralık: 0 - {self.n_cells - 1}"
            )

        N = self.n_cells
        is_core_shell = (getattr(self.assembler, "nodal_model", "lumped") == "core_shell")
        is_multi_rxn = (getattr(self.assembler, "kinetics_model", "single_step") == "multi_reaction")

        # Başlangıç sıcaklık vektörü
        y0_temp_base = np.array([c.temperature_K for c in self.cells], dtype=np.float64)

        if trigger_method == "instant_onset":
            t_init_K = celsius_to_kelvin(trigger_initial_temp_C if trigger_initial_temp_C is not None else 220.0)
            applied_trigger_power = 0.0
        elif trigger_method in ("nail_penetration_isc", "oven_ramp"):
            t_init_K = None
            applied_trigger_power = 0.0
        else:
            t_init_K = None
            applied_trigger_power = trigger_power_W

        if is_core_shell:
            y0_core = y0_temp_base.copy()
            y0_shell = y0_temp_base.copy()
            if t_init_K is not None:
                y0_core[trigger_cell_id] = t_init_K
                y0_shell[trigger_cell_id] = t_init_K
            y0_temp = np.concatenate([y0_core, y0_shell])
        else:
            y0_temp = y0_temp_base.copy()
            if t_init_K is not None:
                y0_temp[trigger_cell_id] = t_init_K

        # Başlangıç reaksiyon vektörü
        if is_multi_rxn:
            y0_alpha = np.zeros(4 * N, dtype=np.float64)
            if trigger_method == "instant_onset" and trigger_initial_temp_C is None:
                y0_alpha[trigger_cell_id * 4 + 0] = 0.99
                y0_alpha[trigger_cell_id * 4 + 1] = 0.50
                y0_alpha[trigger_cell_id * 4 + 2] = 0.90
                y0_alpha[trigger_cell_id * 4 + 3] = 0.05
        else:
            y0_alpha = np.array([c.alpha for c in self.cells], dtype=np.float64)
            if trigger_method == "instant_onset" and trigger_initial_temp_C is None:
                y0_alpha[trigger_cell_id] = 0.05

        y0 = np.concatenate([y0_temp, y0_alpha])

        # Zaman ızgarası
        t_eval = np.linspace(t_span[0], t_span[1], num_output_points)

        # ODE sağ taraf fonksiyonu
        def rhs(t, y):
            return self.assembler.compute_derivatives(
                t=t,
                state_vector=y,
                trigger_cell_id=trigger_cell_id,
                trigger_power_W=applied_trigger_power,
                trigger_duration_s=trigger_duration_s,
                trigger_method=trigger_method,
                isc_resistance_ohm=isc_resistance_ohm,
                oven_target_temp_C=oven_target_temp_C,
                oven_ramp_C_per_min=oven_ramp_C_per_min
            )

        # Güvenlik Kesintisi (Termination Event)
        def max_temp_event(t, y):
            temp_boundary = 2 * N if is_core_shell else N
            max_T = np.max(y[:temp_boundary])
            return 1773.15 - max_T
        max_temp_event.terminal = True
        max_temp_event.direction = -1

        # solve_ivp çağrısı
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

        time_points = [round(float(t), 4) for t in sol.t]
        n_steps = len(time_points)

        # Sıcaklık matrislerini ayrıştır
        if is_core_shell:
            core_temps_matrix = sol.y[:N, :]
            shell_temps_matrix = sol.y[N:2*N, :]
            temps_matrix = shell_temps_matrix  # Dış ölçülebilir yüzey sıcaklığı
            rxn_offset = 2 * N
        else:
            temps_matrix = sol.y[:N, :]
            core_temps_matrix = temps_matrix
            shell_temps_matrix = temps_matrix
            rxn_offset = N

        # Alpha matrisini ayrıştır
        sub_alpha_history: Optional[Dict[int, Dict[str, List[float]]]] = None
        if is_multi_rxn:
            alphas_raw = sol.y[rxn_offset : rxn_offset + 4*N, :]
            alphas_matrix = np.zeros((N, n_steps), dtype=np.float64)
            sub_alpha_history = {}
            rxn_names = ["SEI", "anode", "separator", "cathode"]
            for i in range(N):
                # 4. reaksiyon katot bozunumu kaçak göstergesi
                alphas_matrix[i, :] = alphas_raw[i*4 + 3, :]
                sub_alpha_history[i] = {
                    rxn_names[k]: [round(float(alphas_raw[i*4 + k, s]), 4) for s in range(n_steps)]
                    for k in range(4)
                }
        else:
            alphas_matrix = sol.y[rxn_offset : rxn_offset + N, :]

        # Sıcaklık geçmişi (°C)
        temp_history_C: Dict[int, List[float]] = {}
        core_temp_history_C: Dict[int, List[float]] = {}
        alpha_history: Dict[int, List[float]] = {}

        for i in range(N):
            temp_history_C[i] = [round(kelvin_to_celsius(float(T_k)), 2) for T_k in temps_matrix[i, :]]
            core_temp_history_C[i] = [round(kelvin_to_celsius(float(T_k)), 2) for T_k in core_temps_matrix[i, :]]
            alpha_history[i] = [round(float(a), 4) for a in alphas_matrix[i, :]]

        # Isı akıları geçmişi (q_chem, q_abuse, q_cond, q_rad, q_vent, q_cool)
        heat_flux_history_W: Dict[str, Dict[int, List[float]]] = {
            "q_chem": {i: [] for i in range(N)},
            "q_abuse": {i: [] for i in range(N)},
            "q_cond": {i: [] for i in range(N)},
            "q_rad": {i: [] for i in range(N)},
            "q_vent": {i: [] for i in range(N)},
            "q_cool": {i: [] for i in range(N)}
        }
        for s in range(n_steps):
            t_s = float(sol.t[s])
            y_s = sol.y[:, s]
            flows = self.assembler.evaluate_heat_flows(
                t=t_s,
                state_vector=y_s,
                trigger_cell_id=trigger_cell_id,
                trigger_power_W=applied_trigger_power,
                trigger_duration_s=trigger_duration_s,
                trigger_method=trigger_method,
                isc_resistance_ohm=isc_resistance_ohm,
                oven_target_temp_C=oven_target_temp_C,
                oven_ramp_C_per_min=oven_ramp_C_per_min
            )
            for k in ["q_chem", "q_abuse", "q_cond", "q_rad", "q_vent", "q_cool"]:
                arr = flows.get(k, np.zeros(N))
                for i in range(N):
                    heat_flux_history_W[k][i].append(round(float(arr[i]), 2))

        # Hücre durumlarını ve olay zamanlarını tespit et
        cell_summaries: List[Dict[str, Any]] = []
        for i in range(N):
            cell = self.cells[i]
            chem = self.assembler.cell_chemistries[i]
            T_array_K = temps_matrix[i, :]
            T_core_array_K = core_temps_matrix[i, :]
            alpha_array = alphas_matrix[i, :]

            # Max sıcaklıklar
            max_T_K = float(np.max(T_array_K))
            max_T_C = kelvin_to_celsius(max_T_K)
            max_core_T_K = float(np.max(T_core_array_K))
            max_core_T_C = kelvin_to_celsius(max_core_T_K)

            cell.max_temperature_K = max_T_K
            cell.max_shell_temp_K = max_T_K
            cell.max_core_temp_K = max_core_T_K

            # Termal Gecikme (Thermal Lag)
            t_core_peak = time_points[int(np.argmax(T_core_array_K))]
            t_shell_peak = time_points[int(np.argmax(T_array_K))]
            cell.thermal_lag_s = max(0.0, float(t_shell_peak - t_core_peak))

            # Onset zamanı
            onset_indices = np.where(T_core_array_K >= chem.T_onset_K)[0]
            if len(onset_indices) > 0:
                cell.onset_time = float(time_points[onset_indices[0]])
            else:
                cell.onset_time = None

            # Runaway zamanı
            runaway_indices = np.where((T_core_array_K >= chem.T_trigger_K) | (alpha_array >= 0.05))[0]
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
            summary["max_core_temperature_C"] = round(max_core_T_C, 2)
            summary["T_onset_C"] = round(float(kelvin_to_celsius(chem.T_onset_K)), 2)
            summary["T_trigger_C"] = round(float(kelvin_to_celsius(chem.T_trigger_K)), 2)
            summary["chemistry_name"] = chem.name
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
            "trigger_cell_id": trigger_cell_id,
            "nodal_model": getattr(self.assembler, "nodal_model", "lumped"),
            "kinetics_model": getattr(self.assembler, "kinetics_model", "single_step")
        }

        cfg_hash = self.generate_config_hash(config_dict or {"job_id": job_id, "n_cells": N})
        fingerprint = self.generate_execution_fingerprint()

        # Gaz Tehlike Analizi (Mahfaza serbest hacmi boş bırakılmışsa modül hücre hacminden otomatik tahmin edilir)
        gas_summary = None
        try:
            from simulator.core.gas_hazard_engine import GasHazardEngine
            auto_estimated_vol = False
            eff_free_vol_L = enclosure_free_volume_liters
            if eff_free_vol_L is None:
                cells_total_vol_L = sum(
                    float(getattr(c.geometry, "volume", 0.0001)) for c in self.cells
                ) * 1000.0
                eff_free_vol_L = max(0.5, round(cells_total_vol_L * 0.90, 2))
                auto_estimated_vol = True

            gas_summary = GasHazardEngine.evaluate_gas_hazard(
                time_points=time_points,
                alpha_history=alpha_history,
                cells=self.cells,
                cell_chemistries=self.assembler.cell_chemistries,
                enclosure_free_vol_L=eff_free_vol_L,
                vent_valve_area_cm2=vent_valve_area_cm2,
                vent_burst_pressure_kpa=vent_burst_pressure_kpa,
                soc_percent=getattr(self.assembler, "soc_percent", 100.0),
                enclosure_volume_auto_estimated=auto_estimated_vol
            )
        except Exception:
            gas_summary = None

        res = SimulationResult(
            job_id=job_id,
            config_hash=cfg_hash,
            execution_fingerprint=fingerprint,
            time_points_s=time_points,
            temperature_history_C=temp_history_C,
            core_temperature_history_C=core_temp_history_C if is_core_shell else None,
            sub_alpha_history=sub_alpha_history,
            heat_flux_history_W=heat_flux_history_W,
            gas_hazard_summary=gas_summary,
            alpha_history=alpha_history,
            cell_summaries=cell_summaries,
            pack_metrics=pack_metrics,
            validation_status="literature_calibrated",
            solver_metadata={
                "solver_method": method,
                "rtol": rtol,
                "atol": atol,
                "total_steps": len(time_points),
                "nfev": sol.nfev,
                "nodal_model": getattr(self.assembler, "nodal_model", "lumped"),
                "kinetics_model": getattr(self.assembler, "kinetics_model", "single_step")
            }
        )
        return res
