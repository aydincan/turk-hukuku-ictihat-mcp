"""Yargıtay kararları istemcisi (Adalet Bakanlığı Bedesten servisi).

Veri kaynağı: https://bedesten.adalet.gov.tr (UYAP Mevzuat ve İçtihat Programı'nın arka ucu).
Kararın herkese açık sayfası: https://mevzuat.adalet.gov.tr/ictihat/<id>
UYAP Emsal'in herkese açık arayüzü Yargıtay kararı içermez; Yargıtay buradan gelir.

  POST /emsal-karar/searchDocuments
       {"data":{"phrase":Q,"itemTypeList":["YARGITAYKARARI"],"pageSize":N,"pageNumber":M},
        "paging":true}
       -> künye: documentId, birimAdi, esasNo, kararNo, kararTarihiStr
  POST /emsal-karar/getDocumentContent
       {"data":{"documentId":ID}}
       -> tam metin: base64 kodlu HTML (mimeType text/html)

Resmî web uygulamasının adı (gövdede applicationName, başlıkta AdaletApplicationName)
gönderilmez; servis onsuz da yanıt veriyor (Ekim 2026'da denendi). İstekler ortak.istek
kapısından geçer: kendini tanıtan User-Agent, site başına sıra ve sert durma.

Arama sözdizimi: servis düz sözcükleri VEYA ile arar; ifade ortak.ve_sorgusu ile VE
sorgusuna çevrilir (+ zorunlu, - hariç, çift tırnak tam ifade). Servis harf ve rakam
dışındaki işaretleri reddeder ("*" gibi); ve_sorgusu bunları ayıklar.
"""
from __future__ import annotations

import base64
import html as _html
import re

import httpx

from . import ortak
from .ortak import ve_sorgusu

_BASE = "https://bedesten.adalet.gov.tr/emsal-karar"
_SAYFA = "https://mevzuat.adalet.gov.tr/ictihat"
_AD = "Bedesten (Yargıtay)"
_RESMI = "https://mevzuat.adalet.gov.tr"
# Kimlik (User-Agent) ortak.istek'te eklenir; tarayıcı taklidi yapan başlık gönderilmez.
_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json; charset=UTF-8",
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
    govde: dict = {"data": veri}
    if sayfali:
        govde["paging"] = True
    cevap = ortak.json_istek("POST", f"{_BASE}/{uc}", kaynak=_AD, site=_RESMI,
                             json=govde, headers=_HEADERS, timeout=_TIMEOUT)
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
    """Bir Yargıtay kararının tam metnini çeker (id, ictihat_ara sonucundan gelir).

    Dönen `id`, verilen id'nin aynısıdır (`yargitay:` öneki dahil); istemci aramadaki
    sonuçla eşleştirebilsin.
    """
    verilen = str(karar_id).strip()
    belge = verilen[len(_ONEK):] if verilen.lower().startswith(_ONEK) else verilen
    veri = _post("getDocumentContent", {"documentId": belge})
    kaynak = f"{_SAYFA}/{belge}"
    icerik = veri.get("content")
    if not icerik:
        raise LookupError(f"id={verilen} için Yargıtay karar metni bulunamadı. id'yi "
                          f"ictihat_ara (mahkeme='yargitay' ya da 'adli') sonucundan alın.")
    if "html" not in (veri.get("mimeType") or "text/html"):
        return {"id": verilen, "kaynak": kaynak, "uzunluk": 0, "metin": None,
                "uyari": f"Karar metni {veri.get('mimeType')} biçiminde; tam metni kaynak bağlantısından okuyun."}
    metin = _metne_cevir(base64.b64decode(icerik).decode("utf-8", "replace"))
    return {"id": verilen, "kaynak": kaynak, "uzunluk": len(metin), "metin": metin}
