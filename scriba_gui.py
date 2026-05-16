"""
Interface graphique (point d'entree de l'executable).

Fonctions :
- saisie de la cle API Gemini et du dossier surveille ;
- cle API chiffree (Windows DPAPI) et memorisee entre deux sessions ;
- demarrage/arret de la surveillance, journal en direct ;
- option "lancer au demarrage de Windows" ;
- notification Windows a chaque renommage.
"""

import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
import winreg
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import notify
import secret
import tray
from scan_engine import ScanEngine, test_api
from version import APP_NAME
from version import __version__ as APP_VERSION

# --------------------------------------------------------------------------
# Emplacements
# --------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent

CONFIG_DIR = Path(os.getenv("APPDATA", str(APP_DIR))) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_FILE = CONFIG_DIR / "scriba.log"

# Largeur fixe ; hauteur ajustee au contenu (journal masque) ou fixe (affiche).
_WIN_WIDTH = 700
_EXPANDED_HEIGHT = 615


def _default_watch_dir() -> str:
    """Dossier de scans par defaut : 'Numerisations' dans les Images de l'utilisateur."""
    pictures = ""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as k:
            pictures = winreg.QueryValueEx(k, "My Pictures")[0]
    except OSError:
        pass
    base = Path(pictures) if pictures else Path.home() / "Pictures"
    return str(base / "Numérisations")


DEFAULTS = {
    # Alias toujours a jour : pointe en permanence vers le dernier flash-lite.
    # Modifiable par un utilisateur avance en editant config.json.
    "model": "gemini-flash-lite-latest",
    "watch_dir": _default_watch_dir(),
    "dry_run": False,
    "scan_existing": False,
    "notify": True,
}

# --------------------------------------------------------------------------
# Demarrage automatique avec Windows (cle de registre Run, par utilisateur)
# --------------------------------------------------------------------------

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --autostart'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    launcher = pyw if pyw.exists() else Path(sys.executable)
    return f'"{launcher}" "{Path(__file__).resolve()}" --autostart'


def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
        return True
    except OSError:
        return False


def set_autostart(enabled: bool) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ,
                                  _startup_command())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# Configuration persistante (cle API chiffree via DPAPI)
# --------------------------------------------------------------------------


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    cfg["api_key"] = ""
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    for key in DEFAULTS:
        if key in raw:
            cfg[key] = raw[key]
    enc = raw.get("api_key_enc")
    if enc:
        try:
            cfg["api_key"] = secret.unprotect(enc)
        except Exception:
            cfg["api_key"] = ""  # config issue d'une autre session Windows
    elif raw.get("api_key"):
        cfg["api_key"] = raw["api_key"]  # ancienne config en clair (sera migree)
    return cfg


def save_config(cfg: dict) -> None:
    data = {key: cfg.get(key, DEFAULTS[key]) for key in DEFAULTS}
    api_key = (cfg.get("api_key") or "").strip()
    if api_key:
        try:
            data["api_key_enc"] = secret.protect(api_key)
        except Exception:
            # DPAPI indisponible : on ne stocke PAS la cle en clair.
            # Elle sera simplement a ressaisir au prochain lancement.
            pass
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------

LEVEL_COLORS = {
    "info": "#dcdcdc",
    "warn": "#e8b339",
    "error": "#e8554e",
    "success": "#5fcf80",
}


class ScribaApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.engine: ScanEngine | None = None
        self.log_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()

        cfg = load_config()
        self.log_visible = False
        # Modele : pas de choix dans l'interface, valeur tiree de la config.
        self.model = cfg["model"] or DEFAULTS["model"]
        root.title(f"{APP_NAME} v{APP_VERSION}  -  renommage automatique de scans")
        root.geometry(f"{_WIN_WIDTH}x320")
        root.minsize(620, 280)

        self.key_var = tk.StringVar(value=cfg["api_key"])
        self.dir_var = tk.StringVar(value=cfg["watch_dir"])
        self.dry_var = tk.BooleanVar(value=cfg["dry_run"])
        self.existing_var = tk.BooleanVar(value=cfg["scan_existing"])
        self.notify_var = tk.BooleanVar(value=cfg["notify"])
        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        self.show_key_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._fit_window()  # hauteur ajustee au contenu (journal masque)

        self._tray_hinted = False
        self.tray = tray.TrayIcon(on_show=self._tray_show,
                                  on_quit=self._tray_quit)
        self.tray.start()

        # Lancee au demarrage de Windows : demarre repliee dans la zone de
        # notification (si l'icone tray permet de la rouvrir ensuite).
        if "--autostart" in sys.argv and tray.available():
            self.root.withdraw()

        self.root.after(150, self._drain_log)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Surveillance lancee automatiquement si la cle et le dossier sont prets
        self.root.after(400, self._maybe_autostart)

    # ---- construction de l'interface -------------------------------------

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        self.frm = ttk.Frame(self.root, padding=12)
        frm = self.frm
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        # Cle API
        ttk.Label(frm, text="Clé API Gemini :").grid(row=0, column=0,
                                                     sticky="w", **pad)
        self.key_entry = ttk.Entry(frm, textvariable=self.key_var, show="•")
        self.key_entry.grid(row=0, column=1, sticky="ew", **pad)
        keybtns = ttk.Frame(frm)
        keybtns.grid(row=0, column=2, sticky="e", **pad)
        ttk.Button(keybtns, text="Obtenir une clé ?",
                   command=self._show_key_help).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(keybtns, text="Afficher", variable=self.show_key_var,
                        command=self._toggle_key).pack(side="left")
        self.test_btn = ttk.Button(keybtns, text="Tester", command=self._test_key)
        self.test_btn.pack(side="left", padx=(6, 0))

        # Dossier surveille
        ttk.Label(frm, text="Dossier surveillé :").grid(row=1, column=0,
                                                        sticky="w", **pad)
        self.dir_entry = ttk.Entry(frm, textvariable=self.dir_var)
        self.dir_entry.grid(row=1, column=1, sticky="ew", **pad)
        self.browse_btn = ttk.Button(frm, text="Parcourir...", command=self._browse)
        self.browse_btn.grid(row=1, column=2, sticky="e", **pad)

        # Options
        opts = ttk.LabelFrame(frm, text="Options", padding=8)
        opts.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)
        opts.columnconfigure(0, weight=1)
        opts.columnconfigure(1, weight=1)
        self.dry_check = ttk.Checkbutton(
            opts, text="Mode test (analyse sans renommer)", variable=self.dry_var)
        self.dry_check.grid(row=0, column=0, sticky="w", pady=2)
        self.existing_check = ttk.Checkbutton(
            opts, text="Traiter les fichiers déjà présents",
            variable=self.existing_var)
        self.existing_check.grid(row=0, column=1, sticky="w", pady=2)
        ttk.Checkbutton(opts, text="Notification Windows à chaque renommage",
                        variable=self.notify_var).grid(row=1, column=0,
                                                       sticky="w", pady=2)
        ttk.Checkbutton(opts, text="Lancer au démarrage de Windows",
                        variable=self.autostart_var,
                        command=self._toggle_autostart).grid(row=1, column=1,
                                                             sticky="w", pady=2)

        # Bouton demarrer/arreter + statut + acces au journal
        ctrl = ttk.Frame(frm)
        ctrl.grid(row=3, column=0, columnspan=3, sticky="ew", **pad)
        self.toggle_btn = ttk.Button(ctrl, text="Démarrer la surveillance",
                                     command=self._toggle)
        self.toggle_btn.pack(side="left")
        self.status_var = tk.StringVar(value="●  Arrêté")
        self.status_lbl = ttk.Label(ctrl, textvariable=self.status_var,
                                    foreground="#999")
        self.status_lbl.pack(side="left", padx=12)
        self.log_btn = ttk.Button(ctrl, text="Afficher les journaux",
                                  command=self._toggle_log)
        self.log_btn.pack(side="right")

        # Journal : masque par defaut, affiche via le bouton ci-dessus.
        # Le poids de la ligne (rowconfigure) n'est mis qu'a l'affichage,
        # sinon une bande vide s'etire quand le journal est masque.
        self.log_panel = ttk.Frame(frm)
        self.log_panel.grid(row=4, column=0, columnspan=3, sticky="nsew",
                            padx=8, pady=(6, 8))
        self.log_panel.columnconfigure(0, weight=1)
        self.log_panel.rowconfigure(1, weight=1)
        frm.rowconfigure(4, weight=0)
        ttk.Label(self.log_panel, text="Journal :").grid(
            row=0, column=0, sticky="w", pady=(0, 2))
        logfrm = ttk.Frame(self.log_panel)
        logfrm.grid(row=1, column=0, sticky="nsew")
        self.log_text = tk.Text(logfrm, height=12, wrap="word", bg="#1e1e1e",
                                fg="#dcdcdc", insertbackground="#dcdcdc",
                                relief="flat", font=("Consolas", 9))
        scroll = ttk.Scrollbar(logfrm, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for level, color in LEVEL_COLORS.items():
            self.log_text.tag_config(level, foreground=color)
        self.log_text.tag_config("ts", foreground="#6a9955")
        self.log_panel.grid_remove()

        # Mention confidentialite / RGPD
        rgpd = ttk.Label(
            frm, foreground="#888", justify="left",
            wraplength=_WIN_WIDTH - 48,
            text=("Confidentialité (RGPD) : chaque document déposé est "
                  "transmis aux serveurs Google (Gemini) pour analyse. "
                  f"N'utilise {APP_NAME} qu'avec des documents dont le "
                  "traitement par un service tiers est autorisé."))
        rgpd.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8,
                  pady=(2, 6))

    def _fit_window(self):
        """Ajuste la hauteur de la fenetre au contenu (journal masque)."""
        self.root.update_idletasks()
        self.root.geometry(f"{_WIN_WIDTH}x{self.root.winfo_reqheight()}")

    # ---- actions ----------------------------------------------------------

    def _toggle_key(self):
        self.key_entry.configure(show="" if self.show_key_var.get() else "•")

    def _browse(self):
        chosen = filedialog.askdirectory(title="Choisir le dossier à surveiller",
                                         initialdir=self.dir_var.get() or APP_DIR)
        if chosen:
            self.dir_var.set(chosen)

    def _show_key_help(self):
        """Petit tutoriel : comment obtenir une cle API Gemini."""
        win = tk.Toplevel(self.root)
        win.title("Obtenir une clé API Gemini")
        win.transient(self.root)
        win.resizable(False, False)
        box = ttk.Frame(win, padding=16)
        box.pack(fill="both", expand=True)

        ttk.Label(box, text="Obtenir une clé API Gemini (gratuit)",
                  font=("", 11, "bold")).pack(anchor="w", pady=(0, 10))
        steps = (
            '1.  Ouvre Google AI Studio (bouton ci-dessous).\n\n'
            '2.  Connecte-toi avec ton compte Google.\n\n'
            '3.  Clique sur "Create API key" / "Créer une clé API".\n\n'
            '4.  Choisis un projet Google Cloud, ou laisse-en créer un.\n\n'
            "5.  Copie la clé qui s'affiche.\n\n"
            f'6.  Reviens dans {APP_NAME}, colle-la dans le champ\n'
            '     "Clé API Gemini", puis clique sur "Tester".'
        )
        ttk.Label(box, text=steps, justify="left").pack(anchor="w")
        ttk.Label(box, foreground="#888", wraplength=430, justify="left",
                  text=("La clé reste gratuite dans le palier gratuit de "
                        f"Gemini. {APP_NAME} la chiffre et la conserve sur ce "
                        "PC uniquement.")).pack(anchor="w", pady=(12, 14))

        btns = ttk.Frame(box)
        btns.pack(fill="x")
        ttk.Button(btns, text="Ouvrir Google AI Studio",
                   command=lambda: webbrowser.open(
                       "https://aistudio.google.com/apikey")).pack(side="left")
        ttk.Button(btns, text="Fermer", command=win.destroy).pack(side="right")

        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width()
                                   - win.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height()
                                   - win.winfo_height()) // 2
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        win.grab_set()

    def _toggle_autostart(self):
        want = self.autostart_var.get()
        if not set_autostart(want):
            self.autostart_var.set(not want)
            messagebox.showerror(APP_NAME,
                                 "Impossible de modifier le démarrage Windows.")
            return
        self._enqueue_log(
            "Démarrage avec Windows : activé." if want
            else "Démarrage avec Windows : désactivé.", "info")

    def _current_config(self) -> dict:
        return {
            "api_key": self.key_var.get().strip(),
            "model": self.model,
            "watch_dir": self.dir_var.get().strip(),
            "dry_run": self.dry_var.get(),
            "scan_existing": self.existing_var.get(),
            "notify": self.notify_var.get(),
        }

    def _test_key(self):
        api_key = self.key_var.get().strip()
        if not api_key:
            messagebox.showwarning(APP_NAME, "Renseigne d'abord ta clé API.")
            return
        self.test_btn.configure(state="disabled")
        self._enqueue_log("Test de la clé API en cours...", "info")

        def run():
            try:
                test_api(api_key, self.model)
                self._enqueue_log("Clé API valide.", "success")
            except Exception as e:
                self._enqueue_log(f"Clé API invalide : {e}", "error")
            finally:
                self.root.after(0,
                                lambda: self.test_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _toggle(self):
        if self.engine and self.engine.is_running():
            self._stop()
        else:
            self._start()

    def _start(self) -> bool:
        cfg = self._current_config()
        if not cfg["api_key"]:
            messagebox.showwarning(APP_NAME, "Renseigne ta clé API Gemini.")
            return False
        if not cfg["watch_dir"]:
            messagebox.showwarning(APP_NAME, "Choisis un dossier à surveiller.")
            return False
        save_config(cfg)

        self.engine = ScanEngine(
            cfg["api_key"], cfg["model"], cfg["watch_dir"],
            dry_run=cfg["dry_run"], log=self._enqueue_log,
            on_renamed=self._handle_renamed,
        )
        try:
            self.engine.start()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Démarrage impossible :\n{e}")
            self.engine = None
            return False
        if cfg["scan_existing"]:
            threading.Thread(target=self.engine.scan_existing,
                             daemon=True).start()
        self._set_running(True)
        return True

    def _stop(self):
        if self.engine:
            self.engine.stop()
        self._set_running(False)

    def _maybe_autostart(self):
        """Lancement de l'app : demarre seul si la config est complete."""
        cfg = self._current_config()
        if cfg["api_key"] and cfg["watch_dir"]:
            self._start()

    def _set_running(self, running: bool):
        state = "disabled" if running else "normal"
        for w in (self.key_entry, self.dir_entry, self.browse_btn,
                  self.dry_check, self.existing_check, self.test_btn):
            w.configure(state=state)
        if running:
            self.toggle_btn.configure(text="Arrêter la surveillance")
            self.status_var.set("●  En surveillance")
            self.status_lbl.configure(foreground="#1e8449")
        else:
            self.toggle_btn.configure(text="Démarrer la surveillance")
            self.status_var.set("●  Arrêté")
            self.status_lbl.configure(foreground="#999")
        self.tray.set_running(running)

    def _handle_renamed(self, old_name: str, new_name: str, summary: str):
        if self.notify_var.get():
            notify.notify(f"{APP_NAME} - fichier renommé",
                          f"{old_name}\n->  {new_name}")

    # ---- journal ----------------------------------------------------------

    def _toggle_log(self):
        if self.log_visible:
            self.log_panel.grid_remove()
            self.frm.rowconfigure(4, weight=0)
            self.log_btn.configure(text="Afficher les journaux")
            self._fit_window()
        else:
            self.frm.rowconfigure(4, weight=1)
            self.log_panel.grid()
            self.log_btn.configure(text="Masquer les journaux")
            self.root.geometry(f"{_WIN_WIDTH}x{_EXPANDED_HEIGHT}")
        self.log_visible = not self.log_visible

    def _enqueue_log(self, msg: str, level: str = "info"):
        """Appele depuis n'importe quel thread (moteur inclus)."""
        self.log_queue.put((msg, level))

    def _drain_log(self):
        try:
            while True:
                msg, level = self.log_queue.get_nowait()
                self._append_log(msg, level)
        except queue.Empty:
            pass
        self.root.after(150, self._drain_log)

    def _append_log(self, msg: str, level: str):
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", ts + "  ", "ts")
        self.log_text.insert("end", msg + "\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{ts}  {level.upper():8}{msg}\n")
        except Exception:
            pass

    # ---- fermeture --------------------------------------------------------

    def _on_close(self):
        """Bouton X : repli dans la zone de notification, sinon quitte."""
        if tray.available():
            save_config(self._current_config())
            self.root.withdraw()
            if not self._tray_hinted:
                self._tray_hinted = True
                notify.notify(
                    APP_NAME,
                    "L'application continue en arrière-plan. Icône en bas à "
                    "droite : clic pour rouvrir, clic droit pour quitter.")
        else:
            self._do_quit()

    def _do_quit(self):
        if self.engine and self.engine.is_running():
            self.engine.stop()
        save_config(self._current_config())
        self.tray.stop()
        self.root.quit()
        self.root.destroy()

    def _tray_show(self):
        # appele depuis le thread pystray : rebascule vers le thread Tk
        self.root.after(0, self._restore_window)

    def _restore_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _tray_quit(self):
        self.root.after(0, self._do_quit)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")  # rendu natif Windows
    except tk.TclError:
        pass
    try:
        ico = Path(getattr(sys, "_MEIPASS", APP_DIR)) / "icon.ico"
        if ico.exists():
            root.iconbitmap(str(ico))
    except Exception:
        pass
    ScribaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
