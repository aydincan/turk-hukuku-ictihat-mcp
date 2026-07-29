"""Danıştay Karar Arama istemcisi (idari yargı).

Veri kaynağı: https://karararama.danistay.gov.tr (Danıştay Başkanlığı).
UYAP Emsal'den iki farkla ayrılır:
  - Arama anahtar kelimeleri **liste** olarak gider (`andKelimeler`), tek string değil.
  - Belge metni JSON değil, **entity-encoded HTML** döner (önce unescape, sonra etiket temizliği).

  POST /aramalist     -> {"data":{"andKelimeler":[...], "orKelimeler":[], "notAndKelimeler":[],
                                   "notOrKelimeler":[], "pageSize":N, "pageNumber":M}}
                         künye: id, daireKurul, esasNo, kararNo, kararTarihi
  GET  /getDokuman?id=<id>&arananKelime=  -> kararın tam metni (HTML)
"""
from __future__ import annotations

import html as _html
import re

import httpx

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_BASE = "https://karararama.danistay.gov.tr"
_HEADERS = {
    "User-Agent": _UA,
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{_BASE}/",
    "Content-Type": "application/json; charset=UTF-8",
}
# bağlantı 10 sn, okuma/yazma 30 sn: asılı kalan istek sunucuyu uzun süre meşgul etmesin
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _atif(k: dict) -> str:
    daire = (k.get("daireKurul") or "").strip()
    if daire and not daire.lower().startswith("danıştay"):
        daire = f"Danıştay {daire}"
    esas = (k.get("esasNo") or "").strip()
    karar = (k.get("kararNo") or "").strip()
    tarih = (k.get("kararTarihi") or "").strip()
    return f"{daire}, E.{esas} K.{karar}, T.{tarih}".strip(", ")


def ara(ifade: str, adet: int = 10, sayfa: int = 1) -> dict:
    """Danıştay'da karar arar (idari yargı). Künye listesi + atıf döndürür."""
    adet = max(1, min(adet, 50))
    sayfa = max(1, sayfa)
    # Boşlukla ayrılmış sözcükler AND mantığıyla aranır
    kelimeler = [w for w in ifade.split() if w]
    govde = {"data": {"andKelimeler": kelimeler or [ifade], "orKelimeler": [],
                      "notAndKelimeler": [], "notOrKelimeler": [],
                      "pageSize": adet, "pageNumber": sayfa}}
    r = httpx.post(f"{_BASE}/aramalist", json=govde, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    cevap = r.json()
    if (cevap.get("metadata") or {}).get("FMTY") == "ERROR":
        raise LookupError((cevap["metadata"]).get("FMTE", "Danıştay arama hatası"))
    govde_veri = cevap.get("data") or {}
    sonuclar = []
    for k in govde_veri.get("data") or []:
        daire = (k.get("daireKurul") or "").strip()
        mahkeme = f"Danıştay {daire}" if daire and not daire.lower().startswith("danıştay") else daire
        sonuclar.append({
            "id": str(k.get("id", "")),
            "mahkeme": mahkeme,
            "esas_no": k.get("esasNo"),
            "karar_no": k.get("kararNo"),
            "karar_tarihi": k.get("kararTarihi"),
            "durum": None,
            "atif": _atif(k),
        })
    return {"ifade": ifade, "sayfa": sayfa,
            "toplam": govde_veri.get("recordsTotal", 0), "sonuclar": sonuclar}


def _metne_cevir(ham: str) -> str:
    s = _html.unescape(ham)                                   # iç içe kodlamayı aç
    s = re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", "", s)   # style/script blokları
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|tr|h[1-6])>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def karar(karar_id: str) -> dict:
    """Bir Danıştay kararının tam metnini çeker (id, ictihat_ara sonucundan gelir)."""
    karar_id = str(karar_id).strip()
    r = httpx.get(f"{_BASE}/getDokuman", params={"id": karar_id, "arananKelime": ""},
                  headers={"User-Agent": _UA, "Referer": f"{_BASE}/"}, timeout=_TIMEOUT)
    r.raise_for_status()
    metin = _metne_cevir(r.text)
    if not metin or len(metin) < 40:
        raise LookupError(
            f"id={karar_id} için Danıştay karar metni bulunamadı. id'yi ictihat_ara "
            f"(mahkeme='idari') sonucundan alın.")
    return {"id": karar_id, "kaynak": f"{_BASE}/getDokuman?id={karar_id}",
            "uzunluk": len(metin), "metin": metin}
