"""UYAP Emsal Karar istemcisi: yargı kararlarını resmî kaynaktan arar/çeker.

Veri kaynağı: https://emsal.uyap.gov.tr (Adalet Bakanlığı Emsal Karar Arama).
Kapsam: Yargıtay, Bölge Adliye Mahkemeleri ve ilk derece mahkeme kararları (adli yargı).

İki uç nokta tersine mühendislikle çözüldü:
  POST /aramalist     -> {"data":{"aranan":Q,"arananKelime":Q,"pageSize":N,"pageNumber":M}}
                         künye listesi döndürür (daire, esasNo, kararNo, kararTarihi, durum)
  GET  /getDokuman?id -> kararın tam metni (HTML)

Künye (mahkeme + daire + esas/karar no + tarih) **yapısal** gelir; bu yüzden
model künyeyi metinden ayıklamak zorunda değildir — sahte numara üretme riski yoktur.
"""
from __future__ import annotations

import html as _html
import re

import httpx

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_BASE = "https://emsal.uyap.gov.tr"

_HEADERS = {
    "User-Agent": _UA,
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{_BASE}/",
    "Content-Type": "application/json; charset=UTF-8",
}
# bağlantı 10 sn, okuma/yazma 30 sn: asılı kalan istek sunucuyu uzun süre meşgul etmesin
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _atif(k: dict) -> str:
    """Yapısal künyeden doğrulanabilir atıf dizesi kurar."""
    daire = (k.get("daire") or "").strip()
    esas = (k.get("esasNo") or "").strip()
    karar = (k.get("kararNo") or "").strip()
    tarih = (k.get("kararTarihi") or "").strip()
    return f"{daire}, E.{esas} K.{karar}, T.{tarih}".strip(", ")


def ara(ifade: str, adet: int = 10, sayfa: int = 1) -> dict:
    """UYAP Emsal'de karar arar. Künye listesi + atıf döndürür.

    Dönen her sonuçtaki `id`, `karar_getir`'e verilerek tam metin alınır.
    """
    adet = max(1, min(adet, 50))
    sayfa = max(1, sayfa)
    govde = {"data": {"aranan": ifade, "arananKelime": ifade,
                      "pageSize": adet, "pageNumber": sayfa}}
    r = httpx.post(f"{_BASE}/aramalist", json=govde, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    cevap = r.json()
    if (cevap.get("metadata") or {}).get("FMTY") == "ERROR":
        raise LookupError((cevap["metadata"]).get("FMTE", "UYAP Emsal hatası"))
    govde_veri = cevap.get("data") or {}
    kayitlar = govde_veri.get("data") or []
    sonuclar = [{
        "id": str(k.get("id", "")),
        "mahkeme": k.get("daire"),
        "esas_no": k.get("esasNo"),
        "karar_no": k.get("kararNo"),
        "karar_tarihi": k.get("kararTarihi"),
        "durum": k.get("durum"),
        "atif": _atif(k),
    } for k in kayitlar]
    return {"ifade": ifade, "sayfa": sayfa,
            "toplam": govde_veri.get("recordsTotal", 0), "sonuclar": sonuclar}


def _metne_cevir(html_metin: str) -> str:
    s = re.sub(r"(?i)<br\s*/?>", "\n", html_metin)
    s = re.sub(r"(?i)</(p|div|tr)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def karar(karar_id: str) -> dict:
    """Bir kararın tam metnini UYAP Emsal'den çeker (id arama sonucundan gelir).

    Dönen `metin` kararın resmî tam metnidir (künye + gerekçe + hüküm). Metni ve
    künyeyi aynen aktar; karar numarası/tarihi değiştirme, uydurma.
    """
    karar_id = str(karar_id).strip()
    r = httpx.get(f"{_BASE}/getDokuman", params={"id": karar_id},
                  headers={"User-Agent": _UA, "Referer": f"{_BASE}/"}, timeout=_TIMEOUT)
    r.raise_for_status()
    cevap = r.json()
    ham = cevap.get("data")
    if not ham:
        raise LookupError(
            f"id={karar_id} için karar metni bulunamadı. id'yi ictihat_ara "
            f"sonucundan alın.")
    metin = _metne_cevir(ham)
    return {"id": karar_id, "kaynak": f"{_BASE}/getDokuman?id={karar_id}",
            "uzunluk": len(metin), "metin": metin}
