# V2 Roadmap & Architecture Notes

## Mevcut Durum (Faz 1)
Termal ağ motorumuz, ısı iletimini, katı radyasyonu ve yarı-ampirik gaz sıçrama (ejecta) ısı akısını (`Q_vent`) başarıyla çözmektedir. Ancak, %100 kusursuz bir ürün için gelecekte çözülmesi gereken aerodinamik konular vardır.

## Faz 1.5 - Orta Vadeli: TRF (Thermal Runaway Front) Çapraz Kontrolü
Mevcut diferansiyel ısı denklemi (ODE) solver'ına bağımsız, ikinci bir onay mekanizması eklenmesi planlanmaktadır:
- **Konsept:** Fiziksel ODE yayılımı öngörmese dahi, geometrik "Termal Kaçak Cephe Hızı (TRF)" algoritmasıyla hücre aralıkları doğrultusunda saniye/mm tabanlı düz bir matematiksel kesişim kontrolü yapılacak.
- **Hedef:** Kullanıcıya "Termal model yayılmadı diyor, ancak ampirik hız modeline göre X saniyede yayılabilir" şeklinde çift taraflı (double-blind) bir risk uyarısı verebilmek.

## Faz 2.0 - Uzun Vadeli: Tam CFD ve Gerçek Akışkanlar Dinamiği
Şu anki V1 versiyonumuz, gaz ve ejecta akışını Yarı-Ampirik `Q_vent` terimi ile statik olarak çözmektedir.
- **Geçiş Kriteri:** Pilot kullanıcı sayısı arttığında ve laboratuvardan/sahadan gerçek doğrulanmış (validation) veriler gelmeye başladığında, 3D hava ve rüzgar dinamiğini simüle edecek gerçek bir CFD motoru (OpenFOAM gibi açık kaynaklı) backend'e asenkron bir worker (işçi) modülü olarak entegre edilebilir.
- **Odak:** Alevin (flaming) yukarı doğru gaz püskürtmesi, valf açılma basıncı, çevresel rüzgarın modül üzerindeki kaotik alev dağıtımı.
