"""Anayasa Mahkemesi — Bireysel Başvuru kararları istemcisi.

Veri kaynağı: https://kararlarbilgibankasi.anayasa.gov.tr (AYM Kararlar Bilgi Bankası).
KBB Haziran 2026'da yenilendi: eski HTML uçları (GET /Ara) kaldırıldı, arama ve
tam metin artık tek bir JSON API'sinden servis ediliyor:

  POST /api/core/public/search   gövde: {"kararTipi": "BireyselBasvuru", ...}
    arama:      {"query": <ifade>, "page": N, "size": N}
    no ile:     {"basvuruNo": "<yil/no>"}          -> tek kayıt (uuid çözümü)
    tam metin:  {"id": "<uuid>", "page": 1, "size": 1}  -> kayit["icerik"] (HTML)

Gövde ham UTF-8 gönderilir (API aksi hâlde 400 döndürebiliyor). Künye alanları
(başvuru no, karar tarihi, sonuç, bölüm) API'nin yapısal alanlarından okunur;
model künye uydurmaz. Kararın insan yüzlü adresi değişmedi: /BB/<yil>/<no>.
"""
from __future__ import annotations

import html as _html
import json
import re

import httpx

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_BASE = "https://kararlarbilgibankasi.anayasa.gov.tr"
_API = f"{_BASE}/api/core/public/search"
_HEADERS = {"User-Agent": _UA,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "Referer": f"{_BASE}/"}
# bağlantı 10 sn, okuma/yazma 30 sn: asılı kalan istek sunucuyu uzun süre meşgul etmesin
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_UUID = re.compile(r"^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
_BASVURU_NO = re.compile(r"(\d{4})/(\d+)")


def _post(payload: dict) -> dict:
    ham = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = httpx.post(_API, content=ham, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _duz(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", _html.unescape(s or ""))).strip()


def _tarih(iso: str | None) -> str | None:
    """'2016-09-28' -> '28/9/2016' (atıflardaki alışılmış gün/ay/yıl biçimi)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    if not m:
        return iso or None
    return f"{int(m.group(3))}/{int(m.group(2))}/{int(m.group(1))}"


def _kayit_ozeti(r: dict) -> dict:
    basvuru_no = (r.get("basvuruNo") or "").strip()
    tarih = _tarih(r.get("kararTarihi"))
    return {
        "id": r.get("id"),
        "basvuru_no": basvuru_no,
        "baslik": _duz(r.get("basvuruAdi") or ""),
        "karar_tarihi": tarih,
        "sonuc": _duz(r.get("kararTuruBasvuruSonucuLabel") or "") or None,
        "birim": _duz(r.get("kararVerenBirimLabel") or "") or None,
        "konu": _duz(r.get("kararKonusu") or "") or None,
        "kaynak": f"{_BASE}/BB/{basvuru_no}" if basvuru_no else _BASE,
        "atif": (f"AYM, B. No: {basvuru_no}"
                 + (f", K.T. {tarih}" if tarih else "")),
    }


def ara(ifade: str, adet: int = 10, sayfa: int = 1) -> dict:
    """AYM bireysel başvuru kararlarında arar. Künye listesi + atıf döndürür."""
    adet = max(1, min(adet, 50))
    sayfa = max(1, sayfa)
    d = _post({"kararTipi": "BireyselBasvuru", "query": ifade,
               "page": sayfa, "size": adet})
    sonuclar = [_kayit_ozeti(r) for r in d.get("data") or []]
    return {"ifade": ifade, "sayfa": sayfa,
            "toplam": int(d.get("total") or len(sonuclar)),
            "sonuclar": sonuclar}


def _metne_cevir(ham: str) -> str:
    s = re.sub(r"(?is)<(style|script|head)[^>]*>.*?</\1>", "", ham)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|tr|h[1-6]|li)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _uuid_coz(karar_id: str) -> str:
    """id'yi uuid'ye çevirir; eski biçimler ('BB/2014/5167', URL) de kabul edilir."""
    s = str(karar_id).strip()
    if _UUID.match(s):
        return s
    m = _BASVURU_NO.search(s)
    if not m:
        raise LookupError(
            f"id={karar_id} çözümlenemedi. id'yi ictihat_ara (mahkeme='anayasa') "
            f"sonucundan alın.")
    no = f"{m.group(1)}/{m.group(2)}"
    d = _post({"kararTipi": "BireyselBasvuru", "basvuruNo": no})
    kayitlar = d.get("data") or []
    if not kayitlar or not kayitlar[0].get("id"):
        raise LookupError(
            f"Başvuru no {no} için AYM kaydı bulunamadı. id'yi ictihat_ara "
            f"(mahkeme='anayasa') sonucundan alın.")
    return kayitlar[0]["id"]


def karar(karar_id: str) -> dict:
    """Bir AYM bireysel başvuru kararının tam metnini çeker (id ictihat_ara'dan gelir)."""
    uuid = _uuid_coz(karar_id)
    d = _post({"kararTipi": "BireyselBasvuru", "id": uuid, "page": 1, "size": 1})
    kayitlar = d.get("data") or []
    kayit = kayitlar[0] if kayitlar else {}
    metin = _metne_cevir(kayit.get("icerik") or "")
    if not metin or len(metin) < 60:
        raise LookupError(
            f"id={karar_id} için AYM karar metni bulunamadı. id'yi ictihat_ara "
            f"(mahkeme='anayasa') sonucundan alın.")
    basvuru_no = (kayit.get("basvuruNo") or "").strip()
    kaynak = f"{_BASE}/BB/{basvuru_no}" if basvuru_no else _BASE
    return {"id": karar_id, "kaynak": kaynak, "uzunluk": len(metin), "metin": metin}
