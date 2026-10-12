"""İstemcilerin ortak yardımcıları: arama sözdizimi ve erişim sınırı.

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
"""
from __future__ import annotations

import re

import httpx

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


def erisim_siniri(r: httpx.Response, kaynak: str) -> None:
    """HTTP 429'da modele anlaşılır bir Türkçe hata verir (bekleyip yeniden denemez)."""
    if r.status_code == 429:
        sure = r.headers.get("retry-after") or "birkaç"
        raise LookupError(f"{kaynak} erişim sınırı aşıldı; {sure} sn sonra tekrar deneyin.")
