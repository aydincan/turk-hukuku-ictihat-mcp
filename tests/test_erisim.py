"""Erişim kuralları: kimlik, site başına sıra, sert durma ve karar önbelleği.

Ağ kullanılmaz: ortak._gonder sahte bir taşıyıcıyla değiştirilir.
Çalıştırma: python -m pytest tests
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import anyio
import httpx
import pytest

from turk_hukuku_ictihat import __version__, adli, anayasa, danistay, ortak, server, uyap, yargitay

TAKLIT_BASLIKLARI = {"referer", "origin", "x-requested-with", "adaletapplicationname"}


class Sahte:
    """ortak._gonder yerine geçer; her çağrıyı (başlangıç, bitiş, yöntem, url, başlıklar, kw) kaydeder."""

    def __init__(self, yanit=None, sure: float = 0.0):
        self.kayit: list[tuple] = []
        self.yanit = yanit or (lambda yontem, url, kw: (200, {"content-type": "application/json"},
                                                        b'{"data": {}}'))
        self.sure = sure
        self._kilit = threading.Lock()

    def __call__(self, yontem, url, headers=None, **kw):
        bas = time.monotonic()
        if self.sure:
            time.sleep(self.sure)
        bitis = time.monotonic()
        with self._kilit:
            self.kayit.append((bas, bitis, yontem, url, dict(headers or {}), kw))
        durum, basliklar, govde = self.yanit(yontem, url, kw)
        return httpx.Response(durum, headers=basliklar, content=govde,
                              request=httpx.Request(yontem, url))


def json_yanit(veri, durum=200, ek=None):
    basliklar = {"content-type": "application/json", **(ek or {})}
    return lambda yontem, url, kw: (durum, basliklar, json.dumps(veri).encode())


def html_yanit(metin, durum=200, ek=None):
    basliklar = {"content-type": "text/html;charset=UTF-8", **(ek or {})}
    return lambda yontem, url, kw: (durum, basliklar, metin.encode())


@pytest.fixture(autouse=True)
def temiz():
    ortak._kapilar.clear()
    ortak.karar_onbellegi.temizle()
    yield
    ortak._kapilar.clear()
    ortak.karar_onbellegi.temizle()


@pytest.fixture
def sahte(monkeypatch):
    s = Sahte()
    monkeypatch.setattr(ortak, "_gonder", s)
    return s


# --- Kimlik ----------------------------------------------------------------------

def test_user_agent_durust_ve_surumlu():
    assert ortak.USER_AGENT == f"turk-hukuku-ictihat-mcp/{__version__} (+https://turk-hukuku.com/mcp/)"
    assert "Mozilla" not in ortak.USER_AGENT


@pytest.mark.parametrize("cagri, yanit", [
    (lambda: yargitay.ara("kira tespit", adet=1), {"data": {"emsalKararList": [], "total": 0}}),
    (lambda: uyap.ara("kira tespit", adet=1), {"data": {"data": [], "recordsTotal": 0}}),
    (lambda: danistay.ara("kira tespit", adet=1), {"data": {"data": [], "recordsTotal": 0}}),
    (lambda: anayasa.ara("kira tespit", adet=1), {"data": [], "total": 0}),
    (lambda: anayasa.norm_ara("kira tespit", adet=1), {"data": [], "total": 0}),
])
def test_her_modul_kendini_tanitir_taklit_basligi_gondermez(monkeypatch, cagri, yanit):
    s = Sahte(json_yanit(yanit))
    monkeypatch.setattr(ortak, "_gonder", s)
    cagri()
    assert len(s.kayit) == 1
    basliklar = {k.lower(): v for k, v in s.kayit[0][4].items()}
    assert basliklar["user-agent"] == ortak.USER_AGENT
    assert not TAKLIT_BASLIKLARI & set(basliklar)


def test_bedesten_govdesinde_uygulama_adi_yok(monkeypatch):
    s = Sahte(json_yanit({"data": {"emsalKararList": [], "total": 0}}))
    monkeypatch.setattr(ortak, "_gonder", s)
    yargitay.ara("kira", adet=1)
    govde = s.kayit[0][5]["json"]
    assert "applicationName" not in govde
    assert govde["data"]["phrase"] == "+kira"


# --- Site başına sıra ---------------------------------------------------------------

def test_ayni_siteye_iki_istek_en_az_bir_saniye_arayla(sahte):
    ortak.istek("GET", "https://a.example/1", kaynak="A")
    ortak.istek("GET", "https://a.example/2", kaynak="A")
    (_, bitis1, *_), (bas2, *_) = sahte.kayit
    assert bas2 - bitis1 >= ortak.ARALIK


def test_ayni_siteye_ayni_anda_tek_istek(monkeypatch):
    s = Sahte(sure=0.2)
    monkeypatch.setattr(ortak, "_gonder", s)
    is_parcaciklari = [threading.Thread(target=ortak.istek, args=("GET", f"https://a.example/{i}"),
                                        kwargs={"kaynak": "A"}) for i in range(2)]
    for t in is_parcaciklari:
        t.start()
    for t in is_parcaciklari:
        t.join()
    (bas1, bitis1, *_), (bas2, bitis2, *_) = sorted(s.kayit)
    assert bas2 >= bitis1                    # örtüşme yok
    assert bas2 - bitis1 >= ortak.ARALIK     # ve arada en az bir saniye


def test_farkli_siteler_birbirini_beklemez(sahte):
    ortak.istek("GET", "https://a.example/1", kaynak="A")
    ortak.istek("GET", "https://b.example/1", kaynak="B")
    (_, bitis1, *_), (bas2, *_) = sahte.kayit
    assert bas2 - bitis1 < 0.5


def test_farkli_siteye_istek_ayni_anda_gidebilir(monkeypatch):
    s = Sahte(sure=0.5)
    monkeypatch.setattr(ortak, "_gonder", s)
    t1 = threading.Thread(target=ortak.istek, args=("GET", "https://a.example/1"), kwargs={"kaynak": "A"})
    t2 = threading.Thread(target=ortak.istek, args=("GET", "https://b.example/1"), kwargs={"kaynak": "B"})
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    (bas1, bitis1, *_), (bas2, *_) = sorted(s.kayit)
    assert bas2 < bitis1                      # iki farklı site aynı anda meşgul edilebilir


# --- Sert durma -----------------------------------------------------------------------

def test_403_durur_yeniden_denemez(monkeypatch):
    s = Sahte(html_yanit("<html>Forbidden</html>", durum=403))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        uyap.ara("kira")
    assert "HTTP 403" in str(e.value) and "https://emsal.uyap.gov.tr" in str(e.value)
    assert len(s.kayit) == 1


def test_429_mesaji_ve_retry_after(monkeypatch):
    s = Sahte(json_yanit({}, durum=429, ek={"retry-after": "30"}))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        yargitay.ara("kira")
    assert "Bedesten (Yargıtay) erişim sınırı aşıldı; 30 sn sonra tekrar deneyin." in str(e.value)
    assert e.value.bekleme == 30
    assert len(s.kayit) == 1


@pytest.mark.parametrize("modul, ad", [(danistay, "Danıştay Karar Arama"),
                                       (anayasa, "AYM Kararlar Bilgi Bankası")])
def test_429_danistay_ve_anayasada_da_var(monkeypatch, modul, ad):
    s = Sahte(json_yanit({}, durum=429))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        modul.ara("kira")
    assert f"{ad} erişim sınırı aşıldı;" in str(e.value)
    assert isinstance(e.value, LookupError)


@pytest.mark.parametrize("govde", [
    '{"metadata": {"isDisplayCaptcha": true}}',
    '{"metadata": {"isDisplayCaptcha": "true"}}',
    '{"data": null, "reCaptchaTimeout": 300}',
])
def test_json_icinde_captcha_isareti_durur(monkeypatch, govde):
    s = Sahte(lambda y, u, kw: (200, {"content-type": "application/json"}, govde.encode()))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        uyap.ara("kira")
    assert "captcha" in str(e.value) and "çözmez" in str(e.value)


def test_captcha_false_durmaz(monkeypatch):
    s = Sahte(lambda y, u, kw: (200, {"content-type": "application/json"},
                                b'{"isDisplayCaptcha": false, "data": {"data": [], "recordsTotal": 0}}'))
    monkeypatch.setattr(ortak, "_gonder", s)
    assert uyap.ara("kira")["sonuclar"] == []


@pytest.mark.parametrize("sayfa", [
    "<html><body><script>grecaptcha.execute()</script></body></html>",
    '<html><body><div class="g-recaptcha" data-sitekey="6Lc-ornek"></div></body></html>',
    "<html><body><form><div class='captcha'><div id='kutu'></div></div></form></body></html>",
    "<html><body><div data-class='kutu' class=g-recaptcha></div></body></html>",
    '<html><body><p id="isDisplayCaptcha" class="d-none">true</p></body></html>',
    '<html><body><script>var d = {"status": "EXCEPTION", "detailMessage": "reCaptchaTimeout"};'
    '</script></body></html>',
])
def test_html_sayfada_captcha_durur(monkeypatch, sayfa):
    s = Sahte(html_yanit(sayfa))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        danistay.karar("123")
    assert "captcha" in str(e.value) and "https://karararama.danistay.gov.tr" in str(e.value)
    with pytest.raises(ortak.ErisimDurdu):                 # bekleme sürüyor: ağa gidilmez
        danistay.karar("124")
    assert len(s.kayit) == 1


# Canlı karar sayfasının yapısı (Ekim 2026): recaptcha/api.js yüklenir, karar metni gizli
# bir <p> içinde HTML kodlu durur.
_KARAR_CUMLESI = ("Davacı, idarenin internet sitesinde &quot;Ben robot değilim&quot; kutusunu "
                  "işaretlediğini, grecaptcha doğrulamasının ve reCaptchaTimeout uyarısının "
                  "başvurusunu engellediğini ileri sürmüştür. ")


@pytest.mark.parametrize("sayfa", [
    ("<!DOCTYPE html><html><head><script src='https://www.google.com/recaptcha/api.js'>"
     "</script></head><body><p id=\"hiddencontent\" style=\"display: none\">&lt;p&gt;"
     + _KARAR_CUMLESI * 3 + "&lt;/p&gt;</p></body></html>"),
    ("<html><body><p>" + "Davacı, ben robot değilim kutusunu işaretlediğini beyan etmiştir. " * 3
     + "</p></body></html>"),
])
def test_robot_degilim_sozunu_aktaran_karar_sayfasi_durmaz(monkeypatch, sayfa):
    s = Sahte(html_yanit(sayfa))
    monkeypatch.setattr(ortak, "_gonder", s)
    assert "robot değilim" in danistay.karar("123")["metin"].lower()
    danistay.karar("124")                                  # bekleme başlamadı
    assert len(s.kayit) == 2


# Canlı ana sayfadan kısaltılmış örnek: betikler bu sözleri doğrulama yokken de içerir;
# doğrulamanın gerekip gerekmediğini gizli bayrak söyler.
_ANA_SAYFA = (
    "<!DOCTYPE html><html><body><p id=\"isDisplayCaptcha\" class=\"d-none\">BAYRAK</p>"
    "<script src='https://www.google.com/recaptcha/api.js'></script><script>"
    "var captchaValidation = function() { if (!isDisplayCaptcha()) { return true; }"
    " if (grecaptcha.getResponse() === '') { toastr['warning']"
    "(\"Lütfen 'Ben robot değilim' Onay Kutusunu İşaretleyiniz!\"); } };"
    " if (data.detailMessage === \"reCaptchaTimeout\") { grecaptcha.reset(); }"
    " $('.captcha').remove();</script></body></html>")


def test_ana_sayfa_bayrak_false_iken_durmaz_true_iken_durur(monkeypatch):
    s = Sahte(html_yanit(_ANA_SAYFA.replace("BAYRAK", "false")))
    monkeypatch.setattr(ortak, "_gonder", s)
    adres = "https://karararama.danistay.gov.tr/"
    ortak.istek("GET", adres, kaynak="Danıştay", beklenen="html")
    s.yanit = html_yanit(_ANA_SAYFA.replace("BAYRAK", "true"))
    with pytest.raises(ortak.ErisimDurdu) as e:
        ortak.istek("GET", adres, kaynak="Danıştay", beklenen="html")
    assert "captcha" in str(e.value)


def test_json_fmte_displaycaptcha_durur(monkeypatch):
    # Danıştay arayüzü captcha gerektiğinde metadata.FMTE içinde "DisplayCaptcha" arar
    s = Sahte(json_yanit({"metadata": {"FMTY": "ERROR", "FMTE": "DisplayCaptcha"}, "data": None}))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        danistay.ara("kira")
    assert "captcha" in str(e.value)


def test_karar_sayfasi_yerine_yonlendirme_sert_durmadir(monkeypatch):
    s = Sahte(lambda y, u, kw: (302, {"location": "/captcha"}, b""))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        danistay.karar("123")
    assert "yönlendirdi (HTTP 302)" in str(e.value)
    assert "https://karararama.danistay.gov.tr" in str(e.value)
    with pytest.raises(ortak.ErisimDurdu):                 # bekleme sürüyor: ağa gidilmez
        danistay.karar("123")
    assert len(s.kayit) == 1


@pytest.mark.parametrize("cagri, durum, tur, govde, ad", [
    (lambda: danistay.karar("123"), 503, "text/html", b"<html>Service Unavailable</html>",
     "Danıştay Karar Arama"),
    (lambda: danistay.karar("123"), 404, "text/html", b"<html>Not Found</html>",
     "Danıştay Karar Arama"),
    (lambda: uyap.ara("kira"), 502, "text/html", b"<html><body>Bad Gateway</body></html>",
     "UYAP Emsal"),
    (lambda: yargitay.ara("kira"), 500, "application/json", b'{"error": "Internal Server Error"}',
     "Bedesten (Yargıtay)"),
    (lambda: anayasa.ara("kira"), 400, "application/json", b'{"title": "Bad Request"}',
     "AYM Kararlar Bilgi Bankası"),
])
def test_diger_http_hatalari_kisa_turkce_bekleme_yok(monkeypatch, cagri, durum, tur, govde, ad):
    s = Sahte(lambda y, u, kw: (durum, {"content-type": tur}, govde))
    monkeypatch.setattr(ortak, "_gonder", s)
    for _ in range(2):                                     # bekleme yok: ikinci çağrı da gider
        with pytest.raises(ortak.KaynakHatasi) as e:
            cagri()
        mesaj = str(e.value)
        assert not isinstance(e.value, ortak.ErisimDurdu)
        assert mesaj.startswith(f"{ad} ") and f"(HTTP {durum}" in mesaj
        assert "Resmî site: https://" in mesaj and "error" not in mesaj.lower()
    assert len(s.kayit) == 2


def test_5xx_captcha_sayfasi_yine_sert_durmadir(monkeypatch):
    s = Sahte(html_yanit("<html><body><div class='g-recaptcha' data-sitekey='x'></div>"
                         "</body></html>", durum=503))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        danistay.karar("123")
    assert "captcha" in str(e.value)


@pytest.mark.parametrize("hata, parca", [
    (httpx.ConnectTimeout("timed out"), "zaman aşımı"),
    (httpx.ConnectError("[Errno 8] nodename nor servname provided"), "ağ hatası"),
])
def test_ag_hatasi_kisa_turkce_bekleme_yok(monkeypatch, hata, parca):
    def yanit(yontem, url, kw):
        raise hata
    s = Sahte(yanit)
    monkeypatch.setattr(ortak, "_gonder", s)
    for _ in range(2):
        with pytest.raises(ortak.KaynakHatasi) as e:
            uyap.ara("kira")
        assert str(e.value).startswith("UYAP Emsal ") and parca in str(e.value)
        assert "Errno" not in str(e.value)
    assert len(s.kayit) == 2


def test_danistay_normal_sayfadaki_recaptcha_betigi_durdurmaz(monkeypatch):
    sayfa = ("<!DOCTYPE html><html><head><script src='https://www.google.com/recaptcha/api.js'>"
             "</script></head><body><p>" + "Dava, idari işlemin iptali istemiyle açılmıştır. " * 5
             + "</p></body></html>")
    s = Sahte(html_yanit(sayfa))
    monkeypatch.setattr(ortak, "_gonder", s)
    sonuc = danistay.karar("123")
    assert "idari işlemin iptali" in sonuc["metin"]


def _ham_json(veri):
    # gerçek siteler gibi ham UTF-8 (\u kaçışı yok)
    return lambda y, u, kw: (200, {"content-type": "application/json"},
                             json.dumps(veri, ensure_ascii=False).encode("utf-8"))


@pytest.mark.parametrize("modul, kayit", [
    (uyap, {"id": "9", "daire": "X BAM 1. HD", "esasNo": "2020/1", "kararNo": "2021/2",
            "kararTarihi": "01.01.2021", "arananKelime": '"robot değilim" +grecaptcha'}),
    (danistay, {"id": "9", "daireKurul": "4. Daire", "esasNo": "2020/1", "kararNo": "2021/2",
                "kararTarihi": "01.01.2021", "arananKelime": "robot değilim,grecaptcha"}),
])
def test_json_yanitta_yansiyan_sorgu_captcha_sayilmaz(monkeypatch, modul, kayit):
    # UYAP Emsal ve Danıştay aranan sözcükleri her sonuçta (arananKelime) geri yansıtır
    # (Ekim 2026 canlı yanıtında görüldü); "robot değilim" aramak siteyi durdurmamalı.
    s = Sahte(_ham_json({"data": {"data": [kayit], "recordsTotal": 1}}))
    monkeypatch.setattr(ortak, "_gonder", s)
    sonuc = modul.ara('"robot değilim" grecaptcha')
    assert [x["id"] for x in sonuc["sonuclar"]] == ["9"]
    modul.ara("ikinci")                                    # bekleme başlamadı
    assert len(s.kayit) == 2


def test_json_icindeki_karar_metni_captcha_sayilmaz(monkeypatch):
    govde = {"data": "<p>Davacı, sahte sitede ben robot değilim kutusunu işaretlediğini "
                     "beyan etmiştir.</p>" * 3}
    s = Sahte(_ham_json(govde))
    monkeypatch.setattr(ortak, "_gonder", s)
    assert "robot değilim" in uyap.karar("123")["metin"]


def test_json_yerine_captcha_sayfasi_captcha_mesajiyla_durur(monkeypatch):
    s = Sahte(html_yanit("<html><body><div class='g-recaptcha'></div>"
                         "<script>grecaptcha.render()</script></body></html>"))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        uyap.ara("kira")
    assert "captcha" in str(e.value) and "çözmez" in str(e.value)


def test_json_yerine_html_durur(monkeypatch):
    s = Sahte(html_yanit("<!DOCTYPE html><html><body>Bakım</body></html>"))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu) as e:
        anayasa.ara("kira")
    assert "JSON yerine bir HTML sayfası" in str(e.value)
    assert "https://kararlarbilgibankasi.anayasa.gov.tr" in str(e.value)


def test_json_yerine_yonlendirme_durur(monkeypatch):
    s = Sahte(lambda y, u, kw: (302, {"location": "/captcha"}, b""))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu):
        uyap.karar("123")


def test_gecersiz_json_durur(monkeypatch):
    s = Sahte(lambda y, u, kw: (200, {"content-type": "application/json"}, b"not json"))
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu):
        uyap.ara("kira")
    with pytest.raises(ortak.ErisimDurdu):     # bekleme sürüyor: ağa gidilmez
        uyap.ara("kira")
    assert len(s.kayit) == 1


def test_durmadan_sonra_siteye_istek_gitmez_diger_siteler_calisir(monkeypatch):
    def yanit(yontem, url, kw):
        if "emsal.uyap.gov.tr" in url:
            return 403, {"content-type": "text/html"}, b"<html>Forbidden</html>"
        return 200, {"content-type": "application/json"}, json.dumps(
            {"data": {"emsalKararList": [], "total": 0}}).encode()
    s = Sahte(yanit)
    monkeypatch.setattr(ortak, "_gonder", s)
    with pytest.raises(ortak.ErisimDurdu):
        uyap.ara("kira")
    with pytest.raises(ortak.ErisimDurdu) as e:
        uyap.karar("123")
    assert "sn daha istek gönderilmeyecek" in str(e.value)
    yargitay.ara("kira")                                   # başka site etkilenmez
    assert [k[3] for k in s.kayit] == [
        "https://emsal.uyap.gov.tr/aramalist",
        "https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments",
    ]


def test_adli_bir_kaynak_durunca_digeriyle_devam_eder(monkeypatch):
    def yanit(yontem, url, kw):
        if "bedesten" in url:
            return 429, {"content-type": "application/json", "retry-after": "60"}, b"{}"
        return 200, {"content-type": "application/json"}, json.dumps({"data": {"data": [
            {"id": "9", "daire": "X BAM 1. HD", "esasNo": "2020/1", "kararNo": "2021/2",
             "kararTarihi": "01.01.2021", "durum": "KESİNLEŞTİ"}], "recordsTotal": 1}}).encode()
    s = Sahte(yanit)
    monkeypatch.setattr(ortak, "_gonder", s)
    sonuc = adli.ara("kira", adet=2)
    assert [x["id"] for x in sonuc["sonuclar"]] == ["9"]
    assert "erişim sınırı aşıldı; 60 sn sonra" in sonuc["uyari"]
    assert sonuc["sonuclar"][0]["kaynak"] == "https://mevzuat.adalet.gov.tr/ictihat/9"


# --- Karar önbelleği --------------------------------------------------------------

def test_onbellek_lru():
    o = ortak.KararOnbellegi(2)
    o.koy("a", {"x": 1})
    o.koy("b", {"x": 2})
    assert o.al("a") == {"x": 1}          # a en son kullanılan oldu
    o.koy("c", {"x": 3})                  # en eski (b) atılır
    assert o.al("b") is None
    assert o.al("a") == {"x": 1} and o.al("c") == {"x": 3}
    assert len(o) == 2


def test_onbellek_kopya_dondurur():
    o = ortak.KararOnbellegi(2)
    o.koy("a", {"x": 1})
    d = o.al("a")
    d["x"] = 99
    assert o.al("a") == {"x": 1}


def test_varsayilan_kapasite_256():
    assert ortak.karar_onbellegi.kapasite == 256


def _sayac(monkeypatch, modul, ad="karar"):
    cagrilar = []

    def sahte_karar(karar_id):
        cagrilar.append(karar_id)
        return {"id": karar_id, "kaynak": f"https://ornek/{karar_id}", "uzunluk": 5, "metin": "metin"}
    monkeypatch.setattr(modul, ad, sahte_karar)
    return cagrilar


def test_karar_getir_ikinci_kez_siteye_gitmez(monkeypatch):
    cagrilar = _sayac(monkeypatch, danistay)
    s1 = anyio.run(server.karar_getir, "123", "idari")
    s2 = anyio.run(server.karar_getir, " 123 ", "idari")
    assert cagrilar == ["123"]
    assert s1 == s2 and s1["mahkeme_turu"] == "idari"


def test_karar_getir_yargitay_oneki_anahtarin_parcasi(monkeypatch):
    y = _sayac(monkeypatch, yargitay)
    e = _sayac(monkeypatch, uyap)
    anyio.run(server.karar_getir, "yargitay:5", "adli")
    anyio.run(server.karar_getir, "yargitay:5", "emsal")    # önek her durumda Yargıtay'a gider
    anyio.run(server.karar_getir, "5", "emsal")             # öneksiz id: UYAP Emsal, ayrı kayıt
    anyio.run(server.karar_getir, "5", "emsal")
    assert y == ["yargitay:5"]
    assert e == ["5"]


def test_karar_getir_hatayi_onbellege_almaz(monkeypatch):
    sayi = []

    def hatali(karar_id):
        sayi.append(karar_id)
        raise LookupError("yok")
    monkeypatch.setattr(anayasa.norm, "karar", hatali)
    for _ in range(2):
        with pytest.raises(LookupError):
            anyio.run(server.karar_getir, "E.2024/1", "norm")
    assert sayi == ["E.2024/1", "E.2024/1"]


# --- Metin kuralları ------------------------------------------------------------------

def test_model_ve_kullanici_metinlerinde_uzun_tire_yok():
    kok = Path(__file__).resolve().parent.parent
    dosyalar = [*sorted((kok / "turk_hukuku_ictihat").glob("*.py")),
                kok / "README.md", kok / "PRIVACY.md", kok / "SORUMLULUK-REDDI.md"]
    bulunan = [f"{d.name}:{no}" for d in dosyalar
               for no, satir in enumerate(d.read_text(encoding="utf-8").splitlines(), 1)
               if chr(0x2014) in satir or chr(0x2013) in satir]      # uzun ve orta tire
    assert bulunan == []
