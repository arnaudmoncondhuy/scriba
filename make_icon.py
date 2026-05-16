"""Genere icon.ico (l'icone de l'application) a partir de primitives Pillow.

Lance automatiquement par build_exe.ps1 avant PyInstaller. Permet de versionner
le dessin de l'icone (ce fichier) plutot qu'un binaire .ico.
"""

import math

from PIL import Image, ImageDraw

SIZE = 256
_BG = (47, 79, 224, 255)      # bleu Scriba (carre de fond)
_PAGE = (255, 255, 255, 255)  # la page
_LINE = (171, 178, 201, 255)  # gris des lignes de texte
_ACCENT = (47, 79, 224, 255)  # bleu : la ligne "renommee" par Scriba
_SPARK = (255, 193, 64, 255)  # etincelle doree (touche IA)


def _sparkle(draw, cx, cy, outer, inner):
    """Dessine une etincelle a 4 branches."""
    pts = []
    for i in range(8):
        ang = math.pi / 2 + i * math.pi / 4
        r = outer if i % 2 == 0 else inner
        pts.append((cx + r * math.cos(ang), cy - r * math.sin(ang)))
    draw.polygon(pts, fill=_SPARK)


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Carre arrondi de fond
    d.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=52, fill=_BG)
    # Page blanche
    d.rounded_rectangle((62, 46, 194, 210), radius=16, fill=_PAGE)
    # Lignes de texte
    for y in (96, 124, 152):
        d.rounded_rectangle((86, y, 170, y + 11), radius=5, fill=_LINE)
    # Ligne accentuee = le nom attribue par Scriba
    d.rounded_rectangle((86, 180, 150, 191), radius=5, fill=_ACCENT)
    # Etincelle (touche "IA")
    _sparkle(d, 166, 76, 19, 7)
    return img


if __name__ == "__main__":
    build().save("icon.ico",
                 sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                        (64, 64), (128, 128), (256, 256)])
    print("icon.ico genere.")
