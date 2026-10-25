"""Vistas previas: comparación antes/después y un GIF con los destellos."""
from PIL import Image, ImageDraw, ImageFont

import build

OUT = build.ROOT / "images"
FONT = "C:/Windows/Fonts/segoeuib.ttf"
INK = (64, 60, 96)
MAIN = ["coal_ore", "iron_ore", "copper_ore", "gold_ore", "redstone_ore", "lapis_ore", "diamond_ore", "emerald_ore"]


def background(w, h):
    bg = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(bg)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=(round(220 + 30 * t), round(236 - 8 * t), 255))
    return bg


def compare(tex, vanilla):
    """Arriba el original, abajo Sparkly Ores (cuadro con destello)."""
    S, gap = 96, 24
    rows = [MAIN, [f"deepslate_{n}" for n in MAIN]]
    w = gap + len(MAIN) * (S + gap)
    h = 100 + len(rows) * (2 * S + 98)
    bg = background(w, h)
    d = ImageDraw.Draw(bg)
    d.text((w // 2, 60), "Sparkly Ores", font=ImageFont.truetype(FONT, 52), fill=INK, anchor="mm")
    small = ImageFont.truetype(FONT, 18)
    y = 120
    for row in rows:
        for i, n in enumerate(row):
            x = gap + i * (S + gap)
            bg.paste(vanilla[n].resize((S, S), Image.NEAREST), (x, y))
            strip, _ = tex[n]
            frame = max(range(build.FRAMES), key=lambda f: sum(
                strip.getpixel((px, py + 16 * f))[:3] == (255, 255, 255) for px in range(16) for py in range(16)))
            bg.paste(strip.crop((0, 16 * frame, 16, 16 * frame + 16)).resize((S, S), Image.NEAREST), (x, y + S + 8))
        y += 2 * S + 30
        d.text((w // 2, y), "↑ vanilla   ·   Sparkly Ores ↓" if row is rows[0] else "", font=small, fill=(130, 126, 160), anchor="mm")
        y += 60
    return bg


def wall(tex, vanilla):
    """Una pared de cueva con minerales, animada."""
    layout = [
        "s.s.d.s.",
        "g.sCs.ls",
        "sEs.sIsR",
        "s.Ds.s.s",
    ]
    key = {"d": "diamond_ore", "g": "gold_ore", "C": "copper_ore", "l": "lapis_ore", "E": "emerald_ore",
           "I": "iron_ore", "R": "redstone_ore", "D": "diamond_ore"}
    S = 64
    frames = []
    for f in range(build.FRAMES):
        im = Image.new("RGB", (len(layout[0]) * S, len(layout) * S))
        for y, row in enumerate(layout):
            for x, ch in enumerate(row):
                if ch in key:
                    tile = tex[key[ch]][0].crop((0, 16 * f, 16, 16 * f + 16))
                else:
                    tile = vanilla["stone"]
                im.paste(tile.resize((S, S), Image.NEAREST), (x * S, y * S))
        frames.append(im)
    return frames


if __name__ == "__main__":
    _, tex = build.build("26.3")
    jar = build.zipfile.ZipFile(build.LOOM / "26.3" / "minecraft-client.jar")
    read = lambda n: Image.open(build.io.BytesIO(jar.read(f"{build.BLOCK}{n}.png"))).convert("RGBA")
    vanilla = {n: read(n) for n in list(build.ORES) + ["stone"]}
    OUT.mkdir(exist_ok=True)
    compare(tex, vanilla).save(OUT / "comparacion.png")
    frames = wall(tex, vanilla)
    frames[0].save(OUT / "brillos.gif", save_all=True, append_images=frames[1:],
                   duration=build.FRAMETIME * 50, loop=0)
    build.pack_icon(tex).save(OUT / "icono.png")
    print("ok")
