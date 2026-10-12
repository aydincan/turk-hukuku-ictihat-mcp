# turk-hukuku-ictihat-mcp

Türk **yargı kararlarını** resmî kaynaktan yapay zekâ araçlarına açan bir **MCP sunucusu**:
**Yargıtay** ([Adalet Bakanlığı Mevzuat ve İçtihat](https://mevzuat.adalet.gov.tr)),
**Bölge Adliye ve ilk derece** ([UYAP Emsal](https://emsal.uyap.gov.tr)),
**idari yargı** ([Danıştay](https://karararama.danistay.gov.tr)) ve **anayasa yargısı**
([AYM Kararlar Bilgi Bankası](https://kararlarbilgibankasi.anayasa.gov.tr)).

Amaç tek cümle: model bir karara atıf yaparken künyeyi (**mahkeme, daire, esas/karar no,
tarih**) hafızasından değil **resmî kaynaktan** alsın. Künye yapısal döner; Yargıtay ve
AYM sonuçları kaynak bağlantısı taşır, diğerlerinde bağlantı `karar_getir` ile gelir.
Model yine de yanılabilir; her künyeyi resmî kaynaktan teyit edin.

> **Hukuki danışmanlık değildir.** Bu araç içtihada erişimi kolaylaştırır; kararın güncelliğini,
> kesinleşme durumunu ve somut olaya uygunluğunu siz değerlendirin. Bir kararın bağlayıcılığı
> ve emsal değeri ayrı bir hukuki analiz gerektirir.

Ayrıntı: [`SORUMLULUK-REDDI.md`](./SORUMLULUK-REDDI.md) · [`PRIVACY.md`](./PRIVACY.md) (veri toplama yok, telemetri yok; dış bağlantılar yalnızca resmî karar siteleri).

**Belgeler ve kurulum rehberi:** [turk-hukuku.com/mcp](https://turk-hukuku.com/mcp/) · Terminal kullanmıyorsanız [masaüstü uygulaması](https://turk-hukuku.com/uygulama/) bu sunucuyu kendisi kurup çalıştırır (Mac ve Windows).

---

## Ne yapar

| Tool | İşlev |
|------|-------|
| `ictihat_ara(ifade, mahkeme, adet, sayfa)` | Karar arar; künye + atıf + `id` döndürür |
| `karar_getir(karar_id, mahkeme)` | Bir kararın resmî **tam** metni (künye + gerekçe + hüküm) |

`mahkeme` şu değerleri alır:

| Değer | Kapsam | Kaynak |
|-------|--------|--------|
| **`adli`** (varsayılan) | Yargıtay + Bölge Adliye ve ilk derece, birlikte | Bedesten + UYAP Emsal |
| **`yargitay`** | Yargıtay daireleri ve kurulları | Bedesten (mevzuat.adalet.gov.tr) |
| **`emsal`** | Bölge Adliye hukuk daireleri ve ilk derece | UYAP Emsal |
| **`idari`** | Danıştay | karararama.danistay.gov.tr |
| **`anayasa`** | AYM bireysel başvuru | kararlarbilgibankasi.anayasa.gov.tr |
| **`norm`** | AYM norm denetimi (iptal/itiraz) | aynı kaynak |

`karar_getir`'e aramada kullandığın `mahkeme` değerini aynen geçir (`yargitay:` önekli id
her durumda Yargıtay'dan gelir). Sözcükler birlikte aranır, hepsi geçmeli; tam ifade için
çift tırnak kullan (`"ihtiyaç nedeniyle tahliye"`). Yargıtay, emsal ve AYM aramasında
başına eksi hariç tutar (`-ceza`), `OR` "veya" demektir. Kesme işaretinden sonraki ek
atılır ("TMK'nın" → "TMK"). `adli` aramada `adet` en az 2'dir.

Tipik akış: `ictihat_ara("ihtiyaç nedeniyle tahliye", mahkeme="yargitay")` → sonuçtan bir
`id` seç → `karar_getir(id, mahkeme="yargitay")` → kararın tam metni. Her sonuç hazır bir
`atif` taşır: *"Yargıtay 6. Hukuk Dairesi, E.2015/2565 K.2016/25, T.18.01.2016"* ·
*"Danıştay 6. Daire, E.2023/1084 K.2025/10046"* · *"AYM, B. No: 2020/36883, K.T. 16/12/2025"*.
Yargıtay sonuçları ayrıca kararın herkese açık sayfasını (`kaynak`) verir.

## Kapsam

- **Yargıtay** (`mahkeme="yargitay"`): hukuk ve ceza daireleri ile kurulların kararları;
  Adalet Bakanlığı'nın Mevzuat ve İçtihat Programı'nın arka ucu (bedesten.adalet.gov.tr).
  Her kararın herkese açık sayfası: `https://mevzuat.adalet.gov.tr/ictihat/<id>`.
- **Bölge Adliye ve ilk derece** (`mahkeme="emsal"`): Bölge Adliye Mahkemeleri hukuk
  daireleri ve bazı ilk derece mahkemeleri (asliye ticaret, fikrî ve sınaî haklar); UYAP
  Emsal. Herkese açık UYAP Emsal Yargıtay kararı içermez.
- **Adli yargı birlikte** (`mahkeme="adli"`, varsayılan): iki kaynağı aynı anda arar;
  Yargıtay sonuçlarının id'si `yargitay:` önekini taşır.
- **İdari yargı** (`mahkeme="idari"`): Danıştay kararları (karararama.danistay.gov.tr —
  390.000+ doküman).
- **Anayasa yargısı** (`mahkeme="anayasa"`): AYM bireysel başvuru kararları
  (kararlarbilgibankasi.anayasa.gov.tr).
- **Norm denetimi** (`mahkeme="norm"`): AYM iptal/itiraz kararları; künye E./K.
  numaraları ve Resmî Gazete bilgisiyle döner (aynı kaynak).

## Nasıl çalışır

Her kaynak bir arama + bir belge uç noktası sunar:

```
Bedesten   : POST /emsal-karar/searchDocuments       + POST /emsal-karar/getDocumentContent
UYAP Emsal : POST /aramalist (aranan)               + GET /getDokuman?id
Danıştay   : POST /aramalist (andKelimeler[])        + GET /getDokuman?id&arananKelime
AYM        : POST /api/core/public/search (JSON)     — arama da tam metin de aynı uçtan
```

Sunucu aramayı yapar, künyeleri yapısal döndürür ve metni okunur düz metne çevirir
(Danıştay iç içe HTML kodlamasından, AYM Word-export gövdesinden arındırılır). Tamamen
yereldir; veri toplanmaz.

## Kurulum

[PyPI](https://pypi.org/project/turk-hukuku-ictihat-mcp/)'de yayımlıdır; [`uv`](https://docs.astral.sh/uv/)
ile ayrı kurulum gerekmeden çalışır.

### Claude Code

```bash
claude mcp add turk-hukuku-ictihat -- uvx --from turk-hukuku-ictihat-mcp turk-hukuku-ictihat
```

### OpenAI Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.turk-hukuku-ictihat]
command = "uvx"
args = ["--from", "turk-hukuku-ictihat-mcp", "turk-hukuku-ictihat"]
```

### Gemini CLI

`~/.gemini/settings.json` içindeki `mcpServers` altına:

```json
"turk-hukuku-ictihat": {
  "command": "uvx",
  "args": ["--from", "turk-hukuku-ictihat-mcp", "turk-hukuku-ictihat"]
}
```

### Alternatif: pip

```bash
pip install turk-hukuku-ictihat-mcp
# komut: turk-hukuku-ictihat   (ya da: python -m turk_hukuku_ictihat)
```

İlgili: kanun/mevzuat metni için [`turk-hukuku-mevzuat-mcp`](https://github.com/aydincan/turk-hukuku-mevzuat-mcp).

## Lisans

[MIT](./LICENSE) · © 2026 Aydın Can Polatkan

Veriler kaynak kurumlara aittir ([Adalet Bakanlığı](https://mevzuat.adalet.gov.tr),
[UYAP Emsal](https://emsal.uyap.gov.tr), Danıştay, Anayasa Mahkemesi); bu proje yalnızca kamuya
açık resmî karar metnine erişimi kolaylaştıran bağımsız bir istemcidir.

---

*Bu çalışma, ömrünü Türk yargısına adamış babam Hâkim Vahit Polatkan'ın ebedi anısına
ithaf edilmiştir.*

<!-- mcp-name: io.github.aydincan/turk-hukuku-ictihat-mcp -->
