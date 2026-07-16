# Gizlilik Politikası — Privacy Policy

`turk-hukuku-ictihat-mcp`, Türk yargı kararlarını resmî kaynaklardan yapay zekâ araçlarına
açan bir **MCP sunucusudur.** Tamamen **sizin makinenizde / oturumunuzda** çalışır.

## Veri toplama: YOK

- Sunucu **hiçbir kişisel veri toplamaz, saklamaz veya proje sahibine göndermez.**
- **Telemetri, analitik, izleme yoktur.** Kaynak kodda loglama, veritabanı veya disk
  önbelleği bulunmaz; sorgular ve sonuçlar **kalıcı olarak saklanmaz.**
- Proje sahibi sizin sorgularınıza **erişemez.**

## Dışarıya giden bağlantılar

Sunucu yalnızca aşağıdaki resmî, kamuya açık karar kaynaklarına bağlanır:

- **`https://emsal.uyap.gov.tr`** — UYAP Emsal (Yargıtay / Bölge Adliye / ilk derece)
- **`https://karararama.danistay.gov.tr`** — Danıştay karar arama
- **`https://kararlarbilgibankasi.anayasa.gov.tr`** — AYM Bireysel Başvuru kararları

Arama ifadeniz yalnızca seçtiğiniz mahkemeye ait bu resmî siteye iletilir; başka hiçbir
üçüncü tarafa gitmez. Bu sitelere yapılan istekler, ilgili kurumun kendi gizlilik ve
erişim koşullarına tabidir.

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
sites **`emsal.uyap.gov.tr`**, **`karararama.danistay.gov.tr`** and
**`kararlarbilgibankasi.anayasa.gov.tr`**; requests there are subject to those institutions'
own policies. Do not put client names or personal data in your search terms.
