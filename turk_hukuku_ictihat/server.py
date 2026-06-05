"""turk-hukuku-ictihat MCP sunucusu.

Türk yargı kararlarını resmî kaynaktan arar ve getirir:
  - **adli yargı** (Yargıtay + Bölge Adliye + ilk derece) → UYAP Emsal
  - **idari yargı** (Danıştay) → Danıştay Karar Arama

Amaç: model bir karara atıf yaparken künyeyi (mahkeme, daire, esas/karar no, tarih)
**hafızadan değil resmî kaynaktan** alsın — sahte karar numarası üretmesin.

Çalıştırma:  python -m turk_hukuku_ictihat
Taşıma:      stdio (Claude Code / Codex / Gemini CLI ile uyumlu)
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import danistay, uyap

mcp = FastMCP("turk-hukuku-ictihat")

_KAYNAK = {"adli": uyap, "idari": danistay}


def _coz(mahkeme: str):
    m = (mahkeme or "adli").strip().lower()
    if m in ("yargıtay", "yargitay", "emsal", "bam"):
        m = "adli"
    elif m in ("danıştay", "danistay", "idare"):
        m = "idari"
    if m not in _KAYNAK:
        raise ValueError("mahkeme yalnızca 'adli' (Yargıtay/BAM) ya da 'idari' (Danıştay) olabilir.")
    return m, _KAYNAK[m]


@mcp.tool()
def ictihat_ara(ifade: str, mahkeme: str = "adli", adet: int = 10, sayfa: int = 1) -> dict:
    """Türk yargı kararı arar; künye + atıf + `id` döndürür.

    Bir karara atıf yapmadan ÖNCE bunu çağır. Dönen her sonuç yapısal künye taşır
    (mahkeme, esas_no, karar_no, karar_tarihi) ve hazır bir `atif` dizesi verir —
    bunları aynen kullan, uydurma. Tam metin için sonuçtaki `id` ile aynı `mahkeme`
    değerini `karar_getir`'e geçir.

    mahkeme: "adli" (Yargıtay + Bölge Adliye + ilk derece, UYAP Emsal) ya da
             "idari" (Danıştay). Varsayılan "adli".
    adet: en çok kaç sonuç (1-50). sayfa: sayfalama (1'den başlar).
    """
    m, istemci = _coz(mahkeme)
    sonuc = istemci.ara(ifade, adet=adet, sayfa=sayfa)
    sonuc["mahkeme_turu"] = m
    return sonuc


@mcp.tool()
def karar_getir(karar_id: str, mahkeme: str = "adli") -> dict:
    """Bir kararın resmî TAM metnini getirir (id + mahkeme, ictihat_ara sonucundan).

    Dönen `metin` kararın künyesi + gerekçesi + hükmüdür. Metni ve künyeyi aynen
    aktar; esas/karar numarasını ve tarihi değiştirme. `mahkeme`, aramada kullandığın
    değerle aynı olmalı ("adli" → UYAP Emsal, "idari" → Danıştay).
    """
    m, istemci = _coz(mahkeme)
    sonuc = istemci.karar(karar_id)
    sonuc["mahkeme_turu"] = m
    return sonuc


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
