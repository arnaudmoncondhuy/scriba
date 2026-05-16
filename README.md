<!-- Astuce : ajoutez une capture d'ecran de l'app en docs/capture.png
     puis decommentez la ligne ci-dessous.
<p align="center"><img src="docs/capture.png" width="520" alt="Scriba"></p>
-->

# 📄 Scriba

> **Vos numérisations, nommées intelligemment — automatiquement.**

![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D6?logo=windows&logoColor=white)
![Exe autonome](https://img.shields.io/badge/exe-autonome-2ECC71)
![Google Gemini](https://img.shields.io/badge/IA-Google%20Gemini-4285F4?logo=googlegemini&logoColor=white)

Vous scannez un document. Il atterrit dans votre dossier sous un nom du genre
`scan_20260512_0042.pdf`. Multipliez par cent. Bon courage pour retrouver votre
facture d'électricité de mars.

**Scriba règle ça.** Il surveille votre dossier de numérisation et **renomme
chaque scan tout seul**, en *lisant réellement* le contenu du document grâce à
l'IA. Vous scannez — Scriba nomme et range.

## 🪄 Avant / après

```
scan_20260512_0042.pdf       →   2026-05-12_facture-edf-mars.pdf
IMG_3391.jpg                 →   2026-04-02_attestation-assurance-maaf.jpg
Numérisation_001.pdf         →   2026-03-18_releve-compte-credit-agricole.pdf
doc20260510.pdf              →   2026-05-10_ordonnance-dr-martin.pdf
```

## ✨ Fonctionnalités

- 🤖 **Renommage intelligent** — Gemini identifie le type de document
  (facture, contrat, relevé, attestation…), l'émetteur et la date, et propose
  un nom clair, daté et prêt à classer.
- 👁️ **Surveillance en continu** — déposez un scan, il est renommé dans la
  foulée. Rien à lancer, rien à cliquer.
- 🔔 **Notifications Windows** — un toast discret à chaque fichier renommé.
- 🪟 **Discret** — vit dans la zone de notification, peut démarrer avec Windows
  et tourner en arrière-plan sans fenêtre.
- 🔐 **Clé API chiffrée** — stockée chiffrée via Windows DPAPI, liée à votre
  session, jamais en clair.
- 🎯 **Modèles toujours à jour** — la liste des modèles Gemini se rafraîchit
  seule depuis l'API.
- 💸 **Quasi gratuit** — avec un modèle *flash-lite*, environ **0,0001 $ par
  document** (≈ 7 centimes pour 1000 scans).
- 📦 **Zéro installation** — un seul `.exe` autonome, aucun Python requis sur
  la machine.

## 🚀 Prise en main (30 secondes)

1. Lancez **`Scriba.exe`**.
2. Cliquez **« Obtenir une clé ? »** — le mini-tuto intégré vous guide pour
   créer une clé Gemini **gratuite**, puis collez-la et cliquez **« Tester »**.
3. Choisissez le **dossier à surveiller** (par défaut `Images\Numérisations`).
4. **« Démarrer la surveillance »**.

➡️ Déposez un scan dans le dossier et regardez-le se renommer. ✨

## 🧠 Sous le capot

1. Scriba surveille le dossier et attend que le fichier soit complètement écrit.
2. Le document (PDF ou image) est envoyé à Gemini avec un prompt d'archivage.
3. Gemini renvoie un nom descriptif ; Scriba l'assainit et renomme le fichier.
4. Si le nom existe déjà, un suffixe `_2`, `_3`… est ajouté — **jamais
   d'écrasement**.

Formats pris en charge : `.pdf`, `.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`.

## 🔒 Confidentialité

> Chaque document est transmis aux serveurs **Google (Gemini)** pour analyse.
> À n'utiliser qu'avec des documents dont le traitement par un service tiers
> est autorisé.

La clé API, elle, ne quitte jamais votre machine : elle est chiffrée (DPAPI)
et stockée dans `%APPDATA%\Scriba\config.json`. Vos réglages survivent aux
mises à jour de l'exécutable.

## 🧰 Construire depuis les sources

```powershell
pip install -r requirements.txt
.\build_exe.ps1
```

Le script lit le nom dans `version.py`, génère l'icône et les métadonnées de
l'exe, puis produit `dist\Scriba.exe` — autonome.

Une **version console** (`scriba.py`) existe aussi pour le débogage et les
lancements automatisés ; elle lit sa configuration dans `.env`
(voir `.env.example`).

## 🗂️ Architecture du projet

| Fichier | Rôle |
|---|---|
| `version.py` | Nom et version de l'app — **source unique** |
| `scriba_gui.py` | Interface graphique (point d'entrée de l'exe) |
| `scan_engine.py` | Moteur : surveillance, appel Gemini, renommage |
| `secret.py` | Chiffrement de la clé API (Windows DPAPI) |
| `notify.py` | Notifications Windows (toast) |
| `tray.py` | Icône de zone de notification |
| `make_icon.py` | Génère l'icône de l'application |
| `make_version_info.py` | Génère les métadonnées de l'exe |
| `scriba.py` | Version console |

## 🗺️ Roadmap

Multilingue, estimation de coût en direct, détection de doublons, classement
en sous-dossiers… → voir **[ROADMAP.md](ROADMAP.md)**.

## ⚠️ Limites connues

- Pas de TIFF (non géré nativement par Gemini).
- Renommage à plat, sans classement en sous-dossiers.
- Notification et icône s'affichent sans identité d'application enregistrée
  auprès de Windows.

## 👤 Auteur

Développé par **Arnaud Moncond'huy**.
