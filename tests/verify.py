#!/usr/bin/env python3
"""rail-cinema dogrulama kapilari (Blender'siz calisir: python3 tests/verify.py)"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from patika import GAUGE, Parca, Patika


def karisik_patika():
    return Patika([
        Parca("duz", uzunluk=120),
        Parca("viraj", yaricap=500, aci_deg=40, yon=1, v_kmh=110),
        Parca("duz", uzunluk=60),
        Parca("viraj", yaricap=350, aci_deg=30, yon=-1, v_kmh=90),
        Parca("duz", uzunluk=100),
    ])


def ray_noktalari(patika, s):
    from mathutils import Vector  # yoksa pure fallback
    return None


def vektor_cikarma(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def uzunluk3(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def ray_basi(patika, s, taraf):
    """taraf: +1 sag / -1 sol; cant roll uygulanmis ray basi dunya noktasi."""
    konum, teget, sag, cant, _ = patika.cerceve(s)
    yan = taraf * GAUGE / 2
    cos_r, sin_r = math.cos(cant), math.sin(cant)
    y = yan * cos_r
    z = yan * sin_r
    return (konum[0] + sag[0] * y, konum[1] + sag[1] * y, z)


def main():
    p = karisik_patika()
    ok_adet = 0
    fail_adet = 0

    def kapil(ad, kosul, detay=""):
        nonlocal ok_adet, fail_adet
        if kosul:
            ok_adet += 1
            print(f"  [ok] {ad} {detay}")
        else:
            fail_adet += 1
            print(f"  [FAIL] {ad} {detay}")

    # 1) genislik sabiti: viraj + cant ile birlikte her s'de 1.435 m
    p = karisik_patika()
    en_kotu = 0.0
    s = 0.0
    while s <= p.uzunluk:
        sag_r = ray_basi(p, s, +1)
        sol_r = ray_basi(p, s, -1)
        olcen = uzunluk3(vektor_cikarma(sag_r, sol_r))
        en_kotu = max(en_kotu, abs(olcen - GAUGE))
        s += 5.0
    kapil("genislik sabit 1.435 m (cant'li virajlarda bile)", en_kotu < 0.002,
          f"(maks sapma {en_kotu * 1000:.2f} mm)")

    # 2) yay uzerinde kiriş/uzunluk orani analitik degerle ayni (konum butunlugu)
    R, ds = 500.0, 0.6
    p2 = Patika([Parca("viraj", yaricap=R, aci_deg=40, yon=1, cant_mm=150)])
    p2.cerceve(0.0)
    a = p2.cerceve(10.0)[0]
    b = p2.cerceve(10.0 + ds)[0]
    kiris = math.hypot(b[0] - a[0], b[1] - a[1])
    beklenen = 2 * R * math.sin(ds / (2 * R))
    kapil("viraj konum integrasyonu (kiristik uzunluk)", abs(kiris - beklenen) < 1e-6,
          f"({kiris:.9f} ~ {beklenen:.9f})")

    # 3) cant yuksekligi: sag ray yukarida ve dogru miktarda (R500, 150mm)
    p3 = Patika([Parca("viraj", yaricap=500, aci_deg=40, yon=1, cant_mm=150)])
    s = 20.0
    z_sag = ray_basi(p3, s, +1)[2]
    z_sol = ray_basi(p3, s, -1)[2]
    fark_mm = (z_sag - z_sol) * 1000
    kapil("supereleyisyon 150 mm (sag ray yukarida)", abs(fark_mm - 150.0) < 3.0,
          f"(olculen {fark_mm:.1f} mm)")

    # 4) sureklilik: parca eklerinde teget acisal atlama yok
    p4 = karisik_patika()
    maks_atlama = 0.0
    for (s0, s1, parca) in p4.sinirlar:
        t1 = p4.cerceve(s1 - 1e-6)[1]
        t2 = p4.cerceve(s1 + 1e-6)[1]
        aci = math.degrees(math.acos(max(-1.0, min(1.0,
                           t1[0] * t2[0] + t1[1] * t2[1]))))
        maks_atlama = max(maks_atlama, aci)
    kapil("parca eklerinde teget surekli", maks_atlama < 0.01,
          f"(maks atlama {maks_atlama:.2e} derece)")

    # 5) duz hat: konum ilerlemesi = arclength (zaten bilinen yol)
    p5 = Patika([Parca("duz", uzunluk=100)])
    a = p5.cerceve(20.0)[0]
    b = p5.cerceve(53.0)[0]
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    kapil("duz hat arclength", abs(d - 33.0) < 1e-9, f"({d:.6f} ~ 33)")

    # 6) determinizm
    p6 = karisik_patika()
    c1 = p6.cerceve(211.3)
    c2 = karisik_patika().cerceve(211.3)
    kapil("determinizm", c1[0] == c2[0] and c1[1] == c2[1])

    print(f"\n{'TUM KAPILAR GECTI' if fail_adet == 0 else 'KAPILARDA FAIL VAR'}"
          f" ({ok_adet} ok, {fail_adet} fail)")
    sys.exit(0 if fail_adet == 0 else 1)


if __name__ == "__main__":
    main()
