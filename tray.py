"""
Icone de zone de notification Windows (system tray).

Repose sur pystray (+ Pillow). Si ces librairies sont absentes, l'application
continue de fonctionner : available() renvoie alors False et l'icone est
simplement desactivee.
"""

from version import APP_NAME

try:
    import pystray
    from PIL import Image, ImageDraw
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

_GREEN = (40, 170, 90, 255)
_GREY = (150, 150, 150, 255)


def available() -> bool:
    return _AVAILABLE


def _icon_image(color):
    """Petite icone : une 'page' claire avec une pastille de couleur d'etat."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((8, 6, 56, 58), radius=10, fill=(245, 245, 245, 255))
    draw.ellipse((22, 24, 42, 44), fill=color)
    return img


class TrayIcon:
    """Icone de notification refletant l'etat de la surveillance.

    on_show / on_quit sont appeles depuis le thread de pystray : l'appelant
    doit y rebasculer vers son thread d'interface (root.after).
    """

    def __init__(self, on_show, on_quit):
        self._icon = None
        if not _AVAILABLE:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Afficher la fenetre",
                             lambda icon, item: on_show(), default=True),
            pystray.MenuItem(f"Quitter {APP_NAME}",
                             lambda icon, item: on_quit()),
        )
        self._icon = pystray.Icon(APP_NAME, _icon_image(_GREY),
                                  f"{APP_NAME} - arrete", menu)

    def start(self) -> None:
        if self._icon is not None:
            self._icon.run_detached()

    def set_running(self, running: bool) -> None:
        if self._icon is None:
            return
        self._icon.icon = _icon_image(_GREEN if running else _GREY)
        self._icon.title = (f"{APP_NAME} - surveillance active" if running
                            else f"{APP_NAME} - arrete")

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
