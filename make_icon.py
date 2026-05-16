"""Genere icon.ico (l'icone de l'application) a partir de primitives Pillow.

Le dessin est realise en haute resolution puis reduit (anti-aliasing par
sur-echantillonnage) : les bords restent nets a toutes les tailles.
Lance automatiquement par build_exe.ps1 avant PyInstaller.

Deux styles, selectionnes par STYLE :
- "full"   : page blanche posee sur un carre bleu plein (style d'origine) ;
- "border" : la MEME page (meme ratio, meme contenu) bordee de bleu, sans
             carre de fond.
"""

import math

from PIL import Image, ImageDraw

STYLE = "border"   # "border" ou "full"

_MASTER = 1024   # resolution de travail (sur-echantillonnee)
_BASE = 256      # coordonnees du dessin pensees pour 256 px
_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48),
          (64, 64), (128, 128), (256, 256)]

_BG = (47, 79, 224, 255)      # bleu Scriba
_PAGE = (255, 255, 255, 255)  # la page
_LINE = (171, 178, 201, 255)  # gris des lignes de texte
_ACCENT = (47, 79, 224, 255)  # bleu : la ligne "renommee" par Scriba
_SPARK = (255, 193, 64, 255)  # etincelle doree (touche IA)

# Disposition interne, exprimee en FRACTIONS de la page. Issue de la page de
# reference 132 x 164 px : elle reste donc identique quel que soit le style
# et quelle que soit la taille de la page.
_LINE_X0, _LINE_X1 = 24 / 132, 108 / 132
_LINE_YS = (50 / 164, 78 / 164, 106 / 164)
_LINE_H = 11 / 164
_ACCENT_X1 = 88 / 132
_ACCENT_Y = 134 / 164
_RADIUS = 5 / 132
_SPARK_CX, _SPARK_CY = 104 / 132, 30 / 164
_SPARK_OUTER, _SPARK_INNER = 19 / 132, 7 / 132


def _sparkle(draw, cx, cy, outer, inner):
    """Dessine une etincelle a 4 branches."""
    pts = []
    for i in range(8):
        ang = math.pi / 2 + i * math.pi / 4
        r = outer if i % 2 == 0 else inner
        pts.append((cx + r * math.cos(ang), cy - r * math.sin(ang)))
    draw.polygon(pts, fill=_SPARK)


def _canvas():
    """Image transparente + ImageDraw + facteur d'echelle + helper sc()."""
    k = _MASTER / _BASE
    img = Image.new("RGBA", (_MASTER, _MASTER), (0, 0, 0, 0))

    def sc(*v):
        return tuple(x * k for x in v)

    return img, ImageDraw.Draw(img), k, sc


def _draw_content(d, page):
    """Dessine lignes de texte + ligne accentuee + etincelle.

    'page' = (x0, y0, x1, y1) de la page blanche. Le contenu est place
    proportionnellement : il est identique quel que soit le style.
    """
    x0, y0, x1, y1 = page
    pw, ph = x1 - x0, y1 - y0
    rad = max(1, int(_RADIUS * pw))
    lh = _LINE_H * ph
    for fy in _LINE_YS:
        y = y0 + fy * ph
        d.rounded_rectangle((x0 + _LINE_X0 * pw, y, x0 + _LINE_X1 * pw, y + lh),
                            radius=rad, fill=_LINE)
    ay = y0 + _ACCENT_Y * ph
    d.rounded_rectangle((x0 + _LINE_X0 * pw, ay, x0 + _ACCENT_X1 * pw, ay + lh),
                        radius=rad, fill=_ACCENT)
    _sparkle(d, x0 + _SPARK_CX * pw, y0 + _SPARK_CY * ph,
             _SPARK_OUTER * pw, _SPARK_INNER * pw)


def _master_full() -> Image.Image:
    """Style d'origine : page blanche sur carre bleu plein."""
    img, d, k, sc = _canvas()
    d.rounded_rectangle(sc(8, 8, 248, 248), radius=int(52 * k), fill=_BG)
    page = sc(62, 46, 194, 210)
    d.rounded_rectangle(page, radius=int(16 * k), fill=_PAGE)
    _draw_content(d, page)
    return img


def _master_border() -> Image.Image:
    """Variante : meme page (meme ratio 132:164) bordee de bleu, sans fond."""
    img, d, k, sc = _canvas()
    # Bordure bleue (rectangle arrondi plein) puis page blanche concentrique
    # par-dessus : il reste un anneau bleu de 15 px de large.
    d.rounded_rectangle(sc(33, 13, 223, 243), radius=int(34 * k), fill=_BG)
    page = sc(48, 28, 208, 228)
    d.rounded_rectangle(page, radius=int(19 * k), fill=_PAGE)
    _draw_content(d, page)
    return img


def _master() -> Image.Image:
    return _master_border() if STYLE == "border" else _master_full()


def build() -> Image.Image:
    """Renvoie l'icone 256 px, bords lisses (reduction LANCZOS du master)."""
    return _master().resize((_BASE, _BASE), Image.LANCZOS)


if __name__ == "__main__":
    master = _master()
    frames = {s: master.resize(s, Image.LANCZOS) for s in _SIZES}
    frames[(256, 256)].save("icon.ico", sizes=_SIZES,
                            append_images=list(frames.values()))
    print(f"icon.ico genere (style '{STYLE}', anti-aliase).")
