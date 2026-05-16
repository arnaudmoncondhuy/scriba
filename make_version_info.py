"""Genere version_info.txt pour PyInstaller a partir de version.py.

Garde le numero de version et le nom de l'application a une source unique.
Lance automatiquement par build_exe.ps1 avant PyInstaller.
"""

from version import APP_NAME, __version__

AUTHOR = "Arnaud Moncond'huy"

_parts = (__version__.split(".") + ["0", "0", "0", "0"])[:4]
_vtuple = tuple(int(p) if p.isdigit() else 0 for p in _parts)
_vstr = ".".join(str(n) for n in _vtuple)

# repr() choisit automatiquement les bons guillemets (apostrophe dans l'auteur).
_content = f"""# Genere automatiquement par make_version_info.py - ne pas editer.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={_vtuple},
    prodvers={_vtuple},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040C04B0', [
        StringStruct('CompanyName', {AUTHOR!r}),
        StringStruct('FileDescription', {f"{APP_NAME} - renommage automatique de scans"!r}),
        StringStruct('FileVersion', {_vstr!r}),
        StringStruct('InternalName', {APP_NAME!r}),
        StringStruct('LegalCopyright', {f"(C) 2026 {AUTHOR}"!r}),
        StringStruct('OriginalFilename', {f"{APP_NAME}.exe"!r}),
        StringStruct('ProductName', {APP_NAME!r}),
        StringStruct('ProductVersion', {__version__!r}),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x040C, 1200])])
  ]
)
"""

if __name__ == "__main__":
    with open("version_info.txt", "w", encoding="utf-8") as f:
        f.write(_content)
    print(f"version_info.txt genere : {APP_NAME} v{_vstr} - {AUTHOR}")
