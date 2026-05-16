"""
Chiffrement de secrets via l'API Windows DPAPI (CryptProtectData).

Un jeton produit par protect() ne peut etre dechiffre par unprotect() que
sur la meme session Windows (meme compte utilisateur, meme machine).
Aucune dependance externe : uniquement ctypes.
"""

import base64
import ctypes
from ctypes import wintypes


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_crypt32.CryptProtectData.restype = wintypes.BOOL
_crypt32.CryptUnprotectData.restype = wintypes.BOOL

_CRYPTPROTECT_UI_FORBIDDEN = 0x01  # jamais d'invite : adapte a une appli de fond


def _run(func, data: bytes) -> bytes:
    # buf reste reference le temps de l'appel -> pointeur valide
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DataBlob()
    ok = func(ctypes.byref(blob_in), None, None, None, None,
              _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        _kernel32.LocalFree(blob_out.pbData)


def protect(text: str) -> str:
    """Chiffre une chaine. Renvoie un jeton base64 stockable dans un fichier."""
    encrypted = _run(_crypt32.CryptProtectData, text.encode("utf-8"))
    return base64.b64encode(encrypted).decode("ascii")


def unprotect(token: str) -> str:
    """Dechiffre un jeton produit par protect() sur la meme session Windows."""
    decrypted = _run(_crypt32.CryptUnprotectData, base64.b64decode(token))
    return decrypted.decode("utf-8")
