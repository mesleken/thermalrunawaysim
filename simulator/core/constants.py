"""
Merkezi Sabitler ve Kod Sözleşmesi Değerleri
Faz 0.5 Sözleşme 1 ve Sözleşme 2'ye tam uyumlu merkezi tanımlamalar.
"""

from enum import Enum

# Evrensel Fiziksel Sabitler
R_GAS = 8.314462618  # Evrensel gaz sabiti, J/(mol * K)
STEFAN_BOLTZMANN = 5.670374419e-8  # Stefan-Boltzmann sabiti, W/(m^2 * K^4)
KELVIN_ZERO_C = 273.15  # 0 °C = 273.15 K

# Birim Dönüşüm Fonksiyonları (Hesaplamalar daima Kelvin kullanır)
def celsius_to_kelvin(temp_c: float) -> float:
    return float(temp_c) + KELVIN_ZERO_C

def kelvin_to_celsius(temp_k: float) -> float:
    return float(temp_k) - KELVIN_ZERO_C

class CellState(str, Enum):
    """Hücre Yaşam Döngüsü ve Termal Kaçak Durum Makinesi."""
    NORMAL = "NORMAL"          # T < T_onset, stabil çalışma
    ONSET = "ONSET"            # T_onset <= T < T_trigger, kendi kendine ekzotermik ısınma başladı
    RUNAWAY = "RUNAWAY"        # T >= T_trigger veya dT/dt >= 1.0 K/s, kontrolsüz kaçak
    BURNED_OUT = "BURNED_OUT"  # alpha >= 0.99, aktif reaksiyon maddesi tükendi

class PropagationStatus(str, Enum):
    """Modül Düzeyi Yayılım Güvenlik Sınıflandırması."""
    NO_PROPAGATION = "NO_PROPAGATION"                  # Sadece tetikleyici yandı, komşular güvende
    LOCAL_CONTAINED = "LOCAL_CONTAINED"                # Komşu 1-2 hücre etkilendi ancak durduruldu
    UNCONTROLLED_CASCADE = "UNCONTROLLED_CASCADE"      # Zincirleme kontrolsüz yayılım

class CellFormat(str, Enum):
    """Desteklenen Hücre Geometri Formatları."""
    CYLINDRICAL_18650 = "18650"
    CYLINDRICAL_21700 = "21700"
    CYLINDRICAL_4680 = "4680"
    PRISMATIC = "prismatic"

# Çözücü Kararlılık ve Tolerans Sabitleri (Sözleşme 2)
SOLVER_DEFAULT_RTOL = 1e-5
SOLVER_DEFAULT_ATOL = 1e-6
SOLVER_DEFAULT_MAX_STEP = 0.5   # saniye
SOLVER_DEFAULT_FIRST_STEP = 1e-4 # saniye
SOLVER_METHOD = "LSODA"          # Otomatik sertlik (stiffness) algılamalı

# Ön-Tanımlı Standart Silindirik Boyutlar (Çap, Yükseklik metre cinsinden)
CYLINDRICAL_SPECS = {
    CellFormat.CYLINDRICAL_18650: {"diameter": 0.018, "height": 0.065, "mass": 0.046, "cp": 1050.0},
    CellFormat.CYLINDRICAL_21700: {"diameter": 0.021, "height": 0.070, "mass": 0.068, "cp": 1020.0},
    CellFormat.CYLINDRICAL_4680:  {"diameter": 0.046, "height": 0.080, "mass": 0.355, "cp": 1100.0},
}
