# 🔏 Signature de Scriba

Scriba est un `.exe` PyInstaller. Sans signature de code, Windows affiche
**SmartScreen** (« Windows a protégé votre PC »), **Smart App Control** peut le
bloquer, et certains antivirus le suppriment (faux positif). Ce document
explique les options, de la gratuite à la payante.

> Côté build, on a déjà désactivé **UPX** (`build_exe.ps1`), première cause de
> faux positifs antivirus sur les exes PyInstaller.

---

## ⚡ Mode d'emploi rapide (mémo)

### 🔁 Sortir une nouvelle version sur MON PC

```powershell
.\build_exe.ps1
```

C'est tout. Le build re-signe **automatiquement** l'exe avec le certificat local
(s'il existe). Résultat : `dist\Scriba.exe`, signé et approuvé sur ce PC.

### 🆕 Nouveau PC, ou « le certificat n'existe plus »

À faire **une seule fois** par machine, en administrateur :

```powershell
.\build_exe.ps1     # produit dist\Scriba.exe
.\sign_local.ps1    # cree le certificat, l'installe, signe -> cliquer "Oui" sur l'UAC
```

Ensuite, on retombe dans le cas du dessus : `.\build_exe.ps1` suffit.

### ✅ Vérifier que l'exe est bien signé

```powershell
Get-AuthenticodeSignature .\dist\Scriba.exe | Format-List Status, SignerCertificate
```

`Status` doit valoir **Valid**.

### 🌍 Pour mes utilisateurs (autres PC)

Le certificat local ne vaut que sur tes machines. Pour distribuer signé, voir
les options plus bas (SignPath Foundation gratuit, ou Azure Trusted Signing).

### 🧯 Si ça coince

| Symptôme | Cause probable | Solution |
|---|---|---|
| `Status` = `NotSigned` après un build | Pas de certificat local | Lancer `.\sign_local.ps1` |
| `Status` = `UnknownError` / `NotTrusted` | Certificat absent des magasins de confiance | Relancer `.\sign_local.ps1` (réinstalle dans Root + TrustedPublisher) |
| L'UAC n'apparaît pas | PowerShell déjà en admin, ou politique bloquée | Lancer dans un PowerShell **admin** : `powershell -ExecutionPolicy Bypass -File .\sign_local.ps1` |
| SmartScreen revient malgré la signature | Tu testes sur **un autre PC** | Normal : le certificat n'est de confiance que sur tes machines |

---

## 🧭 Quelle option choisir ?

| Option | Coût | Supprime SmartScreen | Smart App Control | Pour qui |
|---|---|---|---|---|
| **Confiance locale** (`sign_local.ps1`) | 0 € | ✅ mais **sur votre PC seulement** | ✅ local | Vous, vos machines |
| **SignPath Foundation** (OV) | 0 € | ⏳ progressif (réputation) | ✅ | Distribution OSS |
| **Azure Trusted Signing** | ~10 $/mois | ✅ quasi immédiat | ✅ | Distribution large |
| **Certum Open Source** (OV) | ~80-100 €/an | ⏳ progressif | ✅ | Alternative SignPath |

- **OV** (Organization/Individual Validation) : la réputation SmartScreen se
  construit avec les téléchargements et **se cumule entre versions** (elle est
  rattachée au certificat). L'écran bleu disparaît une fois le seuil atteint.
- **Trusted Signing** : chaîne vers une racine de confiance Microsoft →
  réputation quasi immédiate.

---

## 🆓 Option 1 — Confiance locale (votre PC)

Pour ne plus jamais être bloqué **sur vos propres machines**, sans rien payer :

```powershell
# Une seule fois, en administrateur :
.\sign_local.ps1
```

Le script crée un certificat auto-signé, l'installe dans vos magasins de
confiance et signe `dist\Scriba.exe`. Ensuite, `build_exe.ps1` re-signe
automatiquement chaque build. Ce certificat **ne vaut que sur les machines où
il est installé** — il ne règle rien pour vos utilisateurs.

---

## 🆓 Option 2 — SignPath Foundation (distribution, gratuit)

[SignPath Foundation](https://signpath.org/) offre la signature de code
**gratuite aux projets open-source**. C'est la voie recommandée pour distribuer
Scriba signé sans frais.

### Checklist de candidature

- [ ] Dépôt **public** sur GitHub — ✅ `arnaudmoncondhuy/scriba`
- [ ] Licence **OSI** (MIT) — ✅ `LICENSE`
- [ ] Projet un minimum **établi** (historique de commits, activité, quelques
      étoiles/téléchargements) — *critère filtrant : un projet tout neuf peut
      être refusé ; reposter plus tard si besoin.*
- [ ] `README` clair décrivant l'application — ✅
- [ ] Build **reproductible** depuis les sources — ✅ `build_exe.ps1`
- [ ] Demande envoyée via le formulaire SignPath Foundation
- [ ] Une fois approuvé : récupérer `ORGANIZATION_ID`, `PROJECT_SLUG`,
      `SIGNING_POLICY_SLUG` et un **API token**, les mettre dans les
      *Secrets* GitHub du dépôt :
      `SIGNPATH_API_TOKEN`, `SIGNPATH_ORG_ID`.

### Workflow GitHub Actions

Un workflow prêt à l'emploi est fourni :
[`.github/workflows/release-sign.yml`](.github/workflows/release-sign.yml).
Il se déclenche sur un tag `v*`, construit l'exe, l'envoie à SignPath pour
signature, puis attache l'exe signé à la *release* GitHub. Renseignez d'abord
les secrets et les slugs (placeholders `<...>` dans le fichier).

---

## 💵 Option 3 — Azure Trusted Signing (le plus efficace, ~10 $/mois)

Service de signature cloud de Microsoft. Réputation SmartScreen quasi
immédiate, Smart App Control satisfait tout de suite. Désormais ouvert aux
**particuliers** (avec vérification d'identité).

1. Créer une ressource **Trusted Signing** dans le portail Azure.
2. Vérifier l'identité (Individual Validation).
3. Créer un *Certificate Profile*.
4. Signer avec l'extension `Azure.CodeSigning` de `signtool`, ou l'action
   GitHub `azure/trusted-signing-action`.

C'est l'option à privilégier si vous sortez du « zéro coût » : c'est ce qui
débloque réellement et rapidement **tous** vos utilisateurs.

---

## 📣 En attendant la signature — note pour vos utilisateurs

Voir le README, section « Premier lancement » : marche à suivre pour passer
l'écran SmartScreen (`Informations complémentaires` → `Exécuter quand même`).
