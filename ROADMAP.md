# Roadmap

Suivi des évolutions de Scriba. Version courante : voir `version.py`.

## v0.5 — actuel

- [x] Surveillance d'un dossier, renommage automatique des scans (PDF + images) via Gemini
- [x] Interface graphique : clé API, dossier, modèle, options
- [x] Clé API chiffrée (Windows DPAPI), configuration mémorisée dans `%APPDATA%`
- [x] Liste des modèles chargée en direct depuis l'API, restreinte aux `flash` / `flash-lite`
- [x] Démarrage automatique de la surveillance à l'ouverture
- [x] Lancement au démarrage de Windows
- [x] Notification Windows à chaque renommage
- [x] Icône dans la zone de notification (reflète l'état de la surveillance)
- [x] Journal repliable, tokens entrée/sortie affichés
- [x] Tutoriel intégré pour obtenir une clé API
- [x] Mention RGPD
- [x] Nom de l'application : Scriba (source unique dans `version.py`)
- [x] Métadonnées de l'exécutable (version, éditeur, description, copyright)

## À venir — court terme

- [ ] **Multilingue** — interface en plusieurs langues (FR / EN au minimum),
      avec détection automatique de la langue de Windows
- [ ] Estimation du coût par scan dans le journal (table de prix par modèle)
- [ ] Détection de doublons par contenu (hash), en complément du suffixe `_2`, `_3`
- [ ] Choix d'une licence et d'un mode de distribution

## Idées — plus tard

- [ ] Classement automatique en sous-dossiers (par type de document)
- [ ] Convention de nommage configurable (format de date, ordre des champs)
- [ ] Support TIFF (conversion automatique avant analyse)
- [ ] Choix d'autres moteurs IA (OpenAI, modèle local) en plus de Gemini
- [ ] Historique des renommages + annulation (undo)
- [ ] Mode validation : proposer le nom et demander confirmation avant renommage
- [ ] Option Vertex AI (facturation Google Cloud, données en UE)
- [ ] Signature numérique de l'exécutable
- [ ] Enregistrement de l'app auprès de Windows (notifications/icône à sa propre identité)
