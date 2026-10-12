"""Yargıtay kararları istemcisi (Adalet Bakanlığı Bedesten servisi).

Veri kaynağı: https://bedesten.adalet.gov.tr (UYAP Mevzuat ve İçtihat Programı'nın arka ucu).
Kararın herkese açık sayfası: https://mevzuat.adalet.gov.tr/ictihat/<id>
UYAP Emsal'in herkese açık arayüzü Yargıtay kararı içermez; Yargıtay buradan gelir.

  POST /emsal-karar/searchDocuments
       {"data":{"phrase":Q,"itemTypeList":["YARGITAYKARARI"],"pageSize":N,"pageNumber":M},
        "applicationName":"UyapMevzuat","paging":true}
       -> künye: documentId, birimAdi, esasNo, kararNo, kararTarihiStr
  POST /emsal-karar/getDocumentContent
       {"data":{"documentId":ID},"applicationName":"UyapMevzuat"}
       -> tam metin: base64 kodlu HTML (mimeType text/html)

Arama sözdizimi: servis düz sözcükleri VEYA ile arar; ifade ortak.ve_sorgusu ile VE
sorgusuna çevrilir (+ zorunlu, - hariç, çift tırnak tam ifade). Servis harf ve rakam
dışındaki işaretleri reddeder ("*" gibi); ve_sorgusu bunları ayıklar.
"""
from __future__ import annotations

import base64
import html as _html
import re

import httpx

from .ortak import erisim_siniri, ve_sorgusu

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_BASE = "https://bedesten.adalet.gov.tr/emsal-karar"
_SAYFA = "https://mevzuat.adalet.gov.tr/ictihat"
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json",
    "Content-Type": "application/json; charset=UTF-8",
    "AdaletApplicationName": "UyapMevzuat",
    "Origin": "https://mevzuat.adalet.gov.tr",
    "Referer": "https://mevzuat.adalet.gov.tr/",
}
# bağlantı 10 sn, okuma/yazma 30 sn: asılı kalan istek sunucuyu uzun süre meşgul etmesin
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_ONEK = "yargitay:"


def _mahkeme(birim: str) -> str:
    birim = (birim or "").strip()
    return birim if not birim or birim.lower().startswith("yargıtay") else f"Yargıtay {birim}"


def _atif(mahkeme: str, esas: str, karar: str, tarih: str) -> str:
    return f"{mahkeme}, E.{esas} K.{karar}, T.{tarih}".strip(", ")


def _post(uc: str, veri: dict, sayfali: bool = False) -> dict:
    govde = {"data": veri, "applicationName": "UyapMevzuat"}
    if sayfali:
        govde["paging"] = True
    r = httpx.post(f"{_BASE}/{uc}", json=govde, headers=_HEADERS, timeout=_TIMEOUT)
    erisim_siniri(r, "Bedesten (Yargıtay)")
    r.raise_for_status()
    cevap = r.json()
    meta = cevap.get("metadata") or {}
    if meta.get("FMTY") == "ERROR":
        raise LookupError(meta.get("FMTE", "Bedesten hatası"))
    return cevap.get("data") or {}


def ara(ifade: str, adet: int = 10, sayfa: int = 1) -> dict:
    """Yargıtay kararı arar (Bedesten). Künye listesi + atıf + kaynak bağlantısı döndürür."""
    adet = max(1, min(adet, 50))
    sayfa = max(1, sayfa)
    veri = _post("searchDocuments", {"phrase": ve_sorgusu(ifade), "itemTypeList": ["YARGITAYKARARI"],
                                     "pageSize": adet, "pageNumber": sayfa}, sayfali=True)
    sonuclar = []
    for k in veri.get("emsalKararList") or []:
        kid = str(k.get("documentId", ""))
        mahkeme = _mahkeme(k.get("birimAdi"))
        esas, karar, tarih = (k.get("esasNo") or ""), (k.get("kararNo") or ""), (k.get("kararTarihiStr") or "")
        sonuclar.append({
            "id": kid,
            "mahkeme": mahkeme,
            "esas_no": esas,
            "karar_no": karar,
            "karar_tarihi": tarih,
            "durum": k.get("kesinlesmeDurumu"),
            "atif": _atif(mahkeme, esas, karar, tarih),
            "kaynak": f"{_SAYFA}/{kid}",
        })
    return {"ifade": ifade, "sayfa": sayfa, "toplam": veri.get("total", 0), "sonuclar": sonuclar}


def _metne_cevir(ham: str) -> str:
    s = re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", "", ham)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def karar(karar_id: str) -> dict:
    """Bir Yargıtay kararının tam metnini çeker (id, ictihat_ara sonucundan gelir)."""
    karar_id = str(karar_id).strip()
    if karar_id.lower().startswith(_ONEK):
        karar_id = karar_id[len(_ONEK):]
    veri = _post("getDocumentContent", {"documentId": karar_id})
    kaynak = f"{_SAYFA}/{karar_id}"
    icerik = veri.get("content")
    if not icerik:
        raise LookupError(f"id={karar_id} için Yargıtay karar metni bulunamadı. id'yi "
                          f"ictihat_ara (mahkeme='yargitay' ya da 'adli') sonucundan alın.")
    if "html" not in (veri.get("mimeType") or "text/html"):
        return {"id": karar_id, "kaynak": kaynak, "uzunluk": 0, "metin": None,
                "uyari": f"Karar metni {veri.get('mimeType')} biçiminde; tam metni kaynak bağlantısından okuyun."}
    metin = _metne_cevir(base64.b64decode(icerik).decode("utf-8", "replace"))
    return {"id": karar_id, "kaynak": kaynak, "uzunluk": len(metin), "metin": metin}
