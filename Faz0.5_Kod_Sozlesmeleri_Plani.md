# Sonraki Adım Planı: Kod Sözleşmelerinin (Code Contracts) Dondurulması
## Faz 0.5 — Mimari Sözleşmeler, Faz 1 Kodlamasından Önce

*(AeroSeat/koltuk projesindeki "5 Code Contracts" yönteminin battery thermal runaway simülatörüne uyarlanmış hali. Amaç: Faz 1'de yazılacak kodun, Faz 3'teki veri modeli netleşince baştan revize edilmesini önlemek.)*

---

## 1. Bu Adımın Amacı

Faz 0 (kinetik parametre araştırması) tamamlandığında elimizde sayısal değerler olacak, ama "bu değerler sistemde nasıl temsil edilecek, hangi katman neye sorumlu olacak, sonuçlar nasıl saklanacak ve doğrulama nasıl raporlanacak" gibi mimari kararlar henüz netleşmiş değil. AeroSeat projesinde bu kararları erken, kod yazmadan önce "sözleşme" (contract) olarak dondurmak; sonradan "önce şöyle yazmıştık, şimdi böyle olması gerekiyor" tipi geriye dönük revizyonları büyük ölçüde önledi. Aynı disiplin burada da uygulanmalı.

Bu adım, Faz 0 ile Faz 1 arasına girer: Faz 0'ın çıktısı (parametre kütüphanesi) hazır olduğunda, kodlamaya geçmeden önce aşağıdaki 5 sözleşme yazılı olarak netleştirilip dondurulmalı.

---

## 2. Kapsam — 5 Sözleşme

### Sözleşme 1: Bilimsel İşleme Sözleşmesi (Scientific Processing Contract)
Neyin, hangi birimde, hangi ayrıklaştırma seviyesinde temsil edileceğini tanımlar.
- Her hücrenin durum değişkenleri: `T` (K, daima Kelvin — °C/K karışıklığı Bölüm 5.4'teki gibi birim hatalarına yol açabilir, bu yüzden iç hesaplamada tek birim standardı zorunlu), `alpha` (0-1 arası, boyutsuz), `state` (NORMAL/ONSET/RUNAWAY/BURNED_OUT enum'u — ana plandaki `CellModel.state` ile birebir)
- Hangi fiziksel etkinin V1'de modellendiği, hangisinin modellenmediğinin kesin listesi (ana plan Bölüm 4'teki kapsam dışı listesiyle birebir tutarlı olmalı — kod yazan kişi "bu da eklensin" diye kapsam genişletmemeli)
- Zaman adımı (dt) kontrol politikası: sabit mi, adaptif mi (ana plandaki "scipy solve_ivp" adaptif adım kullanıyor — bu durumda "adaptif" olarak dondurulmalı, sabit dt varsayımıyla yazılan hiçbir kod kabul edilmemeli)

### Sözleşme 2: Çözücü Sözleşmesi (Solver Contract)
- V1'de tek çözücü: `scipy.integrate.solve_ivp`, yöntem: LSODA (sertlik/stiffness otomatik algılama) — ana plan Bölüm 6.2'de belirtildiği gibi
- Çözücü arayüzü, AeroSeat'teki gibi "solver-agnostic interface" mantığıyla soyutlanmalı mı, yoksa V1'de doğrudan scipy'ye bağlı mı kalınacak? **Karar:** V1'de doğrudan bağlı kalınması önerilir (AeroSeat'teki LS-DYNA soyutlaması, birden fazla ticari solver'ı desteklemek zorunda olduğu için gerekliydi; bu projede V1'de tek matematiksel yöntem yeterli — erken soyutlama gereksiz karmaşıklık ekler). V2'de gerçek CFD entegrasyonu gündeme gelirse o zaman soyutlama eklenir.
- Yakınsama/hata toleransı sabitleri (rtol, atol) ve bunların hangi dosyada/config'de tanımlı olacağı

### Sözleşme 3: Veri Modeli ve Değişmezlik Sözleşmesi (Data Model & Immutability Contract)
- Bir simülasyon job'ı tamamlandıktan sonra sonuçları değiştirilemez (immutable) — AeroSeat'teki "DB trigger ile RAISE EXCEPTION" yaklaşımı burada da uygulanmalı, sessiz no-op kural yerine
- **Configuration Hash:** Pack geometrisi + malzeme/kimya seçimleri + tetikleyici konfigürasyonunun hash'i — aynı config tekrar simüle edilirse aynı sonucu üretmesi (determinism) garanti edilmeli
- **Execution Fingerprint:** Hangi solver versiyonu, hangi parametre kütüphanesi versiyonu (Faz 0 çıktısının kendi versiyon numarası olmalı) ile çalıştırıldığının kaydı — ileride "bu sonuç hangi parametre setiyle üretildi" sorusuna cevap verebilmek için
- `simulation_jobs` ve `simulation_results` tablolarının (ana plan Bölüm 6.3) hangi alanlarının immutable, hangilerinin (örn. job status) mutable olduğunun net listesi

### Sözleşme 4: Kanıt ve Raporlama Sözleşmesi (Evidence & Reporting Contract)
- PDF raporun içereceği zorunlu alanlar: config hash, execution fingerprint, kullanılan parametre kütüphanesi versiyonu ve kaynakları (Faz 0 çıktısındaki `source_references`), belirsizlik bandı ifadesi
- Raporda kullanılacak dil netleştirilmeli: "sertifikasyon garantisi" ifadesi kesinlikle kullanılmayacak, "mühendislik ön-değerlendirmesi / certification readiness assessment" ifadesi standart olacak (AeroSeat'teki regülasyon dili riskiyle birebir aynı konu — orada nasıl çözüldüyse burada da aynı dil politikası uygulanmalı)
- Risk skorunun (Bölüm 5.5, ana plan) raporda tek bir sayı olarak mı yoksa AeroSeat'teki gibi çok boyutlu bir vektör (magnitude/phase/shape/peak/RMS error'a benzer, burada: propagation time + kaç hücre + belirsizlik bandı) olarak mı sunulacağı — **Karar:** tek "geçti/kaldı" sayısı yerine çok boyutlu sunum önerilir, AeroSeat'teki "no universal credibility % pass threshold" prensibiyle tutarlı.

### Sözleşme 5: Doğrulama / Referans Veri Seti Sözleşmesi (Validation / Golden Dataset Contract)
- Golden dataset'in henüz olmadığı (ana plan Bölüm 11) açıkça kod seviyesinde de işaretlenmeli — örn. `PropagationEvaluator` çıktısında `validation_status: "literature_calibrated"` gibi bir alan olmalı, ileride gerçek test verisiyle doğrulanırsa `validation_status: "physically_validated"` olarak güncellenebilir
- Literatür kalibrasyonuyla physically-validated durum arasındaki fark, raporda kullanıcıya açıkça gösterilmeli (güven seviyesi etiketi)

---

## 3. Metodoloji: Sözleşmeler Nasıl Dondurulacak

1. Yukarıdaki 5 sözleşmenin her biri ayrı bir kısa doküman (1-2 sayfa) olarak yazılır — kod değil, düz metin karar kaydı
2. Her sözleşme için "hangi alternatifler değerlendirildi, hangisi seçildi, neden" kısa bir gerekçe bölümü içerir (Sözleşme 2'deki solver-agnostic tartışması gibi)
3. Sözleşmeler yazıldıktan sonra "dondurulur" — yani Faz 1 kodlaması sırasında bir sözleşmeyi değiştirme ihtiyacı doğarsa, önce sözleşme dokümanı güncellenir, sonra kod yazılır (tersi değil)
4. Faz 1 kodlamasına ancak tüm 5 sözleşme yazılı hale geldikten sonra başlanır

---

## 4. Zaman Çizelgesi

| Adım | Süre (tahmini) |
|---|---|
| Sözleşme 1 (Bilimsel İşleme) | 1 gün |
| Sözleşme 2 (Çözücü) | 0.5 gün |
| Sözleşme 3 (Veri Modeli/Immutability) | 1 gün |
| Sözleşme 4 (Kanıt/Raporlama) | 1 gün |
| Sözleşme 5 (Doğrulama/Golden Dataset) | 0.5 gün |
| Gözden geçirme ve son dondurma | 1 gün |
| **Toplam** | **~5 gün** |

Bu adım Faz 0'ın hemen ardından, Faz 1'in hemen öncesinde yapılmalı — ana proje planındaki zaman çizelgesine yaklaşık 1 hafta ekler, ama AeroSeat deneyiminde görüldüğü gibi bu yatırım, sonraki fazlarda geriye dönük kod revizyonlarını önleyerek zamandan fazlasıyla tasarruf ettirir.

---

## 5. Bu Adımın Çıktısının Sonraki Fazlara Bağlantısı

- **Faz 1:** `CellModel`, `ThermalNetworkAssembler`, `ArrheniusKineticsEngine` sınıfları Sözleşme 1 ve 2'deki kararlara birebir uyacak şekilde yazılır — birim, durum makinesi ve çözücü seçimi tartışmasız netleşmiş olur.
- **Faz 3:** `simulation_jobs`/`simulation_results` şeması Sözleşme 3'teki immutability ve hash/fingerprint kararlarıyla doğrudan uyumlu kurulur.
- **Faz 5:** Rapor modülü Sözleşme 4'teki zorunlu alan listesini ve dil politikasını uygular; `PropagationEvaluator` Sözleşme 5'teki `validation_status` alanını üretir.

---

## 6. Açık Riskler

- Sözleşmeleri dondurmak, ileride gerçekten gerekli olan bir esnekliği baştan kapatabilir (örn. V2'de gerçek CFD entegrasyonu gerektiğinde Sözleşme 2'deki "solver-agnostic değil" kararının geri alınması gerekebilir) — bu yüzden her sözleşmede "bu karar hangi koşulda yeniden açılır" notu da eklenmeli.
- 5 sözleşmenin tamamının yazılması ek bir hafta demek — eğer zaman baskısı varsa, en azından Sözleşme 1 ve 3 (bilimsel temsil ve veri modeli) önceliklendirilip 2/4/5 Faz 1 sırasında paralel olgunlaştırılabilir.
