"""İstemcilerin ortak yardımcıları: arama sözdizimi, HTTP kapısı, erişim durdurma, önbellek.

Bedesten (Yargıtay), UYAP Emsal ve AYM Kararlar Bilgi Bankası düz sözcükleri VEYA ile
arar; "kira tahliye" iki sözcükten birini içeren yüz binlerce kararı getirir.
`ve_sorgusu` serbest metni üç servisin de anladığı VE sorgusuna çevirir:

  - sözcükler ve tırnaklı ifadeler `+` ile zorunlu kılınır;
  - başında `-` olan sözcük ya da ifade hariç tutulur ve olduğu gibi kalır;
  - kesme işaretinden sonraki ek atılır ("TMK'nın" -> "TMK"); ek ayrı bir zorunlu
    sözcük olarak kalırsa sonuç sayısı onda bire düşer;
  - AND / OR / NOT yazılmışsa (and / or küçük harfle de) kullanıcının sözdizimine
    dokunulmaz; yalnız baştaki, sondaki ve art arda gelen işleçler atılır. Küçük
    "not" işleç sayılmaz: Türkçede sözcüktür ("tapuya not düşülmesi");
  - harf, rakam, boşluk, tırnak, + ve - dışındaki işaretler boşluğa çevrilir
    (Bedesten diğerlerini reddeder; UYAP Emsal noktada hata verir).

HTTP kapısı (`istek`, `json_istek`): bütün modüllerin isteği buradan geçer.

  - Sunucu kendini açıkça tanıtır: User-Agent `turk-hukuku-ictihat-mcp/<sürüm>
    (+https://turk-hukuku.com/mcp/)`. Tarayıcıyı ya da resmî web uygulamasını taklit eden
    başlıklar (Origin, Referer, X-Requested-With, AdaletApplicationName) gönderilmez.
  - Site başına sıra: aynı siteye aynı anda tek istek gider; iki istek arasında en az
    `ARALIK` (1 sn) beklenir. FastMCP araçları worker thread'lerde çalıştığı için kilit
    `threading.Lock`'tur.
  - Sert durma: HTTP 403 ve 429, yanıtta captcha işareti, beklenen içerik yerine
    yönlendirme ve JSON beklenirken HTML gelmesi `ErisimDurdu` hatası verir. İstek
    yinelenmez; captcha çözülmez, atlanmaz. Sunucu o siteye `DURMA_SURESI` boyunca (429'da
    Retry-After ne diyorsa o kadar) yeni istek göndermez ve kullanıcıyı resmî siteye
    yönlendirir.
  - Diğer HTTP hataları (5xx, 404 vb.) ve ağ hataları kısa bir Türkçe `KaynakHatasi`
    verir: istek yinelenmez, bekleme başlatılmaz.
  - Kararlar id ile süreç içinde önbelleğe alınır (`karar_onbellegi`, en çok 256 karar);
    aynı karar ikinci kez istenince siteye gidilmez.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import OrderedDict
from typing import Any
from urllib.parse import urlsplit

import httpx

from . import __version__

# MCP SDK günlüğü INFO düzeyinde açar; httpx de her isteği adresiyle (karar id'leri dahil)
# yazar. Bu satırlar istemci günlüklerinde kalmasın diye httpx yalnızca uyarı yazar.
logging.getLogger("httpx").setLevel(logging.WARNING)

USER_AGENT = f"turk-hukuku-ictihat-mcp/{__version__} (+https://turk-hukuku.com/mcp/)"
ARALIK = 1.0          # aynı siteye iki istek arasında en az bu kadar saniye
DURMA_SURESI = 120    # sert durmadan sonra o siteye istek gönderilmeyen süre (sn)

_ISLEC = {"AND", "OR", "NOT"}
_KUCUK_ISLEC = {"and", "or"}
_PARCA = re.compile(r'([+-]?)("[^"]*"|[^\s"]+)')


def _islec(isaret: str, govde: str) -> str | None:
    if isaret:
        return None
    if govde in _ISLEC:
        return govde
    if govde in _KUCUK_ISLEC:
        return govde.upper()
    return None


def ve_sorgusu(ifade: str) -> str:
    """Serbest metni VE sorgusuna çevirir. Harf ya da rakam yoksa ValueError."""
    s = re.sub(r"['’‘`´]\w*", "", ifade or "")
    s = re.sub(r'[^\w\s"+\-]|_', " ", s)
    if s.count('"') % 2:                          # eşlenmemiş tırnak servis hatası verir
        s = s.replace('"', " ")

    parcalar: list[tuple[str, str]] = []
    for isaret, govde in _PARCA.findall(s):
        if govde.startswith('"'):
            ic = " ".join(re.sub(r"[+\-]", " ", govde[1:-1]).split())
            if ic:
                parcalar.append((isaret, f'"{ic}"'))
            continue
        # sözcük içindeki + ve - ayırıcıdır ("a+b", "iş-güç"); yalnız kalan işaret atılır
        for i, w in enumerate(w for w in re.split(r"[+\-]+", govde) if w):
            parcalar.append((isaret if i == 0 else "", w))

    if any(_islec(i, g) for i, g in parcalar):
        cikti: list[str] = []
        for i, g in parcalar:
            op = _islec(i, g)
            if op:
                if cikti and cikti[-1] not in _ISLEC:
                    cikti.append(op)
            else:
                cikti.append(i + g)
        while cikti and cikti[-1] in _ISLEC:
            cikti.pop()
    else:
        cikti = [(i or "+") + g for i, g in parcalar]

    if not cikti:
        raise ValueError("Arama ifadesi harf ya da rakam içermeli.")
    return " ".join(cikti)


class ErisimDurdu(LookupError):
    """Kaynak site erişimi sınırladı, reddetti ya da doğrulama (captcha) istedi.

    Sunucu isteği yinelemez; `bekleme` saniye boyunca o siteye yeni istek göndermez.
    """

    def __init__(self, mesaj: str, bekleme: float = DURMA_SURESI):
        super().__init__(mesaj)
        self.bekleme = bekleme


class KaynakHatasi(LookupError):
    """Kaynak site geçici ya da beklenmeyen bir hata verdi (5xx, 404, ağ hatası).

    Sert durma değildir: o siteye bekleme başlatılmaz. Sunucu isteği yinelemez.
    """


def _resmi_site(site: str | None) -> str:
    return f" Resmî site: {site}" if site else ""


def durum_hatasi(r: httpx.Response, kaynak: str, site: str | None = None) -> KaynakHatasi:
    """Sert durma sayılmayan HTTP hatası (5xx, 404 vb.) için kısa Türkçe hata."""
    kod = r.status_code
    if kod >= 500:
        neden = (f"şu anda yanıt veremiyor (HTTP {kod}, sunucu hatası). Sunucu isteği "
                 f"yinelemez; biraz sonra yeniden deneyin.")
    elif kod == 404:
        neden = "istenen kaydı bulamadı (HTTP 404). Sunucu isteği yinelemez."
    elif kod >= 400:
        neden = f"isteği kabul etmedi (HTTP {kod}). Sunucu isteği yinelemez."
    else:
        neden = f"beklenmeyen bir yanıt verdi (HTTP {kod}). Sunucu isteği yinelemez."
    return KaynakHatasi(f"{kaynak} {neden}{_resmi_site(site)}")


def erisim_siniri(r: httpx.Response, kaynak: str, site: str | None = None) -> None:
    """HTTP 429'da modele anlaşılır bir Türkçe hata verir (bekleyip yeniden denemez)."""
    if r.status_code == 429:
        ham = (r.headers.get("retry-after") or "").strip()
        bekleme = int(ham) if ham.isdigit() else DURMA_SURESI
        raise ErisimDurdu(
            f"{kaynak} erişim sınırı aşıldı; {bekleme} sn sonra tekrar deneyin. Sunucu isteği "
            f"kendisi yinelemez.{_resmi_site(site)}", bekleme)


# Captcha işaretleri yapısaldır: metinde geçen sözcük değil, doğrulama isteyen alan ya da
# öğe aranır. "Ben robot değilim" sözünü aktaran bir karar ya da bu sözcüklerle yapılan
# bir arama siteyi durdurmamalı.
#
# JSON yanıt: UYAP Emsal ve Danıştay aranan sözcükleri her sonuçta (arananKelime) geri
# yansıtır; UYAP ve AYM karar metnini JSON içinde verir. Bu yüzden yalnız alanlar aranır:
# "isDisplayCaptcha": true, metadata.FMTE içinde DisplayCaptcha (Danıştay arayüzünün
# captcha hatası) ve reCaptchaTimeout.
_CAPTCHA_JSON = re.compile(
    r'"isDisplayCaptcha"\s*:\s*"?true|"FMTE"\s*:\s*"[^"]*DisplayCaptcha|reCaptchaTimeout',
    re.IGNORECASE)

# HTML sayfa (Ekim 2026'da canlı sayfalarla denendi): Danıştay'ın karar sayfası
# recaptcha/api.js betiğini yükler ve karar metnini gizli bir <p> içinde HTML kodlu
# (&lt;...&gt;) verir. Ana sayfanın betikleri "grecaptcha", "Ben robot değilim" ve
# reCaptchaTimeout sözlerini doğrulama yokken de içerir; doğrulama gerekip gerekmediğini
# <p id="isDisplayCaptcha" class="d-none">false</p> bayrağı söyler. Bu yüzden sayfa
# yalnız şu yapısal izlerden captcha sayfası sayılır:
#   - sitenin bayrağı doğrulama istiyor (<p id="isDisplayCaptcha">true</p> ya da
#     "isDisplayCaptcha": true);
#   - sayfada bir doğrulama kutusu var (g-recaptcha, h-captcha, cf-turnstile ya da sitenin
#     captcha sınıfını taşıyan bir öğe, ya da data-sitekey özniteliği);
#   - satır içi bir betik doğrulama kutusu çiziyor ya da çalıştırıyor (grecaptcha.render,
#     grecaptcha.execute);
#   - sayfa bir captcha hata iletisi taşıyor ("detailMessage": "reCaptchaTimeout" ya da
#     FMTE içinde DisplayCaptcha).
_CAPTCHA_SAYFA = re.compile(
    r'<[a-z][^>]*\bid\s*=\s*["\']?isDisplayCaptcha\b[^>]*>\s*true\s*<'
    r'|"isDisplayCaptcha"\s*:\s*"?true'
    r'|<[a-z][^>]*\bdata-sitekey\s*='
    r'|"detailMessage"\s*:\s*"reCaptchaTimeout"'
    r'|"FMTE"\s*:\s*"[^"]*DisplayCaptcha',
    re.IGNORECASE)
# class özniteliği (data-class gibi adlar sayılmaz); tırnaklı ya da tırnaksız değer
_SINIF = re.compile(r'<[a-z][^>]*?(?<![\w-])class\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'>]+))',
                    re.IGNORECASE)
_DOGRULAMA_SINIFLARI = {"g-recaptcha", "h-captcha", "cf-turnstile", "captcha"}
_BETIK = re.compile(r"<script\b[^>]*>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL)
_BETIK_CAPTCHA = re.compile(r"grecaptcha\s*\.\s*(?:render|execute)\s*\(", re.IGNORECASE)


def captcha_sayfasi_mi(govde: str) -> bool:
    """HTML sayfada bir doğrulama (captcha) isteği var mı? Yalnız yapısal izlere bakar."""
    if _CAPTCHA_SAYFA.search(govde):
        return True
    for degerler in _SINIF.findall(govde):
        if _DOGRULAMA_SINIFLARI & set(" ".join(degerler).lower().split()):
            return True
    return any(_BETIK_CAPTCHA.search(betik) for betik in _BETIK.findall(govde))


def denetle(r: httpx.Response, kaynak: str, site: str | None, beklenen: str = "json") -> None:
    """Yanıtı sert durma koşullarına göre denetler; koşul varsa ErisimDurdu verir.

    beklenen: "json" (API yanıtı) ya da "html" (karar sayfası). Sert durma sayılmayan
    HTTP hataları (5xx, 404 vb.) burada değil, `istek`te KaynakHatasi olur.
    """
    erisim_siniri(r, kaynak, site)
    if r.status_code == 403:
        raise ErisimDurdu(
            f"{kaynak} isteği reddetti (HTTP 403). Sunucu yeniden denemez ve engeli aşmaya "
            f"çalışmaz; kararı resmî sitede arayın.{_resmi_site(site)}")
    tur = (r.headers.get("content-type") or "").lower()
    govde = "" if any(t in tur for t in ("pdf", "octet-stream", "image/")) else r.text
    sayfa_mi = "html" in tur or govde.lstrip().startswith("<")
    if govde and (captcha_sayfasi_mi(govde) if sayfa_mi else _CAPTCHA_JSON.search(govde)):
        raise ErisimDurdu(
            f"{kaynak} doğrulama (captcha) istedi. Bu sunucu captcha çözmez ve atlamaz; "
            f"aramayı resmî sitede kendiniz yapın.{_resmi_site(site)}")
    if 300 <= r.status_code < 400:
        istenen = "JSON" if beklenen == "json" else "istenen sayfa"
        raise ErisimDurdu(
            f"{kaynak} {istenen} yerine başka bir sayfaya yönlendirdi (HTTP {r.status_code}); "
            f"erişim engeli ya da doğrulama sayfası olabilir. Sunucu yeniden denemez."
            f"{_resmi_site(site)}")
    if beklenen == "json" and r.is_success and sayfa_mi:
        raise ErisimDurdu(
            f"{kaynak} JSON yerine bir HTML sayfası döndürdü (erişim engeli, doğrulama "
            f"ya da bakım sayfası olabilir). Sunucu yeniden denemez.{_resmi_site(site)}")


# --- HTTP kapısı ----------------------------------------------------------------

class _Kapi:
    """Bir sitenin (host) sırası: tek istek, aralık ve sert durma sonrası bekleme."""

    def __init__(self) -> None:
        self.kilit = threading.Lock()
        self.son = float("-inf")       # son isteğin bittiği an (time.monotonic)
        self.durma_bitis = 0.0         # bu ana kadar siteye istek gönderilmez
        self.durma_mesaji = ""


_kapilar: dict[str, _Kapi] = {}
_kapilar_kilidi = threading.Lock()
_gonder = httpx.request               # testler bunu sahte bir taşıyıcıyla değiştirir


def _kapi(host: str) -> _Kapi:
    with _kapilar_kilidi:
        k = _kapilar.get(host)
        if k is None:
            k = _kapilar[host] = _Kapi()
        return k


def _durdur(kapi: _Kapi, hata: ErisimDurdu) -> None:
    # önce mesaj, sonra süre: süreyi gören iş parçacığı mesajı da görsün; süren daha uzun
    # bir bekleme (ör. 429 Retry-After) kısaltılmaz
    kapi.durma_mesaji = str(hata)
    kapi.durma_bitis = max(kapi.durma_bitis, time.monotonic() + max(0.0, float(hata.bekleme)))


def _bekleme_suruyor_mu(kapi: _Kapi) -> None:
    kalan = kapi.durma_bitis - time.monotonic()
    if kalan > 0:
        raise ErisimDurdu(
            f"{kapi.durma_mesaji} (Bu siteye {int(kalan) + 1} sn daha istek gönderilmeyecek.)",
            kalan)


def istek(yontem: str, url: str, *, kaynak: str, site: str | None = None,
          beklenen: str = "json", headers: dict | None = None, **kw: Any) -> httpx.Response:
    """Tek HTTP kapısı: kimlik, site başına sıra ve aralık, sert durma denetimi.

    Aynı siteye aynı anda tek istek gider; iki istek arasında en az ARALIK saniye
    beklenir. 403, 429, captcha, yönlendirme ve JSON yerine HTML ErisimDurdu verir (o
    siteye bir süre istek gitmez). Diğer HTTP hataları (5xx, 404 vb.) ve ağ hataları
    KaynakHatasi verir (bekleme yok). Hiçbir istek yinelenmez.
    """
    host = urlsplit(url).hostname or url
    kapi = _kapi(host)
    basliklar = {**(headers or {}), "User-Agent": USER_AGENT}
    with kapi.kilit:
        _bekleme_suruyor_mu(kapi)
        bekle = kapi.son + ARALIK - time.monotonic()
        if bekle > 0:
            time.sleep(bekle)
        try:
            r = _gonder(yontem, url, headers=basliklar, **kw)
        except httpx.TimeoutException as hata:
            raise KaynakHatasi(
                f"{kaynak} zamanında yanıt vermedi (zaman aşımı). Sunucu isteği yinelemez; "
                f"biraz sonra yeniden deneyin.{_resmi_site(site)}") from hata
        except httpx.TransportError as hata:
            raise KaynakHatasi(
                f"{kaynak} ile bağlantı kurulamadı (ağ hatası). Sunucu isteği yinelemez; "
                f"bağlantınızı denetleyip biraz sonra yeniden deneyin.{_resmi_site(site)}") from hata
        finally:
            kapi.son = time.monotonic()
        try:
            denetle(r, kaynak, site, beklenen)
        except ErisimDurdu as hata:
            _durdur(kapi, hata)
            raise
    if not r.is_success:
        raise durum_hatasi(r, kaynak, site)
    return r


def json_istek(yontem: str, url: str, *, kaynak: str, site: str | None = None,
               **kw: Any) -> Any:
    """`istek` + JSON çözümleme. Geçersiz JSON da sert durmadır (beklenmeyen sayfa)."""
    r = istek(yontem, url, kaynak=kaynak, site=site, beklenen="json", **kw)
    try:
        return r.json()
    except ValueError:
        hata = ErisimDurdu(
            f"{kaynak} geçerli bir JSON yanıtı döndürmedi (beklenmeyen sayfa). Sunucu yeniden "
            f"denemez.{_resmi_site(site)}")
        _durdur(_kapi(urlsplit(url).hostname or url), hata)
        raise hata from None


# --- Karar önbelleği ------------------------------------------------------------

class KararOnbellegi:
    """id ile anahtarlanan, iş parçacığı güvenli, sınırlı (LRU) süreç içi önbellek."""

    def __init__(self, kapasite: int = 256) -> None:
        self.kapasite = kapasite
        self._veri: OrderedDict[Any, dict] = OrderedDict()
        self._kilit = threading.Lock()

    def al(self, anahtar: Any) -> dict | None:
        with self._kilit:
            deger = self._veri.get(anahtar)
            if deger is None:
                return None
            self._veri.move_to_end(anahtar)
            return dict(deger)

    def koy(self, anahtar: Any, deger: dict) -> None:
        with self._kilit:
            self._veri[anahtar] = dict(deger)
            self._veri.move_to_end(anahtar)
            while len(self._veri) > self.kapasite:
                self._veri.popitem(last=False)

    def temizle(self) -> None:
        with self._kilit:
            self._veri.clear()

    def __len__(self) -> int:
        with self._kilit:
            return len(self._veri)


karar_onbellegi = KararOnbellegi(256)
