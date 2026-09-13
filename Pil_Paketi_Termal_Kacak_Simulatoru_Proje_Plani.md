# Pil Paketi Termal Kaçak Yayılımı (Thermal Runaway Propagation) Simülatörü
## Kapsamlı Proje Planı v1.0

---

## 1. Yönetici Özeti

Bu proje, lityum-iyon pil paketlerinde bir hücrede başlayan termal kaçağın (thermal runaway) komşu hücrelere yayılıp yayılmayacağını, yayılırsa ne kadar sürede ve hangi yolla yayılacağını tahmin eden, sertifikasyon-öncesi (pre-certification) bir mühendislik simülasyon aracıdır.

Hedef: ANSYS Fluent/Icepak ve büyük OEM'lere yönelik battery-tasarım paketleri (çok pahalı, CFD uzmanlığı gerektiren, ağır) ile büyük OEM dışı — e-bisiklet, drone, robotik, küçük ölçekli enerji depolama (ESS), elektrikli el aletleri — pil paketi üreticileri arasındaki boşluğu doldurmak. Bu firmalar UL 9540A / UN 38.3 / IEC 62619 testlerine girmeden önce ucuz, hızlı, "ön-tarama" (pre-screening) seviyesinde bir analiz aracına ihtiyaç duyar ama bugün ya hiç araç kullanmıyor ya da aşırı donanımlı ve pahalı bir CFD paketine para veriyorlar.

Konumlandırma AeroSeat projesindeki mantığın aynısı: "sertifikasyon garantisi vermeyen ama sertifikasyona hazırlık/mühendislik değerlendirmesi sağlayan" bir araç. Yani "TÜM testleri geçireceğinizi garanti ederiz" değil, "fiziksel teste girmeden önce tasarımınızın nerede zayıf olduğunu gösteririz" konumu.

---

## 2. Problem Tanımı ve Pazar Boşluğu

### 2.1 Mevcut Durum
- Büyük OEM'ler (otomotiv, büyük ESS üreticileri) ANSYS Fluent/Icepak, Siemens Simcenter Battery Design Studio gibi araçları kullanıyor. Bunlar tam CFD çözücüleri, lisans maliyeti yüksek (yıllık on binlerce dolar), kurulum ve kullanım için özel CFD mühendisi gerektiriyor, çözüm süreleri saatler/günler mertebesinde.
- Küçük-orta ölçekli üreticiler (e-bisiklet, drone, robotik, taşınabilir ESS) bu araçlara erişemiyor veya erişse bile ROI'si yok. Bu firmalar genelde:
  - Deneme-yanılma ile fiziksel prototip test ediyor (pahalı, yavaş, tehlikeli — hücre patlatma testleri özel güvenlik altyapısı gerektirir)
  - Ya da hiç ön analiz yapmadan doğrudan sertifikasyon laboratuvarına (UL, TÜV, Element vb.) gidip orada başarısız oluyor, tekrar tasarım/tekrar test döngüsüne giriyor — bu döngü aylar ve on binlerce dolar kaybettiriyor.

### 2.2 Boşluk
Hücre aralığı, separatör/yalıtım malzemesi, soğutma kanalı yerleşimi, hücre kimyası gibi tasarım parametrelerini hızlıca değiştirip "bu pack tasarımı thermal runaway propagation testini geçer mi, geçmez mi" sorusuna dakikalar içinde yaklaşık bir cevap veren, CFD uzmanlığı gerektirmeyen, web tabanlı/masaüstü hafif bir araç yok.

### 2.3 Neden Bu Proje Senin İçin Uygun
- Sertifikasyon mantığı (pass/fail kriterleri, evidence/rapor üretimi, "certification readiness" konumlandırması) AeroSeat projesinde zaten kurguladığın mimariyle doğrudan örtüşüyor.
- Matematik modeli (ısı transferi, kütle/enerji dengesi, sonlu farklar/eleman tipi ayrıklaştırma) MATLAB/Python deneyimin ve METU'daki 2D FEA solver projenle doğrudan örtüşüyor.
- Rapor/sertifikasyon çıktısı üretme deneyimi AeroJoint'teki PDF rapor modülünden taşınabilir.

---

## 3. Hedef Kullanıcı ve Değer Önerisi

**Birincil kullanıcı:** Küçük-orta ölçekli pil paketi tasarımcıları (e-bisiklet/e-scooter, drone, taşınabilir/sabit ESS, elektrikli el aletleri üreticileri), pil pack tasarım mühendisleri, mühendislik danışmanlık firmaları.

**Değer önerisi:** "Fiziksel UL 9540A / UN 38.3 testine girmeden önce, pack tasarımınızın termal kaçak yayılımına karşı ne kadar dayanıklı olduğunu dakikalar içinde, CFD uzmanı gerektirmeden öğrenin."

**Fiyatlandırma yönü (öneri, netleştirilecek):** SaaS abonelik (aylık/proje bazlı) — AeroJoint'teki bulut modeliyle aynı mantık, ağır donanım kullanıcı tarafında gerekmiyor.

---

## 4. Kapsam (V1.0)

### V1.0 içine girenler
- Prizmatik ve silindirik hücre formatları (18650, 21700, 4680 gibi standart silindirik formlar + kullanıcı tanımlı prizmatik boyutlar)
- Tek bir pack geometrisi tanımı: hücre sayısı, dizilim (satır/sütun), hücre-arası boşluk, separatör malzemesi ve kalınlığı
- Pasif soğutma (doğal konveksiyon) ve basit aktif soğutma (soğutma plakası/kanalı, sabit sıcaklık sınır şartı olarak) senaryoları
- Tek bir "tetikleyici hücre" (trigger cell) üzerinden başlatılan runaway olayının komşu hücrelere yayılıp yayılmadığının simülasyonu
- Zamana bağlı sıcaklık dağılımı çıktısı (2D ısı haritası + zaman serisi grafikleri)
- Pass/Fail benzeri bir "yayılım riski" değerlendirmesi + hangi hücrelerin, ne zaman kritik sıcaklığa ulaştığının raporu
- PDF rapor çıktısı (mühendislik değerlendirme raporu formatında)

### V1.0 dışında bırakılanlar (V2+ için)
- Tam 3D CFD (gaz/duman yayılımı, venting gazlarının hareketi, basınç dalgası) — V1 sadece iletim-ağırlıklı (conduction-dominant) lumped/2D ısıl ağ modeli kullanır, tam Navier-Stokes çözümü yapmaz
- Mekanik hasar/gaz patlaması sonucu yapısal deformasyon
- Elektrokimyasal (SEI ayrışması, gaz oluşum kinetiği detaylı) tam modelleme — basitleştirilmiş Arrhenius tabanlı bir kaçak kinetiği kullanılacak
- Çoklu hücre kimyası kütüphanesinin tam otomatik kalibrasyonu (V1'de kullanıcı belirli parametreleri girer veya hazır bir "tipik NMC/LFP" kütüphanesinden seçer)
- Gerçek zamanlı IoT/BMS entegrasyonu

---

## 5. Teknik Model — Matematik Çekirdeği

### 5.1 Genel Yaklaşım: Lumped-Parameter Termal Ağ Modeli (Thermal Network Model)

Tam CFD yerine, her hücre bir "düğüm" (node) olarak modellenir. Düğümler arası ısı transferi iletim (conduction), doğal/zorlanmış konveksiyon ve (yüksek sıcaklıklarda) radyasyon direnç/kapasitans ağı üzerinden hesaplanır. Bu yaklaşım, tam 3D CFD'ye göre çözüm süresini saniyeler/dakikalar mertebesine indirir ve V1 kapsamı için yeterli doğruluğu sağlar (validasyon planı Bölüm 7'de).

Her hücre için enerji dengesi diferansiyel denklemi:

```
m_i * c_p,i * dT_i/dt = Q_gen,i(t) - Σ_j Q_cond,i→j - Q_conv,i - Q_rad,i
```

Burada:
- `m_i`: hücre i'nin kütlesi
- `c_p,i`: hücre i'nin özgül ısı kapasitesi
- `T_i`: hücre i'nin (lumped) sıcaklığı
- `Q_gen,i(t)`: hücre i içindeki ısı üretimi (normal çalışma kaybı + runaway sırasında ekzotermik reaksiyon ısısı)
- `Q_cond,i→j`: hücre i'den komşu hücre j'ye iletimle geçen ısı
- `Q_conv,i`: hücre i'den çevreye (hava/soğutma sıvısı) konveksiyonla giden ısı
- `Q_rad,i`: yüksek sıcaklıkta (runaway sırasında, genelde >150-200°C üzerinde anlamlı hale gelir) radyasyonla giden ısı

### 5.2 Hücreler Arası İletim Modeli

```
Q_cond,i→j = k_eff,ij * A_ij * (T_i - T_j) / d_ij
```

- `k_eff,ij`: hücre i-j arasındaki etkin ısı iletim katsayısı (separatör malzemesi, hava boşluğu, dolgu malzemesi kombinasyonuna göre seri direnç modeliyle hesaplanır)
- `A_ij`: temas/etkileşim yüzey alanı
- `d_ij`: hücreler arası mesafe

Seri termal direnç modeli (birden fazla katman varsa — örn. hücre kabuğu + hava boşluğu + separatör + komşu hücre kabuğu):

```
R_total,ij = R_shell,i + R_gap + R_separator + R_shell,j
k_eff,ij = d_ij / (A_ij * R_total,ij)
```

### 5.3 Konveksiyon Modeli

Doğal konveksiyon için Nusselt sayısı korelasyonları (Churchill-Chu, dikey/yatay silindir için standart korelasyonlar) kullanılarak taşınım katsayısı h hesaplanır:

```
Q_conv,i = h_i * A_surface,i * (T_i - T_ambient)
```

Aktif soğutma senaryosunda (soğutma plakası), plaka sabit sıcaklık veya sabit ısı akısı sınır şartı olarak modellenir; kullanıcı soğutma plakası temas alanı ve etkin h değerini (veya tipik bir soğutma sıvısı/malzeme seçip yazılımın hesaplamasını) girer.

### 5.4 Termal Kaçak Kinetiği: Basitleştirilmiş Arrhenius Modeli

Runaway'i tetikleyen ekzotermik reaksiyon ısı üretimi, basitleştirilmiş çok-adımlı Arrhenius kinetik modeliyle temsil edilir (literatürde yaygın kullanılan basitleştirilmiş modellere dayanır — SEI ayrışması, anot-elektrolit reaksiyonu, katot ayrışması gibi adımlar tek bir "etkin" reaksiyon adımına indirgenmiş halde):

```
dα/dt = A * exp(-E_a / (R * T)) * f(α)
Q_gen,runaway = m_active * ΔH_reaction * dα/dt
```

- `α`: reaksiyon ilerleme derecesi (0 = hiç reaksiyon yok, 1 = tamamlandı)
- `A`: pre-exponential faktör (kullanıcı tarafından hücre kimyasına göre kütüphaneden seçilir — NMC, LFP, NCA için literatürden alınan tipik değerler)
- `E_a`: aktivasyon enerjisi
- `R`: evrensel gaz sabiti
- `T`: hücre sıcaklığı (Kelvin)
- `f(α)`: reaksiyon modeli fonksiyonu (V1'de basit n'inci derece model: `f(α) = (1-α)^n`)
- `ΔH_reaction`: reaksiyon entalpisi (birim kütle başına açığa çıkan enerji — hücre kimyasına göre kütüphaneden)

Toplam ısı üretimi terimi normal çalışma kaybı (I²R, dahili direnç ısınması — V1'de basit sabit/kullanıcı girdisi olarak) ile runaway kaynaklı ekzotermik ısının toplamıdır:

```
Q_gen,i(t) = Q_ohmic,i + Q_gen,runaway,i(t)
```

### 5.5 Tetikleme ve Yayılım Kriteri

- **Tetikleme (onset):** Kullanıcı bir "tetikleyici hücre" seçer ve bu hücrenin belirli bir sıcaklığa (`T_onset`, tipik olarak literatürde 150-180°C civarı, kullanıcı/kütüphane tarafından ayarlanabilir) veya doğrudan bir "anlık ısı darbesi" (kJ cinsinden, harici bir tetikleyici — çivi testi benzeri — simüle etmek için) girdisiyle başlatılır.
- **Yayılım kriteri:** Komşu bir hücrenin sıcaklığı kendi `T_onset` değerine ulaşırsa, o hücre de kendi Arrhenius kinetiğiyle ısı üretmeye başlar (zincirleme reaksiyon). Yazılım her hücre için "runaway'e girdi mi, girmedi mi" ve "kaç saniyede girdi" bilgisini kaydeder.
- **Çıktı metriği:** "Propagation Time" (tetikleyici hücreden komşu hücreye yayılma süresi, UL 9540A'daki "time to propagation" kavramına paralel) ve "Pack-level Propagation Risk" (tüm pack'in kaç hücresinin runaway'e girdiği, hangi yol/patika üzerinden yayıldığı).

---

## 6. Yazılım Mimarisi

Mimari, AeroJoint'te kullanılan stack ile tutarlı tutulacak (öğrenme eğrisi ve kod tekrar kullanımı avantajı için): React+TypeScript frontend, FastAPI backend, Python tabanlı sayısal çözücü çekirdeği.

### 6.1 Genel Mimari Diyagramı (kavramsal)

```
[React + TS Frontend]
   │  (Axios / REST)
   ▼
[FastAPI Backend — API Katmanı]
   │
   ├──> [Pack Configuration Service]   (geometri, malzeme, hücre kimyası girdisi doğrulama)
   ├──> [Solver Orchestrator]          (async job kuyruğu, Celery/RQ benzeri worker)
   │        │
   │        ▼
   │   [Thermal Network Solver Core]   (Python/NumPy/SciPy — ODE çözücü)
   │        │
   │        ├── CellModel
   │        ├── PackGeometryBuilder
   │        ├── ThermalNetworkAssembler
   │        ├── ArrheniusKineticsEngine
   │        └── PropagationEvaluator
   │
   ├──> [Materials Library Service]    (hücre kimyası, separatör, soğutma malzemesi kütüphanesi)
   ├──> [Report Generator]             (PDF rapor — AeroJoint'teki modülle aynı mantık)
   └──> [Results Store]                (PostgreSQL + zaman serisi verisi için ayrı tablo/parquet dosyası)
```

### 6.2 Backend Modülleri (Python)

**`cell_model.py`**
```python
class CellModel:
    """Tek bir hücrenin fiziksel/termal/kinetik özelliklerini tutar."""
    def __init__(self, cell_id, chemistry, mass, cp, geometry, position):
        self.cell_id = cell_id
        self.chemistry = chemistry          # "NMC", "LFP", "NCA" vb. -> kütüphaneden parametre çeker
        self.mass = mass
        self.cp = cp
        self.geometry = geometry            # silindirik/prizmatik boyutlar
        self.position = position            # pack içindeki (x, y) konumu
        self.alpha = 0.0                    # reaksiyon ilerleme derecesi
        self.temperature = None             # simülasyon sırasında güncellenir
        self.state = "NORMAL"                # NORMAL / ONSET / RUNAWAY / BURNED_OUT

    def heat_generation(self, T, dt):
        """Ohmik + Arrhenius kinetik ısı üretimini hesaplar."""
        ...
```

**`pack_geometry.py`**
```python
class PackGeometryBuilder:
    """Kullanıcı girdisinden (satır/sütun, hücre aralığı, format) pack topolojisini kurar,
    komşuluk matrisini (adjacency matrix) ve hücreler arası mesafe/temas alanı verilerini üretir."""
    def build_adjacency(self, rows, cols, spacing, cell_format):
        ...
    def compute_contact_area(self, cell_i, cell_j, spacing):
        ...
```

**`thermal_network.py`**
```python
class ThermalNetworkAssembler:
    """Tüm hücreler için ısı transfer katsayı matrisini (iletim + konveksiyon) kurar
    ve sistemin ODE denklem setini (dT/dt = f(T, t)) oluşturur."""
    def assemble_conduction_matrix(self, cells, adjacency, materials_lib):
        ...
    def assemble_convection_terms(self, cells, cooling_config):
        ...
    def build_ode_system(self, cells, conduction_matrix, convection_terms, kinetics_engine):
        # scipy.integrate.solve_ivp ile zaman entegrasyonu için fonksiyon döndürür
        ...
```

**`kinetics_engine.py`**
```python
class ArrheniusKineticsEngine:
    """Her hücre için reaksiyon ilerleme derecesi ve ısı üretimini hesaplar."""
    def reaction_rate(self, alpha, T, chemistry_params):
        # dα/dt = A * exp(-Ea / (R*T)) * (1-alpha)^n
        ...
    def heat_release(self, dalpha_dt, mass_active, delta_H):
        ...
```

**`propagation_evaluator.py`**
```python
class PropagationEvaluator:
    """Simülasyon sonuçlarını tarayarak hangi hücrelerin runaway'e girdiğini,
    ne zaman girdiğini ve yayılım yolunu (propagation path) belirler."""
    def evaluate(self, time_series, cells, T_onset_map):
        # Her hücre için ilk kez T_onset'i aştığı zamanı bul
        # Propagation graph oluştur (tetikleyici -> hücre -> hücre)
        ...
    def compute_risk_score(self, propagation_graph, total_cells):
        ...
```

**`solver_orchestrator.py`**
```python
class SolverOrchestrator:
    """Async iş kuyruğu üzerinden simülasyonu tetikler, ilerleme durumunu takip eder
    (AeroSeat projesindeki QUEUED/RUNNING/COMPLETED durum mantığıyla tutarlı)."""
    async def run_simulation(self, job_id, pack_config):
        # 1. PackGeometryBuilder ile topoloji kur
        # 2. ThermalNetworkAssembler ile ODE sistemini kur
        # 3. scipy.integrate.solve_ivp (veya sertlik durumuna göre LSODA/BDF) ile zaman entegrasyonu
        # 4. PropagationEvaluator ile sonuçları değerlendir
        # 5. Sonuçları Results Store'a yaz, job durumunu COMPLETED yap
        ...
```

### 6.3 Veri Modeli (PostgreSQL şeması — özet)

- `packs` (pack_id, name, geometry_config JSON, created_at)
- `cells` (cell_id, pack_id FK, chemistry, mass, cp, position_x, position_y)
- `materials_library` (material_id, name, type [separator/coolant/shell], k_thermal, other_params JSON)
- `chemistry_library` (chemistry_id, name, A, Ea, delta_H, T_onset, n_order)
- `simulation_jobs` (job_id, pack_id FK, status, trigger_cell_id, trigger_config JSON, created_at, completed_at)
- `simulation_results` (result_id, job_id FK, cell_id FK, time_series_ref [parquet dosya yolu veya JSONB], entered_runaway_at, max_temperature)
- `reports` (report_id, job_id FK, pdf_path, generated_at)

### 6.4 API Endpoint Tasarımı (özet)

```
POST   /api/packs                     -> yeni pack geometrisi oluştur
GET    /api/packs/{pack_id}           -> pack detayını getir
POST   /api/materials/library         -> özel malzeme ekle (opsiyonel, V1'de çoğunlukla read-only kütüphane)
GET    /api/chemistry/library         -> mevcut hücre kimyası kütüphanesini listele
POST   /api/simulations               -> yeni simülasyon job'ı başlat (async)
GET    /api/simulations/{job_id}      -> job durumu ve ilerleme
GET    /api/simulations/{job_id}/results   -> zaman serisi + risk skoru sonuçları
GET    /api/simulations/{job_id}/report    -> PDF rapor indir
```

### 6.5 Frontend Modülleri (React + TS)

- `PackBuilder.tsx` — satır/sütun, hücre formatı, hücre aralığı, soğutma konfigürasyonu girişi (AeroJoint'teki GeometryEditor'a paralel)
- `ChemistryPicker.tsx` — hücre kimyası kütüphanesinden seçim veya özel parametre girişi (AeroJoint'teki MaterialManager mantığına paralel)
- `TriggerConfigurator.tsx` — tetikleyici hücre seçimi ve tetikleme yöntemi (sıcaklık eşiği / anlık ısı darbesi)
- `ThermalHeatmapView.tsx` — zamana bağlı 2D sıcaklık haritası (Plotly.js, AeroJoint'teki ContourPlot mantığına paralel — burada FEM stres yerine sıcaklık alanı gösterilir)
- `PropagationTimeline.tsx` — hangi hücrenin ne zaman runaway'e girdiğini gösteren zaman çizelgesi/graph görünümü
- `RiskSummaryCard.tsx` — pack-level risk skoru, kritik hücre, propagation time özeti (AeroJoint'teki Safety Margin gauge mantığına paralel)
- `ReportDownload.tsx` — PDF rapor indirme

---

## 7. Doğrulama (Validasyon) Stratejisi

- V1'de kendi fiziksel test verisi (golden dataset) yok — bu, AeroSeat projesinde de karşılaşılan bir kısıt, aynı şekilde ele alınmalı: sonuçlar "mühendislik tahmini" olarak sunulur, "kesin sertifikasyon garantisi" olarak değil.
- Literatürden alınan yayınlanmış thermal runaway propagation test verileri (akademik makaleler, NASA/NREL batarya güvenlik raporları, UL 9540A test raporları — halka açık örnekler) ile model çıktıları karşılaştırılarak kalibrasyon yapılacak.
- Basit doğrulama senaryoları: tek hücre adiyabatik ısınma testi (literatürdeki Accelerating Rate Calorimetry - ARC verisiyle karşılaştırma), iki hücreli minimal propagation testi.
- Model belirsizliği açıkça raporlanacak: "±X°C sıcaklık tahmin hatası", "±Y% propagation time belirsizliği" gibi bantlar (AeroSeat'teki correlation vektörü — magnitude/phase/shape/peak/RMS error — mantığına paralel bir yaklaşım burada da uygulanabilir).

---

## 8. Sertifikasyon / Regülasyon Bağlamı

- **UL 9540A:** Hücre, modül ve pack seviyesinde thermal runaway fire propagation testi standardı. V1'in ana referans noktası.
- **UN 38.3:** Lityum pillerin taşınması için güvenlik test standardı (bu proje kapsamında dolaylı referans — asıl odak UL 9540A tipi propagation testi).
- **IEC 62619:** Endüstriyel lityum-iyon pil güvenlik standardı.
- Ürün konumlandırması: "certification readiness / engineering pre-screening assessment" — AeroSeat'teki gibi, doğrudan sertifika vermez, sertifikasyon öncesi mühendislik değerlendirmesi sunar.

---

## 9. Geliştirme Yol Haritası

**Faz 1 — Çekirdek Fizik Motoru (4-6 hafta)**
- Tek hücre enerji dengesi + Arrhenius kinetik modelinin Python'da doğrulanması (ARC verisiyle basit karşılaştırma)
- Basit 2 hücreli iletim modeli prototipi

**Faz 2 — Pack Topolojisi ve Çoklu Hücre Ağı (4 hafta)**
- PackGeometryBuilder, ThermalNetworkAssembler modüllerinin tamamlanması
- N-hücreli pack için ODE sisteminin kurulması ve scipy.solve_ivp ile zaman entegrasyonu

**Faz 3 — Backend API ve Async Job Altyapısı (3-4 hafta)**
- FastAPI endpoint'leri, PostgreSQL şeması, async worker (Celery/RQ) entegrasyonu
- Materials/Chemistry kütüphanesinin ilk sürümü (NMC, LFP için tipik literatür parametreleri)

**Faz 4 — Frontend MVP (4-5 hafta)**
- PackBuilder, ChemistryPicker, TriggerConfigurator, ThermalHeatmapView bileşenleri
- AeroJoint'teki görsel dil ve UX kalıplarının bu projeye uyarlanması

**Faz 5 — Değerlendirme, Rapor ve Doğrulama (3 hafta)**
- PropagationEvaluator, RiskSummaryCard, PDF rapor modülü
- Literatür verisiyle ilk doğrulama turu, belirsizlik bantlarının raporlanması

**Faz 6 — Beta ve Geri Bildirim (sürekli)**
- Hedef kullanıcı segmentinden (küçük ESS/e-bisiklet/drone pack üreticileri) pilot kullanıcı bulma, geri bildirim toplama

---

## 10. İş Modeli / Ticarileştirme Yönü

- SaaS abonelik modeli (aylık veya proje/simülasyon-bazlı kredi sistemi)
- Hedef ilk müşteri profili: küçük-orta ölçekli e-mobilite ve ESS pack tasarım firmaları, mühendislik danışmanlık şirketleri
- Farklılaşma: "CFD uzmanı gerektirmeyen, dakikalar içinde sonuç veren, sertifikasyon-öncesi ön-tarama aracı" — büyük CFD paketleriyle rekabet etmiyor, onların çok pahalı/ağır kaldığı segmenti dolduruyor

---

## 11. Riskler ve Açık Sorular

- **Model doğruluğu riski:** Lumped-parameter yaklaşımın gerçek 3D ısı/gaz yayılım fiziğini ne kadar iyi temsil ettiği — özellikle venting gazı ve alev yayılımı gibi konveksiyon-ağırlıklı mekanizmalar V1'de modellenmiyor, bu açıkça kullanıcıya belirtilmeli.
- **Golden dataset eksikliği:** Kendi fiziksel test verisi yok; literatür verisiyle kalibrasyon yeterli güven verecek mi, yoksa bir noktada gerçek/üçüncü taraf test verisi lisanslamak/edinmek gerekecek mi — açık soru.
- **Kütüphane genişliği:** Farklı hücre kimyaları ve formatları için parametre kütüphanesinin ne kadar geniş olması gerektiği (V1'de sınırlı, muhtemelen sadece NMC/LFP tipik değerleri) — genişletme önceliklendirmesi kullanıcı geri bildirimine bağlı olmalı.
- **Regülasyon dili riski:** "Certification readiness" konumlandırmasının yasal/pazarlama dilinin, sertifika verdiği izlenimi yaratmayacak şekilde çok dikkatli kurgulanması gerekiyor (AeroSeat'te de karşılaşılan bir konu).

---

*Bu doküman, projenin ilk kapsamlı planlama aşamasıdır. Faz 1 başlamadan önce, özellikle Bölüm 5'teki kinetik model parametrelerinin (A, Ea, ΔH, T_onset) hangi literatür kaynaklarından alınacağı netleştirilmeli.*
