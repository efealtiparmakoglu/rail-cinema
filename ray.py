#!/usr/bin/env python3
"""rail-cinema — patika uzerine gercek demiryolu geometrisi (Blender icinde).

Katmanlar (z=0 ray basi ust yuzeyi):
    rayler       : poly curve + UIC-60 sadirlestirilmis profil bevel
    traversler   : 2.6 x 0.26 x 0.20 beton, 0.60 m aralik (tek mesh, cok obje)
    balast       : yamuk kesitli loft band
    katoneri     : her 50 m direk + konsol + sarkali messenger + kontakt teli

Cant (supereleyisyon): kesit teget etrafinda roll edilir; R = Rz(yaw)·Rx(roll).
"""

import math

import bpy
from mathutils import Vector

from patika import GAUGE, Patika

RAY_YUKSEKLIK = 0.172
TRAVES = (2.6, 0.26, 0.20)
TRAVES_ARALIK = 0.60
TRAVES_UST = -(RAY_YUKSEKLIK + 0.005)
BALAST_UST = TRAVES_UST - TRAVES[2]
BALAST_DERINLIK = 0.42
MUHABERE_YUKSEKLIK = 5.30
KONSOL_YUKSEKLIK = 6.15
KATONERI_ARALIK = 50.0
SARKA = 0.35

MAT_CACHE = {}


def mat_yap(ad, renk, rough=0.6, metalik=0.0):
    if ad in MAT_CACHE:
        return MAT_CACHE[ad]
    m = bpy.data.materials.new(ad)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (renk[0], renk[1], renk[2], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metalik
    MAT_CACHE[ad] = m
    return m


def kutu(ad, merkez, boyut, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=merkez)
    o = bpy.context.active_object
    o.name = ad
    o.scale = boyut
    o.data.materials.append(mat)
    return o


def ray_profili():
    """UIC-60 sadirlestirilmis kesit; ray basi (0,0) merkezli poly curve."""
    H = RAY_YUKSEKLIK
    noktalar = [
        (-0.075, -H), (0.075, -H),
        (0.075, -H + 0.030), (0.030, -0.130), (0.018, -0.060),
        (0.036, -0.028), (0.036, -0.012),
        (-0.036, -0.012), (-0.036, -0.028), (-0.018, -0.060),
        (-0.030, -0.130), (-0.075, -H + 0.030),
    ]
    curve = bpy.data.curves.new("RayKesit", "CURVE")
    spline = curve.splines.new("POLY")
    spline.points.add(len(noktalar) - 1)
    for i, (x, y) in enumerate(noktalar):
        spline.points[i].co = (x, y, 0.0, 1.0)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new("RayKesitProfili", curve)
    bpy.context.collection.objects.link(obj)
    return obj


def egrisel_tel(ad, noktalar, r, mat):
    curve = bpy.data.curves.new(ad, "CURVE")
    spline = curve.splines.new("POLY")
    spline.points.add(len(noktalar) - 1)
    for i, p in enumerate(noktalar):
        spline.points[i].co = (p[0], p[1], p[2], 1.0)
    curve.bevel_mode = "ROUND"
    curve.bevel_depth = r
    curve.bevel_resolution = 3
    curve.use_fill_caps = True
    obj = bpy.data.objects.new(ad, curve)
    obj.data.materials.append(mat)
    bpy.context.collection.objects.link(obj)
    return obj


def cerceve(patika, s):
    """s -> (Vector konum z=0, Vector teget, Vector sag, cant_roll rad)."""
    konum, teget, sag, cant, _ = patika.cerceve(s)
    return (Vector((konum[0], konum[1], 0.0)),
            Vector((teget[0], teget[1], 0.0)),
            Vector((sag[0], sag[1], 0.0)),
            cant)


def kesit_dunya(konum, sag, roll, ofsetler):
    """(yanal, dusey) listesini cant roll ile dunya noktalarina gecer."""
    cos_r, sin_r = math.cos(roll), math.sin(roll)
    cikti = []
    for (yan, z) in ofsetler:
        y = yan * cos_r - z * sin_r
        zz = yan * sin_r + z * cos_r
        cikti.append((konum.x + sag.x * y, konum.y + sag.y * y, zz))
    return cikti


def hat_kur(patika: Patika, hat_cfg, kok):
    once = set(bpy.data.objects)

    balast_m = mat_yap("Balast", (0.25, 0.23, 0.21), rough=1.0)
    traves_m = mat_yap("Traves", (0.55, 0.54, 0.52), rough=0.85)
    ray_m = mat_yap("Ray", (0.78, 0.79, 0.82), rough=0.22, metalik=0.95)
    celik_m = mat_yap("Catelik", (0.45, 0.46, 0.48), rough=0.5, metalik=0.7)
    bet_m = mat_yap("Katoneri", (0.62, 0.60, 0.58), rough=0.8)

    adim = hat_cfg.get("ornek_adim", 0.5)
    n = int(patika.uzunluk / adim) + 1
    sler = [min(i * adim, patika.uzunluk) for i in range(n)]

    # ---------------- balast band
    kesit = [(-2.2, BALAST_UST), (2.2, BALAST_UST),
             (3.4, BALAST_UST - BALAST_DERINLIK),
             (-3.4, BALAST_UST - BALAST_DERINLIK)]
    verts = []
    for s in sler:
        konum, teget, sag, roll = cerceve(patika, s)
        verts.extend(kesit_dunya(konum, sag, roll, kesit))
    faces = []
    m = len(kesit)
    for i in range(len(sler) - 1):
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((i * m + j, i * m + j2, (i + 1) * m + j2, (i + 1) * m + j))
    mesh = bpy.data.meshes.new("BalastBandi")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bal_obj = bpy.data.objects.new("BalastBandi", mesh)
    bal_obj.data.materials.append(balast_m)
    bpy.context.collection.objects.link(bal_obj)

    # ---------------- traversler (tek mesh, cok obje)
    traves_mesh = None
    s = hat_cfg.get("traves_baslangic", 0.0)
    adet = 0
    while s <= patika.uzunluk:
        konum, teget, sag, roll = cerceve(patika, s)
        yaw = math.atan2(teget.y, teget.x)
        o = kutu(f"Traves{adet}", (konum.x, konum.y,
                                   TRAVES_UST + TRAVES[2] / 2), TRAVES, traves_m)
        if traves_mesh is None:
            traves_mesh = o.data
        else:
            o.data = traves_mesh
        o.rotation_euler = (roll, 0.0, yaw - math.pi / 2)  # XYZ: Rz·Rx
        adet += 1
        s += TRAVES_ARALIK

    # ---------------- rayler (2 ofset curve + profil bevel)
    profil = ray_profili()
    for taraf in (-1, 1):
        pts = []
        for s in sler:
            konum, teget, sag, roll = cerceve(patika, s)
            yan = taraf * GAUGE / 2
            p = kesit_dunya(konum, sag, roll, [(yan, 0.0)])[0]
            pts.append(p)
        curve = bpy.data.curves.new(f"Ray{taraf}", "CURVE")
        spline = curve.splines.new("POLY")
        spline.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            spline.points[i].co = (p[0], p[1], p[2], 1.0)
        curve.bevel_mode = "OBJECT"
        curve.bevel_object = profil
        curve.use_fill_caps = True
        obj = bpy.data.objects.new(f"Ray{taraf}", curve)
        obj.data.materials.append(ray_m)
        bpy.context.collection.objects.link(obj)

    # ---------------- katoneri
    aralik = hat_cfg.get("katoneri_aralik", KATONERI_ARALIK)
    if aralik > 0:
        mast_s = aralik / 2
        mastlar = []
        i = 0
        while mast_s <= patika.uzunluk:
            konum, teget, sag, roll = cerceve(patika, mast_s)
            yaw = math.atan2(teget.y, teget.x)
            yan = 2.9
            mx = konum.x + sag.x * yan
            my = konum.y + sag.y * yan
            mast = kutu(f"Mast{i}", (mx, my, (KONSOL_YUKSEKLIK + 0.4) / 2),
                        (0.30, 0.30, KONSOL_YUKSEKLIK + 0.4), bet_m)
            mast.rotation_euler = (0, 0, yaw - math.pi / 2)
            kol_uz = yan - 0.35
            kol = kutu(f"Konsol{i}",
                       (konum.x + sag.x * (yan - kol_uz / 2),
                        konum.y + sag.y * (yan - kol_uz / 2),
                        KONSOL_YUKSEKLIK),
                       (0.12, kol_uz, 0.12), celik_m)
            kol.rotation_euler = (0, 0, yaw - math.pi / 2)
            mastlar.append(mast_s)
            i += 1
            mast_s += aralik

        if len(mastlar) >= 2:
            s0 = mastlar[0]
            s1 = mastlar[-1]
            msg, kon, aski = [], [], []
            s = s0
            aski_adim = hat_cfg.get("aski_aralik", 8.0)
            aski_s = s0 + aski_adim / 2
            while s <= s1 + 1e-6:
                konum, teget, sag, roll = cerceve(patika, s)
                faz = ((s - s0) % aralik) / aralik
                sarka = SARKA * math.sin(math.pi * faz)
                msg.append((konum.x, konum.y, KONSOL_YUKSEKLIK - sarka))
                kon.append((konum.x, konum.y, MUHABERE_YUKSEKLIK))
                s += 1.0
            while aski_s <= s1 - aski_adim / 2:
                konum, teget, sag, roll = cerceve(patika, aski_s)
                faz = ((aski_s - s0) % aralik) / aralik
                sarka = SARKA * math.sin(math.pi * faz)
                yuk = (KONSOL_YUKSEKLIK - sarka) - MUHABERE_YUKSEKLIK
                aski.append((konum.x, konum.y, MUHABERE_YUKSEKLIK + yuk / 2, yuk))
                aski_s += aski_adim
            egrisel_tel("MessengerTeli", msg, 0.014, celik_m)
            egrisel_tel("KontaktTeli", kon, 0.012, celik_m)
            for j, (x, y, z, yuk) in enumerate(aski):
                kutu(f"Aski{j}", (x, y, z), (0.05, 0.05, yuk), celik_m)

    # ---------------- peron (istasyon platformu)
    peron_cfg = hat_cfg.get("peron")
    if peron_cfg:
        peron_kur(patika, peron_cfg, kok, once)

    yeni = set(bpy.data.objects) - once
    for o in yeni:
        if o is not kok:
            o.parent = kok
    return yeni


def peron_kur(patika, peron_cfg, kok, once_set):
    """Platform bandi + sari guvenlik cizgisi + lambalar + tabela.
    s0..s1 arasi, taraf: +1 sag / -1 sol."""
    s0, s1 = peron_cfg.get("s0", 0.0), min(peron_cfg.get("s1", 40.0),
                                           patika.uzunluk)
    taraf = peron_cfg.get("taraf", 1)
    p_yuksek = 0.92
    p_kenar = 1.75   # ray merkezinden platform kenari
    p_arka = 4.6     # dis kenar

    beton = mat_yap("PeronBeton", (0.52, 0.51, 0.49), rough=0.8)
    sari = mat_yap("PeronSari", (0.85, 0.65, 0.05), rough=0.6)
    metal = MAT_CACHE["Catelik"] if "Catelik" in MAT_CACHE else \
        mat_yap("Catelik", (0.45, 0.46, 0.48), rough=0.5, metalik=0.7)
    beyaz = mat_yap("TabelaBeyaz", (0.85, 0.85, 0.86), rough=0.5)

    adim = 1.0
    n = int((s1 - s0) / adim) + 1
    kesit = [(taraf * p_kenar, 0.0), (taraf * p_arka, 0.0),
             (taraf * p_arka, p_yuksek), (taraf * p_kenar, p_yuksek)]
    verts, faces = [], []
    m = len(kesit)
    for i in range(n):
        s = s0 + (s1 - s0) * i / (n - 1)
        konum, teget, sag, roll = cerceve(patika, s)
        pts = kesit_dunya(konum, sag, roll, kesit)
        verts.extend(pts)
    for i in range(n - 1):
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((i * m + j, i * m + j2, (i + 1) * m + j2, (i + 1) * m + j))
    mesh = bpy.data.meshes.new("Peron")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    po = bpy.data.objects.new("Peron", mesh)
    po.data.materials.append(beton)
    bpy.context.collection.objects.link(po)

    # sari guvenlik cizgisi: ince band platform ustunde
    cizgi_kesit = [(taraf * (p_kenar + 0.15), p_yuksek + 0.005),
                   (taraf * (p_kenar + 0.55), p_yuksek + 0.005),
                   (taraf * (p_kenar + 0.55), p_yuksek + 0.02),
                   (taraf * (p_kenar + 0.15), p_yuksek + 0.02)]
    verts, faces = [], []
    for i in range(n):
        s = s0 + (s1 - s0) * i / (n - 1)
        konum, teget, sag, roll = cerceve(patika, s)
        verts.extend(kesit_dunya(konum, sag, roll, cizgi_kesit))
    for i in range(n - 1):
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((i * m + j, i * m + j2, (i + 1) * m + j2, (i + 1) * m + j))
    mesh2 = bpy.data.meshes.new("PeronCizgi")
    mesh2.from_pydata(verts, [], faces)
    mesh2.update()
    co = bpy.data.objects.new("PeronCizgi", mesh2)
    co.data.materials.append(sari)
    bpy.context.collection.objects.link(co)

    # lambalar + tabela
    for i, s in enumerate([s0 + 6.0, (s0 + s1) / 2, s1 - 6.0]):
        if s > patika.uzunluk:
            continue
        konum, teget, sag, roll = cerceve(patika, s)
        yan = taraf * (p_arka - 0.5)
        mx, my = konum.x + sag.x * yan, konum.y + sag.y * yan
        yaw = math.atan2(teget.y, teget.x)
        direk = kutu(f"PeronLamba{i}", (mx, my, p_yuksek + 2.1),
                     (0.10, 0.10, 4.2), metal)
        direk.rotation_euler = (0, 0, yaw - math.pi / 2)
        kol_uz = 1.3
        kol = kutu(f"PeronLambaKol{i}",
                   (mx + sag.x * -taraf * kol_uz / 2,
                    my + sag.y * -taraf * kol_uz / 2, p_yuksek + 4.1),
                   (0.08, kol_uz, 0.08), metal)
        kol.rotation_euler = (0, 0, yaw - math.pi / 2)
        m_isik = bpy.data.materials.new(f"PeronIsik{i}")
        m_isik.use_nodes = True
        nti = m_isik.node_tree
        nti.nodes.clear()
        emi = nti.nodes.new("ShaderNodeEmission")
        emi.inputs["Color"].default_value = (1.0, 0.85, 0.6, 1)
        emi.inputs["Strength"].default_value = 18.0
        outi = nti.nodes.new("ShaderNodeOutputMaterial")
        nti.links.new(emi.outputs["Emission"], outi.inputs["Surface"])
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.16, segments=16, ring_count=12,
            location=(mx + sag.x * -taraf * kol_uz,
                      my + sag.y * -taraf * kol_uz, p_yuksek + 4.0))
        kure = bpy.context.active_object
        kure.name = f"PeronLambaKure{i}"
        bpy.ops.object.shade_smooth()
        kure.data.materials.append(m_isik)

    # tabela (iki bacak + panel)
    s_t = (s0 + s1) / 2
    konum, teget, sag, roll = cerceve(patika, s_t)
    yan = taraf * (p_arka - 1.1)
    mx, my = konum.x + sag.x * yan, konum.y + sag.y * yan
    yaw = math.atan2(teget.y, teget.x)
    for dx in (-1.1, 1.1):
        bac = kutu(f"TabelaBacak{dx}", (mx + teget.x * dx, my + teget.y * dx, p_yuksek + 1.1),
                   (0.07, 0.07, 2.2), metal)
    panel = kutu("TabelaPanel", (mx, my, p_yuksek + 2.0), (2.6, 0.08, 0.7), beyaz)
    panel.rotation_euler = (0, 0, yaw)
