# Scriba

Surveille un dossier de numérisation et renomme automatiquement chaque scan
(PDF ou image) grâce à un LLM (Google Gemini / AI Studio).

Le nom et le numéro de version sont définis une seule fois, dans `version.py`
(`APP_NAME`, `__version__`).

## Comment ça marche

1. L'application surveille un dossier.
2. Dès qu'un scan y apparaît, elle attend la fin de l'écriture du fichier.
3. Elle envoie le document à Gemini, qui propose un nom descriptif.
4. Le fichier est renommé sur place (ex. `2026-05-12_facture_edf.pdf`).

Formats pris en charge : `.pdf`, `.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`.

> **Confidentialité (RGPD)** : chaque document est transmis aux serveurs
> Google (Gemini) pour analyse. À n'utiliser qu'avec des documents dont le
> traitement par un service tiers est autorisé.

## Application graphique

L'exécutable `dist\Scriba.exe` ouvre une interface où l'on règle tout :

- **Clé API Gemini** : saisie dans l'interface, **chiffrée via Windows DPAPI**
  (déchiffrable uniquement par ta session Windows). Boutons « Obtenir une
  clé ? » (tutoriel intégré) et « Tester ».
- **Modèle** : liste chargée en direct depuis l'API Gemini, restreinte aux
  modèles `flash` / `flash-lite` (rapides et économiques). `gemini-3.1-flash-lite`
  par défaut.
- **Dossier surveillé** : par défaut `Images\Numérisations` de l'utilisateur,
  modifiable via « Parcourir... ».
- **Démarrage automatique** de la surveillance à l'ouverture si la clé et le
  dossier sont prêts.
- **Journal** masqué par défaut, affiché via un bouton ; tokens entrée/sortie.
- **Notification Windows** à chaque renommage.
- **Lancer au démarrage de Windows** (registre `Run`, par utilisateur).
- **Icône dans la zone de notification** : verte = surveillance active,
  grise = arrêtée. Fermer la fenêtre replie l'app dans cette icône ;
  clic droit → « Quitter ».

### Mémorisation et mises à jour

La configuration (clé chiffrée, dossier, options) est stockée dans
`%APPDATA%\Scriba\config.json`, **en dehors de l'exécutable**. Remplacer
`Scriba.exe` par une nouvelle version ne touche donc pas aux réglages.

## Construire l'exécutable

```powershell
pip install -r requirements.txt
.\build_exe.ps1
```

Le script lit le nom dans `version.py`, génère les métadonnées de l'exe
(`version_info.txt`) puis produit `dist\Scriba.exe` — autonome, aucune
installation de Python requise sur la machine cible.

## Version console (debug / lancement automatisé)

`scriba.py` fonctionne sans interface et lit sa configuration dans `.env`
(voir `.env.example`).

## Fichiers du projet

| Fichier | Rôle |
|---|---|
| `version.py` | Nom (`APP_NAME`) et version (`__version__`) — source unique |
| `scriba_gui.py` | Interface graphique (point d'entrée de l'exe) |
| `scan_engine.py` | Moteur : surveillance, appel Gemini, renommage |
| `secret.py` | Chiffrement de la clé API (Windows DPAPI) |
| `notify.py` | Notifications Windows (toast) |
| `tray.py` | Icône de zone de notification (pystray) |
| `make_version_info.py` | Génère les métadonnées de l'exe pour le build |
| `scriba.py` | Version console (lit `.env`) |

## Auteur

Arnaud Moncond'huy

## Limites connues

- Pas de TIFF (non géré nativement par Gemini).
- Renommage à plat, pas de classement en sous-dossiers.
- Notification et icône s'affichent sans identité d'app enregistrée auprès
  de Windows.

Voir `ROADMAP.md` pour les évolutions prévues.
