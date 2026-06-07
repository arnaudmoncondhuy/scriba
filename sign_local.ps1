# =====================================================================
#  sign_local.ps1  -  Confiance locale de Scriba (votre PC uniquement)
# ---------------------------------------------------------------------
#  A lancer UNE SEULE FOIS, en tant qu'administrateur.
#  Cree un certificat de signature de code auto-signe, l'installe dans
#  vos magasins de confiance (Racines de confiance + Editeurs approuves),
#  puis signe dist\Scriba.exe.
#
#  Resultat : sur CE PC, Windows considere Scriba comme un editeur connu.
#  Plus d'ecran bleu SmartScreen, plus de blocage Smart App Control, plus
#  de suppression antivirus pour cet exe.
#
#  NB : ce certificat ne vaut que sur les machines ou il est installe
#  (la votre). Pour distribuer a d'autres, il faut une vraie signature
#  (voir SIGNING.md).
#
#  Usage :  clic droit -> "Executer avec PowerShell" (admin)
#       ou  PowerShell admin :  .\sign_local.ps1
# =====================================================================

$ErrorActionPreference = "Stop"
$Subject = "CN=Scriba (Arnaud Moncond'huy)"
$ExePath = Join-Path $PSScriptRoot "dist\Scriba.exe"

# --- Auto-elevation en administrateur si necessaire -------------------
$admin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host "Elevation en administrateur..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList `
        "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    return
}

# --- 1. Reutiliser ou creer le certificat -----------------------------
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
    Where-Object { $_.Subject -eq $Subject } | Select-Object -First 1

if (-not $cert) {
    Write-Host "Creation du certificat auto-signe..." -ForegroundColor Cyan
    $cert = New-SelfSignedCertificate `
        -Subject $Subject `
        -Type CodeSigningCert `
        -KeyUsage DigitalSignature `
        -KeyAlgorithm RSA -KeyLength 3072 `
        -CertStoreLocation Cert:\CurrentUser\My `
        -NotAfter (Get-Date).AddYears(10)
} else {
    Write-Host "Certificat existant reutilise." -ForegroundColor Cyan
}

# --- 2. Installer le certificat public dans les magasins de confiance --
$pubCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 `
    (,$cert.RawData)
foreach ($store in @("Root", "TrustedPublisher")) {
    $s = New-Object System.Security.Cryptography.X509Certificates.X509Store `
        $store, "LocalMachine"
    $s.Open("ReadWrite")
    $s.Add($pubCert)
    $s.Close()
    Write-Host "Installe dans LocalMachine\$store." -ForegroundColor Green
}

# --- 3. Signer l'executable ------------------------------------------
if (-not (Test-Path $ExePath)) {
    Write-Host "dist\Scriba.exe introuvable. Lancez d'abord .\build_exe.ps1." `
        -ForegroundColor Red
    return
}
Set-AuthenticodeSignature -FilePath $ExePath -Certificate $cert `
    -TimestampServer "http://timestamp.digicert.com" | Out-Null

Write-Host ""
Write-Host "Termine. Scriba.exe est signe et approuve sur ce PC." `
    -ForegroundColor Green
Write-Host "Desormais build_exe.ps1 re-signera automatiquement chaque build." `
    -ForegroundColor Cyan
