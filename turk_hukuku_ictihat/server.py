"""turk-hukuku-ictihat MCP sunucusu.

Türk yargı kararlarını resmî kaynaktan arar ve getirir:
  - **Yargıtay** → Adalet Bakanlığı Bedesten (mevzuat.adalet.gov.tr)
  - **Bölge Adliye + ilk derece** → UYAP Emsal
  - **adli** (varsayılan) → ikisi birlikte
  - **idari yargı** (Danıştay) → Danıştay Karar Arama
  - **anayasa yargısı** (AYM bireysel başvuru + norm denetimi) → Kararlar Bilgi Bankası

Amaç: model bir karara atıf yaparken künyeyi (mahkeme, daire, esas/karar no, tarih)
**hafızadan değil resmî kaynaktan** alsın; sahte karar numarası üretmesin.

Erişim kuralları (ortak.py): sunucu kendini User-Agent ile tanıtır, aynı siteye saniyede
en çok bir istek gönderir, captcha ve erişim sınırında durur (yeniden denemez); getirilen
kararlar süreç içinde id ile önbellekte tutulur.

Çalıştırma:  python -m turk_hukuku_ictihat
Taşıma:      stdio (Claude Code / Codex / Gemini CLI ile uyumlu)
"""
from __future__ import annotations

from functools import partial

import anyio
from mcp.server.fastmcp import FastMCP

from . import adli, anayasa, danistay, uyap, yargitay
from .ortak import karar_onbellegi

mcp = FastMCP("turk-hukuku-ictihat")

_KAYNAK = {"adli": adli, "yargitay": yargitay, "emsal": uyap, "idari": danistay,
           "anayasa": anayasa, "norm": anayasa.norm}


_TR = str.maketrans("ışğüöç", "isguoc")


def _sade(s: str) -> str:
    """Türkçe büyük/küçük harfi ASCII'ye indirger: 'İSTİNAF' -> 'istinaf', 'DANIŞTAY' -> 'danistay'.

    str.lower() 'İ'yi 'i' + birleşik nokta yapar; önce İ'yi i'ye çeviririz.
    """
    return s.strip().replace("İ", "i").replace("I", "ı").lower().replace("\u0307", "").translate(_TR)


def _coz(mahkeme: str):
    m = _sade(mahkeme or "") or "adli"
    if m in ("yargitay karari",):
        m = "yargitay"
    elif m in ("uyap", "uyap emsal", "bam", "bolge adliye", "istinaf"):
        m = "emsal"
    elif m in ("danistay", "idare"):
        m = "idari"
    elif m in ("aym", "anayasa mahkemesi", "bireysel", "bireysel basvuru"):
        m = "anayasa"
    elif m in ("norm denetimi", "normdenetimi", "norm-denetimi", "iptal", "itiraz"):
        m = "norm"
    if m not in _KAYNAK:
        raise ValueError("mahkeme yalnızca 'adli' (Yargıtay + BAM/ilk derece), 'yargitay', "
                         "'emsal' (BAM/ilk derece), 'idari' (Danıştay), 'anayasa' (AYM "
                         "bireysel başvuru) ya da 'norm' (AYM norm denetimi: iptal/itiraz) olabilir.")
    return m, _KAYNAK[m]


# FastMCP senkron araçları event loop üzerinde çalıştırır; bloklayan HTTP çağrısı
# tüm sunucuyu kilitler, bu yüzden işi worker thread'e taşıyoruz.
@mcp.tool()
async def ictihat_ara(ifade: str, mahkeme: str = "adli", adet: int = 10, sayfa: int = 1) -> dict:
    """Türk yargı kararı arar; künye + atıf + `id` döndürür.

    Bir karara atıf yapmadan ÖNCE bunu çağır. Dönen her sonuç yapısal künye taşır
    (mahkeme, esas_no, karar_no, karar_tarihi) ve hazır bir `atif` dizesi verir;
    bunları aynen kullan, uydurma. Tam metin için sonuçtaki `id` ile aynı `mahkeme`
    değerini `karar_getir`'e geçir.

    mahkeme: "adli" (varsayılan: Yargıtay + Bölge Adliye/ilk derece birlikte),
             "yargitay" (yalnız Yargıtay daireleri ve kurulları),
             "emsal" (yalnız Bölge Adliye hukuk daireleri ve ilk derece, UYAP Emsal),
             "idari" (Danıştay), "anayasa" (AYM bireysel başvuru) ya da
             "norm" (AYM norm denetimi: kanun/KHK iptal ve itiraz kararları).
    ifade: sözcükler birlikte aranır (hepsi geçmeli); tam ifade için çift tırnak
           ("ihtiyaç nedeniyle tahliye"). Yargıtay, emsal ve AYM aramasında başına eksi
           hariç tutar (-ceza), OR "veya" demektir. Her sonuç kararın resmî sayfasına
           `kaynak` bağlantısı taşır.
    adet: en çok kaç sonuç (1-50; "adli"de en az 2, iki kaynağa bölünür).
    sayfa: sayfalama (1'den başlar).
    """
    m, istemci = _coz(mahkeme)
    sonuc = await anyio.to_thread.run_sync(partial(istemci.ara, ifade, adet=adet, sayfa=sayfa))
    sonuc["mahkeme_turu"] = m
    return sonuc


@mcp.tool()
async def karar_getir(karar_id: str, mahkeme: str = "adli") -> dict:
    """Bir kararın resmî TAM metnini getirir (id + mahkeme, ictihat_ara sonucundan).

    Dönen `metin` kararın künyesi + gerekçesi + hükmüdür. Metni ve künyeyi aynen
    aktar; esas/karar numarasını ve tarihi değiştirme. `mahkeme`, aramada kullandığın
    değerle aynı olmalı ("adli" → id önekine göre Yargıtay ya da UYAP Emsal,
    "yargitay" → Bedesten, "emsal" → UYAP Emsal, "idari" → Danıştay, "anayasa" → AYM
    bireysel başvuru, "norm" → AYM norm denetimi). `yargitay:` önekli id, `mahkeme`
    ne olursa olsun Yargıtay kaynağından getirilir.
    """
    if str(karar_id).strip().lower().startswith("yargitay:"):
        m, istemci = "yargitay", yargitay
    else:
        m, istemci = _coz(mahkeme)
    anahtar = (m, str(karar_id).strip())        # tam id; "yargitay:" öneki dahil
    sonuc = karar_onbellegi.al(anahtar)
    if sonuc is None:
        sonuc = await anyio.to_thread.run_sync(partial(istemci.karar, karar_id))
        karar_onbellegi.koy(anahtar, sonuc)
    sonuc["mahkeme_turu"] = m
    return sonuc


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
