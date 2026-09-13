# Faz 0.5 — Dondurulmuş Kod Sözleşmeleri (Frozen Code Contracts)

**Proje:** Pil Paketi Termal Kaçak Yayılımı (Thermal Runaway Propagation) Simülatörü  
**Belge Kodu:** TR-FAZ05-CONTRACT-001  
**Tarih:** 2026-09-13  
**Durum:** DONDURULDU (FROZEN)  

Bu belge, Faz 1 kodlamasına başlamadan önce sistemin matematiksel, mimari, veri modeli ve raporlama kurallarını bağlayıcı şekilde tanımlar. Faz 1 ve sonraki fazlarda geliştirilen tüm modüller bu sözleşmelere tam uyumlu olmak zorundadır.

---

## Sözleşme 1: Bilimsel İşleme Sözleşmesi (Scientific Processing Contract)

### 1.1 Birim Standardı
* **Sıcaklık:** Hesaplama motoru içindeki istisnasız tüm sıcaklık değişkenleri **Kelvin ($K$)** cinsinden temsil edilecektir. Kod içinde ara işlemlerde °C kullanımı kesinlikle yasaktır. Celsius dönüşümü yalnızca UI gösterimi ve PDF rapor çıktısında yapılacaktır.
* **Zaman:** Saniye ($s$).
* **Kütle:** Kilogram ($kg$) veya spesifik enerji hesaplamasında açıkça belirtilen gram ($g$).
* **Enerji / Isı Akısı:** Joule ($J$), Watt ($W$), $W/(m \cdot K)$, $J/(kg \cdot K)$.
* **Gaz Sabiti:** $R = 8.314462618 \text{ J/(mol}\cdot\text{K)}$.

### 1.2 Hücre Durum Değişkenleri
Her hücre nesnesi en az aşağıdaki durum değişkenlerini barındırır:
* $T$: Sıcaklık (K)
* $\alpha$: Reaksiyon ilerleme derecesi, $\alpha \in [0.0, 1.0]$. $\alpha=0$ (bozunma başlamadı), $\alpha=1$ (tüm aktif madde tükendi).
* `state`: Hücre durum makinesi enumu:
  - `NORMAL`: $T < T_{onset}$, $\alpha < 0.01$
  - `ONSET`: $T_{onset} \le T < T_{trigger}$, kendi kendine ısınma başladı
  - `RUNAWAY`: $T \ge T_{trigger}$ veya $\frac{dT}{dt} \ge 1.0 \text{ K/s}$, kontrolsüz ekzotermik patlama
  - `BURNED_OUT`: $\alpha \ge 0.999$, kimyasal enerji tükendi, soğuma fazı

### 1.3 Fiziksel Kapsam Sınırları (V1 Kapsam İçi / Dışı)
* **Kapsam İçi:**
  - Hücre-hücre iletimi (seri termal direnç: hücre kabuğu + separatör + hava boşluğu)
  - Hücre-çevre doğal/zorlanmış konveksiyonu ($h_{conv} \cdot A \cdot (T - T_{amb})$)
  - Hücre-soğutma plakası aktif ısı çekişi ($h_{cool} \cdot A_{contact} \cdot (T - T_{cool})$)
  - Yüksek sıcaklık yüzey radyasyonu ($\sigma \cdot \epsilon \cdot A \cdot (T^4 - T_{amb}^4)$)
  - Arrhenius 1. derece etkin ekzotermik reaksiyon kinetiği
* **Kapsam Dışı (V1):**
  - Venting gazlarının 3D CFD Navier-Stokes akış dinamiği
  - Patlama/şok dalgası ve mekanik deformasyon
  - Çok adımlı kompleks elektrokimyasal SEI çözünme modelleri

### 1.4 Zaman Adımı Politikası
* Sistem sert (stiff) diferansiyel denklem karakterine sahip olduğundan, **sabit zaman adımı ($dt$) ile integrasyon yapılması yasaktır**.
* Çözücü, adaptif zaman adımı (`adaptive step-size`) kullanacaktır.

---

## Sözleşme 2: Çözücü Sözleşmesi (Solver Contract)

### 2.1 Seçilen Çözücü Yöntemi
* V1 için matematiksel çözücü olarak `scipy.integrate.solve_ivp` kullanılacaktır.
* Varsayılan metot: **LSODA** (veya stiff fazda **Radau / BDF**).
* Erken soyutlama karmaşıklığından kaçınmak amacıyla V1'de doğrudan SciPy ODE altyapısına bağlanılacaktır.

### 2.2 Tolerans ve Kararlılık Parametreleri
* `rtol` (bağıl tolerans): $1.0 \times 10^{-5}$
* `atol` (mutlak tolerans): $1.0 \times 10^{-6}$
* `max_step`: $0.5 \text{ s}$ (tetikleme fazında kaçırmayı önlemek için)
* `first_step`: $1.0 \times 10^{-4} \text{ s}$
* Bu değerler `simulator/core/constants.py` dosyasında merkezi olarak tanımlanacak, kod içinde "magic number" olarak gezmeyecektir.

---

## Sözleşme 3: Veri Modeli ve Değişmezlik Sözleşmesi (Data Model & Immutability Contract)

### 3.1 Sonuçların Değişmezliği (Immutability)
* Bir simülasyon işi (`simulation_job`) tamamlandıktan (`COMPLETED`) sonra üretilen sonuç kayıtları (`simulation_results`) asla güncellenemez veya üzerine yazılamaz.
* Yeniden çalıştırma talepleri daima yeni bir `job_id` ile kaydedilir.

### 3.2 Configuration Hash (Determinizm Garantisi)
* Her simülasyon girdisi (hücre dizilimi, geometri, malzeme seçimleri, tetikleyici hücre ve parametreleri) deterministik bir JSON stringine serileştirilir ve **SHA-256 hash'i** (`config_hash`) üretilir.
* Aynı girdi hash'i ile çalıştırılan simülasyonların sayısal determinizm sınırları dahilinde birebir aynı sonucu vermesi garanti edilir.

### 3.3 Execution Fingerprint (İzlenebilirlik)
* Her çalıştırmada solver sürümü, Python sürümü ve kullanılan parametre kütüphanesi sürümü/hash'i birleştirilerek bir `execution_fingerprint` üretilir ve sonuç nesnesine mühürlenir.

---

## Sözleşme 4: Kanıt ve Raporlama Sözleşmesi (Evidence & Reporting Contract)

### 4.1 Rapor Zorunlu Alanları
Üretilen her PDF mühendislik raporu aşağıdaki alanları içermek zorundadır:
1. `config_hash` ve `execution_fingerprint`
2. Kullanılan kinetik kütüphane versiyonu ve akademik kaynak referansları
3. Belirsizlik payı beyanı ($\pm X^\circ\text{C}$ ve $\pm Y\%$ propagation süresi)
4. Zaman serisi grafikleri ve 2D sıcaklık yayılım ısı haritası

### 4.2 Regülasyon ve Sorumluluk Dili Politikası
* **KATI KURAL:** Raporda veya API çıktılarında hiçbir koşulda "sertifikasyon garantisi verilmiştir", "UL 9540A sertifikalandırılmıştır" veya benzeri kesin garanti ifadeleri kullanılamaz.
* **STANDART DİL:** "Mühendislik Ön-Değerlendirmesi / Certification Readiness Screening (UL 9540A / UN 38.3 Ön İnceleme Raporu)" başlığı ve formatı standart olarak uygulanır.

### 4.3 Çok Boyutlu Risk Vektörü
Risk skoru tek bir basit "Geçti/Kaldı" boolean değeri yerine çok boyutlu bir vektör olarak sunulur:
* `propagation_time_s`: İlk komşuya yayılma süresi (veya yayılmadıysa `Infinity`)
* `affected_cells_count` / `total_cells`: Kaçağa giren toplam hücre oranı
* `propagation_classification`:
  - `NO_PROPAGATION`: Yalnızca tetikleyici hücre yandı, komşular $T_{onset}$ altında kaldı.
  - `LOCAL_CONTAINED`: Komşu 1-2 hücre etkilendi, ancak yayılım durduruldu.
  - `UNCONTROLLED_CASCADE`: Modülün %50'den fazlasına yayılan zincirleme kaçak.
* `peak_module_temperature_C`: Modül içindeki maksimum ulaşılan sıcaklık.

---

## Sözleşme 5: Doğrulama ve Referans Veri Seti Sözleşmesi (Validation Contract)

### 5.1 Doğrulama Durumu İşareti
* Simülasyon sonuç nesnelerinde ve raporlarda açık bir `validation_status` bayrağı bulunur:
  - `literature_calibrated`: V1 varsayılan durumu (yayınlanmış akademik ARC/DSC verileriyle kalibre edilmiş parametreler).
  - `physically_validated`: Kullanıcının veya laboratuvarın gerçek test eğrileriyle doğrulandığı durum.
* Kullanıcıya sonucun güven düzeyi açık bir rozet/etiket olarak sunulur.

---

## Karar Kaydı Özeti

| Karar | Seçilen Yaklaşım | Alternatif | Neden Seçildi? |
|---|---|---|---|
| Sıcaklık Birimi | Kelvin (K) | Santigrat (°C) | Arrhenius $E_a / (RT)$ ve radyasyon $T^4$ formüllerinde birim hatasını sıfırlamak için |
| Çözücü Mimarisi | Doğrudan SciPy `solve_ivp` | Generic Solver Abstraction | V1 için aşırı mühendislikten kaçınmak, güvenilir ve hızlı teslim sağlamak |
| Zaman Entegrasyonu | Adaptif LSODA / Radau | Sabit dt Euler/RK4 | Kaçak anındaki saniyenin binde biri mertebesindeki stiff geçişleri yakalamak için |
| Sonuç Saklama | Immutable + Config Hash | Mutable DB update | Mühendislik izlenebilirliği ve determinizm denetimi için |
| Rapor Dili | Certification Readiness | Sertifikasyon Uygunluk Onayı | Yasal sorumluluk ve regülasyon uyumu riskini önlemek için |

Bu sözleşmeler Faz 1 kodlama süreci için **DONDURULMUŞTUR**.
