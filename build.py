"""Genera Sparkly Ores: minerales en tonos pastel con destellos animados.

Las texturas originales se leen del juego (caché de Fabric Loom), así el repo
no guarda archivos de Mojang. Resultado: dist/sparkly-ores-<versión>+<mc>.zip
"""
import colorsys
import io
import json
import pathlib
import random
import zipfile

from PIL import Image

VERSION = "1.0.0"
ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"
LOOM = pathlib.Path.home() / ".gradle/caches/fabric-loom"
BLOCK = "assets/minecraft/textures/block/"

VERSIONS = {
    "26.3": {"min_format": 97, "max_format": 97},
    "1.21.1": {"pack_format": 34},
    "1.20.1": {"pack_format": 15},
}

# Rampas de color de oscuro a claro, con la identidad de cada mineral
PALETTES = {
    "diamond": [(24, 120, 140), (56, 200, 210), (120, 236, 232), (196, 255, 250), (245, 255, 255)],
    "emerald": [(14, 110, 60), (36, 190, 104), (96, 234, 150), (176, 255, 204), (236, 255, 244)],
    "gold": [(150, 90, 20), (236, 166, 40), (255, 214, 90), (255, 240, 160), (255, 252, 226)],
    "lapis": [(30, 46, 150), (62, 96, 214), (110, 150, 246), (170, 198, 255), (228, 236, 255)],
    "redstone": [(140, 16, 50), (222, 44, 84), (255, 98, 132), (255, 160, 182), (255, 226, 232)],
    "iron": [(130, 92, 74), (196, 146, 120), (232, 186, 162), (248, 216, 198), (255, 240, 230)],
    "copper": [(150, 70, 52), (214, 112, 84), (246, 154, 124), (255, 198, 176), (255, 232, 220)],
    "verdigris": [(40, 112, 100), (70, 170, 150), (118, 220, 190), (180, 246, 222), (230, 255, 244)],
    "coal": [(30, 26, 40), (48, 42, 62), (70, 62, 90), (96, 86, 120), (130, 120, 156)],
    "quartz": [(150, 120, 120), (214, 196, 196), (240, 228, 230), (252, 244, 246), (255, 255, 255)],
    "debris": [(120, 80, 70), (170, 120, 104), (214, 164, 146), (240, 204, 190), (255, 236, 228)],
}

# textura: (mineral, piedra base)
ORES = {}
for m in ("coal", "iron", "copper", "gold", "redstone", "lapis", "diamond", "emerald"):
    ORES[f"{m}_ore"] = (m, "stone")
    ORES[f"deepslate_{m}_ore"] = (m, "deepslate")
ORES["nether_gold_ore"] = ("gold", "netherrack")
ORES["nether_quartz_ore"] = ("quartz", "netherrack")
ORES["ancient_debris_side"] = ("debris", None)
ORES["ancient_debris_top"] = ("debris", None)

FRAMES = 24
FRAMETIME = 2
SPARKLES = 3


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def sat(c):
    return max(c[:3]) - min(c[:3])


def ramp(pal, t):
    t = min(max(t, 0.0), 1.0) * (len(pal) - 1)
    i = min(int(t), len(pal) - 2)
    f = t - i
    return tuple(round(a + (b - a) * f) for a, b in zip(pal[i], pal[i + 1]))


def is_mineral(c, mineral):
    """Qué píxeles (de los que no están en la piedra) son el mineral en sí."""
    if mineral in ("coal", "quartz"):
        return True
    return sat(c) >= 28


def recolor(im, mineral, base):
    """Pinta los píxeles del mineral con su rampa pastel. Devuelve la imagen y la máscara."""
    im = im.convert("RGBA")
    px = im.load()
    stone = set(base.getdata()) if base else set()
    cells = [(x, y) for y in range(16) for x in range(16)]
    if mineral == "debris":
        # El escombro ancestral queda con su color; solo sus partes claras brillan
        ls = sorted(lum(px[p]) for p in cells)
        cut = ls[int(len(ls) * 0.75)]
        return im, {p for p in cells if lum(px[p]) >= cut}
    else:
        cells_m = [(x, y) for x, y in cells if px[x, y] not in stone and is_mineral(px[x, y], mineral)]
    groups = {}
    for x, y in cells_m:
        c = px[x, y]
        key = mineral
        if mineral == "copper":
            h = colorsys.rgb_to_hsv(*(v / 255 for v in c[:3]))[0]
            key = "verdigris" if 0.3 < h < 0.6 else "copper"
        groups.setdefault(key, []).append((x, y))
    for key, pts in groups.items():
        ls = [lum(px[p]) for p in pts]
        lo, hi = min(ls), max(ls)
        for p, l in zip(pts, ls):
            t = (l - lo) / (hi - lo) if hi > lo else 0.5
            # Curva hacia los tonos claros: más pastel que el original
            t = t ** 0.7 if mineral != "coal" else t
            px[p] = (*ramp(PALETTES[key], t), 255)
    return im, set(cells_m)


def pick_sparkles(im, mask, name):
    """Elige píxeles brillantes del mineral, separados entre sí."""
    rnd = random.Random(name)
    px = im.load()

    def neighbors(p):
        return sum((p[0] + dx, p[1] + dy) in mask for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    cand = [p for p in mask if 2 <= p[0] <= 13 and 2 <= p[1] <= 13]
    cand.sort(key=lambda p: (neighbors(p) * 30 + lum(px[p]) + rnd.random() * 40), reverse=True)
    chosen = []
    for p in cand:
        if all(abs(p[0] - q[0]) + abs(p[1] - q[1]) >= 7 for q in chosen):
            chosen.append(p)
        if len(chosen) == SPARKLES:
            break
    return chosen


def sparkle_shape(step):
    """Píxeles de un destello según su momento: (dx, dy, intensidad 0-2)."""
    small = [(0, 0, 2), (1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1)]
    big = [(0, 0, 2), (1, 0, 2), (-1, 0, 2), (0, 1, 2), (0, -1, 2),
           (2, 0, 1), (-2, 0, 1), (0, 2, 1), (0, -2, 1)]
    return {0: [(0, 0, 1)], 1: small, 2: big, 3: big, 4: big, 5: small, 6: [(0, 0, 1)]}.get(step, [])


def animate(im, mask, mineral, name):
    """Tira vertical de cuadros con los destellos encendiéndose por turnos."""
    pal = PALETTES[mineral]
    glow = {1: pal[4], 2: (255, 255, 255) if mineral != "coal" else (214, 206, 240)}
    spots = pick_sparkles(im, mask, name)
    offset = random.Random(name + "fase").randrange(FRAMES)
    strip = Image.new("RGBA", (16, 16 * FRAMES))
    lit = []
    for f in range(FRAMES):
        frame = im.copy()
        px = frame.load()
        on = set()
        for k, (sx, sy) in enumerate(spots):
            step = (f + offset - k * (FRAMES // SPARKLES)) % FRAMES
            for dx, dy, level in sparkle_shape(step):
                x, y = sx + dx, sy + dy
                if 0 <= x < 16 and 0 <= y < 16:
                    px[x, y] = (*glow[level], 255)
                    on.add((x, y))
        strip.paste(frame, (0, 16 * f))
        lit.append(on)
    return strip, lit


def emissive(strip, mask, lit):
    """Capa _e para OptiFine/Continuity: solo el mineral y los destellos brillan."""
    e = Image.new("RGBA", strip.size)
    src, dst = strip.load(), e.load()
    for f in range(FRAMES):
        for x, y in mask | lit[f]:
            dst[x, y + 16 * f] = src[x, y + 16 * f]
    return e


def png(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def textures(mc):
    """Todas las texturas animadas de una versión del juego."""
    jar = zipfile.ZipFile(LOOM / mc / "minecraft-client.jar")
    read = lambda n: Image.open(io.BytesIO(jar.read(f"{BLOCK}{n}.png"))).convert("RGBA")
    out = {}
    for name, (mineral, base) in ORES.items():
        im, mask = recolor(read(name), mineral, read(base) if base else None)
        strip, lit = animate(im, mask, mineral, name)
        out[name] = (strip, emissive(strip, mask, lit))
    return out


def pack_icon(tex):
    """El diamante con un destello grande sobre fondo pastel."""
    strip, _ = tex["diamond_ore"]
    bg = Image.new("RGBA", (20, 20))
    px = bg.load()
    for y in range(20):
        for x in range(20):
            if min(x, 19 - x) + min(y, 19 - y) >= 2:
                t = y / 19
                px[x, y] = (round(196 + 58 * t), round(226 - 20 * t), 255 - round(10 * t), 255)
    bg.alpha_composite(strip.crop((0, 0, 16, 16)), (2, 2))
    big = bg.resize((120, 120), Image.NEAREST)
    canvas = Image.new("RGBA", (128, 128))
    canvas.alpha_composite(big, (4, 4))
    star = Image.new("RGBA", (9, 9))
    sp = star.load()
    for i in range(9):
        sp[4, i] = sp[i, 4] = (255, 246, 190, 255)
    for i in range(3, 6):
        sp[4, i] = sp[i, 4] = (255, 255, 255, 255)
    canvas.alpha_composite(star.resize((36, 36), Image.NEAREST), (84, 6))
    canvas.alpha_composite(star.resize((18, 18), Image.NEAREST), (10, 98))
    return canvas


def build(mc):
    tex = textures(mc)
    meta = json.dumps({"animation": {"frametime": FRAMETIME}})
    mcmeta = {"pack": {"description": "§bSparkly Ores §e✦\n§7por ccrccne", **VERSIONS[mc]}}
    DIST.mkdir(exist_ok=True)
    out = DIST / f"sparkly-ores-{VERSION}+{mc}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pack.mcmeta", json.dumps(mcmeta, ensure_ascii=False, indent=4))
        z.write(ROOT / "LICENSE", "LICENSE.txt")
        z.writestr("pack.png", png(pack_icon(tex)))
        z.writestr("assets/minecraft/optifine/emissive.properties", "suffix.emissive=_e\n")
        for name, (strip, glow) in tex.items():
            z.writestr(f"{BLOCK}{name}.png", png(strip))
            z.writestr(f"{BLOCK}{name}.png.mcmeta", meta)
            z.writestr(f"{BLOCK}{name}_e.png", png(glow))
            z.writestr(f"{BLOCK}{name}_e.png.mcmeta", meta)
    return out, tex


if __name__ == "__main__":
    for mc in VERSIONS:
        out, tex = build(mc)
        print(out.name, len(tex), "texturas")
