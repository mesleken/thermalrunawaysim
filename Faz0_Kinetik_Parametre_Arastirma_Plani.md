# Sonraki Adım Planı: Kinetik Model Parametrelerinin Belirlenmesi
## Faz 0 — Literatür Araştırması ve Parametre Kütüphanesi Hazırlığı

*(Ana proje planındaki [Pil Paketi Termal Kaçak Simülatörü] Bölüm 11'de belirtilen açık soruya cevap: A, Ea, ΔH, T_onset parametreleri hangi kaynaklardan alınacak — Faz 1 başlamadan önce tamamlanması gereken hazırlık aşaması.)*

---

## 1. Bu Adımın Amacı ve Neden Önce Bu Yapılmalı

Faz 1'deki "tek hücre enerji dengesi + Arrhenius kinetik modelinin doğrulanması" çalışması, elde güvenilir `A` (pre-exponential faktör), `Ea` (aktivasyon enerjisi), `ΔH` (reaksiyon entalpisi) ve `T_onset` (kaçak başlangıç sıcaklığı) değerleri olmadan yapılamaz. Bu parametreler yanlış/temelsiz seçilirse, üzerine kurulan tüm ısıl ağ modeli ve propagation tahminleri anlamsızlaşır. Bu yüzden kod yazımından önce, bu adımın ayrı ve öncelikli bir "Faz 0" olarak ele alınması gerekiyor.

---

## 2. Kapsam

### 2.1 Bu adımda yapılacaklar
- Hücre kimyası başına (önce NMC ve LFP ile sınırlı, V1 kapsamına paralel) yayınlanmış Accelerating Rate Calorimetry (ARC) ve Differential Scanning Calorimetry (DSC) çalışmalarının taranması
- Her kaynaktan çıkan A, Ea, ΔH, T_onset değerlerinin bir karşılaştırma tablosunda toplanması (aynı kimya için farklı makalelerin ne kadar farklı sonuç verdiğinin görülmesi)
- Kaynaklar arası tutarsızlık varsa, hangi aralığın (range) "V1 için makul varsayılan" olarak kullanılacağına karar verilmesi
- Seçilen parametrelerin belirsizlik payının (±%) açıkça not edilmesi — bu değerler ana proje planındaki Bölüm 7 (Doğrulama Stratejisi) ile doğrudan bağlantılı
- Parametre kütüphanesinin ilk sürümünün (V1: sadece NMC + LFP) yapılandırılmış bir formatta (JSON/YAML şeması) taslağının çıkarılması — bu, Faz 3'teki `chemistry_library` veritabanı tablosunun doğrudan girdisi olacak

### 2.2 Bu adımda yapılmayacaklar
- Kendi ARC/DSC deneyini yapmak (bu aşamada bütçe/laboratuvar erişimi kapsamda değil — ileride "golden dataset" ihtiyacı olarak ayrı ele alınacak, ana plan Bölüm 11'de zaten not edildi)
- NCA, LTO gibi diğer kimyaların parametrelerini toplamak (V1 kapsamı dışında, sonraki fazlara bırakılıyor)
- Model kodlamasına başlamak (bu adım tamamen araştırma/veri toplama, Faz 1 kodlaması bu adımın çıktısını bekliyor)

---

## 3. Metodoloji

### 3.1 Kaynak Tarama Sırası
1. **Akademik literatür** — Google Scholar, ScienceDirect, IEEE Xplore üzerinden "lithium-ion battery thermal runaway kinetics ARC", "NMC thermal runaway activation energy", "LFP DSC onset temperature" gibi sorgularla tarama
2. **Halka açık güvenlik raporları** — NREL (National Renewable Energy Laboratory), Sandia National Labs, NASA batarya güvenlik yayınları
3. **Standart/regülasyon destek dokümanları** — UL 9540A test metodolojisi dokümanlarında referans verilen çalışmalar
4. **Yaygın kullanılan simülasyon çalışmalarının referans aldığı kaynaklar** — thermal runaway simülasyonu üzerine yayınlanmış makalelerin "kullanılan parametreler" tablolarının kendisi (bu makaleler zaten birden fazla birincil kaynağı harmanlamış oluyor, hızlı bir başlangıç noktası sağlar)

### 3.2 Her Kaynak İçin Kaydedilecek Bilgiler
- Kaynak (yazar, yıl, dergi/rapor)
- Test edilen hücre kimyası ve formatı (18650 NMC, prizmatik LFP, vb.)
- Test yöntemi (ARC, DSC, nail penetration, vb. — yöntem farkı sonuçları etkiler, bu yüzden kaydedilmeli)
- Raporlanan A, Ea, ΔH değerleri (birimleriyle birlikte — birim tutarlılığı kritik, örn. Ea bazen kJ/mol bazen J/mol raporlanıyor)
- Raporlanan T_onset / self-heating başlangıç sıcaklığı
- Belirtilmişse hata payı / tekrarlanabilirlik notu

### 3.3 Karar Verme Kriteri
Birden fazla kaynak farklı değerler veriyorsa:
- Test yöntemi ve hücre formatı en çok V1 kapsamındaki tipik kullanım senaryosuna (küçük-orta ölçekli e-mobilite/ESS pack'lerinde yaygın format) yakın olan kaynak öncelikli alınır
- Aykırı (outlier) değerler not edilir ama ortalama/tipik aralık belirlenirken dışlanabilir
- Nihai seçilen değer + kaynak + neden seçildiği kütüphane dokümantasyonuna yazılır (şeffaflık için — ileride biri "bu sayı nereden geldi" diye sorduğunda cevap hazır olmalı)

---

## 4. Çıktı Formatı

### 4.1 Karşılaştırma Tablosu (ara çıktı)
| Kimya | Kaynak | Yöntem | A (1/s) | Ea (kJ/mol) | ΔH (J/g) | T_onset (°C) | Not |
|---|---|---|---|---|---|---|---|
| NMC | ... | ARC | ... | ... | ... | ... | ... |
| LFP | ... | DSC | ... | ... | ... | ... | ... |

### 4.2 Nihai Parametre Kütüphanesi (JSON taslağı — Faz 3'teki `chemistry_library` tablosuna doğrudan girdi)
```json
{
  "chemistries": [
    {
      "chemistry_id": "NMC_generic_v1",
      "name": "NMC (genel, V1 varsayılan)",
      "A": "...",
      "Ea_kJ_per_mol": "...",
      "delta_H_J_per_g": "...",
      "T_onset_C": "...",
      "n_order": "...",
      "source_references": ["..."],
      "uncertainty_note": "±X% (kaynaklar arası varyasyona göre)"
    },
    {
      "chemistry_id": "LFP_generic_v1",
      "name": "LFP (genel, V1 varsayılan)",
      "...": "..."
    }
  ]
}
```

---

## 5. Zaman Çizelgesi

| Adım | Süre (tahmini) |
|---|---|
| Kaynak tarama ve ilk liste çıkarma | 3-4 gün |
| Karşılaştırma tablosunun doldurulması | 3-4 gün |
| Tutarsızlıkların değerlendirilmesi, nihai değerlere karar verme | 2 gün |
| JSON kütüphane taslağının hazırlanması ve dokümantasyonu | 1-2 gün |
| **Toplam** | **~2 hafta** |

Bu süre Faz 1'in başlangıcını ~2 hafta erteler ama Faz 1'in üzerine inşa edileceği zemini sağlamlaştırır — parametre seçimi sonradan değiştirilirse Faz 1'deki doğrulama çalışmasının bir kısmı tekrarlanmak zorunda kalınabilir, bu yüzden bu adımın atlanmaması önerilir.

---

## 6. Bu Adımın Çıktısının Sonraki Fazlara Bağlantısı

- **Faz 1** (Çekirdek Fizik Motoru): Bu adımdan çıkan A/Ea/ΔH/T_onset değerleri, tek hücre ARC doğrulama testinin girdisi olacak.
- **Faz 3** (Backend API): JSON kütüphane taslağı, `chemistry_library` veritabanı tablosuna doğrudan seed data olarak yüklenecek.
- **Bölüm 7 — Doğrulama Stratejisi** (ana plan): Buradaki "belirsizlik payı" notları, nihai raporlardaki "±X°C / ±Y% belirsizlik bandı" ifadesinin temelini oluşturacak.

---

## 7. Açık Riskler

- Bazı kaynaklarda birim/tanım farkları olabilir (örn. ΔH bazı çalışmalarda toplam ısı, bazılarında sadece belirli bir reaksiyon adımına ait ısı olarak raporlanıyor) — bu karışıklık kütüphane hazırlanırken dikkatle ayıklanmalı.
- Yayınlanmış literatür değerleri genelde laboratuvar ölçeğinde tek hücre testlerinden geliyor; gerçek ticari pack'lerdeki hücre-hücre etkileşimi farklı davranabilir — bu, ana plandaki golden dataset eksikliği riskiyle aynı kökten geliyor ve V1'in bir sınırlaması olarak açıkça belirtilecek.
