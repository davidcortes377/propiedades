"""Arma el Reel vertical de Casa Peña (1080x1920, 30 fps) a partir de las fotos.

Uso:  python3 casa-pena/video/armar_video.py
Requiere Pillow y ffmpeg. Los textos son las capas PNG de video/capas/
(se generan desde video/textos.html).
"""
import subprocess
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent
FOTOS = BASE.parent / "fotos"
CAPAS = BASE / "capas"
SALIDA = BASE / "casa-pena-reel.mp4"
W, H, FPS, FUNDIDO = 1080, 1920, 30, 0.5

# (foto o capa final, segundos, movimiento inicio -> fin, texto)
# movimiento: (cx, cy, zoom) con el centro en coordenadas 0-1 y zoom 1 = encuadre 9:16 completo
CLIPS = [
    ("vista-calle",          3.6, ((.5, .5, 1.15), (.5, .5, 1.0)),   "intro"),
    ("dormitorio",           3.0, ((.5, .5, 1.0), (.45, .52, 1.12)), "huespedes"),
    ("pasillo",              2.4, ((.5, .5, 1.0), (.5, .55, 1.2)),   None),
    ("living",               3.0, ((.2, .5, 1.05), (.6, .5, 1.05)),  "living"),
    ("cocina-comedor",       3.0, ((.8, .5, 1.05), (.45, .5, 1.05)), "cocina"),
    ("cafetera",             2.4, ((.55, .5, 1.0), (.55, .45, 1.12)), "cafe"),
    ("bano",                 2.2, ((.55, .5, 1.05), (.75, .5, 1.05)), None),
    ("dormitorio-atardecer", 3.0, ((.45, .5, 1.0), (.47, .45, 1.1)), "atardecer"),
    ("sofa-espejos",         2.4, ((.4, .55, 1.05), (.62, .55, 1.05)), None),
    ("vista-calle",          3.0, ((.45, .78, 1.4), (.5, .35, 1.4)), "ubicacion"),
    ("@fin",                 3.8, ((.5, .5, 1.0), (.5, .5, 1.04)),   None),
]


def cargar(nombre):
    if nombre.startswith("@"):
        return Image.open(CAPAS / f"{nombre[1:]}.png").convert("RGB")
    return Image.open(FOTOS / f"{nombre}.jpg").convert("RGB")


def encuadre(img, cx, cy, z):
    sw, sh = img.size
    if sw / sh > W / H:
        bh = sh / z; bw = bh * W / H
    else:
        bw = sw / z; bh = bw * H / W
    x = min(max(cx * sw - bw / 2, 0), sw - bw)
    y = min(max(cy * sh - bh / 2, 0), sh - bh)
    return (x, y, x + bw, y + bh)


def cuadro(clip, img, t):
    _, dur, (a, b), _ = clip
    p = t / dur
    cx, cy, z = (a[i] + (b[i] - a[i]) * p for i in range(3))
    return img.resize((W, H), Image.BICUBIC, box=encuadre(img, cx, cy, z))


def alfa_texto(t, dur):
    entrada = (t - 0.35) / 0.45          # aparece 0,35 s después de empezar la foto
    salida = (dur - FUNDIDO - t) / 0.35   # se va justo antes del fundido
    return max(0.0, min(1.0, entrada, salida))


def con_texto(frame, capa, alfa):
    if capa is None or alfa <= 0:
        return frame
    c = capa
    if alfa < 1:
        c = capa.copy()
        c.putalpha(c.getchannel("A").point(lambda v: int(v * alfa)))
    base = frame.convert("RGBA")
    base.alpha_composite(c)
    return base.convert("RGB")


def main():
    imgs = [cargar(c[0]) for c in CLIPS]
    capas = [Image.open(CAPAS / f"{c[3]}.png").convert("RGBA") if c[3] else None for c in CLIPS]
    inicios, t = [], 0.0
    for c in CLIPS:
        inicios.append(t)
        t += c[1] - FUNDIDO
    total = t + FUNDIDO
    n = int(total * FPS)

    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-shortest", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(SALIDA),
    ], stdin=subprocess.PIPE)

    for f in range(n):
        ts = f / FPS
        activos = [i for i, c in enumerate(CLIPS) if inicios[i] <= ts < inicios[i] + c[1]]
        capas_frame = []
        for i in activos:
            lt = ts - inicios[i]
            fr = con_texto(cuadro(CLIPS[i], imgs[i], lt), capas[i], alfa_texto(lt, CLIPS[i][1]))
            capas_frame.append((i, lt, fr))
        frame = capas_frame[0][2]
        if len(capas_frame) > 1:
            _, lt2, fr2 = capas_frame[1]
            frame = Image.blend(frame, fr2, min(1.0, lt2 / FUNDIDO))
        ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    ff.wait()
    print(f"{SALIDA.name}: {total:.1f} s, {n} cuadros")


if __name__ == "__main__":
    main()
