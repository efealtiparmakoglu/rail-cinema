#!/usr/bin/env python3
"""rail-cinema — sonsuz demiryolu patikasi (SAF MATEMATIK, Blender'siz).

Parça listesi -> serbest uzunluk s (metre) boyunca cerceve:
    konum(s)  : merkez hat uzerinde nokta
    teget(s)  : birim yon (yolun gittigi taraf)
    sag(s)    : birim yatay normal (teget'e dik, sag tarafa bakar)
    cant(s)   : supereleyisyon acisi (radyan; virajda dis ray yukselir)

Viraj supereleyisyonu Gercek demiryolu formuluyle hesaplanir:
    h = 11.8 * v_kmh^2 / R   (mm, teori tam dengelenmis yolcu yuku)
    uygulanacak miktar min(h, max_cant_mm) ile sinirlanir.
"""

import math

GAUGE = 1.435  # standart genislik (m), ray merkezlerinden
MAX_CANT_MM = 150.0


class Parca:
    """tip: 'duz' (uzunluk) | 'viraj' (yaricap, aci_deg, yon:+1 sag/-1 sol)"""

    def __init__(self, tip, uzunluk=0.0, yaricap=0.0, aci_deg=0.0, yon=1,
                 v_kmh=0.0, cant_mm=None):
        self.tip = tip
        if tip == "duz":
            self.uzunluk = uzunluk
            self.yaricap = math.inf
            self.cant = 0.0
        else:
            self.yaricap = yaricap
            self.uzunluk = math.radians(aci_deg) * yaricap
            self.yon = yon
            if cant_mm is None:
                h = 11.8 * v_kmh ** 2 / yaricap if (v_kmh and yaricap) else 0.0
                cant_mm = min(h, MAX_CANT_MM)
            self.cant = cant_mm / 1000.0

    def donusum(self, px, py, tx, ty):
        """(px,py) baslangic noktasi, (tx,ty) baslangic tegesi; parca sonunu doner."""
        if self.tip == "duz":
            return (px + tx * self.uzunluk, py + ty * self.uzunluk, tx, ty)
        # merkez: sag yonde R kadar (yon=-1 ise sol)
        cx = px - self.yon * ty * self.yaricap
        cy = py + self.yon * tx * self.yaricap
        d_faz = self.uzunluk / self.yaricap * self.yon
        cos_d, sin_d = math.cos(d_faz), math.sin(d_faz)
        # teget donusumu
        nx = tx * cos_d - ty * sin_d
        ny = tx * sin_d + ty * cos_d
        # konum: merkez etrafinda donmus baslangic vektoru
        rx, ry = px - cx, py - cy
        return (cx + rx * cos_d - ry * sin_d,
                cy + rx * sin_d + ry * cos_d, nx, ny)


class Patika:
    def __init__(self, parcalar, bas_x=0.0, bas_y=0.0, bas_tx=0.0, bas_ty=1.0):
        self.parcalar = parcalar
        self.baslangic = (bas_x, bas_y, bas_tx, bas_ty)
        self.sinirlar = []  # (s0, s1, parca)
        px, py, tx, ty = baslangic = self.baslangic
        s = 0.0
        for p in parcalar:
            self.sinirlar.append((s, s + p.uzunluk, p))
            s += p.uzunluk
        self.uzunluk = s

    def cerceve(self, s):
        """s -> (konum, teget, sag, cant_acisi_rad, egrilik 1/R)"""
        s = max(0.0, min(self.uzunluk, s))
        px, py, tx, ty = self.baslangic
        for (s0, s1, p) in self.sinirlar:
            if s <= s1 + 1e-9:
                k = s - s0
                if p.tip == "duz":
                    konum = (px + tx * k, py + ty * k)
                    teget = (tx, ty)
                    egri = 0.0
                    cant = 0.0
                else:
                    d_faz = k / p.yaricap * p.yon
                    cos_d, sin_d = math.cos(d_faz), math.sin(d_faz)
                    cx = px - p.yon * ty * p.yaricap
                    cy = py + p.yon * tx * p.yaricap
                    rx, ry = px - cx, py - cy
                    konum = (cx + rx * cos_d - ry * sin_d,
                             cy + rx * sin_d + ry * cos_d)
                    teget = (tx * cos_d - ty * sin_d, tx * sin_d + ty * cos_d)
                    egri = p.yon / p.yaricap
                    cant = math.asin(max(-0.9, min(0.9, p.cant / GAUGE)))
                sag = (-teget[1], teget[0])  # tegi 90 derece sagi
                return konum, teget, sag, cant, egri
            # parca icinde degilsek baslangici parca sonuna tasi
            px, py, tx, ty = p.donusum(px, py, tx, ty)
        # son parca sonunda kal
        konum = (px, py)
        return konum, (tx, ty), (-ty, tx), 0.0, 0.0

    def ornekler(self, adim=0.5):
        """s boyunca duzgun ornek listesi [(s, konum, teget, sag, cant), ...]"""
        cikti = []
        n = int(self.uzunluk / adim) + 1
        for i in range(n):
            s = min(i * adim, self.uzunluk)
            konum, teget, sag, cant, _ = self.cerceve(s)
            cikti.append((s, konum, teget, sag, cant))
        return cikti
