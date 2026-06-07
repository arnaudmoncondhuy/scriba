# Construit l'executable (application graphique) avec PyInstaller.
# Lancer depuis PowerShell :  .\build_exe.ps1

pip install pyinstaller

# Nom de l'application : source unique = version.py
$name = (python -c "import version; print(version.APP_NAME)").Trim()

# Genere les metadonnees et l'icone de l'exe
python make_version_info.py
python make_icon.py

# --noupx : la compression UPX declenche de nombreux faux positifs antivirus
# sur les exes PyInstaller. On la desactive pour reduire les blocages.
pyinstaller --onefile --windowed --name $name `
    --collect-all google.genai --collect-submodules pystray `
    --version-file version_info.txt --icon icon.ico `
    --add-data "icon.ico;." --noupx --noconfirm `
    scriba_gui.py

# Signature locale (facultatif) : si un certificat auto-signe Scriba existe
# dans votre magasin, signe l'exe pour que VOTRE PC lui fasse confiance.
# Voir .\sign_local.ps1 (a lancer une fois pour creer le certificat).
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert -ErrorAction SilentlyContinue |
    Where-Object { $_.Subject -eq "CN=Scriba (Arnaud Moncond'huy)" } | Select-Object -First 1
if ($cert) {
    Set-AuthenticodeSignature -FilePath ".\dist\$name.exe" -Certificate $cert `
        -TimestampServer "http://timestamp.digicert.com" | Out-Null
    Write-Host "Exe signe avec le certificat local Scriba." -ForegroundColor Green
}

Write-Host ""
Write-Host "Termine. L'executable est dans .\dist\$name.exe" -ForegroundColor Green
Write-Host "La cle API se saisit dans l'interface (aucun .env requis)." -ForegroundColor Cyan
