# Pil Paketi Termal Kaçak Yayılımı (Thermal Runaway Propagation) Simülatörü

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/tests-13%20passed-brightgreen.svg)]()
[![Validation](https://img.shields.io/badge/validation-literature--calibrated-orange.svg)]()

Lityum-iyon pil paketlerinde (e-bisiklet, drone, robotik, küçük/orta ölçekli ESS) tek hücrede başlayan termal kaçağın komşu hücrelere yayılıp yayılmayacağını saniyeler içinde simüle eden, **UL 9540A / UN 38.3 Ön-Tarama (Pre-Screening) ve Mühendislik Değerlendirme Aracı**.

---

## 🚀 Hızlı Başlangıç

### 1. Kurulum
Gerekli Python paketlerini yükleyin:
```bash
pip install -r requirements.txt
```

### 2. Simülatör Web Dashboard ve API Sunucusunu Başlatma
```bash
python run_server.py --port 8000
```
Tarayıcınızda açın:
* **İnteraktif Web Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **REST API & Swagger Dokümantasyonu:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Otomatik Testleri Çalıştırma
Tüm birim, ARC adiyabatik kalibrasyon ve iki hücreli yayılım testlerini koşturmak için:
```bash
python -m pytest -v
```

---

## 📁 Proje Mimarisi ve Klasör Yapısı

```
Termal Kaçak Sim/
├── data/
│   ├── chemistry_library.json       # Faz 0: NMC, NMC811, LFP Arrhenius parametreleri
│   └── materials_library.json       # Faz 0: Aerojel, mika, hava boşluğu, silikon, alüminyum
├── docs/
│   ├── Faz0_Kinetik_Parametre_Raporu.md  # Literatür ARC/DSC araştırma raporu
│   ├── Faz0.5_Kod_Sozlesmeleri.md        # Dondurulmuş 5 Mimari Kod Sözleşmesi
│   └── validation_benchmarks.md          # ARC ve yayılım doğrulama raporu
├── simulator/
│   ├── core/
│   │   ├── constants.py             # Sözleşme 1 & 2: Kelvin birimleri, fizik sabitleri, toleranslar
│   │   ├── cell_model.py            # CellModel, CellGeometry, CellState durum makinesi
│   │   ├── kinetics_engine.py       # ArrheniusKineticsEngine (dalpha/dt, Q_gen)
│   │   ├── pack_geometry.py         # PackGeometryBuilder (18650, 21700, 4680, prizmatik)
│   │   ├── thermal_network.py       # ThermalNetworkAssembler (iletim, busbar, radyasyon, konveksiyon, soğutma)
│   │   ├── solver.py                # ThermalRunawaySolver (SciPy LSODA, config hash, execution fingerprint)
│   │   └── propagation_evaluator.py # PropagationEvaluator (çok boyutlu risk vektörü, yayılım grafiği)
│   ├── api/
│   │   ├── models.py                # Pydantic request/response şemaları
│   │   ├── services.py              # Simülasyon servis orkestratörü & değişmez sonuç deposu
│   │   └── app.py                   # FastAPI REST API ve statik sunucu
│   ├── reporting/
│   │   └── report_generator.py      # ReportLab tabanlı profesyonel PDF mühendislik raporu üretici
│   └── static/
│       ├── index.html               # İnteraktif Web UI Dashboard
│       ├── app.js                   # Dinamik 2D Canvas ısı haritası, Chart.js eğrileri, Scrubber
│       └── style.css                # CAE mühendislik arayüzü dark theme stilleri
├── tests/
│   ├── test_kinetics.py             # Arrhenius ve kinetik motor birim testleri
│   ├── test_geometry.py             # Topoloji ve komşuluk hesaplama testleri
│   ├── test_thermal_network.py      # Isıl iletkenlik matrisi ve enerji dengesi testleri
│   ├── test_arc_validation.py       # Tek hücre adiyabatik ARC kalibrasyon testi
│   ├── test_propagation.py          # İki hücreli bariyersiz yayılım ve aerojel sınırlama testleri
│   └── test_api.py                  # API endpoint ve PDF üretim testleri
├── reports/                         # Otomatik üretilen mühendislik değerlendirme PDF raporları
├── pytest.ini
├── requirements.txt
└── run_server.py
```

---

## 🔬 Uygulanan Planlar ve Standartlar

1. **Faz 0 — Kinetik Parametre Araştırma Planı:**
   - Yayınlanmış akademik ARC ve DSC literatürü taranmış, NMC111, NMC622, NMC811 ve LFP için $A$, $E_a$, $\Delta H$, $T_{onset}$ değerleri karşılaştırma tablosunda derlenmiş ve `data/chemistry_library.json` içinde yapılandırılmıştır.
2. **Faz 0.5 — 5 Kod Sözleşmesi (Code Contracts):**
   - **Sözleşme 1 (Bilimsel İşleme):** Hesaplamalarda mutlak Kelvin zorunluluğu, $\alpha \in [0, 1]$, CellState enum.
   - **Sözleşme 2 (Çözücü):** `scipy.integrate.solve_ivp` LSODA sertlik algılamalı adaptif entegrasyon.
   - **Sözleşme 3 (Değişmezlik):** Deterministik SHA-256 `config_hash` ve `execution_fingerprint`.
   - **Sözleşme 4 (Kanıt & Raporlama):** UL 9540A mühendislik ön-değerlendirme dili ve çok boyutlu risk vektörü.
   - **Sözleşme 5 (Doğrulama Durumu):** `validation_status: "literature_calibrated"` şeffaf etiketleme.
3. **Ana Proje Planı (Faz 1 - Faz 5):**
   - Lumped-parameter 2D termal direnç ve radyasyon ağı.
   - Silika aerojel ve mika bariyerleri ile yayılımın durdurulması analizi.
   - Matplotlib ve ReportLab ile otomatik PDF değerlendirme raporu çıktısı.
