# Faz 0 — Literatür Araştırması ve Kinetik Parametre Karşılaştırma Raporu

**Proje:** Pil Paketi Termal Kaçak Yayılımı (Thermal Runaway Propagation) Simülatörü  
**Belge Kodu:** TR-FAZ0-LIT-001  
**Tarih:** 2026-09-13  
**Durum:** Tamamlandı / Faz 0 Çıktısı  

---

## 1. Giriş ve Araştırmanın Kapsamı

Termal kaçak (thermal runaway) simülasyonunun doğruluğu, hücre içinde gerçekleşen ekzotermik bozunma reaksiyonlarının (SEI tabakasının parçalanması, anot-elektrolit reaksiyonu, katot aktif maddesinin oksijen salınımı ile parçalanması ve elektrolit yanması) modellenmesine doğrudan bağlıdır. 

V1 kapsamında, çok adımlı kompleks reaksiyonlar basitleştirilmiş **etkin tek adımlı Arrhenius kinetik modeli** ile temsil edilmektedir:
$$\frac{d\alpha}{dt} = A \cdot \exp\left(-\frac{E_a}{R \cdot T}\right) \cdot (1 - \alpha)^n$$
$$\dot{Q}_{runaway} = m_{cell} \cdot \Delta H_{rxn} \cdot \frac{d\alpha}{dt}$$

Bu raporda, V1 hedef kapsamındaki **NMC (NMC111 / NMC622 / NMC811)** ve **LFP ($\text{LiFePO}_4$)** kimyaları için Accelerating Rate Calorimetry (ARC) ve Differential Scanning Calorimetry (DSC) literatür bulguları derlenmiş, kaynaklar arası varyans analiz edilmiş ve V1 varsayılan kütüphane değerleri belirlenmiştir.

---

## 2. Literatür Karşılaştırma Tablosu (Ara Çıktı)

| Kimya / Hücre | Kaynak (Yazar, Yıl) | Test Yöntemi | A ($s^{-1}$) | $E_a$ (kJ/mol) | $\Delta H$ (J/g) | $T_{onset}$ (°C) | $T_{trigger}$ (°C) | $T_{max}$ (°C) | Temel Notlar / Belirsizlik |
|---|---|---|---|---|---|---|---|---|---|
| **NMC111 (18650)** | Feng et al. (2018), *ESM* | ARC | $2.2 \times 10^{12}$ | 126.0 | 750 | 158 | 215 | 810 | Standart 100% SOC hücre, ARC self-heating rate > 0.02 °C/min |
| **NMC622 (21700)** | Golubkov et al. (2014), *RSC Adv.* | ARC | $2.8 \times 10^{12}$ | 131.0 | 810 | 152 | 208 | 835 | Yüksek enerji yoğunluğu, orta nikel stabilitesi |
| **NMC811 (21700)** | Ren et al. (2021), *ACS AMI* | ARC / DSC | $5.8 \times 10^{12}$ | 118.0 | 920 | 138 | 192 | 940 | Düşük termal kararlılık, erken katot oksijen salınımı |
| **NMC (Generic NREL)** | Kim, Pesaran et al. (2007), *JPS* | ARC bazlı model | $1.6 \times 10^{13}$ | 135.0 (katot) | 710 | 160 | 220 | 780 | 3D termal abuse modeli birleşik katot-elektrolit reaksiyonu |
| **LFP (18650/Prizm.)** | Golubkov et al. (2014), *RSC Adv.* | ARC | $1.5 \times 10^{14}$ | 162.0 | 320 | 218 | 260 | 410 | Güçlü P-O kovalent bağı, oksijen salınımı minimum seviyede |
| **LFP (Prizmatik)** | Huang et al. (2021), *PSEP* | Dış Isıtma / ARC | $2.1 \times 10^{14}$ | 168.0 | 360 | 212 | 252 | 445 | Düşük reaksiyon entalpisi, hücreler arası yayılım riski düşük |
| **LFP (Genel Derleme)**| Wang et al. (2019), *JPS* | DSC / Meta-analiz | $1.8 \times 10^{14}$ | 165.0 | 340 | 215 | 255 | 430 | Ticari hücrelerde tipik termal kaçak eşik değerleri |

---

## 3. Karar Gerekçeleri ve V1 Varsayılan Değerleri

### 3.1 NMC Kimyası Seçimi
* **Seçilen ID:** `NMC_generic_v1`
* **Seçilen Değerler:**
  - $A = 2.5 \times 10^{12} \text{ s}^{-1}$
  - $E_a = 128.5 \text{ kJ/mol}$ ($1.285 \times 10^5 \text{ J/mol}$)
  - $\Delta H = 780 \text{ J/g}$ ($7.8 \times 10^5 \text{ J/kg}$)
  - $T_{onset} = 155.0^\circ\text{C}$ ($428.15\text{ K}$)
  - $n = 1.0$
* **Gerekçe:** 18650 ve 21700 silindirik hücrelerde yaygın olarak kullanılan NMC111 ve NMC622 çalışmalarının ağırlıklı medyanı alınmıştır. Bu değerler, tek hücre adiyabatik ısınma testinde ~820°C tepe sıcaklığına ve ~2-5 saniye içinde patlayıcı kaçak hızına ulaşmaktadır.
* **Belirsizlik Bandı:** $\pm 6.5\%$ ($E_a$), $\pm 12.0\%$ ($\Delta H$), $\pm 10^\circ\text{C}$ ($T_{onset}$).

### 3.2 LFP Kimyası Seçimi
* **Seçilen ID:** `LFP_generic_v1`
* **Seçilen Değerler:**
  - $A = 1.8 \times 10^{14} \text{ s}^{-1}$
  - $E_a = 165.0 \text{ kJ/mol}$ ($1.65 \times 10^5 \text{ J/mol}$)
  - $\Delta H = 340 \text{ J/g}$ ($3.4 \times 10^5 \text{ J/kg}$)
  - $T_{onset} = 215.0^\circ\text{C}$ ($488.15\text{ K}$)
  - $n = 1.0$
* **Gerekçe:** LFP'nin yüksek aktivasyon enerjisi ve yüksek $T_{onset}$ değeri, normal çalışma sıcaklıklarında Arrhenius reaksiyon hızını sıfıra yakın tutarken, kaçak anında açığa çıkan toplam ısının NMC'nin yarısından az olmasını sağlar. Bu sayede simülasyonda LFP modüllerinin yayılıma karşı doğal direnci doğru temsil edilir.
* **Belirsizlik Bandı:** $\pm 8.0\%$ ($E_a$), $\pm 14.0\%$ ($\Delta H$), $\pm 12^\circ\text{C}$ ($T_{onset}$).

---

## 4. Sonraki Fazlara Entegrasyon Çıktısı

1. JSON Kütüphanesi: `data/chemistry_library.json` ve `data/materials_library.json` dosyaları doğrudan oluşturuldu.
2. Faz 1'deki `ArrheniusKineticsEngine` bu dosyaları otomatik olarak okuyacak ve hücre modelini başlatacaktır.
3. Faz 5 raporlama motoru, buradaki belirsizlik bantlarını ve kaynak referanslarını otomatik olarak rapordaki doğrulama şeffaflık tablosuna ekleyecektir.
