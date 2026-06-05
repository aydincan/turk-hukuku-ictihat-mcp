# turk-hukuku-ictihat-mcp

Türk **yargı kararlarını** resmî kaynaktan ([UYAP Emsal Karar](https://emsal.uyap.gov.tr) —
Adalet Bakanlığı) yapay zekâ araçlarına açan bir **MCP sunucusu**.

Amaç tek cümle: model bir karara atıf yaparken künyeyi (**mahkeme, daire, esas/karar no,
tarih**) hafızasından değil **resmî kaynaktan** alsın. UYAP Emsal künyeyi yapısal döndürür;
böylece model künye uydurmaz, **sahte karar numarası üretmez.**

> **Hukuki danışmanlık değildir.** Bu araç içtihada erişimi kolaylaştırır; kararın güncelliğini,
> kesinleşme durumunu ve somut olaya uygunluğunu siz değerlendirin. Bir kararın bağlayıcılığı
> ve emsal değeri ayrı bir hukuki analiz gerektirir.

---

## Ne yapar

| Tool | İşlev |
|------|-------|
| `ictihat_ara(ifade, adet, sayfa)` | Karar arar; künye + atıf + `id` döndürür |
| `karar_getir(karar_id)` | Bir kararın resmî **tam** metni (künye + gerekçe + hüküm) |

Tipik akış: `ictihat_ara("kira sözleşmesi tahliye")` → sonuçtan bir `id` seç →
`karar_getir(id)` → kararın tam metni. Her sonuç hazır bir `atif` dizesi taşır:
*"İstanbul BAM 1. Hukuk Dairesi, E.2019/1405 K.2019/1934, T.30.12.2019"*.

## Kapsam

- **Adli yargı:** Yargıtay, Bölge Adliye Mahkemeleri ve ilk derece mahkeme kararları
  (UYAP Emsal — 800.000+ karar).
- **Planlanan:** Danıştay (idari yargı) ve Anayasa Mahkemesi kararları. Bu sistemler ayrı
  arama altyapıları (ve kısmen CAPTCHA) kullandığından henüz kapsam dışıdır.

## Nasıl çalışır

UYAP Emsal iki uç nokta sunar:

```
POST /aramalist     -> künye listesi (daire, esasNo, kararNo, kararTarihi, durum)
GET  /getDokuman?id -> kararın tam metni
```

Sunucu aramayı yapar, künyeleri yapısal döndürür ve metni okunur düz metne çevirir.
Tamamen yereldir; hiçbir veri toplanmaz.

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
