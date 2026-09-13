# Batarya Termal Kaçak (Thermal Runaway) Simülasyon Platformu
## Pazara Yönelik UI/UX, Model Doğrulama ve Stratejik Yol Haritası

**Sürüm:** V1.1  
**Tarih:** Eylül 2026  
**Standart Uyumu:** UL 9540A (BESS Cell-to-Cell Propagation Test) / UN 38.3  
**Mimari Referans:** SimScale Workbench SaaS CAE Modeli  

---

## 1. Executive Özeti (Yönetici Özeti)

Batarya termal runaway simülasyon aracı için **pazara yönelik UI/UX ve model yol haritası** hazırlanmıştır. Sol panelde proje ağacı, ortada 3D/2D hücre görselleştirici, sağda dinamik özellik panelleri, alt kısımda zaman çizelgesi ve performans göstergeleri (KPI) konumlandırılmıştır. Bu yapı, SimScale Workbench’in kullanıcı dostu tasarım prensipleri (ayar panellerinin görüntü üzerinde yüzer halde gösterilmesi, iş akışının tek ağaçta toplanması, sol panelde ağaç menü) esas alınarak oluşturulmuştur. 

Model tarafında UL 9540A test metodolojisine uygun hücre-çalışma doğrulama aşamaları ve literatür bazlı kinetik/dikey ısı geçiş verileri (NMC-katot DSC ve ARC verileri) kullanılarak doğrulama ve belirsizlik analizleri yürütülmektedir.

---

## 2. Aşamalı Yol Haritası (Phased Roadmap) ve Mevcut Durum

| Faz | Hedefler ve Özellikler | Durum |
| :--- | :--- | :---: |
| **Faz 0 – Temel (Çekirdek)** | Prototip UI iskeleti: sol proje ağacı, merkezde hücre gösterimi, sağ panel. FastAPI REST sözleşmesi (`GET/POST`). Arrhenius kinetik denklemi, termal direnç ağı ve SciPy LSODA stiff diferansiyel çözücü. | **TAMAMLANDI** |
| **Faz 1 – UI Geliştirme (Workbench)** | Responsive Grid yerleşim, CSS Dark Engineering SaaS tasarımı; Proje Ağacı (Simulation Tree), Dinamik Özellik Panelleri, Zaman Çizelgesi (Scrubber), KPI Çubuğu, Çok Seviyeli Kütüphane Yöneticisi Modalı. | **TAMAMLANDI** |
| **Faz 2 – 3D/2D Görselleştirme** | 3D perspektif hücre sahnesi ve 2D termal ağ Canvas'ı; renk skalalı ısı haritası, hücre bazlı seçim/hover, yayılım vektör çizgileri. İkinci aşama için Three.js / React Three Fiber altyapı hazırlığı. | **TAMAMLANDI** (CSS 3D + Canvas v1) |
| **Faz 3 – Simülasyon Entegrasyonu** | FastAPI ile tam entegrasyon; `POST /api/simulations/run` sonucu dinamik zaman çizelgesi güncellemesi. Canlı oynat/duraklat animasyonu, Chart.js sıcaklık eğrileri, otomatik UL 9540A PDF rapor üretimi. | **TAMAMLANDI** |
| **Faz 4 – Gelişmiş Özellikler** | “Advanced Physics” parametre paneli (Arrhenius $A, E_a, n, \Delta H$, gaz venting parametreleri $h_{vent}, T_{gas}$). Tasarım Çalışması (Design Study: Spacing sweep, separatör karşılaştırması). | **SIRADAKİ ADIM** |
| **Faz 5 – Doğrulama & Optimizasyon** | Bireysel hücre (ARC/DSC) deney verileriyle otomatik kalibrasyon, Monte Carlo belirsizlik/duyarlılık analizi, Pareto tabanlı çok amaçlı güvenlik optimizasyonu. | **PLANLANDI** |

---

## 3. UI Bileşenleri ve Davranış Matriksi

```text
┌───────────────────────────────────────────────────────────────────────────────────┐
│  TR  THERMAL RUNAWAY WORKBENCH       Proje Adı       📚 Kütüphane  📈 Grafik  ⚡ Başlat│
├──────────────┬────────────────────────────────────────────────────┬───────────────┤
│              │                                                    │               │
│ PROJE AĞACI  │              3D / 2D BATTERY WORKSPACE             │   ÖZELLİKLER  │
│              │                                                    │  (PROPERTIES) │
│ MODEL        │        [3D Modül]  [2D Termal Ağ]  [Heatmap]       │               │
│ ▣ Geometri ✓ │                                                    │ Hücre /       │
│ ◉ Kimya   ✓ │                 ◯   ◯   ◯   ◯                  │ Geometri /    │
│ ◌ Termal  ✓ │                 ◯  🔥   ◯   ◯                  │ Kimya /       │
│ ❄ Soğutma ○ │                 ◯   ◯   ◯   ◯                  │ Termal /      │
│ ⚡ Tetikleme✓│                                                    │ Soğutma /     │
│              │             [Sıcaklık Lejantı Barı]                │ Sonuçlar      │
│ ÇÖZÜM        │      25°C ───── 155°C ───── 210°C ───── 800°C+     │               │
│ ▶ Çözücü  ✓ │                                                    │               │
│ ▤ Sonuçlar✓ │                                                    │               │
├──────────────┴────────────────────────────────────────────────────┴───────────────┤
│  ▶ 0.00 s   ━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 90.00 s     Hız: 0.5x 1x 2x  │
│  Olaylar: 🔥 Tetikleyici #0 (t=1.8s, 659°C)  ➜  ⚡ #2 Hücre #1 (t=3.1s, 480°C)     │
├───────────────────────────────────────────────────────────────────────────────────┤
│ Tmax 659.4°C │ Kaçak: 3 / 9 │ Yayılım: 33.3% │ İlk Yayılma: 2.84s │ Risk: 46.4/100│
└───────────────────────────────────────────────────────────────────────────────────┘
```

| Bileşen | İşlev | Etkileşim & Davranış |
| :--- | :--- | :--- |
| **Sol Panel (Proje Ağacı)** | Geometri, kimya, termal, soğutma, abuse tetikleme, çözücü ve sonuç düğümleri. | Düğüm tıklandığında sağ panel anında ilgili alt bölüme geçer. Yapılandırılmış adımlar `✓`, opsiyoneller `○` gösterir. |
| **Merkez Görselleştirici** | 3D modül perspektifi ve 2D termal iletim ağı. Sıcaklık gradyanı, parlamalı kaçak efekti. | Hücreye tıklama (Picking) ile doğrudan hücre inceleme moduna geçiş; tetikleyici hücre atama. Zoom ve fit kontrolleri. |
| **Sağ Panel (Özellikler)** | Seçilen öğeye (hücre, geometri, kimya, soğutma vb.) ait parametre girişleri. | Çift yönlü senkronizasyon: Değer değiştikçe ortadaki 3D/2D batarya geometrisi ve kimya verisi anlık güncellenir. |
| **Zaman Çizelgesi (Timeline)** | Simülasyon zaman ilerlemesini gösterir; sıralı olaylar (onset, runaway) listelenir. | Oynat/Durdur (`▶`/`⏸`), Başa Sar (`⏮`), Scrubber ile zamanda gezinme, 0.5x-2x hız ayarı. |
| **KPI Çubuğu** | $T_{max}$, Etkilenen Hücre Sayısı, Yayılım Yüzdesi, İlk Yayılma Süresi, UL 9540A Risk Skoru. | Ekranın altında sürekli sabit kalır; simülasyon tamamlandığında otomatik güncellenir. |

---

## 4. API Sözleşmesi Mimarisi

- `GET /api/chemistry/library`: Kullanılabilir kinetik Arrhenius modellerini listeler.
- `GET /api/materials/library`: Termal bariyer, separatör ve hava/dolgu malzemelerini döner.
- `GET /api/formats/library`: Silindirik (18650, 21700, 4680) ve prizmatik hücre formatlarını döner.
- `POST /api/simulations/run`: Modül geometrisi, kimyası, termal şartları ve tetikleme senaryosunu içeren JSON yükü alır; simülasyonu çözer.
- `GET /api/simulations/{job_id}/results`: Zaman serisi sıcaklık matrisini, reaksiyon dönüşümünü ($\alpha$) ve UL 9540A değerlendirme raporunu döner.
- `GET /api/simulations/{job_id}/report`: Tam teşekküllü mühendislik PDF raporunu indirir.

---

## 5. Doğrulama ve Fidelity Katmanları

| Doğrulama Katmanı | İçerik ve Kabul Kriterleri |
| :--- | :--- |
| **Bileşen Testleri** | Kinetik Arrhenius reaksiyon hızı sınırları ($0 \le \alpha \le 1$), iletkenlik matris simetrisi ($G_{ij} = G_{ji}$), adyabatik denge durumunda enerji korunumu ($\sum Q_{in} = \sum Q_{out}$). |
| **Tek Hücre ARC/DSC** | ARC (Accelerated Rate Calorimetry) deney veri eşleştirmesi: $T_{onset} = 155^\circ\text{C}$, $T_{trigger} = 210^\circ\text{C}$, NMC katot $780\text{ J/g}$ entalpi çıkışı. |
| **Modül Yayılım Testi** | UL 9540A test metodolojisine uygun tek hücre termal kaçak zorlaması; komşu hücrelerin $T_{onset}$ eşiğini aşıp aşmadığının kontrolü. |
| **Belirsizlik Analizi** | Literatür varyansına dayalı $\pm 10^\circ\text{C}$ sıcaklık ve $\pm 12\%$ yayılım süresi belirsizlik bandı. |
| **Tasarım Optimizasyonu** | Spacing sweep (hücre aralığı taraması), aerojel/mika bariyer kalınlık optimizasyonu. |

---

## 6. Sonraki Adım: Faz 4 & Faz 5 Odak Alanları

1. **Gelişmiş Fizik Paneli ("Advanced Physics Mode"):**
   - Arrhenius $A$, $E_a$, $n$, $\Delta H$, gaz tahliye $h_{vent}$, gaz sıcaklığı $T_{gas}$, yüzey emmisivitesi $\varepsilon$ değerlerinin doğrudan düzenlenmesi.
2. **Tasarım Çalışması Modülü (Design Study / Spacing Sweep):**
   - Kullanıcının tek tıklamayla $1.5\text{ mm}$, $2.0\text{ mm}$, $2.5\text{ mm}$ ve $3.0\text{ mm}$ aralıklarını aynı anda koşturup en güvenli tasarımı otomatik puanlaması.
3. **Three.js / WebGL Yüksek Çözünürlüklü 3D Görselleştirici:**
   - 100+ hücreli büyük paketler için GPU hızlandırmalı Three.js Canvas motoru.
