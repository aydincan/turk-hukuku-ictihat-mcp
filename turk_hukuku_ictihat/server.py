"""turk-hukuku-ictihat MCP sunucusu.

Türk yargı kararlarını (UYAP Emsal: Yargıtay + Bölge Adliye + ilk derece) resmî
kaynaktan arar ve getirir. Amaç: model bir karara atıf yaparken künyeyi (mahkeme,
daire, esas/karar no, tarih) **hafızadan değil resmî kaynaktan** alsın — sahte
karar numarası üretmesin.

Çalıştırma:  python -m turk_hukuku_ictihat
Taşıma:      stdio (Claude Code / Codex / Gemini CLI ile uyumlu)
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import uyap

mcp = FastMCP("turk-hukuku-ictihat")


@mcp.tool()
def ictihat_ara(ifade: str, adet: int = 10, sayfa: int = 1) -> dict:
    """UYAP Emsal'de yargı kararı arar (Yargıtay/BAM/ilk derece — adli yargı).

    Bir karara atıf yapmadan ÖNCE bunu çağır. Dönen her sonuç yapısal künye taşır
    (mahkeme, esas_no, karar_no, karar_tarihi, durum) ve hazır bir `atif` dizesi
    verir — bunları aynen kullan, uydurma. Tam metin için sonuçtaki `id` ile
    `karar_getir`'i çağır.

    adet: en çok kaç sonuç (1-50). sayfa: sayfalama (1'den başlar).
    """
    return uyap.ara(ifade, adet=adet, sayfa=sayfa)


@mcp.tool()
def karar_getir(karar_id: str) -> dict:
    """Bir kararın resmî TAM metnini getirir (id, ictihat_ara sonucundan gelir).

    Dönen `metin` kararın künyesi + gerekçesi + hükmüdür. Metni ve künyeyi aynen
    aktar; esas/karar numarasını ve tarihi değiştirme.
    """
    return uyap.karar(karar_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
