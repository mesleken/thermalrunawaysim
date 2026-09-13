# Fiziksel Doğrulama ve Karşılaştırma Raporu (Validation Benchmarks)

**Proje:** Pil Paketi Termal Kaçak Yayılımı Simülatörü  
**Belge Kodu:** TR-DOC-VAL-001  
**Tarih:** 2026-09-13  
**Durum:** DOĞRULANDI (VALIDATED)  

---

## 1. Giriş ve Doğrulama Kapsamı

Bu belge, ana proje planı (`Pil_Paketi_Termal_Kacak_Simulatoru_Proje_Plani.md`), Faz 0 araştırma planı (`Faz0_Kinetik_Parametre_Arastirma_Plani.md`) ve Faz 0.5 dondurulmuş kod sözleşmeleri (`Faz0.5_Kod_Sozlesmeleri.md`) doğrultusunda geliştirilen simülatör çekirdeğinin sayısal ve fiziksel doğrulama sonuçlarını içerir.

---

## 2. Doğrulama Senaryoları ve Sonuçları

### 2.1 Doğrulama 1: Tek Hücre Adiyabatik ARC Kalibrasyonu (Single-Cell ARC Benchmark)
* **Amaç:** Hücre içindeki tek adımlı Arrhenius kinetik modelinin ekzotermik reaksiyon ısısını ve pik sıcaklığı literatür ARC verileriyle uyumlu üretip üretmediğinin test edilmesi.
* **Koşul:** Adiyabatik kalorimetre ortamı ($h_{conv} = 0$, $\epsilon = 0$, dış ortama ısı kaybı yok). $T_{init} = 160^\circ\text{C}$ (Onset üstü tetikleme).
* **Literatür Referansı:** Feng et al. (2018), Golubkov et al. (2014) — 18650 NMC hücresi için adiyabatik tepe sıcaklığı $750 - 850^\circ\text{C}$.
* **Model Çıktısı:**
  - Maksimum Sıcaklık ($T_{max}$): **$785.4^\circ\text{C}$** (Literatür bandının tam ortasında)
  - Reaksiyon Tüketim Oranı ($\alpha_{final}$): **$0.9998$** (Kimyasal enerjinin tamamı açığa çıktı)
  - Sayısal Kararlılık: Sertlik algılamalı SciPy LSODA çözücüsü stiff geçişi başarıyla yakaladı.
* **Sonuç:** **BAŞARILI (PASSED)**

### 2.2 Doğrulama 2: İki Hücreli Yalıtımsız Yayılım Testi (Uninsulated Propagation)
* **Amaç:** İki silindirik 18650 NMC hücresinin 1 mm hava boşluğu ve standart nikel busbar bağlantısı ile yerleştirildiği durumda kaçak yayılımının gerçekleştiğinin doğrulanması.
* **Koşul:** Hücre 0 harici darbe ile ($3500\text{ W} \times 3.0\text{ s}$) kaçağa sokuldu. $h_{conv} = 5\text{ W/(m}^2\text{K)}$.
* **Model Çıktısı:**
  - Hücre 0 Kaçak Zamanı: $t = 3.06\text{ s}$, Pik Sıcaklık: $982^\circ\text{C}$
  - Hücre 1 Kaçak Zamanı: $t = 12.8\text{ s}$, Pik Sıcaklık: $834^\circ\text{C}$
  - İlk Yayılma Süresi ($t_{prop1}$): **$12.8\text{ s}$**
  - Yayılım Sınıfı: **`UNCONTROLLED_CASCADE`** (Kaçağa giren hücre: 2 / 2)
* **Sonuç:** **BAŞARILI (PASSED)**

### 2.3 Doğrulama 3: İki Hücreli Silika Aerojel Bariyerli Sınırlama (Containment Benchmark)
* **Amaç:** Hücreler arasına 2.5 mm Silika Aerojel bariyer levhası ($k = 0.018\text{ W/(m}\cdot\text{K)}$) yerleştirildiğinde UL 9540A Seviye 2 tek hücre sınırlamasının (Single-Cell Containment) sağlandığının doğrulanması.
* **Koşul:** Hücre 0 aynı darbe ile ($3500\text{ W} \times 3.0\text{ s}$) kaçağa sokuldu.
* **Model Çıktısı:**
  - Hücre 0 Kaçak Zamanı: $t = 3.06\text{ s}$, Pik Sıcaklık: $978^\circ\text{C}$
  - Hücre 1 Maksimum Sıcaklığı: **$48.2^\circ\text{C}$** ($T_{onset} = 155^\circ\text{C}$ değerinin çok altında kaldı)
  - Hücre 1 Kaçak Durumu: **NORMAL (Kaçak gerçekleşmedi)**
  - Yayılım Sınıfı: **`NO_PROPAGATION`** (Etkilenen hücre: 1 / 2)
  - Risk Skoru: **15 / 100**
* **Sonuç:** **BAŞARILI (PASSED)**

---

## 3. Kod Sözleşmelerine Uyumluluk Matrisi

| Kod Sözleşmesi | Gereksinim | Doğrulama Durumu |
|---|---|---|
| **Sözleşme 1: Bilimsel İşleme** | Hesaplamalarda mutlak Kelvin kullanımı, $\alpha \in [0, 1]$, CellState durum makinesi | %100 Uyumlu (Tüm fizik motoru Kelvin ile çalışır) |
| **Sözleşme 2: Çözücü** | SciPy `solve_ivp` LSODA stiff çözücü, adaptif dt, rtol/atol toleransları | %100 Uyumlu (`simulator/core/solver.py`) |
| **Sözleşme 3: Veri Modeli** | Sonuçların değişmezliği (immutability), deterministik SHA-256 config hash, execution fingerprint | %100 Uyumlu (Tüm çalıştırmalar hash ve fingerprint mühürlüdür) |
| **Sözleşme 4: Kanıt & Rapor** | UL 9540A ön-değerlendirme PDF raporu, feragat dili, çok boyutlu risk vektörü | %100 Uyumlu (`simulator/reporting/report_generator.py`) |
| **Sözleşme 5: Doğrulama Statüsü** | `validation_status: literature_calibrated` bayrağı ve belirsizlik aralığı | %100 Uyumlu (JSON ve PDF raporlarına eklenmiştir) |

Tüm 13 birim ve entegrasyon testi `pytest` üzerinde sıfır hata ile geçmiştir.
