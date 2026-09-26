#!/usr/bin/env python3
# Blender icinde: blender --background --python rail_render.py -- --scene scenes/yay_kirsasi.json [--gif 36]
"""rail-cinema — sonsuz demiryolunu Cycles ile render eder.

Kamera modlari:
    "sabit" : position/look_at dunya koordinati (fast film cekimi)
    "dolly" : patikayi takip eden yan vinç — s(t) ilerler, look_ahead noktasina bakar
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

import bpy
from mathutils import Vector

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)

from patika import Patika, Parca  # noqa: E402
import ray  # noqa: E402

G = 9.81


# ---------------------------------------------------------------- sahne (ocean-cinema ailesi ayni kalip)

def gunes_vektoru(el_rad, az_rad):
    return Vector((math.cos(el_rad) * math.sin(az_rad),
                   -math.cos(el_rad) * math.cos(az_rad),
                   math.sin(el_rad)))


def temiz():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def kamera_kur(konum, hedef, lens=50):
    cam = bpy.data.cameras.new("Cam")
    cam.lens = lens
    co = bpy.data.objects.new("kamera", cam)
    bpy.context.collection.objects.link(co)
    co.location = konum
    yon = Vector(hedef) - Vector(konum)
    co.rotation_euler = yon.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = co
    return co


def govcem_diski(cfg, cam_konum):
    d = cfg["sun"].get("disk")
    if not d:
        return
    el = math.radians(cfg["sun"]["elevation_deg"])
    az = math.radians(cfg["sun"]["azimuth_deg"])
    dist = d.get("distance", 400)
    merkez = gunes_vektoru(el, az) * dist
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=d.get("radius", 3.0),
                                      fill_type="NGON", location=merkez)
    disk = bpy.context.active_object
    disk.name = "govcem_diski"
    yon = Vector(cam_konum) - merkez
    disk.rotation_euler = yon.to_track_quat("Z", "Y").to_euler()
    m = bpy.data.materials.new("DiskMat")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    renk = list(d.get("color", (1.0, 0.6, 0.3)))
    if len(renk) == 3:
        renk.append(1.0)
    em.inputs["Color"].default_value = renk
    em.inputs["Strength"].default_value = d.get("strength", 40.0)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    disk.data.materials.append(m)


def sahne_kur(cfg):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for dv in prefs.devices:
            dv.use = True
        sc.cycles.device = "GPU"
    except Exception as e:
        print("  [uyari] GPU:", e)
    sc.cycles.samples = cfg["render"].get("samples", 128)
    sc.cycles.use_denoising = True
    sc.render.resolution_x = cfg["render"].get("width", 1600)
    sc.render.resolution_y = cfg["render"].get("height", 900)
    sc.view_settings.view_transform = "Filmic"
    sc.view_settings.exposure = cfg["render"].get("exposure", 0.0)
    look = cfg["render"].get("look")
    if look:
        try:
            sc.view_settings.look = look
        except Exception as e:
            print(f"  [uyari] look '{look}': {e}")

    dunya = bpy.data.worlds.new("Gokyuzu")
    sc.world = dunya
    dunya.use_nodes = True
    nt = dunya.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "HOSEK_WILKIE"
    sun_elev = math.radians(cfg["sun"]["elevation_deg"])
    sun_azim = math.radians(cfg["sun"]["azimuth_deg"])
    sky.sun_elevation = sun_elev
    sky.sun_rotation = sun_azim
    skycfg = cfg.get("sky", {})
    try:
        sky.turbidity = skycfg.get("turbidity", 2.2)
    except Exception as e:
        print("  [uyari] turbidity:", e)
    sky.sun_rotation = sun_azim + math.radians(skycfg.get("az_offset", 0))
    bg_node = nt.nodes.new("ShaderNodeBackground")
    bg_node.inputs["Strength"].default_value = skycfg.get("strength", 1.0)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg_node.inputs["Color"])
    nt.links.new(bg_node.outputs["Background"], out.inputs["Surface"])

    sun_data = bpy.data.lights.new("gunes", "SUN")
    sun_data.energy = cfg["sun"].get("strength", 3.5)
    sun_data.angle = math.radians(1.2)
    sun_data.color = tuple(cfg["sun"].get("color", (1.0, 0.9, 0.75)))
    sun_obj = bpy.data.objects.new("gunes_isigi", sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = gunes_vektoru(sun_elev, sun_azim).to_track_quat("Z", "Y").to_euler()
    return sc


def zemin_kur(cfg):
    z = cfg.get("zemin", {})
    m = bpy.data.materials.new("Zemin")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    renk = z.get("color", (0.07, 0.075, 0.04))
    b.inputs["Base Color"].default_value = (renk[0], renk[1], renk[2], 1)
    b.inputs["Roughness"].default_value = z.get("roughness", 0.95)
    bpy.ops.mesh.primitive_plane_add(size=z.get("boyut", 2000),
                                     location=(0, 0, z.get("yukseklik", -0.86)))
    o = bpy.context.active_object
    o.name = "Zemin"
    o.data.materials.append(m)

    # uz tepeler (deterministik)
    if z.get("tepeler"):
        import random
        rng = random.Random(z.get("tepe_tohum", 5))
        m_t = bpy.data.materials.new("Tepe")
        m_t.use_nodes = True
        bt = m_t.node_tree.nodes["Principled BSDF"]
        renk_t = z.get("tepe_renk", (0.05, 0.06, 0.045))
        bt.inputs["Base Color"].default_value = (renk_t[0], renk_t[1], renk_t[2], 1)
        bt.inputs["Roughness"].default_value = 0.95
        for i in range(z.get("tepe_adet", 7)):
            aci = rng.uniform(0, 2 * math.pi)
            mesafe = rng.uniform(260, 620)
            x, y = math.cos(aci) * mesafe, math.sin(aci) * mesafe
            bpy.ops.mesh.primitive_uv_sphere_add(
                radius=rng.uniform(70, 150), segments=24, ring_count=14,
                location=(x, y, -55))
            t = bpy.context.active_object
            t.name = f"Tepe{i}"
            t.scale = (rng.uniform(1.8, 3.4), rng.uniform(1.2, 2.2),
                       rng.uniform(0.55, 0.85))
            t.data.materials.append(m_t)


# ---------------------------------------------------------------- kamera modlari

def dolly_konum(patika, s, cam_cfg):
    konum, teget, sag, cant = ray.cerceve(patika, s)
    yanal = cam_cfg.get("yanal", 6.0)
    yuksek = cam_cfg.get("yukseklik", 2.4)
    pos = konum + sag * yanal + Vector((0, 0, yuksek))
    hedef_s = s + cam_cfg.get("look_ahead", 35.0)
    hedef_k, _, _, _ = ray.cerceve(patika, hedef_s)
    hedef = hedef_k + Vector((0, 0, cam_cfg.get("look_yukseklik", 1.5)))
    return pos, hedef


# ---------------------------------------------------------------- ana

def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--gif", type=int, default=0)
    ap.add_argument("--fps", type=int, default=12)
    a = ap.parse_args(args)

    cfg = json.load(open(a.scene, encoding="utf-8"))
    if os.environ.get("HIZLI") == "1":
        cfg["render"] = {**cfg.get("render", {}), "width": 800, "height": 450,
                         "samples": 32}
        cfg["output"] = "/tmp/onizleme_ray_" + os.path.basename(a.scene).replace(".json", ".png")
        print("  [HIZLI] onizleme ->", cfg["output"])

    temiz()
    sc = sahne_kur(cfg)
    zemin_kur(cfg)

    parcalar = [Parca(p["tip"], uzunluk=p.get("uzunluk", 0),
                      yaricap=p.get("yaricap", 0), aci_deg=p.get("aci_deg", 0),
                      yon=p.get("yon", 1), v_kmh=p.get("v_kmh", 0),
                      cant_mm=p.get("cant_mm"))
                for p in cfg["patika"]["segments"]]
    patika = Patika(parcalar)
    print(f"  [patika] uzunluk={patika.uzunluk:.1f} m")

    kok = bpy.data.objects.new("Hat", None)
    bpy.context.collection.objects.link(kok)
    ray.hat_kur(patika, cfg.get("hat", {}), kok)

    cam_cfg = cfg["camera"]
    if a.gif:
        cfg["render"] = {**cfg.get("render", {}), "width": 1280, "height": 720,
                         "samples": 48}
        out = os.path.splitext(cfg["output"])[0] + ".gif"
    else:
        out = cfg["output"]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    if cam_cfg.get("mode") == "dolly":
        ilk_pos, ilk_hedef = dolly_konum(patika, cam_cfg.get("s", 10.0), cam_cfg)
        cam_obj = kamera_kur(ilk_pos, ilk_hedef, cam_cfg.get("lens", 35))
    else:
        cam_obj = kamera_kur(cam_cfg["position"], cam_cfg["look_at"],
                             cam_cfg.get("lens", 40))
        print(f"  [kamera] sabit {cam_cfg['position']} -> {cam_cfg['look_at']}")
    govcem_diski(cfg, cam_obj.location)

    if not a.gif:
        sc.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print(f"== BİTTİ -> {out}")
        return

    tmp = out + ".frames"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    v = cam_cfg.get("hiz", 10.0)
    s0 = cam_cfg.get("s", 10.0)
    for f in range(a.gif):
        t = f / a.fps
        s = s0 + v * t
        pos, hedef = dolly_konum(patika, s, cam_cfg)
        cam_obj.location = pos
        yon = hedef - pos
        cam_obj.rotation_euler = yon.to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = f"{tmp}/f{f:05d}.png"
        bpy.ops.render.render(write_still=True)
        print(f"  kare {f + 1}/{a.gif} s={s:.1f}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps),
                    "-i", f"{tmp}/f%05d.png",
                    "-vf", "palettegen=max_colors=256:stats_mode=diff",
                    f"{tmp}/pal.png"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps),
                    "-i", f"{tmp}/f%05d.png", "-i", f"{tmp}/pal.png",
                    "-lavfi", "paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
                    "-loop", "0", out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"== BİTTİ -> {out}")


if __name__ == "__main__":
    main()
