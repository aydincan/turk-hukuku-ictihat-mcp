"""Anayasa Mahkemesi — Bireysel Başvuru kararları istemcisi.

Veri kaynağı: https://kararlarbilgibankasi.anayasa.gov.tr (AYM Kararlar Bilgi Bankası).
Diğer iki kaynaktan farkı: JSON API değil, **HTML** döndürür (GET + sorgu parametresi);
sonuç listesi ve karar metni HTML'den ayıklanır.

  GET /Ara?KelimeAra[]=<ifade>&page=<N>   -> sonuç listesi (HTML)
  GET /BB/<yil>/<no>                       -> kararın tam metni (HTML)

Künye (başvuru no + karar tarihi + sonuç + kurul) sonuç kartından yapısal çıkarılır;
model künye uydurmaz.
"""
from __future__ import annotations

import html as _html
import re

import httpx

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_BASE = "https://kararlarbilgibankasi.anayasa.gov.tr"
_HEADERS = {"User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{_BASE}/"}
# bağlantı 10 sn, okuma/yazma 30 sn: asılı kalan istek sunucuyu uzun süre meşgul etmesin
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_HREF = re.compile(r'href="(' + re.escape(_BASE) + r'/BB/\d+/\d+)"')
_BASLIK = re.compile(r'<titles[^>]*>(.*?)</titles>', re.S)
_BILGI = re.compile(r'<div class="kararbilgileri">(.*?)</div>', re.S)
_KONU = re.compile(r'<div class="basvurukonualani">(.*?)</div>', re.S)


def _duz(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", _html.unescape(s or ""))).strip()


def ara(ifade: str, adet: int = 10, sayfa: int = 1) -> dict:
    """AYM bireysel başvuru kararlarında arar. Künye listesi + atıf döndürür."""
    adet = max(1, min(adet, 50))
    sayfa = max(1, sayfa)
    params = [("KelimeAra[]", ifade)]
    if sayfa > 1:
        params.append(("page", str(sayfa)))
    r = httpx.get(f"{_BASE}/Ara", params=params, headers=_HEADERS, timeout=_TIMEOUT,
                  follow_redirects=True)
    r.raise_for_status()
    sonuclar = []
    for blok in r.text.split('class="birkarar')[1:]:
        href = _HREF.search(blok)
        if not href:
            continue
        url = href.group(1)
        no_m = re.search(r"/BB/(\d+)/(\d+)", url)
        basvuru_no = f"{no_m.group(1)}/{no_m.group(2)}" if no_m else ""
        bilgi = _duz((_BILGI.search(blok) or [None, ""])[1] if _BILGI.search(blok) else "")
        tarih_m = re.search(r"Karar Tarihi\s*:?\s*([\d/.]+)", bilgi)
        sonuc_m = re.search(r"\(([^)]*İhlal[^)]*)\)", bilgi)
        sonuclar.append({
            "id": f"BB/{basvuru_no}",
            "basvuru_no": basvuru_no,
            "baslik": _duz(_BASLIK.search(blok).group(1)) if _BASLIK.search(blok) else "",
            "karar_tarihi": tarih_m.group(1) if tarih_m else None,
            "sonuc": sonuc_m.group(1).strip() if sonuc_m else None,
            "konu": _duz(_KONU.search(blok).group(1)) if _KONU.search(blok) else None,
            "kaynak": url,
            "atif": (f"AYM, B. No: {basvuru_no}"
                     + (f", K.T. {tarih_m.group(1)}" if tarih_m else "")),
        })
        if len(sonuclar) >= adet:
            break
    toplam = len(sonuclar)
    m = re.search(r'(\d[\d.]*)\s*(?:adet|sonu[çc]|kay[ıi]t)', r.text, re.I)
    if m:
        try:
            toplam = int(m.group(1).replace(".", ""))
        except ValueError:
            pass
    return {"ifade": ifade, "sayfa": sayfa, "toplam": toplam, "sonuclar": sonuclar}


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


def karar(karar_id: str) -> dict:
    """Bir AYM bireysel başvuru kararının tam metnini çeker (id ictihat_ara'dan gelir)."""
    yol = str(karar_id).strip().lstrip("/")
    url = yol if yol.startswith("http") else f"{_BASE}/{yol}"
    r = httpx.get(url, headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    # Karar metni Word-export gövdesindedir: <div class="WordSection1"> ... </div>
    i = r.text.find('class="WordSection1"')
    if i >= 0:
        i = r.text.find(">", i) + 1
    metin = _metne_cevir(r.text[i:] if i >= 0 else r.text)
    if not metin or len(metin) < 60:
        raise LookupError(
            f"id={karar_id} için AYM karar metni bulunamadı. id'yi ictihat_ara "
            f"(mahkeme='anayasa') sonucundan alın.")
    return {"id": karar_id, "kaynak": url, "uzunluk": len(metin), "metin": metin}
