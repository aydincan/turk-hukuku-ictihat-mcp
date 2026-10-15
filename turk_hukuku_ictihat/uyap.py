"""UYAP Emsal Karar istemcisi: yargı kararlarını resmî kaynaktan arar/çeker.

Veri kaynağı: https://emsal.uyap.gov.tr (Adalet Bakanlığı Emsal Karar Arama).
Kapsam: Bölge Adliye Mahkemeleri hukuk daireleri ve bazı ilk derece mahkemeleri (asliye
ticaret, fikrî ve sınaî haklar). Herkese açık arayüz Yargıtay kararı içermez; Yargıtay
kararları yargitay.py (Bedesten) üzerinden gelir.

İki uç nokta tersine mühendislikle çözüldü:
  POST /aramalist     -> {"data":{"aranan":Q,"arananKelime":Q,"pageSize":N,"pageNumber":M}}
                         künye listesi döndürür (daire, esasNo, kararNo, kararTarihi, durum)
  GET  /getDokuman?id -> kararın tam metni (HTML)

Künye (mahkeme + daire + esas/karar no + tarih) **yapısal** gelir; model numarayı
metinden ayıklamak ya da hafızadan yazmak zorunda kalmaz.

Kaynak bağlantısı: getDokuman tarayıcıda okunur bir sayfa değil (JSON/XML döner). Emsal
id'leri Bedesten ile aynı belge kimliği uzayında olduğundan karar, Adalet Bakanlığı'nın
herkese açık sayfasında okunur biçimde açılır: https://mevzuat.adalet.gov.tr/ictihat/<id>
"""
from __future__ import annotations

import html as _html
import re

import httpx

from . import ortak
from .ortak import ve_sorgusu

_BASE = "https://emsal.uyap.gov.tr"
_SAYFA = "https://mevzuat.adalet.gov.tr/ictihat"

_AD = "UYAP Emsal"
# Kimlik (User-Agent) ortak.istek'te eklenir; tarayıcı taklidi yapan başlık gönderilmez.
# Tarayıcıdaki captcha korumalı /arama adımı çağrılmaz; site doğrulama isterse sunucu
# durur ve kullanıcıyı resmî siteye yönlendirir (ortak.denetle).
_HEADERS = {"Content-Type": "application/json; charset=UTF-8"}
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
    sorgu = ve_sorgusu(ifade)   # düz sözcükler VEYA ile aranır; bkz. ortak.py
    govde = {"data": {"aranan": sorgu, "arananKelime": sorgu,
                      "pageSize": adet, "pageNumber": sayfa}}
    cevap = ortak.json_istek("POST", f"{_BASE}/aramalist", kaynak=_AD, site=_BASE,
                             json=govde, headers=_HEADERS, timeout=_TIMEOUT)
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
        "kaynak": f"{_SAYFA}/{k.get('id', '')}",
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
    if karar_id.lower().startswith("yargitay:"):   # Bedesten ile aynı belge kimliği uzayı
        karar_id = karar_id[len("yargitay:"):]
    cevap = ortak.json_istek("GET", f"{_BASE}/getDokuman", kaynak=_AD, site=_BASE,
                             params={"id": karar_id}, timeout=_TIMEOUT)
    ham = cevap.get("data")
    if not ham:
        raise LookupError(
            f"id={karar_id} için karar metni bulunamadı. id'yi ictihat_ara "
            f"sonucundan alın.")
    metin = _metne_cevir(ham)
    return {"id": karar_id, "kaynak": f"{_SAYFA}/{karar_id}",
            "uzunluk": len(metin), "metin": metin}
