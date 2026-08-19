# turk-hukuku-ictihat-mcp

Türk yargı kararlarını (Yargıtay ve Bölge Adliye: UYAP Emsal, Danıştay, AYM bireysel
başvuru) resmî kaynaklardan yapay zekâ araçlarına açan MCP sunucusu. Bu npm paketi,
PyPI'daki Python sunucusunu `uvx` ile başlatan ince bir sarmalayıcıdır; `npx`
alışkanlığındaki kullanıcılar için ek bir kapıdır.

**Gereksinim:** [uv](https://docs.astral.sh/uv/getting-started/installation/) kurulu
olmalıdır (sunucunun kendisi Python tabanlıdır).

## Kullanım

```bash
npx -y turk-hukuku-ictihat-mcp
```

Claude Code'a eklemek için:

```bash
claude mcp add turk-hukuku-ictihat -- npx -y turk-hukuku-ictihat-mcp
```

uv zaten kuruluysa npm katmanına gerek yoktur; doğrudan da eklenebilir:

```bash
claude mcp add turk-hukuku-ictihat -- uvx --from turk-hukuku-ictihat-mcp turk-hukuku-ictihat
```

## Araçlar

- `ictihat_ara` : karar arama; künye + atıf + id döndürür (adli/idari/anayasa)
- `karar_getir` : bir kararın resmî tam metni

## Bağlantılar

- Site: https://turk-hukuku.com/mcp/
- Kaynak: https://github.com/aydincan/turk-hukuku-ictihat-mcp
- PyPI: https://pypi.org/project/turk-hukuku-ictihat-mcp/

Hukuki danışmanlık değildir; kararlar künyesiyle, resmî kaynaktan aktarılır.

<!-- mcp-name: io.github.aydincan/turk-hukuku-ictihat-mcp -->
