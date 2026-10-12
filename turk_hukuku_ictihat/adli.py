"""Adli yargı birleşik araması: Yargıtay (Bedesten) + Bölge Adliye ve ilk derece (UYAP Emsal).

İki kaynak aynı sayfa numarasıyla sorgulanır; `adet` ikisine bölünür (önce Yargıtay).
`adet` en az 2'dir: her kaynağa en az bir yer kalsın, toplam iki kaynağın toplamı olsun.
Yargıtay sonuçlarının id'si `yargitay:` önekini taşır; `karar_getir` öneke bakarak
doğru kaynağa gider. Önceki sürümlerde dönen öneksiz UYAP Emsal id'leri aynen çalışır.
Bir kaynak yanıt vermezse diğerinin sonuçları `uyari` ile döner.
"""
from __future__ import annotations

from . import uyap, yargitay

_ONEK = "yargitay:"


def ara(ifade: str, adet: int = 10, sayfa: int = 1) -> dict:
    adet = max(2, min(adet, 50))
    sayfa = max(1, sayfa)
    y_adet = (adet + 1) // 2
    e_adet = adet - y_adet                      # adet >= 2 olduğundan en az 1
    sonuclar: list[dict] = []
    toplam = 0
    uyarilar: list[str] = []

    try:
        y = yargitay.ara(ifade, adet=y_adet, sayfa=sayfa)
        for s in y["sonuclar"]:
            s["id"] = _ONEK + s["id"]
            s["kaynak_turu"] = "yargitay"
        sonuclar += y["sonuclar"]
        toplam += y.get("toplam") or 0
    except Exception as hata:  # bir kaynağın aksaması diğerini düşürmesin
        uyarilar.append(f"Yargıtay (Bedesten) aranamadı: {hata}")

    if e_adet:
        try:
            em = uyap.ara(ifade, adet=e_adet, sayfa=sayfa)
            for s in em["sonuclar"]:
                s["kaynak_turu"] = "emsal"
            sonuclar += em["sonuclar"]
            toplam += em.get("toplam") or 0
        except Exception as hata:
            uyarilar.append(f"UYAP Emsal (BAM/ilk derece) aranamadı: {hata}")

    if not sonuclar and uyarilar:
        raise LookupError("; ".join(uyarilar))
    sonuc = {"ifade": ifade, "sayfa": sayfa, "toplam": toplam, "sonuclar": sonuclar}
    if uyarilar:
        sonuc["uyari"] = "; ".join(uyarilar)
    return sonuc


def karar(karar_id: str) -> dict:
    karar_id = str(karar_id).strip()
    if karar_id.lower().startswith(_ONEK):
        return yargitay.karar(karar_id[len(_ONEK):])
    return uyap.karar(karar_id)
