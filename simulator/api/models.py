"""
API Pydantic Veri Modelleri (Şemalar)
FastAPI istek ve yanıt yapılarının tanımı.
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
    trigger_method: str = Field(default="thermal_pulse", description="'thermal_pulse' veya 'instant_onset'")
    trigger_power_W: float = Field(default=3500.0, ge=0.0, description="Harici ısı darbesi gücü (Watt)")
    trigger_duration_s: float = Field(default=3.0, ge=0.1, le=300.0, description="Isı darbesi uygulama süresi (saniye)")
    trigger_initial_temp_C: Optional[float] = Field(default=220.0, description="Anlık başlangıç sıcaklığı (varsa)")

    # Gelişmiş Fizik ve Kinetik Parametreleri (Advanced Physics Mode)
    advanced_physics_enabled: bool = Field(default=False, description="Gelişmiş fizik parametreleri aktif mi?")
    custom_A_pre_exponential: Optional[float] = Field(default=None, description="Özel Arrhenius frekans çarpanı A (1/s)")
    custom_Ea_J_per_mol: Optional[float] = Field(default=None, description="Özel aktivasyon enerjisi Ea (J/mol)")
    custom_delta_H_J_per_g: Optional[float] = Field(default=None, description="Özel reaksiyon entalpisi delta_H (J/g)")
    custom_reaction_order_n: Optional[float] = Field(default=1.0, ge=0.1, le=3.0, description="Reaksiyon mertebesi n")
    custom_active_mass_ratio: Optional[float] = Field(default=None, ge=0.05, le=1.0, description="Aktif kütle oranı")
    h_vent_W_per_m2_K: float = Field(default=100.0, ge=0.0, le=2000.0, description="Venting gaz konveksiyon katsayısı")
    T_vent_gas_C: Optional[float] = Field(default=None, description="Venting gaz sıcaklığı (°C)")
    surface_emissivity: float = Field(default=0.85, ge=0.05, le=1.0, description="Yüzey termal ışınım emmisivitesi")

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

class DesignStudyRequest(BaseModel):
    sweep_type: str = Field(default="spacing_sweep", description="'spacing_sweep', 'separator_sweep', 'cooling_sweep'")
    base_config: PackSimulationRequest
    sweep_values: Optional[List[Any]] = Field(default=None, description="Taranacak parametre değerleri listesi")

class DesignStudyResponse(BaseModel):
    study_id: str
    sweep_type: str
    recommended_case_index: int
    recommended_reason: str
    cases: List[DesignStudyCase]


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
    format_name: str = Field(..., description="Format Adı (Örn: 46950)")
    radius_mm: float = Field(..., description="Yarıçap (mm)")
    height_mm: float = Field(..., description="Yükseklik (mm)")
    mass_kg: float = Field(..., description="Toplam Hücre Ağırlığı (kg)")
    casing_thickness_mm: float = Field(default=0.3, description="Kasa Et Kalınlığı (mm)")
