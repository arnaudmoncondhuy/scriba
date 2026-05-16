# Construit l'executable (application graphique) avec PyInstaller.
# Lancer depuis PowerShell :  .\build_exe.ps1

pip install pyinstaller

# Nom de l'application : source unique = version.py
$name = (python -c "import version; print(version.APP_NAME)").Trim()

# Genere les metadonnees et l'icone de l'exe
python make_version_info.py
python make_icon.py

pyinstaller --onefile --windowed --name $name `
    --collect-all google.genai --collect-submodules pystray `
    --version-file version_info.txt --icon icon.ico `
    --add-data "icon.ico;." --noconfirm `
    scriba_gui.py

Write-Host ""
Write-Host "Termine. L'executable est dans .\dist\$name.exe" -ForegroundColor Green
Write-Host "La cle API se saisit dans l'interface (aucun .env requis)." -ForegroundColor Cyan
