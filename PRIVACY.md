# Gizlilik Politikası / Privacy Policy

`turk-hukuku-ictihat-mcp`, Türk yargı kararlarını resmî kaynaklardan yapay zekâ araçlarına
açan bir **MCP sunucusudur.** Tamamen **sizin makinenizde / oturumunuzda** çalışır.

## Veri toplama: YOK

- Sunucu **hiçbir kişisel veri toplamaz, saklamaz veya proje sahibine göndermez.**
- **Telemetri, analitik, izleme yoktur.** Kaynak kodda loglama, veritabanı veya disk
  önbelleği bulunmaz; sorgular ve sonuçlar **kalıcı olarak saklanmaz.**
- Getirilen kararlar yalnızca oturum boyunca bellekte tutulur (en çok 256 karar), aynı
  karar yeniden istenince siteye tekrar gidilmez; sunucu kapanınca silinir.
- Proje sahibi sizin sorgularınıza **erişemez.**

## Dışarıya giden bağlantılar

Sunucu yalnızca aşağıdaki resmî, kamuya açık karar kaynaklarına bağlanır:

- **`https://bedesten.adalet.gov.tr`**: Adalet Bakanlığı Mevzuat ve İçtihat (Yargıtay kararları)
- **`https://emsal.uyap.gov.tr`**: UYAP Emsal (Bölge Adliye / ilk derece)
- **`https://karararama.danistay.gov.tr`**: Danıştay karar arama
- **`https://kararlarbilgibankasi.anayasa.gov.tr`**: AYM bireysel başvuru ve norm denetimi kararları

Arama ifadeniz yalnızca seçtiğiniz mahkemeye ait resmî site(ler)e iletilir (varsayılan
`adli` arama hem `bedesten.adalet.gov.tr` hem `emsal.uyap.gov.tr` adresine gider); başka
hiçbir üçüncü tarafa gitmez. Bu sitelere yapılan istekler, ilgili kurumun kendi gizlilik ve
erişim koşullarına tabidir.

## Resmî sitelere karşı tutum

- Sunucu bu sitelere kendi adıyla bağlanır: her istekte User-Agent olarak
  `turk-hukuku-ictihat-mcp/<sürüm> (+https://turk-hukuku.com/mcp/)` gönderir; tarayıcı ya da
  resmî uygulama taklidi yapmaz.
- İstekler site başına sıraya konur: aynı siteye aynı anda tek istek gider, iki istek
  arasında en az bir saniye beklenir.
- Captcha çözülmez ve atlanmaz. Site doğrulama isterse, erişimi reddederse (HTTP 403),
  erişim sınırı bildirirse (HTTP 429) ya da karar yerine başka bir sayfaya yönlendirirse
  sunucu durur, isteği yinelemez, o siteye bir süre istek göndermez ve sizi resmî siteye
  yönlendirir.
- Diğer hatalarda (sunucu hatası, bulunamayan karar, ağ hatası) kısa bir Türkçe ileti
  verilir; istek yinelenmez.

## Müvekkil ve kişisel veri uyarısı

Karar ararken **arama ifadenize müvekkil adı veya kişisel veri koymamaya** dikkat edin;
KVKK ve meslek sırrı yükümlülükleriniz sizdedir
(bkz. [`SORUMLULUK-REDDI.md`](./SORUMLULUK-REDDI.md)).

## İletişim

Sorular için bu depoda bir **issue** açabilirsiniz.

---

**In English:** `turk-hukuku-ictihat-mcp` is an MCP server that exposes Turkish court
decisions from official sources to AI tools. It runs entirely **locally** on your
machine/session. It **collects, stores, or transmits no personal data**, has **no
telemetry, analytics, logging, database, or disk cache**, and the maintainer cannot
access your queries. Its outbound connections are **only** to the official public case-law
sites **`bedesten.adalet.gov.tr`**, **`emsal.uyap.gov.tr`**, **`karararama.danistay.gov.tr`** and
**`kararlarbilgibankasi.anayasa.gov.tr`** (the default `adli` search queries the first two);
requests there are subject to those institutions' own policies. Do not put client names or personal data in your search terms.
