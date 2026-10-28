"""
API Pydantic Veri Modelleri (Şemalar)
FastAPI istek ve yanıt yapılarının tanımı.
Aşama 1 (Core-Shell, Çoklu-Kinetik, Kütle Kaybı) ve Aşama 2 (Validasyon Motoru & Monte Carlo UQ) modelleri eklendi.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class PackSimulationRequest(BaseModel):
    # Geometri parametreleri
    rows: int = Field(default=3, ge=1, le=10, description="Hücre matrisi satır sayısı")
    cols: int = Field(default=3, ge=1, le=10, description="Hücre matrisi sütun sayısı")
    cell_format: str = Field(default="18650", description="Hücre formatı: 18650, 21700, 4680, prismatic")
    spacing_x_mm: float = Field(default=2.0, ge=0.2, le=50.0, description="X yönünde hücreler arası boşluk (mm)")
    spacing_y_mm: float = Field(default=2.0, ge=0.2, le=50.0, description="Y yönünde hücreler arası boşluk (mm)")
    staggered: bool = Field(default=False, description="Üçgensel / heksagonal kaydırmalı dizilim")

    # Kimya ve Malzeme seçimi
    chemistry_id: str = Field(default="NMC_generic_v1", description="data/chemistry_library.json'daki kimya ID")
    separator_material_id: Optional[str] = Field(default=None, description="Separatör malzeme ID (örn. aerogel_insulation, mica_sheet)")
    separator_thickness_mm: float = Field(default=0.0, ge=0.0, le=20.0, description="Separatör et kalınlığı (mm)")
    gap_material_id: str = Field(default="air_gap", description="Boşluk dolgu malzemesi ID (örn. air_gap, epoxy_potting)")
    busbar_conductance_W_per_K: float = Field(default=0.60, ge=0.0, description="Hücreler arası busbar iletim katsayısı (W/K)")

    # Termal Sınır Şartları
    T_ambient_C: float = Field(default=25.0, description="Ortam sıcaklığı (°C)")
    h_ambient_W_per_m2_K: float = Field(default=10.0, ge=0.0, description="Ortam doğal konveksiyon katsayısı")
    active_cooling_enabled: bool = Field(default=False, description="Taban sıvı soğutma plakası aktif mi?")
    h_cooling_plate_W_per_m2_K: float = Field(default=800.0, description="Soğutma plakası ısı taşınım katsayısı")
    T_coolant_C: float = Field(default=25.0, description="Soğutma sıvısı sıcaklığı (°C)")

    # Tetikleyici Senaryo (Trigger Abuse)
    trigger_cell_id: int = Field(default=0, ge=0, description="Termal kaçağın başlatılacağı hücre indeksi")
    trigger_method: str = Field(default="thermal_pulse", description="'thermal_pulse', 'external_heater', 'nail_penetration_isc', 'oven_ramp', 'instant_onset'")
    trigger_power_W: float = Field(default=3500.0, ge=0.0, description="Harici ısı darbesi gücü (Watt)")
    trigger_duration_s: float = Field(default=3.0, ge=0.1, le=300.0, description="Isı darbesi uygulama süresi (saniye)")
    trigger_initial_temp_C: Optional[float] = Field(default=220.0, description="Anlık başlangıç sıcaklığı (varsa)")
    soc_percent: float = Field(default=100.0, ge=0.0, le=100.0, description="Hücre Şarj Seviyesi (SOC %)")
    isc_resistance_ohm: float = Field(default=0.05, ge=0.0001, le=10.0, description="Dahili kısa devre (ISC) direnci (Ohm)")
    oven_target_temp_C: Optional[float] = Field(default=None, description="Fırın testi hedef sıcaklığı (°C)")
    oven_ramp_C_per_min: float = Field(default=5.0, ge=0.5, le=50.0, description="Fırın sıcaklık artış hızı (°C/dk)")

    # Gaz Salınımı ve Mahfaza Basınç Parametreleri
    enclosure_free_volume_liters: Optional[float] = Field(default=None, ge=0.1, description="Mahfaza içi net serbest hacim (L)")
    vent_valve_area_cm2: float = Field(default=2.0, ge=0.1, le=500.0, description="Tahliye valfi alanı (cm²)")
    vent_burst_pressure_kpa: float = Field(default=35.0, ge=1.0, le=500.0, description="Tahliye valfi patlama basıncı (kPa)")

    # Gelişmiş Fizik ve Kinetik Parametreleri (Advanced Physics Mode)
    advanced_physics_enabled: bool = Field(default=False, description="Gelişmiş fizik parametreleri aktif mi?")
    nodal_model: str = Field(default="lumped", description="'lumped' (1-düğüm) veya 'core_shell' (2-düğüm 1D radyal)")
    kinetics_model: str = Field(default="single_step", description="'single_step' veya 'multi_reaction' (4-kademe)")
    ejecta_mass_loss_ratio: float = Field(default=0.0, ge=0.0, le=0.50, description="Venting esnasında atılan kütle oranı (0.0 - 0.50)")
    vent_direction_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0, description="Yönlü venting açısı (0 - 360 derece)")
    custom_A_pre_exponential: Optional[float] = Field(default=None, description="Özel Arrhenius frekans çarpanı A (1/s)")
    custom_Ea_J_per_mol: Optional[float] = Field(default=None, description="Özel aktivasyon enerjisi Ea (J/mol)")
    custom_delta_H_J_per_g: Optional[float] = Field(default=None, description="Özel reaksiyon entalpisi delta_H (J/g)")
    custom_reaction_order_n: Optional[float] = Field(default=1.0, ge=0.1, le=3.0, description="Reaksiyon mertebesi n")
    custom_active_mass_ratio: Optional[float] = Field(default=None, ge=0.05, le=1.0, description="Aktif kütle oranı")
    custom_sub_reactions: Optional[List[Dict[str, Any]]] = Field(default=None, description="Özel 4-kademe reaksiyon kinetiği listesi")
    h_vent_W_per_m2_K: float = Field(default=100.0, ge=0.0, le=2000.0, description="Venting gaz konveksiyon katsayısı")
    T_vent_gas_C: Optional[float] = Field(default=None, description="Venting gaz sıcaklığı (°C)")
    surface_emissivity: float = Field(default=0.85, ge=0.0, le=1.0, description="Yüzey termal ışınım emmisivitesi")

    # Kullanıcı Tanımlı Özel (Inline / Canlı) Parametreler
    custom_chemistry_params: Optional[Dict[str, Any]] = Field(default=None, description="Anlık tanımlanan özel kimya kinetik parametreleri")
    custom_separator_params: Optional[Dict[str, Any]] = Field(default=None, description="Anlık tanımlanan özel separatör parametreleri")
    custom_gap_params: Optional[Dict[str, Any]] = Field(default=None, description="Anlık tanımlanan özel dolgu parametreleri")

    # Çözücü parametreleri
    simulation_time_s: float = Field(default=90.0, ge=10.0, le=600.0, description="Toplam simülasyon süresi (s)")
    num_output_points: int = Field(default=250, ge=50, le=1000, description="Çıktı zaman adımı sayısı")


class DesignStudyCase(BaseModel):
    case_index: int
    case_name: str
    param_label: str
    param_value: Any
    peak_module_temp_C: float
    affected_cells_count: int
    total_cells: int
    propagation_ratio_percent: float
    time_to_first_propagation_s: Optional[float]
    risk_score_100: float
    status: str
    is_recommended: bool = False
    job_id: str
    # Aşama 3: Kütle ve Pareto Metrikleri
    module_mass_kg: float = 0.0
    mass_penalty_index_percent: float = 0.0
    is_pareto_optimal: bool = False
    utopia_distance: Optional[float] = None


class DesignStudyRequest(BaseModel):
    sweep_type: str = Field(default="spacing_sweep", description="'spacing_sweep', 'separator_sweep', 'cooling_sweep'")
    base_config: PackSimulationRequest
    sweep_values: Optional[List[Any]] = Field(default=None, description="Taranacak parametre değerleri listesi")
    # Aşama 3: Çok Amaçlı Optimizasyon Ağırlıkları
    w_safety: float = Field(default=0.6, ge=0.0, le=1.0, description="Güvenlik ağırlığı (0.0 - 1.0)")
    w_mass: float = Field(default=0.4, ge=0.0, le=1.0, description="Kütle optimizasyonu ağırlığı (0.0 - 1.0)")
    task_id: Optional[str] = Field(default=None, description="Canlı SSE ilerleme takibi için istemci görev ID'si")


class DesignStudyResponse(BaseModel):
    study_id: str
    sweep_type: str
    recommended_case_index: int
    recommended_reason: str
    cases: List[DesignStudyCase]
    # Aşama 3: Pareto Cephesi ve Kütle Özeti
    pareto_front_indices: List[int] = Field(default_factory=list)
    knee_point_index: Optional[int] = None
    baseline_mass_kg: float = 0.0
    pareto_summary: str = ""


# ================= Aşama 2: Validasyon ve Monte Carlo UQ Modelleri =================

class ValidationCompareRequest(BaseModel):
    job_id: str = Field(..., description="Karşılaştırılacak simülasyonun Job ID'si")
    csv_content: str = Field(..., description="Laboratuvar ARC/DSC/Heater zaman-sıcaklık sensör CSV metni")
    cell_id: int = Field(default=0, description="Deneysel verinin karşılaştırılacağı simülasyon hücre indeksi")


class ValidationCompareResponse(BaseModel):
    job_id: str
    rmse_C: float
    mae_C: float
    delta_T_onset_C: float
    delta_T_peak_C: float
    delta_t_runaway_s: float
    validation_score_percent: float
    confidence_status: str
    regulatory_verdict: str
    sim_peak_T_C: float
    exp_peak_T_C: float
    aligned_time_points: List[float]
    simulated_temperatures: List[float]
    experimental_temperatures: List[float]


class MonteCarloUQRequest(BaseModel):
    base_config: PackSimulationRequest
    n_samples: int = Field(default=15, ge=5, le=50, description="Monte Carlo varyasyon sayısı")
    variance_percent: float = Field(default=5.0, ge=1.0, le=20.0, description="Parametre sapma toleransı (%)")
    task_id: Optional[str] = Field(default=None, description="Canlı SSE ilerleme takibi için istemci görev ID'si")


class MonteCarloUQResponse(BaseModel):
    study_id: str
    n_samples: int
    variance_percent: float
    p10_peak_temp_C: float
    p50_peak_temp_C: float
    p90_peak_temp_C: float
    confidence_interval_width_C: float
    time_points_s: List[float]
    p10_temperature_history_C: List[float]
    p50_temperature_history_C: List[float]
    p90_temperature_history_C: List[float]
    summary_statement: str


class SimulationJobStatus(BaseModel):
    job_id: str
    status: str # "QUEUED", "RUNNING", "COMPLETED", "FAILED"
    progress_percent: float = 0.0
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class CustomChemistryRequest(BaseModel):
    name: str = Field(..., description="Kimya Adı")
    A_pre_exponential_per_s: float = Field(default=3e14, description="Frekans Çarpanı (1/s)")
    Ea_J_per_mol: float = Field(default=130000.0, description="Aktivasyon Enerjisi (J/mol)")
    delta_H_J_per_g: float = Field(default=500.0, description="Reaksiyon Entalpisi (J/g)")
    T_onset_C: float = Field(default=155.0, description="Kaçak Başlangıç Sıcaklığı (°C)")
    T_trigger_C: float = Field(default=200.0, description="Termal Kaçak Tetikleme Sıcaklığı (°C)")
    active_mass_ratio: float = Field(default=0.55, description="Aktif Madde Oranı")
    source_references: List[str] = Field(default=["Kullanıcı Tanımlı (User Defined)"])


class CustomMaterialRequest(BaseModel):
    name: str = Field(..., description="Malzeme Adı")
    density_kg_per_m3: float = Field(..., description="Yoğunluk (kg/m3)")
    cp_J_per_kg_K: float = Field(..., description="Özgül Isı Kapasitesi (J/kg.K)")
    k_thermal_W_per_m_K: float = Field(..., description="Isıl İletkenlik (W/m.K)")


class CustomFormatRequest(BaseModel):
    format_name: str = Field(..., description="Format Adı (Örn: 46950, Pouch_60Ah)")
    format_type: str = Field(default="cylindrical", description="'cylindrical', 'prismatic', 'pouch'")
    radius_mm: Optional[float] = Field(default=9.0, description="Yarıçap (mm) - Silindirik için")
    height_mm: float = Field(..., description="Yükseklik (mm)")
    width_mm: Optional[float] = Field(default=None, description="Genişlik (mm) - Prizmatik / Pouch için")
    thickness_mm: Optional[float] = Field(default=None, description="Kalınlık (mm) - Prizmatik / Pouch için")
    mass_kg: float = Field(..., description="Toplam Hücre Ağırlığı (kg)")
    cp_J_per_kg_K: float = Field(default=1050.0, ge=300.0, le=3000.0, description="Özgül Isı Kapasitesi (J/kg.K)")
    casing_thickness_mm: float = Field(default=0.3, description="Kasa Et Kalınlığı (mm)")


# ================= Otomatik Kalibrasyon Modelleri =================

class AutoCalibrateRequest(BaseModel):
    csv_content: str = Field(..., description="ARC/DSC test zaman-sıcaklık sensör CSV log metni")
    cell_mass_kg: float = Field(default=0.048, ge=0.005, le=5.0, description="Hücre kütlesi (kg)")
    cp_J_per_kg_K: float = Field(default=950.0, ge=400.0, le=2500.0, description="Özgül ısı kapasitesi (J/kg.K)")
    cell_cp_J_per_kg_K: Optional[float] = Field(default=None, ge=400.0, le=2500.0, description="Özgül ısı kapasitesi takma adı (J/kg.K)")
    active_mass_ratio: float = Field(default=0.60, ge=0.1, le=0.95, description="Aktif madde kütle oranı")
    chemistry_name: str = Field(default="Calibrated_Cell", description="Oluşturulacak kimya ID/adı")
    persist_to_library: bool = Field(default=False, description="Kalıcı kullanıcı kütüphanesine de yazılsın mı?")


class AutoCalibrateResponse(BaseModel):
    frequency_factor_A: float
    activation_energy_J_per_mol: float
    reaction_enthalpy_J_per_kg: float
    r2_score: float
    rmse_C: float
    detected_T_onset_C: Optional[float]
    detected_T_trigger_C: Optional[float]
    fitted_times_s: List[float]
    fitted_temperatures_C: List[float]
    experimental_temperatures_C: List[float]
    calibration_message: str


# ================= 2D Izgara Taraması ve Hassasiyet Modelleri =================

class Grid2DStudyRequest(BaseModel):
    base_config: PackSimulationRequest
    param_x: str = Field(default="spacing_x_mm", description="X ekseni taranacak parametre adı")
    values_x: List[Any] = Field(default=[1.0, 2.0, 3.0], description="X ekseni değerler listesi")
    param_y: str = Field(default="separator_thickness_mm", description="Y ekseni taranacak parametre adı")
    values_y: List[Any] = Field(default=[0.5, 1.0, 1.5], description="Y ekseni değerler listesi")
    task_id: Optional[str] = Field(default=None, description="Canlı SSE ilerleme takibi için istemci görev ID'si")


class Grid2DStudyResponse(BaseModel):
    study_id: str
    param_x: str
    param_y: str
    values_x: List[Any]
    values_y: List[Any]
    matrix_peak_temp_C: List[List[float]]
    matrix_risk_score: List[List[float]]
    cases: List[Dict[str, Any]]


class SensitivityStudyRequest(BaseModel):
    base_config: PackSimulationRequest
    perturbation_percent: float = Field(default=20.0, ge=5.0, le=50.0, description="Parametre sapma oranı (±%)")
    task_id: Optional[str] = Field(default=None, description="Canlı SSE ilerleme takibi için istemci görev ID'si")


class SensitivityStudyResponse(BaseModel):
    study_id: str
    baseline_peak_temp_C: float
    baseline_risk_score: float
    parameters_ranked: List[Dict[str, Any]]
    most_sensitive_parameter: Optional[str]


# ================= Proje Yönetimi ve Karşılaştırma Modelleri =================

class ProjectSaveRequest(BaseModel):
    project_id: Optional[str] = None
    name: str = Field(..., description="Proje adı")
    description: Optional[str] = Field(default="", description="Proje açıklaması")
    payload: Dict[str, Any] = Field(..., description="Tasarım parametreleri konfigürasyonu")


class RunComparisonResponse(BaseModel):
    job_a_id: str
    job_b_id: str
    metrics_a: Dict[str, Any]
    metrics_b: Dict[str, Any]
    delta_metrics: Dict[str, Any]
    temperature_comparison: Dict[str, Any]
