# Batarya Termal Kaçak ve Yayılım Simülatörü (Battery Thermal Workbench)
## Makine Mühendisliği ve Termal Tasarım İçin Kapsamlı Teknik El Kitabı

---

### İçindekiler
1. [Mühendislik Amacı, Kapsam ve UL 9540A Ön-Taraması](#1-mühendislik-amacı-kapsam-ve-ul-9540a-ön-taraması)
2. [Termodinamik ve Isı Transferi Matematiksel Modeli](#2-termodinamik-ve-ısı-transferi-matematiksel-modeli)
   - 2.1 [1. Termodinamik Yasası ve Hücre Enerji Balansı](#21-1-termodinamik-yasası-ve-hücre-enerji-balansı)
   - 2.2 [Arrhenius Kinetiği ve Kimyasal Isı Üretimi](#22-arrhenius-kinetiği-ve-kimyasal-ısı-üretimi)
   - 2.3 [Katı İçi İletim Ağı ve Laplasyen Formülasyonu](#23-katı-içi-iletim-ağı-ve-laplasyen-formülasyonu)
   - 2.4 [Hücreler Arası Stefan-Boltzmann Radyasyon Modeli](#24-hücreler-arası-stefan-boltzmann-radyasyon-modeli)
   - 2.5 [Yarı-Ampirik Sıcak Gaz ve Ejecta Venting Modeli ($Q_{vent}$)](#25-yarı-ampirik-sıcak-gaz-ve-ejecta-venting-modeli-q_vent)
   - 2.6 [Dış Ortam Kayıpları (Doğal Konveksiyon & Radyasyon)](#26-dış-ortam-kayıpları-doğal-konveksiyon--radyasyon)
   - 2.7 [Taban Sıvı Soğutma Plakası (Cold Plate) Modeli](#27-taban-sıvı-soğutma-plakası-cold-plate-modeli)
3. [Sayısal Çözüm Yöntemi ve Algoritmik Kararlılık (LSODA Stiff ODE)](#3-sayısal-çözüm-yöntemi-ve-algoritmik-kararlılık-lsoda-stiff-ode)
   - 3.1 [Stiff (Sert) Diferansiyel Denklem Problemi](#31-stiff-sert-diferansiyel-denklem-problemi)
   - 3.2 [LSODA Çözücüsü ve Hibrit Adams-Moulton / BDF Algoritması](#32-lsoda-çözücüsü-ve-hibrit-adams-moulton--bdf-algoritması)
   - 3.3 [Durum Değişkenleri Sınırlaması ve Sayısal Kararlılık Koruması](#33-durum-değişkenleri-sınırlaması-ve-sayısal-kararlılık-koruması)
4. [Gelişmiş Fizik Paneli (Advanced Physics Mode)](#4-gelişmiş-fizik-paneli-advanced-physics-mode)
   - 4.1 [Kinetik Parametrelerin Açılması ($A, E_a, n, \Delta H, f_{active}$)](#41-kinetik-parametrelerin-açılması-a-e_a-n-delta-h-f_active)
   - 4.2 [Ejecta Venting ve Yüzey Işınım Dinamiği ($h_{vent}, T_{gas}, \varepsilon$)](#42-ejecta-venting-ve-yüzey-ışınım-dinamiği-h_vent-t_gas-varepsilon)
5. [Tasarım Çalışması ve Parametre Taraması Modülü (Design Study Engine)](#5-tasarım-çalışması-ve-parametre-taraması-modülü-design-study-engine)
   - 5.1 [Çoklu Tasarım Taraması Tipleri (`spacing`, `separator`, `cooling`)](#51-çoklu-tasarım-taraması-tipleri-spacing-separator-cooling)
   - 5.2 [Çok Amaçlı Güvenlik Sıralaması (Multi-Objective Safety Ranking)](#52-çok-amaçlı-güvenlik-sıralaması-multi-objective-safety-ranking)
   - 5.3 [Öneri Algoritması ve Çalışma Alanına Anlık Vaka Yükleme](#53-öneri-algoritması-ve-çalışma-alanına-anlık-vaka-yükleme)
6. [Battery Thermal Workbench UI/UX ve CAE Mimarisi](#6-battery-thermal-workbench-uiux-ve-cae-mimarisi)
   - 6.1 [SimScale Workbench Paradigması](#61-simscale-workbench-paradigması)
   - 6.2 [4 Katmanlı Çalışma Alanı ve Etkileşimli 3D/2D Görüntüleyici](#62-4-katmanlı-çalışma-alanı-ve-etkileşimli-3d2d-görüntüleyici)
   - 6.3 [Zaman Çizelgesi, Oynatıcı ve Yayılım Olay Akışı](#63-zaman-çizelgesi-oynatıcı-ve-yayılım-olay-akışı)
7. [Yazılım Mimarisi ve Kod Modülleri Haritası](#7-yazılım-mimarisi-ve-kod-modülleri-haritası)
   - 7.1 [Modül Sorumluluk Matrisi](#71-modül-sorumluluk-matrisi)
   - 7.2 [Çift Katmanlı Malzeme ve Kimya Kütüphanesi Depolaması](#72-çift-katmanlı-malzeme-ve-kimya-kütüphanesi-depolaması)
8. [REST API Sözleşmeleri ve Veri Modelleri](#8-rest-api-sözleşmeleri-ve-veri-modelleri)
9. [Doğrulama, Kabul Kriterleri ve 16 Birim Testi](#9-doğrulama-kabul-kriterleri-ve-16-birim-testi)
10. [Mühendislik Sınırları, Kabuller ve Gelecek Geliştirmeler](#10-mühendislik-sınırları-kabuller-ve-gelecek-geliştirmeler)

---

## 1. Mühendislik Amacı, Kapsam ve UL 9540A Ön-Taraması

### 1.1 Problem Tanımı: Termal Kaçak (Thermal Runaway - TR)
Lityum-iyon piller (özellikle NMC, NCA ve LFP hücre kimyaları), modern elektrikli araçlarda (EV) ve batarya enerji depolama sistemlerinde (BESS) hacimsel/kütlesel enerji yoğunlukları sebebiyle vazgeçilmezdir. Ancak bu hücreler kimyasal olarak **metastabil** haldedir; yanıcı sıvı organik elektrolitler ve yüksek sıcaklıkta oksijen salabilen metal-oksit katotlar barındırırlar.

Hücre; mekanik hasar, yabancı metalik dendrit oluşumu kaynaklı iç kısa devre, aşırı şarj veya dış yangın sebebiyle kritik eşik sıcaklığını (**Kaçak Başlangıç Sıcaklığı - $T_{onset}$**) aştığında ekzotermik bozunma reaksiyonları başlar. Bu reaksiyonlar ısı açığa çıkardıkça hücre sıcaklığı kontrolsüzce artar (**Self-Heating**). Sıcaklık $T_{trigger}$ seviyesine eriştiğinde kimyasal reaksiyon hızı patlama derecesinde artar; hücre saniyeler içinde $600^\circ\text{C} - 900^\circ\text{C}$ sıcaklıklara ulaşarak alev alır, emniyet valfini (vent cap) patlatır ve ortama yüksek enerjili alev/gaz jetleri fırlatır.

### 1.2 Hedef: UL 9540A Seviye 2 Ön-Taraması (Single-Cell Containment)
Bir batarya modülünde bir hücre yandığında, açığa çıkan yüksek ısıl enerji komşu hücrelere iletilir. Eğer komşu hücre de $T_{onset}$ eşiğini geçerse, o da kaçak durumuna girer. Bu zincirleme felakete **Termal Kaçak Yayılımı (Thermal Runaway Cascade)** adı verilir.

**UL 9540A**, batarya sistemlerinde yangın yayılımını değerlendiren en katı uluslararası güvenlik standardıdır. Seviye 2 (Modül Seviyesi) testinin temel kabul kriteri şudur:
> **Single-Cell Containment (Tek Hücre Tutulumu):** Bir hücre kasıtlı olarak termal kaçağa sokulduğunda (termal plaka darbesi veya çivi ile), açığa çıkan ısı komşu hücreleri $T_{onset}$ eşiğinin altında tutmalı ve yangın modülün geneline sıçramadan sönümlenmelidir.

Bu simülatörün mühendislik misyonu:
1. **Fiziksel Test Maliyetlerini Sıfırlamak:** Fiziksel bir UL 9540A patlatma testi 50.000$ - 200.000$ arası maliyete ve haftalarca hazırlığa mal olur.
2. **Hızlı Tasarım Yinelemesi (Iterative Optimization):** Bir makine/termal tasarım mühendisi; hücre aralığını ($0.5\text{ mm}$ ile $10\text{ mm}$ arası), separatör malzemesini (aerojel, mika, silikon dolgu), aktif sıvı soğutma konveksiyon katsayısını ve busbar iletim kesitini **saniyeler içinde** parametrik olarak test edebilmelidir.

### 1.3 Neden 3D Tam CFD Değil de Lumped CHT Isı Transfer Ağı?
* **3D Tam CFD (Computational Fluid Dynamics):** Bir modüldeki 20-50 hücrenin yanmasını, katı içi ısı iletimini ve gaz fazı türbülansını Ansys Fluent veya OpenFOAM ile çözmek milyonlarca sonlu hacim hücresi (mesh) ve saatler/günler süren HPC (High-Performance Computing) süresi gerektirir. Erken tasarım aşamasında yüzlerce varyasyonu taramak imkânsızdır.
* **Lumped Thermal Network (Birleşik Isıl Kapasite Modeli):** Biot sayısı ($Bi = \frac{h L_c}{k} < 0.1$) kabullerine dayanan ve her hücreyi homojenleştirilmiş bir düğüm olarak ele alan diferansiyel denklem ağları, fiziksel deneylerle %5-8 hassasiyet aralığında örtüşürken tüm simülasyonu **1 ila 3 saniye** içinde tamamlar. Bu sayede mühendis "Parametre Taraması (Sweep)" ile optimum tasarımı gerçek zamanlı keşfeder.

---

## 2. Termodinamik ve Isı Transferi Matematiksel Modeli

Model, her hücre için iki temel durum değişkenini ($2N$ boyutlu durum vektörü) zamana bağlı çözen birleşik bir diferansiyel denklem sistemidir:
1. $T_i(t)$ [K]: $i$-inci hücrenin mutlak sıcaklığı.
2. $\alpha_i(t) \in [0, 1]$: $i$-inci hücrenin reaksiyon ilerleme derecesi (Dönüşüm kesri; $\alpha=0$ taze/reaktif hücre, $\alpha=1$ reaktanı tamamen tükenmiş yanmış hücre).

```
                 +--------------------------------------------------+
                 |              Dış Ortam T_amb, h_amb               |
                 +--------------------------------------------------+
                                   ^              ^
                        q_conv,amb |              | q_rad,amb
                                   |              |
                 +-----------------+--------------+------------------+
                 |                HÜCRE i (T_i, m_i, C_p)             |
                 |  m_i * C_p * (dT_i/dt) = Q_net                    |
                 +---------------------------------------------------+
                   ^       ^                 |                 |
      Q_chem(alpha)|       | Q_ext (Isıtıcı) | Q_cond,ij       | Q_rad,ij
                   |       |                 v                 v
                 [Arrhenius]             [Komşu Hücre j]   [Radyasyon T^4]
                                                 |
                                                 v
                                          [Q_vent (Gaz Akısı)]
                                                 |
                                                 v
                                     [Soğutma Plakası Q_cool]
```

### 2.1 1. Termodinamik Yasası ve Hücre Enerji Balansı
Her $i$ hücresi için kontrol hacmi enerji denkliği (1. Yasa):

$$m_i \, C_{p,i} \, \frac{dT_i}{dt} = \dot{Q}_{chem,i} + \dot{Q}_{ext,i} - \dot{Q}_{cond,net,i} - \dot{Q}_{rad,intercell,i} + \dot{Q}_{vent,i} - \dot{Q}_{conv,amb,i} - \dot{Q}_{rad,amb,i} - \dot{Q}_{cool,i}$$

* $m_i$: Hücre toplam kütlesi ($\text{kg}$).
* $C_{p,i}$: Hücrenin efektif özgül ısı kapasitesi ($\text{J/kg}\cdot\text{K}$).
* $T_i$: Hücre sıcaklığı ($\text{K}$).

---

### 2.2 Arrhenius Kinetiği ve Kimyasal Isı Üretimi
Termal kaçak reaksiyonları, reaktan tükenmesini dikkate alan $n$-inci mertebeden Arrhenius kimyasal kinetiği ile modellenir:

$$\frac{d\alpha_i}{dt} = A \cdot (1 - \alpha_i)^n \cdot \exp\left(-\frac{E_a}{R \cdot T_i}\right)$$

* $A$: Frekans faktörü / Pre-exponential faktör ($\text{s}^{-1}$).
* $E_a$: Aktivasyon enerjisi ($\text{J/mol}$).
* $R$: Evrensel gaz sabiti ($8.31446 \, \text{J/mol}\cdot\text{K}$).
* $n$: Reaksiyon mertebesi ($n \approx 1.0$).
* $(1 - \alpha_i)^n$: Kalan aktif kimyasal reaktan konsantrasyonu.

Açığa çıkan ekzotermik kimyasal ısı üretim hızı ($\dot{Q}_{chem,i}$ [W]):

$$\dot{Q}_{chem,i} = m_{active,i} \cdot \Delta H \cdot \frac{d\alpha_i}{dt}$$

* $m_{active,i} = m_i \cdot f_{active}$: Yalnızca elektrokimyasal olarak reaksiyona giren jöle rulo (jelly-roll) kütlesi. Dış çelik kovan ve terminaller reaksiyona girmez ($f_{active} \approx 0.55 - 0.60$).
* $\Delta H$: Toplam reaksiyon entalpisi ($\text{J/kg}$ veya $\text{J/g}$).
* $\dot{Q}_{ext,i}$: Dış test tetikleyici gücü (örneğin UL 9540A uyarınca harici ısıtıcı darbesi $3500\text{ W}$, $3.0\text{ s}$).

---

### 2.3 Katı İçi İletim Ağı ve Laplasyen Formülasyonu
Hücreler arasındaki iletim, silindirik kabuk geometrisi, hava boşluğu, aradaki termal bariyer (aerojel/mika) ve üst busbar iletkenliklerini birleştiren seri/paralel direnç ağı üzerinden hesaplanır:

$$\dot{Q}_{cond,net,i} = \sum_{j \in \mathcal{N}(i)} G_{ij} \cdot (T_i - T_j)$$

Burada $G_{ij}$ [$\text{W/K}$] iki komşu hücre arasındaki toplam eşdeğer ısıl iletkenliktir:

$$G_{ij} = \frac{1}{R_{cell,i} + R_{gap/sep} + R_{cell,j}} + G_{busbar,ij}$$

Silindirik pillerde arayüz direnci:

$$R_{gap/sep} = \frac{L_{eff}}{k_{eff} \cdot A_c}$$

* $A_c = D_{cell} \cdot H_{cell}$: Karşılıklı izdüşüm yüzey alanı.
* $L_{eff}$: Hücre kabukları arasındaki net mesafe (ayrım mesafesi).
* $k_{eff}$: Arayüzdeki malzemenin (hava veya separatör katmanı) ısıl iletkenliği ($\text{W/m}\cdot\text{K}$).
* $G_{busbar,ij}$: Üst kısımdan elektriksel bağlantıyı sağlayan bakır/alüminyum iletim köprüsü katsayısı ($G_{busbar} \approx 0.4 - 0.8 \, \text{W/K}$).

Vektör ve matris formatında toplam iletim akısı:
$$\mathbf{q}_{cond} = \mathbf{L}_G \cdot \mathbf{T}$$
Burada $\mathbf{L}_G$, simetrik iletkenlik Laplasyen matrisidir:
$$\mathbf{L}_{ii} = \sum_{j \neq i} G_{ij}, \quad \mathbf{L}_{ij} = -G_{ij}$$

---

### 2.4 Hücreler Arası Stefan-Boltzmann Radyasyon Modeli
Hücre sıcaklığı $600^\circ\text{C} - 900^\circ\text{C}$ aralığına çıktığında, radyasyon ısı transferi ($T^4$) iletim transferini geride bırakabilir. İki komşu hücre arasında katı opak bir termal bariyer (aerojel/mika) **bulunmadığı** durumlarda net ışınım transferi:

$$\dot{Q}_{rad,ij} = \sigma \cdot \epsilon_{eff} \cdot A_c \cdot \left(T_i^4 - T_j^4\right)$$

* $\sigma = 5.670374 \times 10^{-8} \, \text{W/m}^2\text{K}^4$: Stefan-Boltzmann sabiti.
* $\epsilon_{eff}$: Karşılıklı silindirik yüzeyler için efektif yayım katsayısı:
$$\epsilon_{eff} = \frac{\epsilon}{2 - \epsilon}$$
* Eğer araya katı bir kompozit separatör yerleştirilmişse, görüş faktörü (view factor) sıfırlanır ve $\dot{Q}_{rad,ij} = 0$ kabul edilir.

---

### 2.5 Yarı-Ampirik Sıcak Gaz ve Ejecta Venting Modeli ($Q_{vent}$)
Hücre patladığında (venting), hücre içindeki emniyet tapası fırlar ve ortama sıcak hidrokarbon gazları, buharlaşmış solventler ve erimiş alüminyum/bakır parçacıkları püskürür. CFD çözücüsü olmadan bu taşınım akısını modellemek için yarı-ampirik bir konvektif jet modeli uygulanır:

$$\text{Eğer } T_i \ge T_{trigger} \text{ ve } \alpha_i > 0.05 \text{ (Separatörsüz durumda):}$$

$$\dot{Q}_{vent,j} = h_{vent} \cdot A_c \cdot \left(T_{gas} - T_j\right)$$

* $h_{vent}$: Gaz taşınım katsayısı ($\sim 100 - 200 \, \text{W/m}^2\text{K}$).
* $T_{gas}$: Püsküren gaz ve parçacık bulutunun sıcaklığı (NMC için $\approx 1000^\circ\text{C}$, LFP için $\approx 350^\circ\text{C}$).
* Araya katı aerojel/mika bariyer konulduğunda, alev ve gaz jeti komşuya direkt temas edemeyeceği için bu terim sönümlenir.

---

### 2.6 Dış Ortam Kayıpları (Doğal Konveksiyon & Radyasyon)
Paketin dış çeperinde yer alan hücreler, açıkta kalan yüzey alanları ($A_{exposed,i}$) üzerinden çevreye ısı kaybederler:

$$\dot{Q}_{conv,amb,i} = h_{amb} \cdot A_{exposed,i} \cdot \left(T_i - T_{amb}\right)$$

$$\dot{Q}_{rad,amb,i} = \sigma \cdot \epsilon \cdot A_{exposed,i} \cdot \left(T_i^4 - T_{amb}^4\right)$$

İç hücreler komşu hücrelerle çevrelendiğinden $A_{exposed} \approx 0$ olur ve dış ortama ısı veremezler.

---

### 2.7 Taban Sıvı Soğutma Plakası (Cold Plate) Modeli
Modül tabanında aktif bir soğutma plakası (su/glikol karışımı) tanımlandığında, her hücrenin alt dairesel tabanından çekilen ısı:

$$\dot{Q}_{cool,i} = G_{cool,eff} \cdot \left(T_i - T_{coolant}\right)$$

$$G_{cool,eff} = \frac{1}{\frac{1}{h_{cool} \cdot A_{bottom}} + R_{TIM}}$$

* $A_{bottom} = \pi (D/2)^2$: Hücre taban alanı.
* $h_{cool}$: Soğutucu kanal içi konveksiyon katsayısı ($800 - 1500 \, \text{W/m}^2\text{K}$).
* $R_{TIM}$: Hücre tabanı ile alüminyum plaka arasındaki termal pad (TIM) temas direnci.

---

## 3. Sayısal Çözüm Yöntemi ve Algoritmik Kararlılık (LSODA Stiff ODE)

### 3.1 Stiff (Sert) Diferansiyel Denklem Problemi
Termal kaçak simülasyonu, diferansiyel denklem teorisindeki en sert (stiff) problemlerden biridir. Sistemin iki uç zaman ölçeği vardır:
1. **Yavaş Aşama (Slow Pre-Heating):** Hücre $25^\circ\text{C}$'den $150^\circ\text{C}$'ye ısınırken reaksiyon hızı neredeyse sıfırdır. Zaman sabiti $\tau \sim 10 - 60\text{ saniye}$ düzeyindedir.
2. **Patlama Aşaması (Thermal Runaway Flash):** Sıcaklık $T_{trigger}$ eşiğini aştığında Arrhenius terimindeki $e^{-E_a/RT}$ çarpanı patlar. Sıcaklık artış hızı bir anda $\frac{dT}{dt} > 1000 \, \text{K/s}$ mertebesine çıkar. Zaman sabiti $\tau \sim 10^{-4}\text{ saniye}$ (milisaniye) seviyesine çöker.

Standart açık (explicit) yöntemler (Euler, Klasik RK4) bu aşamada kararlılığını kaybeder; adım boyutu küçültülse dahi sayısal patlama (**Numerical Instability**) yaşar ve $T \to \infty$ ya da `NaN` hatası verir.

### 3.2 LSODA Çözücüsü ve Hibrit Algoritma
Bu problemi çözmek için SciPy kütüphanesinin **LSODA (Livermore Solver for Ordinary Differential Equations)** algoritması entegre edilmiştir:
* **Stiffness Detection:** Çözücü yerel Jacobian özdeğerlerini izleyerek sistemin sertleştiği anı otomatik algılar.
* **Adams-Moulton Yöntemi:** Sistem kararlıyken (stiff değilken) açık yüksek mertebeden Adams yöntemini kullanarak çok büyük zaman adımlarıyla hızla ilerler.
* **BDF (Backward Differentiation Formula) Yöntemi:** Sıcaklık tetiklendiği anda örtük (implicit) Gear/BDF yöntemine geçer; sistem kararlılığını asla kaybetmez.
* **Adaptif Adımlama:** Kaçak anında adım boyutunu otomatik olarak mikrosaniyelere düşürür, sönümlenme evresinde tekrar saniyelere çıkarır.

### 3.3 Durum Değişkenleri Sınırlaması ve Sayısal Kararlılık Koruması
Sayısal türev fonksiyonunda (`compute_derivatives`):
```python
temps = np.maximum(50.0, state_vector[:N])     # Fizik dışı negatif sıcaklıkları engeller
alphas = np.clip(state_vector[N:2*N], 0.0, 1.0) # alpha değerini kesin [0, 1] bandında tutar
```
Bu sıkıştırma (clamping), LSODA deneme adımlarında reaktan oranının negatif veya 1'den büyük olmasını önleyerek modelin daima fiziksel sınırlar içinde kalmasını temin eder.

---

## 4. Gelişmiş Fizik Paneli (Advanced Physics Mode)

Standart modda kullanıcı hazır kimya kütüphanesinden (NMC622, NMC811, LFP) seçim yapar. Ancak Ar-Ge mühendisleri, diferansiyel taramalı kalorimetre (DSC) veya hızlandırıcı oran kalorimetresi (ARC) laboratuvar test sonuçlarına göre kinetik parametreleri doğrudan kalibre etmek isterler.

### 4.1 Kinetik Parametrelerin Açılması
Arayüzdeki **Gelişmiş Fizik Paneli** açıldığında, arka plandaki `PackSimulationRequest.advanced_physics_enabled` bayrağı devreye girer ve aşağıdaki parametreler simülasyon motoruna canlı enjekte edilir:

| Parametre | Simge | Birim | Fiziksel Açıklama | Tipik Değer Aralığı |
| :--- | :--- | :--- | :--- | :--- |
| **Frekans Faktörü** | $A$ | $1/\text{s}$ | Kimyasal moleküler çarpışma frekansı çarpanı | $10^{11} - 10^{16}$ |
| **Aktivasyon Enerjisi** | $E_a$ | $\text{J/mol}$ | Katot/anot bozunma reaksiyonu potansiyel enerji bariyeri | $100.000 - 150.000$ |
| **Reaksiyon Mertebesi** | $n$ | - | Konsantrasyon tükenme kinetiği üssü | $0.8 - 1.5$ |
| **Reaksiyon Entalpisi** | $\Delta H$ | $\text{J/g}$ | Hücrenin kaçakta yaydığı toplam kimyasal yanma enerjisi | $400 - 1200$ |
| **Aktif Kütle Oranı** | $f_{active}$ | - | Toplam kütle içindeki aktif jöle rulo oranı | $0.45 - 0.65$ |

### 4.2 Ejecta Venting ve Yüzey Işınım Dinamiği
Ayrıca hücre kabuk ve emisyon sınır şartları da bu panelden parametrik hale getirilmiştir:
* $h_{vent}$ [$\text{W/m}^2\text{K}$]: Valf patlaması sonrası sıcak gaz türbülans taşınım katsayısı (Varsayılan: $100\text{ W/m}^2\text{K}$).
* $T_{vent,gas}$ [$^\circ\text{C}$]: Püsküren gaz sıcaklığı (NMC için $1000^\circ\text{C}$, LFP için $350^\circ\text{C}$).
* $\varepsilon$: Hücre dış yüzey optik yayım katsayısı (Nikel kaplama için $0.15$, PVC sargı için $0.85$).

---

## 5. Tasarım Çalışması ve Parametre Taraması Modülü (Design Study Engine)

Termal simülatörün en kritik yeniliği, mühendisi tek tek elle parametre deneme zahmetinden kurtaran **Tasarım Çalışması (Design Study / Sweep)** motorudur.

```
                              [Tasarım Çalışması Talebi]
                                           |
                +--------------------------+--------------------------+
                |                          |                          |
        spacing_sweep              separator_sweep             cooling_sweep
     [1.0, 2.0, 3.0, 4.0 mm]    [Hava, Aerojel, Mika]      [0, 500, 1000 W/m2K]
                |                          |                          |
                +--------------------------+--------------------------+
                                           |
                                [Paralel Simülasyonlar]
                                           |
                       [Çok Amaçlı Güvenlik Sıralama Motoru]
                                           |
                       +-----------------------------------+
                       | En Düşük Risk Skoru               |
                       | Minimum Yayılım Oranı             |
                       | Minimum Pik Sıcaklık              |
                       +-----------------------------------+
                                           |
                            [Önerilen Tasarım Rozeti]
```

### 5.1 Desteklenen Tarama Tipleri
1. **Hücre Boşluğu Taraması (`spacing_sweep`):** Hücreler arasındaki $X/Y$ ayrım mesafesini varyasyonlara tabi tutar (Örn: $1.0\text{ mm}, 2.0\text{ mm}, 3.0\text{ mm}, 4.0\text{ mm}, 5.0\text{ mm}$).
2. **Termal Separatör Taraması (`separator_sweep`):** Modülü sırasıyla yalın hava boşluğu (`air_gap`), silika aerojel (`aerogel_insulation`), flogopit mika (`mica_sheet`) ve silikon köpük (`silicone_foam`) ile izole ederek yangın tutulumunu kıyaslar.
3. **Sıvı Soğutma Taraması (`cooling_sweep`):** Taban sıvı soğutma plakasının taşınım katsayısını ($0\text{ W/m}^2\text{K}$ doğal hava, $400\text{ W/m}^2\text{K}$ orta debi, $800\text{ W/m}^2\text{K}$ yüksek debi, $1500\text{ W/m}^2\text{K}$ agresif soğutma) test eder.

### 5.2 Çok Amaçlı Güvenlik Sıralaması (Multi-Objective Safety Ranking)
Çözülen tüm vakalar aşağıdaki ceza fonksiyonuna göre sıralanır:

$$\text{Skor}_{toplam} = w_1 \cdot \text{RiskSkoru} + w_2 \cdot (\text{Etkilenen Hücre Oranı} \times 100) + w_3 \cdot \left(\frac{T_{peak}}{10}\right)$$

* $w_1 = 0.50$ (Risk skoru ağırlığı)
* $w_2 = 0.35$ (Yayılım oranı ağırlığı)
* $w_3 = 0.15$ (Pik sıcaklık şiddeti ağırlığı)

### 5.3 Öneri Algoritması ve Çalışma Alanına Anlık Vaka Yükleme
En düşük ceza puanını alan vaka **"En Güvenli Tasarım (Recommended)"** olarak etiketlenir ve UI üzerinde yeşil başarı rozeti ile gösterilir. 

Kullanıcı tablodaki herhangi bir vakanın yanındaki **"Yükle"** butonuna bastığında, `loadDesignCase()` fonksiyonu o vakanın parametrelerini (mesafe, malzeme, soğutma) anında sol ağaç ve form ayarlarına kopyalar, 3D görselleştiriciyi günceller ve sonuçlarını ekrana getirir.

---

## 6. Battery Thermal Workbench UI/UX ve CAE Mimarisi

Sistem, geleneksel karmaşık ve dikey form blokları yerine modern bulut tabanlı CAE yazılımlarının (SimScale Workbench) kanıtlanmış çalışma alanı paradigmasını benimsemiştir.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ [TOP BAR] Proje Adı | Senaryo Seçici | [⚡ Simülasyonu Başlat] | [📚 Kütüphane] │
├──────────────────┬───────────────────────────────────────────┬───────────────┤
│ [TREE PANEL]     │ [CENTRAL 3D/2D WORKSPACE]                 │ [PROPERTIES]  │
│ 📁 Pack Analizi   │                                           │ (Dinamik Form)│
│  ├─ Geometri     │   [3D Perspektif Modülü / 2D Canvas]      │ Seçili ağaç   │
│  ├─ Kimya        │   Etkileşimli Hücreler, Isı İletim Hatları│ düğümünün     │
│  ├─ Separatör    │   Renk Sıcaklık Skalası (Color Legend)    │ ayar kutusu   │
│  ├─ Soğutma      │   Seçili Hücre HUD Bilgi Kartı            │               │
│  ├─ Tetikleyici  │                                           │               │
│  ├─ Gelişmiş Fiz.│                                           │               │
│  └─ Tasarım Çal. │                                           │               │
├──────────────────┴───────────────────────────────────────────┴───────────────┤
│ [TIMELINE & KPI BAR]                                                         │
│ [▶ Oynat] [====|==================] t=12.4s | 850°C | Yayılım: 1/9 (Single)  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 6.1 SimScale Workbench Paradigması
1. **Sol Simülasyon Ağacı (Simulation Tree):** Simülasyon iş akışının tüm adımları tek bir hiyerarşik ağaçta toplanır.
2. **Merkezi Çalışma Alanı (Viewport):** Ekranın %60'tan fazlasını kaplayan etkileşimli görselleştirme alanı.
3. **Bağlama Duyarlı Özellikler (Context-Sensitive Properties):** Ağaçta tıklanan her düğüm (örneğin "Aktif Soğutma" veya "Tasarım Çalışması"), sağdaki ayar panelini otomatik olarak o konuya odaklar.
4. **Entegre Post-Processing:** Sonuçlar ayrı bir sayfaya gitmez; aynı çalışma alanı üzerinde 2D termal yayılım konturları, Chart.js eğrileri ve zaman çizelgesiyle canlı incelenir.

### 6.2 Etkileşimli 3D/2D Görüntüleyici ve Hücre Seçimi (Canvas Picking)
Kullanıcı merkezi kanvas üzerindeki herhangi bir hücreye fare ile tıkladığında:
* Kanvas hücreyi vurgular (seçim halkası çizer).
* Sağ alt köşede yüzen bir **Hücre Detay HUD Kartı** belirir (Hücre ID, Anlık Sıcaklık, Maksimum Sıcaklık, Kaçak Durumu ve Kinetik $\alpha$ Reaksiyon Tüketim Seviyesi).

### 6.3 Zaman Çizelgesi, Oynatıcı ve Yayılım Olay Akışı
* **Zaman Çubuğu (Scrubber):** Simülasyonun $0$ ile $t_{son}$ saniyesi arasında kare kare ilerleme imkânı.
* **Otomatik Oynatıcı (Play/Pause):** ~12.5 FPS hızında termal kaçak dalgasının komşu hücrelere sıçramasını canlı video gibi oynatır.
* **Yayılım Olay Akışı (Event Stream):** Kaçağa giren hücreleri sırayla kronolojik zincir olarak kutular halinde listeler ($Hücre_0 \to Hücre_1 \to Hücre_2$).

---

## 7. Yazılım Mimarisi ve Kod Modülleri Haritası

Sistem; modüler, test edilebilir ve SOLID prensiplerine uygun katmanlı bir mimariyle kurulmuştur.

```
Termal Kaçak Sim/
├── simulator/
│   ├── core/                       <-- [FİZİK, KİNETİK VE ÇÖZÜCÜ ÇEKİRDEĞİ]
│   │   ├── constants.py            # Stefan-Boltzmann, R_gaz sabitleri, silindirik ebat standartları
│   │   ├── cell_model.py           # CellGeometry & CellModel veri sınıfları (Kapasite m*Cp, yüzeyler)
│   │   ├── pack_geometry.py        # PackGeometryBuilder: Grid/Staggered 2D yerleşim ve komşuluk ağı
│   │   ├── kinetics_engine.py      # ArrheniusKineticsEngine: d(alpha)/dt ve Q_chem ekzotermik hesabı
│   │   ├── thermal_network.py      # ThermalNetworkAssembler: ODE türev sistemi (compute_derivatives)
│   │   ├── solver.py               # ThermalRunawaySolver: SciPy LSODA integratörü ve olay yakalama
│   │   └── propagation_evaluator.py# PropagationEvaluator: UL 9540A risk skoru ve yayılım yolu grafiği
│   │
│   ├── api/                        <-- [WEB VE SERVİS ORKESTRASYON KATMANI]
│   │   ├── models.py               # Pydantic istek/yanıt şemaları ve tip doğrulaması
│   │   ├── services.py             # SimulationService: Simülasyon ve Design Study motoru
│   │   └── app.py                  # FastAPI REST API uç noktaları
│   │
│   ├── reporting/                  <-- [MÜHENDİSLİK RAPORLAMA KATMANI]
│   │   └── report_generator.py     # ReportLab tabanlı profesyonel PDF onay raporu üreticisi
│   │
│   └── static/                     <-- [BATTERY THERMAL WORKBENCH ARAYÜZÜ]
│       ├── index.html              # SimScale Workbench 4-katmanlı UI şablonu ve modallar
│       ├── app.js                  # Etkileşimli Canvas, animatör, Chart.js ve REST istemcisi
│       └── style.css               # Modern CAE koyu tema ve duyarlı CSS grid tasarımı
│
├── data/                           <-- [ÇİFT KATMANLI VERİTABANI]
│   ├── chemistry_library.json      # Onaylı DSC/ARC NMC, NMC811, LFP şablonları
│   ├── materials_library.json      # Onaylı Aerojel, Mika, Silikon, Epoksi özellikleri
│   ├── user_chemistry_library.json # Kullanıcının eklediği özel kimyalar
│   ├── user_materials_library.json # Kullanıcının eklediği özel termal bariyerler
│   └── user_formats_library.json   # Kullanıcının tanımladığı özel hücre ebatları
│
└── tests/                          <-- [BİRİM VE ENTEGRASYON TEST SÜİTİ]
    ├── test_api.py                 # REST API ve HTTP uç nokta testleri
    ├── test_arc_validation.py      # Tek hücre literatür ARC fırın test validasyonu
    ├── test_design_study.py        # Gelişmiş fizik ve parametre tarama (sweep) testleri
    ├── test_geometry.py            # Geometri, mesafe ve komşuluk bağlama testleri
    ├── test_kinetics.py            # Arrhenius reaksiyon hızı ve entalpi sınır testleri
    ├── test_propagation.py         # 2 hücreli yayılım ve aerojel tutulum testleri
    └── test_thermal_network.py     # İletkenlik matrisi simetrisi ve enerji denkliği
```

### 7.1 Modül Sorumluluk Matrisi

| Modül | Fiziksel ve Mühendislik Sorumluluğu | Temel Sınıf ve Fonksiyonlar |
| :--- | :--- | :--- |
| [`constants.py`](file:///C:/Users/maozk/Desktop/Termal%20Ka%C3%A7ak%20Sim/simulator/core/constants.py) | Temel fizik sabitleri, standart hücre ebatları, durum enum'ları. | `STEFAN_BOLTZMANN`, `CYLINDRICAL_SPECS`, `PropagationStatus` |
| [`cell_model.py`](file:///C:/Users/maozk/Desktop/Termal%20Ka%C3%A7ak%20Sim/simulator/core/cell_model.py) | Hücre geometrisi, izdüşüm alanları ve toplam termal kapasite ($m C_p$). | `CellGeometry`, `CellModel` |
| [`pack_geometry.py`](file:///C:/Users/maozk/Desktop/Termal%20Ka%C3%A7ak%20Sim/simulator/core/pack_geometry.py) | Grid/Staggered yerleşim, Von Neumann komşuluk tespiti, dışa açık alan hesabı. | `PackGeometryBuilder.build_pack()` |
| [`kinetics_engine.py`](file:///C:/Users/maozk/Desktop/Termal%20Ka%C3%A7ak%20Sim/simulator/core/kinetics_engine.py) | Arrhenius kimyasal reaksiyon hızı $d\alpha/dt$ ve ekzotermik güç $\dot{Q}_{chem}$. | `ArrheniusKineticsEngine.reaction_rate()`, `heat_generation_rate()` |
| [`thermal_network.py`](file:///C:/Users/maozk/Desktop/Termal%20Ka%C3%A7ak%20Sim/simulator/core/thermal_network.py) | İletkenlik Laplasyeni, radyasyon, venting ve soğutma akıları ile ODE türev hesabı. | `ThermalNetworkAssembler.compute_derivatives()` |
| [`solver.py`](file:///C:/Users/maozk/Desktop/Termal%20Ka%C3%A7ak%20Sim/simulator/core/solver.py) | SciPy `solve_ivp(method="LSODA")` adaptif integrasyonu ve olay eşik yakalayıcıları. | `ThermalRunawaySolver.solve()` |
| [`propagation_evaluator.py`](file:///C:/Users/maozk/Desktop/Termal%20Ka%C3%A7ak%20Sim/simulator/core/propagation_evaluator.py) | UL 9540A ön-taraması, yayılım grafiği (DAG), güvenlik payı ve 4-faktörlü risk skoru. | `PropagationEvaluator.evaluate()` |
| [`services.py`](file:///C:/Users/maozk/Desktop/Termal%20Ka%C3%A7ak%20Sim/simulator/api/services.py) | Uçtan uca simülasyon orkestrasyonu, gelişmiş fizik enjeksiyonu ve Design Study motoru. | `SimulationService.run_simulation()`, `run_design_study()` |
| [`report_generator.py`](file:///C:/Users/maozk/Desktop/Termal%20Ka%C3%A7ak%20Sim/simulator/reporting/report_generator.py) | Sayfalara bölünmüş profesyonel mühendislik PDF onay sertifikası üretimi. | `ReportGenerator.generate_pdf_report()` |

### 7.2 Çift Katmanlı Malzeme ve Kimya Kütüphanesi Depolaması
* **Onaylı Çekirdek Kütüphane (`data/*_library.json`):** Değiştirilemez, literatür onaylı DSC/ARC verilerini içerir (`literature_calibrated`).
* **Kullanıcı Kütüphanesi (`data/user_*_library.json`):** Kullanıcının UI üzerindeki **Kütüphane Yöneticisi** veya modallardan tanımladığı özel verilerdir (`user_defined`). Üretilen PDF raporlarında bu veriler sarı uyarı etiketiyle belirtilir.

---

## 8. REST API Sözleşmeleri ve Veri Modelleri

Sistem, harici otomasyon betikleri veya CI/CD boru hatları tarafından çağrılabilen tam teşekküllü bir RESTful API sunar:

| HTTP Metodu | Uç Nokta | Açıklama |
| :--- | :--- | :--- |
| `POST` | `/api/simulations/run` | Tekil simülasyon başlatır ve anında çözerek sonuç/değerlendirme nesnesini döner. |
| `POST` | `/api/simulations/design-study` | Parametrik tarama (Design Study) başlatır, tüm vakaları çözer ve en güvenli tasarımı sıralar. |
| `GET` | `/api/simulations` | Geçmiş simülasyonların özet listesini döner. |
| `GET` | `/api/simulations/{job_id}/results` | Tam zaman serisi ($T(t), \alpha(t)$) ve değerlendirme metriklerini döner. |
| `GET` | `/api/simulations/{job_id}/report` | Resmi ReportLab onay PDF raporunu binary stream olarak indirir. |
| `GET/POST/DEL`| `/api/libraries/*` | Özel kimya, malzeme ve format kütüphanesi CRUD işlemleri. |

---

## 9. Doğrulama, Kabul Kriterleri ve 16 Birim Testi

Sistemin termodinamik tutarlılığı, sayısal kararlılığı ve işlevselliği `tests/` dizinindeki 16 adet otomatik birim testi ile kesintisiz garanti altına alınmıştır (`pytest tests/ -v`):

1. **`test_api_health`:** FastAPI uygulamasının ayakta ve sağlıklı olduğunu doğrular.
2. **`test_api_chemistry_library`:** Kütüphanedeki kimyasal verilerin eksiksiz yüklendiğini kontrol eder.
3. **`test_api_simulation_run_and_report_download`:** Simülasyon koşturma ve PDF rapor çıktısı alma uçtan uca akışını test eder.
4. **`test_single_cell_arc_nmc_runaway_validation`:** Tek hücre adiabatik kalorimetre (ARC) deneyini doğrular; hücrenin $T_{onset}$ ve $T_{trigger}$ eşiklerine ulaşıp ekzotermik kaçak ürettiğini kanıtlar.
5. **`test_advanced_physics_injection`:** Gelişmiş Fizik modunda kullanıcı tarafından girilen özel $A, E_a, n, \Delta H, h_{vent}$ parametrelerinin çözücüye hatasız aktarıldığını doğrular.
6. **`test_spacing_design_study`:** $1.5\text{ mm}$ ve $3.5\text{ mm}$ aralık taramasında, mesafenin artmasının modül risk skorunu düşürdüğünü doğrular.
7. **`test_separator_design_study`:** Separatörsüz ve aerojelli 4 farklı durumun taranıp en güvenli vakanın doğru önerildiğini test eder.
8. **`test_cylindrical_pack_builder_grid`:** Silindirik hücrelerin 2D grid koordinatlarına hatasız dizildiğini kontrol eder.
9. **`test_prismatic_pack_builder`:** Prizmatik hücre paket geometrisi inşasını test eder.
10. **`test_arrhenius_kinetics_library_loading`:** Kimya JSON kütüphanesinin model nesnelerine doğru dönüştürüldüğünü teyit eder.
11. **`test_reaction_rate_boundaries`:** $\alpha \ge 1$ veya $\alpha \le 0$ durumlarında kimyasal reaksiyon türevinin fiziksel sıfırlanmasını test eder.
12. **`test_heat_generation_calculation`:** $\dot{Q}_{chem}$ entalpi ısı üretiminin termodinamik doğruluğunu test eder.
13. **`test_two_cell_propagation_uninsulated`:** Yalıtımsız yan yana iki hücrede termal kaçağın komşuya kesinlikle sıçradığını (zincirleme yayılım) teyit eder.
14. **`test_two_cell_containment_with_aerogel`:** Araya $2\text{ mm}$ silika aerojel bariyer konulduğunda komşu hücrenin kaçaktan korunduğunu (Single-Cell Containment) kanıtlar.
15. **`test_conductance_matrix_symmetry`:** Hücreler arası iletkenlik Laplasyen matrisinin simetrik olduğunu ($G_{ij} = G_{ji}$) ve enerji korunumunun sağlandığını teyit eder.
16. **`test_energy_balance_isolated_equilibrium`:** Dışa kapalı adyabatik bir sistemde toplam enerjinin korunduğunu doğrular.

---

## 10. Mühendislik Sınırları, Kabuller ve Gelecek Geliştirmeler

Simülasyon sonuçları yorumlanırken aşağıdaki mühendislik sınırları göz önünde bulundurulmalıdır:

1. **Toplu Isıl Kapasite (Lumped Capacitance) Kabulü:** Hücre içindeki radyal sıcaklık gradyanı, modül geneli yayılım hızına kıyasla ihmal edilebilir kabul edilmiştir ($Bi < 0.1$). Tek hücre içi detaylı termal gradyanlar için gelecekte çok düğümlü silindirik çekirdek-kabuk modeli planlanmaktadır.
2. **Yarı-Ampirik Gaz Fazı:** Gaz dinamiği tam Navier-Stokes ile değil, kalibre edilmiş konvektif taşınım ($h_{vent}$) akısı olarak modellenir. Bu, hesaplama süresini günler yerine saniyelere indiren bilinçli bir mühendislik tercihidir.
3. **Mekanik Şarapnel Etkileri:** Patlayan hücre kapağının komşuya mekanik çarpması sonucu oluşabilecek deformasyonlar model kapsamı dışındadır.

---
*Bu teknik kılavuz, batarya sistem ve termal yönetim mühendislerinin simülasyon mantığını, matematiksel arka planını ve kod mimarisini doğrulaması amacıyla güncellenmiştir.*
