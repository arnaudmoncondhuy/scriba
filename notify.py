"""
Notifications Windows (toast) sans dependance externe.
Le toast est genere via l'API WinRT, declenchee par un court script PowerShell.
"""

import base64
import subprocess
import threading

_CREATE_NO_WINDOW = 0x08000000
# AUMID de PowerShell : notifieur deja enregistre par Windows, donc le toast
# s'affiche sans avoir a enregistrer notre propre application.
_AUMID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_SCRIPT = """$ErrorActionPreference='SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null
[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom,ContentType=WindowsRuntime]|Out-Null
$x=New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml(@"
<toast><visual><binding template="ToastGeneric"><text>__TITLE__</text><text>__MSG__</text></binding></visual></toast>
"@)
$t=[Windows.UI.Notifications.ToastNotification]::new($x)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("__AUMID__").Show($t)
"""


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def _show(title: str, message: str) -> None:
    script = (_SCRIPT.replace("__TITLE__", _xml_escape(title))
                     .replace("__MSG__", _xml_escape(message))
                     .replace("__AUMID__", _AUMID))
    # -EncodedCommand : evite tout probleme de guillemets / accents
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-EncodedCommand", encoded],
            creationflags=_CREATE_NO_WINDOW, capture_output=True, timeout=20,
        )
    except Exception:
        pass


def notify(title: str, message: str) -> None:
    """Affiche une notification Windows, sans bloquer l'appelant."""
    threading.Thread(target=_show, args=(title, message), daemon=True).start()
