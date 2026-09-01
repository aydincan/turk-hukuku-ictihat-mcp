# turk-hukuku-ictihat-mcp

Türk **yargı kararlarını** resmî kaynaktan yapay zekâ araçlarına açan bir **MCP sunucusu**:
**adli yargı** ([UYAP Emsal](https://emsal.uyap.gov.tr) — Yargıtay/Bölge Adliye/ilk derece),
**idari yargı** ([Danıştay](https://karararama.danistay.gov.tr)) ve **anayasa yargısı**
([AYM Bireysel Başvuru](https://kararlarbilgibankasi.anayasa.gov.tr)).

Amaç tek cümle: model bir karara atıf yaparken künyeyi (**mahkeme, daire, esas/karar no,
tarih**) hafızasından değil **resmî kaynaktan** alsın. UYAP Emsal künyeyi yapısal döndürür;
böylece model künye uydurmaz, **sahte karar numarası üretmez.**

> **Hukuki danışmanlık değildir.** Bu araç içtihada erişimi kolaylaştırır; kararın güncelliğini,
> kesinleşme durumunu ve somut olaya uygunluğunu siz değerlendirin. Bir kararın bağlayıcılığı
> ve emsal değeri ayrı bir hukuki analiz gerektirir.

Ayrıntı: [`SORUMLULUK-REDDI.md`](./SORUMLULUK-REDDI.md) · [`PRIVACY.md`](./PRIVACY.md) (veri toplama yok, telemetri yok; dış bağlantılar yalnızca resmî karar siteleri).

---

## Ne yapar

| Tool | İşlev |
|------|-------|
| `ictihat_ara(ifade, mahkeme, adet, sayfa)` | Karar arar; künye + atıf + `id` döndürür |
| `karar_getir(karar_id, mahkeme)` | Bir kararın resmî **tam** metni (künye + gerekçe + hüküm) |

`mahkeme` üç değer alır: **`adli`** (Yargıtay + Bölge Adliye + ilk derece — UYAP Emsal,
varsayılan), **`idari`** (Danıştay) ya da **`anayasa`** (AYM bireysel başvuru).
`karar_getir`'e aramada kullandığın `mahkeme` değerini aynen geçir.

Tipik akış: `ictihat_ara("imar planı iptal", mahkeme="idari")` → sonuçtan bir `id` seç →
`karar_getir(id, mahkeme="idari")` → kararın tam metni. Her sonuç hazır bir `atif` taşır:
*"Danıştay 6. Daire, E.2023/1084 K.2025/10046"* · *"AYM, B. No: 2020/36883, K.T. 16/12/2025"*.

## Kapsam

- **Adli yargı** (`mahkeme="adli"`): Yargıtay, Bölge Adliye Mahkemeleri ve ilk derece
  mahkeme kararları (UYAP Emsal — 800.000+ karar).
- **İdari yargı** (`mahkeme="idari"`): Danıştay kararları (karararama.danistay.gov.tr —
  390.000+ doküman).
- **Anayasa yargısı** (`mahkeme="anayasa"`): AYM bireysel başvuru kararları
  (kararlarbilgibankasi.anayasa.gov.tr).
- **Planlanan:** AYM norm denetimi (iptal/itiraz) kararları.

## Nasıl çalışır

Her kaynak bir arama + bir belge uç noktası sunar:

```
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

Veri kaynağı [UYAP Emsal](https://emsal.uyap.gov.tr)'a (Adalet Bakanlığı) aittir; bu proje
yalnızca kamuya açık resmî karar metnine erişimi kolaylaştıran bağımsız bir istemcidir.

---

*Bu çalışma, ömrünü Türk yargısına adamış babam Hâkim Vahit Polatkan'ın ebedi anısına
ithaf edilmiştir.*

<!-- mcp-name: io.github.aydincan/turk-hukuku-ictihat-mcp -->
