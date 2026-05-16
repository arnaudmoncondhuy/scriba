"""
Moteur : surveille un dossier et renomme les scans (PDF / images) en
interrogeant Google Gemini. Sans dependance a une interface : utilisable
aussi bien par l'interface graphique que par la version console.
"""

import json
import queue
import re
import threading
import time
import unicodedata
from pathlib import Path

from google import genai
from google.genai import types
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Extensions prises en charge (PDF + images supportees par Gemini)
EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}
IGNORE_SUFFIX = {".tmp", ".part", ".crdownload"}
INLINE_LIMIT = 18 * 1024 * 1024  # au-dela : passage par la File API Gemini

# Reessais sur erreur Gemini transitoire (backoff exponentiel : 2, 4, 8 s).
_MAX_ATTEMPTS = 4
_RETRY_BASE = 2
_TRANSIENT_CODES = {408, 429, 500, 502, 503, 504}

# --------------------------------------------------------------------------
# Prompt : un style de nommage (preset ou personnalise) + un contrat JSON fixe.
# --------------------------------------------------------------------------

# Partie NON editable : garantit une reponse JSON exploitable par le moteur.
# Toujours ajoutee par build_prompt() -> un style perso ne peut pas la casser.
_PROMPT_CONTRACT = (
    "Réponds UNIQUEMENT en JSON valide, sans texte autour, au format exact :\n"
    '{"filename": "nom-du-fichier-sans-extension", '
    '"summary": "courte description en une phrase"}'
)

_STYLE_HEAD = (
    "Tu es un assistant d'archivage de documents. Analyse le document scanné "
    "(image ou PDF) et propose un nom de fichier clair et descriptif, "
    "SANS extension.\n\n"
    "- Langue : français.\n"
    "- Identifie le type de document (facture, devis, contrat, courrier, "
    "relevé, attestation, ticket...) et l'émetteur ou l'entité principale.\n"
)
_STYLE_TAIL = "- Nom concis (3 à 8 mots), sans caractères spéciaux."

# Presets de nommage : chaque entree definit une 'regle' de structure du nom.
NAMING_PRESETS = {
    "date_sujet": {
        "label": "Date + sujet",
        "rule": ("- Structure : la date du document (AAAA-MM-JJ, si visible), "
                 "puis le type, puis le sujet. Ex. : 2026-05-12_facture_edf."),
    },
    "sujet_date": {
        "label": "Sujet + date",
        "rule": ("- Structure : le type puis le sujet, et la date du document "
                 "(AAAA-MM-JJ, si visible) à la FIN. "
                 "Ex. : facture_edf_2026-05-12."),
    },
    "sujet": {
        "label": "Sujet seul (sans date)",
        "rule": ("- Structure : le type de document puis l'émetteur/sujet. "
                 "N'inclus PAS de date. Ex. : facture_edf."),
    },
    "detaille": {
        "label": "Détaillé",
        "rule": ("- Structure : la date (AAAA-MM-JJ), le type, l'émetteur et "
                 "un élément distinctif (objet, période, référence) si "
                 "pertinent. Ex. : 2026-05-12_facture_edf_electricite_mars."),
    },
}

DEFAULT_PRESET = "date_sujet"


def preset_style(key: str) -> str:
    """Texte d'instructions de style d'un preset (sans le contrat JSON)."""
    preset = NAMING_PRESETS.get(key) or NAMING_PRESETS[DEFAULT_PRESET]
    return f"{_STYLE_HEAD}{preset['rule']}\n{_STYLE_TAIL}"


def build_prompt(style: str) -> str:
    """Assemble le prompt complet : instructions de style + contrat JSON fixe."""
    return f"{(style or '').strip()}\n\n{_PROMPT_CONTRACT}"


# --------------------------------------------------------------------------
# Fonctions utilitaires (pures)
# --------------------------------------------------------------------------


def slugify(text: str, maxlen: int = 90) -> str:
    """Transforme un texte libre en nom de fichier sain (sans accents/symboles)."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip()
    text = re.sub(r"[\s_]+", "_", text)
    text = re.sub(r"-{2,}", "-", text)
    return text[:maxlen].strip("_-")


def unique_path(target: Path) -> Path:
    """Renvoie un chemin libre en suffixant _2, _3... si besoin."""
    if not target.exists():
        return target
    i = 2
    while True:
        candidate = target.with_name(f"{target.stem}_{i}{target.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def parse_json(raw: str) -> dict:
    """Parse la reponse du LLM en tolerant d'eventuels blocs ```json."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    return json.loads(raw)


def usage_of(resp) -> dict:
    """Extrait le nombre de tokens (entree / sortie / total) d'une reponse."""
    u = getattr(resp, "usage_metadata", None)
    if u is None:
        return {"in": 0, "out": 0, "total": 0}
    return {
        "in": getattr(u, "prompt_token_count", 0) or 0,
        "out": getattr(u, "candidates_token_count", 0) or 0,
        "total": getattr(u, "total_token_count", 0) or 0,
    }


def _is_transient(exc: Exception) -> bool:
    """Vrai si l'erreur Gemini est transitoire et merite un nouvel essai.

    On reessaie sur les codes HTTP transitoires (429 quota, 5xx surcharge)
    et sur les erreurs reseau / timeout. Les erreurs permanentes (400 fichier
    invalide, 403 cle invalide...) echouent immediatement.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code in _TRANSIENT_CODES
    # Pas de code HTTP : erreur reseau / timeout probable -> transitoire.
    blob = (type(exc).__name__ + " " + str(exc)).lower()
    return any(k in blob for k in (
        "timeout", "timed out", "connection", "temporarily",
        "unavailable", "overloaded", "rate limit", "exhausted"))


def wait_until_stable(path: Path, timeout: float = 90.0) -> bool:
    """Attend la fin d'ecriture du fichier par le scanner (taille stable)."""
    deadline = time.time() + timeout
    last_size = -1
    stable_reads = 0
    while time.time() < deadline:
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size > 0 and size == last_size:
            stable_reads += 1
            if stable_reads >= 3:
                try:
                    with open(path, "rb"):
                        return True
                except (PermissionError, OSError):
                    stable_reads = 0
        else:
            stable_reads = 0
        last_size = size
        time.sleep(1.0)
    return False


def test_api(api_key: str, model: str) -> str:
    """Verifie qu'une cle API + un modele repondent. Leve une exception sinon."""
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model=model, contents="Reponds : OK")
    return (resp.text or "").strip()


# --------------------------------------------------------------------------
# Watcher interne
# --------------------------------------------------------------------------


class _Handler(FileSystemEventHandler):
    def __init__(self, enqueue):
        self._enqueue = enqueue

    def on_created(self, event):
        if not event.is_directory:
            self._enqueue(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            self._enqueue(Path(event.dest_path))


# --------------------------------------------------------------------------
# Moteur
# --------------------------------------------------------------------------


class ScanEngine:
    """Surveille un dossier et renomme les scans via Gemini.

    log : callable(message: str, level: str) ou level dans
          {"info", "warn", "error", "success"}.
    """

    def __init__(self, api_key, model, watch_dir, dry_run=False, log=None,
                 on_renamed=None, prompt=None):
        self.api_key = api_key
        self.model = model
        self.watch_dir = Path(watch_dir)
        self.dry_run = dry_run
        # Prompt complet (style + contrat) ; defaut = preset de base.
        self.prompt = prompt or build_prompt(preset_style(DEFAULT_PRESET))
        self._log = log or (lambda msg, level="info": None)
        # on_renamed(ancien_nom, nouveau_nom, resume) : appele apres un renommage
        self._on_renamed = on_renamed

        self._client = None
        self._observer = None
        self._worker = None
        self._queue: "queue.Queue[Path | None]" = queue.Queue()
        self._pending: set[Path] = set()
        self._pending_lock = threading.Lock()
        self._renamed: set[Path] = set()
        self._running = False

    def log(self, msg, level="info"):
        self._log(msg, level)

    def is_running(self) -> bool:
        return self._running

    # ---- cycle de vie -----------------------------------------------------

    def start(self):
        if self._running:
            return
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self._client = genai.Client(api_key=self.api_key)
        self._queue = queue.Queue()
        self._pending = set()
        self._running = True

        self._worker = threading.Thread(target=self._work_loop, daemon=True)
        self._worker.start()

        self._observer = Observer()
        self._observer.schedule(_Handler(self._enqueue), str(self.watch_dir),
                                recursive=False)
        self._observer.start()
        mode = "  (mode test : aucun renommage)" if self.dry_run else ""
        self.log(f"Surveillance démarrée : {self.watch_dir}{mode}", "success")

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._queue.put(None)
        self.log("Surveillance arrêtée.", "warn")

    def scan_existing(self):
        """Met en file les fichiers deja presents dans le dossier."""
        try:
            files = sorted(p for p in self.watch_dir.iterdir() if p.is_file())
        except OSError:
            return
        if files:
            self.log(f"{len(files)} fichier(s) déjà présent(s) à traiter.", "info")
        for f in files:
            self._enqueue(f)

    # ---- interne ----------------------------------------------------------

    def _enqueue(self, path: Path):
        if path.suffix.lower() not in EXTS:
            return
        with self._pending_lock:
            if path in self._pending:
                return
            self._pending.add(path)
        self._queue.put(path)

    def _work_loop(self):
        while self._running:
            try:
                path = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if path is None:
                break
            with self._pending_lock:
                self._pending.discard(path)
            try:
                self._process(path)
            except Exception as e:  # ne jamais tuer le worker
                self.log(f"Erreur inattendue : {e}", "error")
            finally:
                self._queue.task_done()

    def _process(self, path: Path):
        if path in self._renamed or not path.exists():
            return
        if path.suffix.lower() in IGNORE_SUFFIX or path.name.startswith(("~", ".")):
            return

        self.log(f"Détecté : {path.name}", "info")
        if not wait_until_stable(path):
            self.log(f"Fichier instable ou verrouillé, ignoré : {path.name}", "warn")
            return

        try:
            result, usage = self._analyze(path)
        except Exception as e:
            self.log(f"Échec de l'analyse de {path.name} : {e}", "error")
            return

        self.log(
            f"Tokens : {usage['in']} entrée / {usage['out']} sortie "
            f"(total {usage['total']})",
            "info",
        )

        base = slugify(result.get("filename", ""))
        if not base:
            self.log(f"Aucun nom proposé pour {path.name}, fichier inchangé", "warn")
            return

        target = unique_path(path.with_name(base + path.suffix.lower()))
        if target == path:
            self.log(f"Nom déjà correct : {path.name}", "info")
            return

        summary = result.get("summary", "")
        if self.dry_run:
            self.log(f"[TEST] {path.name}  ->  {target.name}", "info")
            if summary:
                self.log(f"        {summary}", "info")
            return

        self._renamed.add(target)
        try:
            path.rename(target)
        except OSError as e:
            self._renamed.discard(target)
            self.log(f"Renommage impossible pour {path.name} : {e}", "error")
            return
        old_name = path.name
        self.log(f"{old_name}  ->  {target.name}", "success")
        if summary:
            self.log(f"        {summary}", "info")
        if self._on_renamed:
            try:
                self._on_renamed(old_name, target.name, summary)
            except Exception:
                pass

    def _sleep(self, seconds: float) -> None:
        """Pause interruptible : s'ecourte si la surveillance est arretee."""
        end = time.time() + seconds
        while time.time() < end and self._running:
            time.sleep(0.25)

    def _analyze(self, path: Path) -> tuple[dict, dict]:
        """Envoie le scan a Gemini, avec reessais sur erreur transitoire."""
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return self._analyze_once(path)
            except Exception as e:
                if (attempt >= _MAX_ATTEMPTS or not _is_transient(e)
                        or not self._running):
                    raise
                delay = _RETRY_BASE * 2 ** (attempt - 1)
                self.log(f"Erreur Gemini : {e} — nouvel essai "
                         f"{attempt + 1}/{_MAX_ATTEMPTS} dans {delay} s.",
                         "warn")
                self._sleep(delay)
        raise RuntimeError("nombre de tentatives epuise")  # inatteignable

    def _analyze_once(self, path: Path) -> tuple[dict, dict]:
        """Un essai d'analyse Gemini.

        Renvoie ({'filename': ..., 'summary': ...}, {'in', 'out', 'total'}).
        """
        mime = MIME.get(path.suffix.lower(), "application/octet-stream")
        size = path.stat().st_size
        config = types.GenerateContentConfig(
            temperature=0.2, response_mime_type="application/json"
        )

        if size <= INLINE_LIMIT:
            part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)
            resp = self._client.models.generate_content(
                model=self.model, contents=[self.prompt, part], config=config
            )
            return parse_json(resp.text), usage_of(resp)

        uploaded = self._client.files.upload(file=str(path))
        try:
            for _ in range(60):
                state = getattr(uploaded.state, "name", str(uploaded.state))
                if state == "ACTIVE":
                    break
                if state == "FAILED":
                    raise RuntimeError("Gemini n'a pas pu traiter le fichier")
                time.sleep(1.0)
                uploaded = self._client.files.get(name=uploaded.name)
            resp = self._client.models.generate_content(
                model=self.model, contents=[self.prompt, uploaded], config=config
            )
            return parse_json(resp.text), usage_of(resp)
        finally:
            try:
                self._client.files.delete(name=uploaded.name)
            except Exception:
                pass
