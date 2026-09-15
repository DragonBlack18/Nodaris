"""MonitorPing - monitoramento de equipamentos por ICMP.

Compatível com Windows 10/11 e executável também em Linux para testes.
Dependências opcionais: pygame (áudio), pystray e Pillow (bandeja),
win10toast (notificações no Windows).
"""
from __future__ import annotations

import csv
import json
import logging
import os
import platform
import queue
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import winreg
except ImportError:
    winreg = None
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

try:
    import pygame
except ImportError:
    pygame = None
try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
try:
    from winotify import Notification, audio as winotify_audio
except ImportError:
    Notification = None
    winotify_audio = None
try:
    from win10toast import ToastNotifier
except ImportError:
    ToastNotifier = None

APP_NAME = "MonitorPing"
DEFAULT_INTERVAL = 5
DEFAULT_TIMEOUT = 1000
DEFAULT_FAILURES = 3
MAX_WORKERS = 32


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = app_dir()
DB_PATH = BASE_DIR / "monitorping.db"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler(LOG_DIR / "monitorping.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)


def now_text() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def seconds_since(value: str | None) -> int:
    if not value:
        return 0
    try:
        return max(0, int((datetime.now() - datetime.strptime(value, "%d/%m/%Y %H:%M:%S")).total_seconds()))
    except (TypeError, ValueError):
        return 0


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=10000")
        self._create()

    def _create(self):
        with self.lock, self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS equipamentos (
                    ip TEXT PRIMARY KEY, nome TEXT NOT NULL, grupo TEXT NOT NULL DEFAULT 'Outros',
                    habilitado INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'AGUARDANDO',
                    ping_ms INTEGER, ultima_queda TEXT, ultimo_retorno TEXT, inicio_offline TEXT,
                    falhas INTEGER NOT NULL DEFAULT 0, quedas INTEGER NOT NULL DEFAULT 0,
                    total_offline INTEGER NOT NULL DEFAULT 0, total_online INTEGER NOT NULL DEFAULT 0,
                    soma_ping INTEGER NOT NULL DEFAULT 0, pings INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, ip TEXT,
                    nome TEXT, tipo TEXT NOT NULL, detalhe TEXT
                );
                CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            """)

    def all_equipment(self) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM equipamentos ORDER BY nome COLLATE NOCASE")]

    def equipment(self, ip: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM equipamentos WHERE ip=?", (ip,)).fetchone()
            return dict(row) if row else None

    def save_equipment(self, data: dict[str, Any]):
        columns = ["ip", "nome", "grupo", "habilitado", "status", "ping_ms", "ultima_queda", "ultimo_retorno", "inicio_offline", "falhas", "quedas", "total_offline", "total_online", "soma_ping", "pings"]
        values = [data.get(c) for c in columns]
        with self.lock, self.conn:
            self.conn.execute(f"INSERT OR REPLACE INTO equipamentos ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", values)

    def delete_equipment(self, ip: str):
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM equipamentos WHERE ip=?", (ip,))

    def event(self, ip: str | None, nome: str | None, tipo: str, detalhe: str = ""):
        with self.lock, self.conn:
            self.conn.execute("INSERT INTO eventos(data,ip,nome,tipo,detalhe) VALUES (?,?,?,?,?)", (now_text(), ip, nome, tipo, detalhe))

    def events(self, limit: int = 500):
        with self.lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (limit,))]

    def clear_events(self):
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM eventos")

    def get_config(self, key: str, default: Any = None) -> Any:
        with self.lock:
            row = self.conn.execute("SELECT valor FROM configuracoes WHERE chave=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return row[0]

    def set_config(self, key: str, value: Any):
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False)))

    def close(self):
        with self.lock:
            self.conn.close()


class PingService:
    @staticmethod
    def ping(ip: str, timeout_ms: int) -> tuple[bool, int, str | None]:
        system = platform.system().lower()
        if system == "windows":
            command = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
        else:
            command = ["ping", "-c", "1", "-W", str(max(1, round(timeout_ms / 1000))), ip]
        started = time.perf_counter()
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if system == "windows" else 0,
                                    timeout=max(2, timeout_ms / 1000 + 1))
            elapsed = round((time.perf_counter() - started) * 1000)
            return result.returncode == 0, elapsed if result.returncode == 0 else 0, None
        except subprocess.TimeoutExpired:
            return False, 0, "timeout"
        except Exception as exc:
            return False, 0, str(exc)


class AudioService:
    def __init__(self):
        self.lock = threading.Lock()
        self.path = ""
        self.enabled = True
        self.available = False
        if pygame:
            try:
                pygame.mixer.init()
                self.available = True
            except Exception as exc:
                logger.warning("Áudio indisponível: %s", exc)

    def play(self):
        if not self.enabled:
            return
        with self.lock:
            try:
                if self.path and os.path.exists(self.path) and self.available:
                    pygame.mixer.music.load(self.path)
                    pygame.mixer.music.play()
                    return
                if platform.system().lower() == "windows":
                    import winsound
                    winsound.Beep(1200, 250)
                    winsound.Beep(700, 250)
                else:
                    print("\\a", end="", flush=True)
            except Exception as exc:
                logger.exception("Falha ao reproduzir áudio: %s", exc)

    def close(self):
        if pygame:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception:
                pass


class MonitorEngine:
    def __init__(self, db: Database, publish, get_settings):
        self.db = db
        self.publish = publish
        self.get_settings = get_settings
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="ping")

    def start(self):
        if not self.thread or not self.thread.is_alive():
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run, name="monitor-engine", daemon=True)
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.wake_event.set()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def pause_or_resume(self):
        self.wake_event.set()

    def _run(self):
        logger.info("Monitoramento iniciado")
        while not self.stop_event.is_set():
            settings = self.get_settings()
            if settings["paused"]:
                self.publish(("paused", None))
                self.stop_event.wait(0.5)
                continue
            equipment = [x for x in self.db.all_equipment() if x["habilitado"]]
            futures = {self.executor.submit(PingService.ping, x["ip"], settings["timeout"]): x for x in equipment}
            for future in as_completed(futures):
                if self.stop_event.is_set():
                    break
                item = futures[future]
                try:
                    online, ping, error = future.result()
                    self._process(item["ip"], online, ping, error, settings["failures"])
                except Exception as exc:
                    logger.exception("Erro no resultado do ping %s: %s", item["ip"], exc)
            self.publish(("cycle", now_text()))
            self.stop_event.wait(settings["interval"])
        logger.info("Monitoramento encerrado")

    def _process(self, ip: str, response: bool, ping: int, error: str | None, threshold: int):
        item = self.db.equipment(ip)
        if not item:
            return
        previous = item["status"]
        item["ping_ms"] = ping if response else None
        item["total_online"] = item["total_online"] + (1 if response else 0)
        item["pings"] = item["pings"] + (1 if response else 0)
        item["soma_ping"] = item["soma_ping"] + (ping if response else 0)
        if response:
            item["falhas"] = 0
            item["status"] = "ONLINE"
            if previous == "OFFLINE":
                item["ultimo_retorno"] = now_text()
                item["total_offline"] += seconds_since(item["inicio_offline"])
                item["inicio_offline"] = None
                self.db.event(ip, item["nome"], "ONLINE")
                self.publish(("transition", {"type": "online", "item": item.copy()}))
        else:
            item["falhas"] += 1
            if item["falhas"] >= threshold:
                item["status"] = "OFFLINE"
                if previous != "OFFLINE":
                    item["ultima_queda"] = now_text()
                    item["inicio_offline"] = item["ultima_queda"]
                    item["quedas"] += 1
                    self.db.event(ip, item["nome"], "OFFLINE", error or "falha de ping")
                    self.publish(("transition", {"type": "offline", "item": item.copy()}))
        self.db.save_equipment(item)
        self.publish(("result", item.copy()))


class MonitorPingApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1280x800")
        self.root.minsize(1050, 650)
        self.root.configure(bg="#f4f7fb")
        self.db = Database(DB_PATH)
        self._migrate_legacy_json()
        self.events = queue.Queue()
        self.shutting_down = False
        self.tray = None
        self.mini_window = None
        self.mini_online_var = None
        self.mini_offline_var = None
        self.mini_status_var = None
        self.mini_list = None
        self.audio = AudioService()
        self.interval = tk.IntVar(value=int(self.db.get_config("interval", DEFAULT_INTERVAL)))
        self.timeout = tk.IntVar(value=int(self.db.get_config("timeout", DEFAULT_TIMEOUT)))
        self.failures = tk.IntVar(value=int(self.db.get_config("failures", DEFAULT_FAILURES)))
        self.sound_enabled = tk.BooleanVar(value=bool(self.db.get_config("sound", True)))
        self.notifications_enabled = tk.BooleanVar(value=bool(self.db.get_config("notifications", True)))
        self.minimize_on_close = tk.BooleanVar(value=bool(self.db.get_config("minimize_on_close", True)))
        self.start_minimized = tk.BooleanVar(value=bool(self.db.get_config("start_minimized", False)))
        self.start_with_windows = tk.BooleanVar(value=self._startup_enabled())
        self.dark_mode = tk.BooleanVar(value=bool(self.db.get_config("dark_mode", False)))
        self.paused = False
        self.settings_lock = threading.Lock()
        self.runtime_settings = {
            "interval": max(1, min(60, self.interval.get())),
            "timeout": max(100, min(10000, self.timeout.get())),
            "failures": max(1, min(20, self.failures.get())),
            "paused": False,
        }
        self.audio.enabled = self.sound_enabled.get()
        self.audio.path = self.db.get_config("audio", "")
        self._build_ui()
        self._load_rows()
        self.engine = MonitorEngine(self.db, self.events.put, self._settings)
        self.engine.start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(150, self._drain_events)
        self.root.bind("<F5>", lambda e: self.engine.wake_event.set())
        self.root.bind("<Control-s>", lambda e: self.save_settings())
        self.root.bind("<Escape>", lambda e: self.tree.selection_remove(self.tree.selection()))
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self.root.bind("<Control-n>", lambda e: self.add_dialog())
        self._create_tray()
        self.root.after(700, self.show_mini_window)
        if self.start_minimized.get():
            self.root.after(300, self.minimize_to_tray)
        self.db.event(None, None, "INICIALIZAÇÃO")

    def _migrate_legacy_json(self):
        """Importa o ips.json antigo apenas quando o banco ainda está vazio."""
        try:
            if self.db.all_equipment():
                return
            legacy = BASE_DIR / "ips.json"
            if not legacy.exists():
                return
            with legacy.open("r", encoding="utf-8") as file:
                data = json.load(file)
            for ip, old in data.get("equipamentos", {}).items():
                item = {
                    "ip": ip, "nome": old.get("nome", ip), "grupo": old.get("grupo", "Outros"),
                    "habilitado": 1, "status": "AGUARDANDO", "ping_ms": None,
                    "ultima_queda": old.get("queda") or None, "ultimo_retorno": old.get("retorno") or None,
                    "inicio_offline": None, "falhas": 0, "quedas": 0, "total_offline": 0,
                    "total_online": 0, "soma_ping": 0, "pings": 0,
                }
                self.db.save_equipment(item)
            for key, value in (("interval", data.get("intervalo", DEFAULT_INTERVAL)), ("sound", data.get("som_ativo", True)), ("audio", data.get("arquivo_audio", ""))):
                if self.db.get_config(key) is None:
                    self.db.set_config(key, value)
            logger.info("Configuração legada ips.json importada")
        except Exception as exc:
            logger.exception("Falha ao importar ips.json: %s", exc)

    def _format_duration(self, seconds):
        days, seconds = divmod(int(seconds), 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        if days: return f"{days}d {hours:02d}h"
        if hours: return f"{hours}h {minutes:02d}m"
        return f"{minutes}m {seconds:02d}s"

    def _startup_enabled(self):
        if winreg is None or platform.system().lower() != "windows": return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, APP_NAME)
                return True
        except (FileNotFoundError, OSError): return False

    def toggle_startup(self):
        if winreg is None or platform.system().lower() != "windows":
            self.start_with_windows.set(False)
            messagebox.showinfo("Inicialização", "Esta opção está disponível somente no Windows.", parent=self.root)
            return
        try:
            path = str(Path(sys.executable if getattr(sys, "frozen", False) else sys.executable).resolve())
            if not getattr(sys, "frozen", False): path = f'"{path}" "{Path(__file__).resolve()}"'
            else: path = f'"{path}"'
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Run") as key:
                if self.start_with_windows.get(): winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, path)
                else: winreg.DeleteValue(key, APP_NAME)
            self.db.set_config("start_with_windows", self.start_with_windows.get())
        except OSError as exc:
            self.start_with_windows.set(False)
            logger.exception("Falha ao configurar inicialização: %s", exc)
            messagebox.showerror("Inicialização", str(exc), parent=self.root)

    def test_notification(self):
        self.notify("MonitorPing — teste", "As notificações do Windows estão funcionando.")

    def _settings(self):
        with self.settings_lock:
            return self.runtime_settings.copy()

    def _build_ui(self):
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("App.TFrame", background="#f4f7fb")
        self.style.configure("Header.TFrame", background="#172554")
        self.style.configure("Header.TLabel", background="#172554", foreground="white")
        self.style.configure("Card.TLabelframe", background="white", borderwidth=0)
        self.style.configure("Card.TLabelframe.Label", background="white", foreground="#64748b", font=("Segoe UI", 9, "bold"))
        self.style.configure("CardValue.TLabel", background="white", foreground="#0f172a", font=("Segoe UI", 20, "bold"))
        self.style.configure("Live.TLabel", background="#172554", foreground="#93c5fd", font=("Segoe UI", 10, "bold"))
        self.style.configure("Modern.TButton", padding=(10, 6), font=("Segoe UI", 9, "bold"))
        self.style.configure("Treeview", rowheight=30, font=("Segoe UI", 9), borderwidth=0)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), padding=(8, 8))
        self.style.configure("Section.TLabelframe", background="#ffffff", borderwidth=1)
        self.style.configure("Section.TLabelframe.Label", background="#ffffff", foreground="#334155", font=("Segoe UI", 10, "bold"))
        self.style.configure("Accent.TButton", background="#2563eb", foreground="white", padding=(12, 7), font=("Segoe UI", 9, "bold"))
        self.style.map("Accent.TButton", background=[("active", "#1d4ed8")])
        header = ttk.Frame(self.root, padding=(24, 18), style="Header.TFrame"); header.pack(fill="x")
        ttk.Label(header, text="MONITORPING", style="Header.TLabel", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(header, text="Monitoramento de rede em tempo real", style="Header.TLabel", font=("Segoe UI", 10)).pack(anchor="w")
        self.live_var = tk.StringVar(value="● MONITORAMENTO ATIVO")
        ttk.Label(header, textvariable=self.live_var, style="Live.TLabel").pack(anchor="e", pady=(0, 2))
        cards = ttk.Frame(self.root, padding=(12, 0)); cards.pack(fill="x")
        self.card_vars = {key: tk.StringVar(value="0") for key in ("TOTAL", "ONLINE", "OFFLINE", "ALERTAS", "DISPONIBILIDADE", "PING MÉDIO", "OFFLINE TOTAL")}
        self.card_colors = {"TOTAL":"#2563eb", "ONLINE":"#16a34a", "OFFLINE":"#dc2626", "ALERTAS":"#d97706", "DISPONIBILIDADE":"#7c3aed", "PING MÉDIO":"#0891b2", "OFFLINE TOTAL":"#be123c"}
        for key in self.card_vars:
            box = ttk.LabelFrame(cards, text=key, padding=(14, 10), style="Card.TLabelframe"); box.pack(side="left", fill="x", expand=True, padx=4, pady=(12, 4))
            accent = tk.Frame(box, height=4, bg=self.card_colors[key]); accent.pack(fill="x", pady=(0, 8))
            ttk.Label(box, textvariable=self.card_vars[key], style="CardValue.TLabel").pack()
        controls = ttk.LabelFrame(self.root, text="FILTROS E CONFIGURAÇÕES", padding=12, style="Section.TLabelframe"); controls.pack(fill="x", padx=18, pady=12)
        ttk.Label(controls, text="Pesquisar:").grid(row=0, column=0, padx=4)
        self.search_var = tk.StringVar(); self.search_entry = ttk.Entry(controls, textvariable=self.search_var, width=24); self.search_entry.grid(row=0, column=1, padx=4)
        self.search_var.trace_add("write", lambda *_: self.refresh())
        ttk.Label(controls, text="Grupo:").grid(row=0, column=2, padx=4)
        self.group_var = tk.StringVar(value="Todos"); self.group_combo = ttk.Combobox(controls, textvariable=self.group_var, state="readonly", width=15, values=["Todos"]); self.group_combo.grid(row=0, column=3, padx=4); self.group_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(controls, text="Intervalo s:").grid(row=0, column=4, padx=4); ttk.Spinbox(controls, from_=1, to=60, textvariable=self.interval, width=5).grid(row=0, column=5)
        ttk.Label(controls, text="Timeout ms:").grid(row=0, column=6, padx=4); ttk.Spinbox(controls, from_=100, to=10000, increment=100, textvariable=self.timeout, width=7).grid(row=0, column=7)
        ttk.Label(controls, text="Falhas:").grid(row=0, column=8, padx=4); ttk.Spinbox(controls, from_=1, to=20, textvariable=self.failures, width=5).grid(row=0, column=9)
        ttk.Checkbutton(controls, text="Som", variable=self.sound_enabled, command=self.save_settings).grid(row=1, column=0, pady=6)
        ttk.Checkbutton(controls, text="Notificações", variable=self.notifications_enabled, command=self.save_settings).grid(row=1, column=1, pady=6)
        ttk.Checkbutton(controls, text="Modo escuro", variable=self.dark_mode, command=self.apply_theme).grid(row=1, column=2, pady=6)
        ttk.Checkbutton(controls, text="Minimizar ao fechar", variable=self.minimize_on_close, command=self.save_settings).grid(row=1, column=3, pady=6)
        ttk.Checkbutton(controls, text="Iniciar com Windows", variable=self.start_with_windows, command=self.toggle_startup).grid(row=1, column=4, pady=6)
        ttk.Button(controls, text="Novo equipamento", style="Accent.TButton", command=self.add_dialog).grid(row=1, column=5, padx=3); ttk.Button(controls, text="Editar", style="Modern.TButton", command=self.edit_selected).grid(row=1, column=6, padx=3); ttk.Button(controls, text="Remover", style="Modern.TButton", command=self.remove_selected).grid(row=1, column=7, padx=3); ttk.Button(controls, text="Testar Toast", style="Modern.TButton", command=self.test_notification).grid(row=1, column=8, padx=3)
        ttk.Button(controls, text="Exportar configurações", style="Modern.TButton", command=self.export_settings).grid(row=2, column=5, padx=3, pady=(6, 0)); ttk.Button(controls, text="Importar configurações", style="Modern.TButton", command=self.import_settings).grid(row=2, column=6, padx=3, pady=(6, 0))
        columns = ("nome", "ip", "grupo", "status", "ping", "queda", "retorno", "offline", "quedas")
        frame = ttk.Frame(self.root, padding=(18, 4, 18, 8), style="App.TFrame"); frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        titles = {"nome":"Nome", "ip":"IP", "grupo":"Grupo", "status":"Status", "ping":"Ping", "queda":"Última queda", "retorno":"Último retorno", "offline":"Tempo offline", "quedas":"Quedas"}
        widths = {"nome":170,"ip":130,"grupo":110,"status":90,"ping":75,"queda":145,"retorno":145,"offline":100,"quedas":60}
        for c in columns: self.tree.heading(c, text=titles[c]); self.tree.column(c, width=widths[c], anchor="center")
        self.tree.tag_configure("online", foreground="#166534", background="#f0fdf4")
        self.tree.tag_configure("offline", foreground="#991b1b", background="#fef2f2")
        self.tree.tag_configure("aguardando", foreground="#92400e", background="#fffbeb")
        self.tree.pack(side="left", fill="both", expand=True); scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview); scroll.pack(side="right", fill="y"); self.tree.configure(yscrollcommand=scroll.set)
        footer = ttk.Frame(self.root, padding=(18, 8), style="App.TFrame"); footer.pack(fill="x"); self.status_var = tk.StringVar(value="Monitoramento ativo"); ttk.Label(footer, textvariable=self.status_var).pack(side="left"); ttk.Button(footer, text="Janela compacta", style="Modern.TButton", command=self.show_mini_window).pack(side="right", padx=3); ttk.Button(footer, text="Importar CSV", command=self.import_csv).pack(side="right", padx=3); ttk.Button(footer, text="Exportar CSV", command=self.export_csv).pack(side="right", padx=3); ttk.Button(footer, text="Histórico", command=self.show_history).pack(side="right", padx=3); self.pause_button = ttk.Button(footer, text="Pausar", command=self.toggle_pause); self.pause_button.pack(side="right", padx=3)
        self.apply_theme()

    def show_mini_window(self):
        if self.mini_window is not None and self.mini_window.winfo_exists():
            self.mini_window.deiconify(); self.mini_window.lift(); return
        win = tk.Toplevel(self.root)
        self.mini_window = win
        win.title("MonitorPing — Monitor rápido")
        win.geometry("330x300")
        win.minsize(300, 240)
        win.configure(bg="#0f172a")
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        header = tk.Frame(win, bg="#172554", padx=14, pady=10); header.pack(fill="x")
        tk.Label(header, text="MONITORPING", bg="#172554", fg="white", font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Label(header, text="AO VIVO", bg="#172554", fg="#93c5fd", font=("Segoe UI", 8, "bold")).pack(side="right")
        stats = tk.Frame(win, bg="#0f172a", padx=10, pady=10); stats.pack(fill="x")
        self.mini_online_var = tk.StringVar(value="0 ONLINE")
        self.mini_offline_var = tk.StringVar(value="0 OFFLINE")
        self.mini_status_var = tk.StringVar(value="Monitorando...")
        online_box = tk.Frame(stats, bg="#14532d", padx=10, pady=8); online_box.pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Label(online_box, textvariable=self.mini_online_var, bg="#14532d", fg="#bbf7d0", font=("Segoe UI", 12, "bold")).pack()
        offline_box = tk.Frame(stats, bg="#7f1d1d", padx=10, pady=8); offline_box.pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Label(offline_box, textvariable=self.mini_offline_var, bg="#7f1d1d", fg="#fecaca", font=("Segoe UI", 12, "bold")).pack()
        tk.Label(win, textvariable=self.mini_status_var, bg="#0f172a", fg="#cbd5e1", font=("Segoe UI", 9)).pack(anchor="w", padx=14)
        tk.Label(win, text="Equipamentos offline", bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(10, 3))
        self.mini_list = tk.Listbox(win, height=6, bg="#1e293b", fg="#fecaca", selectbackground="#334155", relief="flat", highlightthickness=0, font=("Segoe UI", 9))
        self.mini_list.pack(fill="both", expand=True, padx=14)
        actions = tk.Frame(win, bg="#0f172a", pady=8); actions.pack(fill="x")
        tk.Button(actions, text="Abrir dashboard", command=self.show_window, bg="#2563eb", fg="white", relief="flat", padx=10).pack(side="left", padx=14)
        tk.Button(actions, text="Ocultar", command=win.withdraw, bg="#334155", fg="white", relief="flat", padx=10).pack(side="right", padx=14)
        self._update_mini(self.db.all_equipment())

    def _update_mini(self, rows):
        if self.mini_window is None or not self.mini_window.winfo_exists():
            return
        online = [x for x in rows if x["status"] == "ONLINE"]
        offline = [x for x in rows if x["status"] == "OFFLINE"]
        self.mini_online_var.set(f"{len(online)} ONLINE")
        self.mini_offline_var.set(f"{len(offline)} OFFLINE")
        self.mini_status_var.set(f"Atualizado às {datetime.now().strftime('%H:%M:%S')} — {len(rows)} equipamentos")
        self.mini_list.delete(0, tk.END)
        for item in offline[:20]:
            self.mini_list.insert(tk.END, f"● {item['nome']}  |  {item['ip']}")
        if not offline:
            self.mini_list.insert(tk.END, "✓ Nenhum equipamento offline")

    def _load_rows(self):
        self.refresh()
        groups = sorted({x["grupo"] for x in self.db.all_equipment()})
        self.group_combo["values"] = ["Todos"] + groups

    def refresh(self):
        query = self.search_var.get().lower(); group = self.group_var.get()
        for iid in self.tree.get_children(): self.tree.delete(iid)
        rows = self.db.all_equipment(); visible = []
        for x in rows:
            if query and query not in (x["nome"] + " " + x["ip"]).lower(): continue
            if group != "Todos" and x["grupo"] != group: continue
            visible.append(x); self._insert_row(x)
        online = sum(x["status"] == "ONLINE" for x in rows); offline = sum(x["status"] == "OFFLINE" for x in rows)
        total = len(rows)
        self.card_vars["TOTAL"].set(str(total)); self.card_vars["ONLINE"].set(str(online)); self.card_vars["OFFLINE"].set(str(offline)); self.card_vars["ALERTAS"].set(str(sum(x["quedas"] for x in rows)))
        self.card_vars["DISPONIBILIDADE"].set(f"{(online / total * 100):.1f}%" if total else "0.0%")
        ping_values = [x["soma_ping"] / x["pings"] for x in rows if x["pings"]]
        self.card_vars["PING MÉDIO"].set(f"{sum(ping_values) / len(ping_values):.0f} ms" if ping_values else "-")
        total_offline = sum(x["total_offline"] + (seconds_since(x["inicio_offline"]) if x["status"] == "OFFLINE" else 0) for x in rows)
        self.card_vars["OFFLINE TOTAL"].set(self._format_duration(total_offline))
        self._update_mini(rows)

    def _insert_row(self, x):
        status = x["status"]
        tag = status.lower() if status in ("ONLINE", "OFFLINE") else "aguardando"
        marker = "● " if status in ("ONLINE", "OFFLINE") else "○ "
        # O tag é aplicado à linha inteira: Nome e IP ficam verdes ou vermelhos juntos.
        self.tree.insert("", "end", iid=x["ip"], values=(f"{marker}{x['nome']}", x["ip"], x["grupo"], status, f"{x['ping_ms']} ms" if x["ping_ms"] else "-", x["ultima_queda"] or "-", x["ultimo_retorno"] or "-", f"{seconds_since(x['inicio_offline'])} s" if status == "OFFLINE" else "-", x["quedas"]), tags=(tag,))

    def _drain_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "result" or kind == "transition": self.refresh()
                elif kind == "cycle":
                    self.status_var.set(f"Última atualização: {value}")
                    self.live_var.set("● MONITORAMENTO ATIVO")
                elif kind == "paused":
                    self.status_var.set("Monitoramento pausado")
                    self.live_var.set("Ⅱ MONITORAMENTO PAUSADO")
                if kind == "transition": self._transition(value)
        except queue.Empty:
            pass
        if not self.shutting_down: self.root.after(150, self._drain_events)

    def _transition(self, event):
        item = event["item"]; typ = event["type"]
        if typ == "offline":
            if self.sound_enabled.get(): threading.Thread(target=self.audio.play, daemon=True).start()
            if self.notifications_enabled.get(): self.notify("EQUIPAMENTO OFFLINE", f"{item['nome']} — {item['ip']}")
        else:
            if self.notifications_enabled.get(): self.notify("EQUIPAMENTO ONLINE", f"{item['nome']} — {item['ip']}")

    def notify(self, title, text):
        if platform.system().lower() != "windows":
            logger.info("Toast ignorado fora do Windows: %s", title)
            return
        try:
            if Notification is not None:
                toast = Notification(app_id=APP_NAME, title=title, msg=text)
                if winotify_audio is not None: toast.set_audio(winotify_audio.Default, loop=False)
                toast.show()
            elif ToastNotifier is not None:
                ToastNotifier().show_toast(title, text, duration=5, threaded=True)
            else:
                logger.warning("Nenhuma biblioteca de Toast instalada")
        except Exception as exc:
            logger.exception("Falha ao exibir Toast: %s", exc)

    def add_dialog(self, existing=None):
        win = tk.Toplevel(self.root); win.title("Equipamento"); win.transient(self.root); win.grab_set()
        vars_ = {"nome": tk.StringVar(value=existing["nome"] if existing else ""), "ip": tk.StringVar(value=existing["ip"] if existing else ""), "grupo": tk.StringVar(value=existing["grupo"] if existing else "Outros")}
        for i, (key, label) in enumerate((("nome", "Nome"), ("ip", "IP"), ("grupo", "Grupo"))): ttk.Label(win, text=label).grid(row=i, column=0, padx=8, pady=8, sticky="w"); ttk.Entry(win, textvariable=vars_[key], width=28).grid(row=i, column=1, padx=8, pady=8)
        def save():
            import ipaddress
            name, ip, group = vars_["nome"].get().strip(), vars_["ip"].get().strip(), vars_["grupo"].get().strip() or "Outros"
            try: ipaddress.ip_address(ip)
            except ValueError: messagebox.showerror("IP inválido", "Digite um endereço IP válido.", parent=win); return
            if not name: messagebox.showwarning("Aviso", "Digite um nome.", parent=win); return
            if not existing and self.db.equipment(ip): messagebox.showwarning("Aviso", "Esse IP já está cadastrado.", parent=win); return
            if existing and ip != existing["ip"] and self.db.equipment(ip): messagebox.showwarning("Aviso", "Esse IP já está cadastrado.", parent=win); return
            data = existing.copy() if existing else {"status":"AGUARDANDO","ping_ms":None,"ultima_queda":None,"ultimo_retorno":None,"inicio_offline":None,"falhas":0,"quedas":0,"total_offline":0,"total_online":0,"soma_ping":0,"pings":0,"habilitado":1}
            if existing and ip != existing["ip"]: self.db.delete_equipment(existing["ip"])
            data.update({"nome":name,"ip":ip,"grupo":group}); self.db.save_equipment(data); self.db.event(ip, name, "ALTERAÇÃO" if existing else "ADICIONADO"); self._load_rows(); win.destroy()
        ttk.Button(win, text="Salvar", command=save).grid(row=3, column=0, columnspan=2, pady=10)

    def edit_selected(self):
        selected = self.tree.selection();
        if selected:
            item = self.db.equipment(selected[0]);
            if item: self.add_dialog(item)

    def remove_selected(self):
        selected = self.tree.selection()
        if not selected: return
        item = self.db.equipment(selected[0])
        if item and messagebox.askyesno("Confirmar", f"Remover {item['nome']}?", parent=self.root): self.db.delete_equipment(selected[0]); self.db.event(selected[0], item["nome"], "REMOÇÃO"); self._load_rows()

    def save_settings(self):
        values = {"interval": self.interval.get(), "timeout": self.timeout.get(), "failures": self.failures.get(), "sound": self.sound_enabled.get(), "notifications": self.notifications_enabled.get(), "minimize_on_close": self.minimize_on_close.get(), "start_minimized": self.start_minimized.get(), "dark_mode": self.dark_mode.get(), "audio": self.audio.path}
        with self.settings_lock:
            self.runtime_settings.update({"interval": max(1, min(60, int(values["interval"]))), "timeout": max(100, min(10000, int(values["timeout"]))), "failures": max(1, min(20, int(values["failures"])))})
        for k, v in values.items(): self.db.set_config(k, v)
        self.audio.enabled = self.sound_enabled.get(); logger.info("Configurações salvas")

    def apply_theme(self):
        """Aplica uma paleta completa sem perder contraste nos estados da tabela."""
        try:
            dark = bool(self.dark_mode.get())
            if dark:
                bg, panel, field, text, muted = "#0f172a", "#111827", "#1e293b", "#f8fafc", "#94a3b8"
                selected = "#334155"
                online_fg, online_bg = "#86efac", "#14532d"
                offline_fg, offline_bg = "#fca5a5", "#7f1d1d"
                waiting_fg, waiting_bg = "#fde68a", "#78350f"
            else:
                bg, panel, field, text, muted = "#f5f7fa", "#ffffff", "#ffffff", "#202124", "#64748b"
                selected = "#dbeafe"
                online_fg, online_bg = "#166534", "#dcfce7"
                offline_fg, offline_bg = "#991b1b", "#fee2e2"
                waiting_fg, waiting_bg = "#92400e", "#fef3c7"
            self.root.configure(bg=bg)
            self.style.configure(".", background=bg, foreground=text)
            self.style.configure("App.TFrame", background=bg)
            self.style.configure("Header.TFrame", background="#172554")
            self.style.configure("Header.TLabel", background="#172554", foreground="white")
            self.style.configure("Card.TLabelframe", background=panel, foreground=text)
            self.style.configure("Card.TLabelframe.Label", background=panel, foreground=muted)
            self.style.configure("CardValue.TLabel", background=panel, foreground=text)
            self.style.configure("Section.TLabelframe", background=panel, foreground=text)
            self.style.configure("Section.TLabelframe.Label", background=panel, foreground=muted)
            self.style.configure("TLabel", background=panel, foreground=text)
            self.style.configure("TCheckbutton", background=panel, foreground=text)
            self.style.configure("TEntry", fieldbackground=field, foreground=text)
            self.style.configure("TCombobox", fieldbackground=field, foreground=text)
            self.style.configure("Treeview", background=field, fieldbackground=field, foreground=text, rowheight=30)
            self.style.configure("Treeview.Heading", background=panel, foreground=text)
            self.style.map("Treeview", background=[("selected", selected)], foreground=[("selected", text)])
            self.style.configure("Accent.TButton", background="#2563eb", foreground="white")
            self.style.map("Accent.TButton", background=[("active", "#1d4ed8")])
            if hasattr(self, "tree"):
                self.tree.tag_configure("online", foreground=online_fg, background=online_bg)
                self.tree.tag_configure("offline", foreground=offline_fg, background=offline_bg)
                self.tree.tag_configure("aguardando", foreground=waiting_fg, background=waiting_bg)
        except tk.TclError as exc:
            logger.warning("Falha ao aplicar tema: %s", exc)
        self.save_settings()

    def toggle_pause(self):
        self.paused = not self.paused
        with self.settings_lock:
            self.runtime_settings["paused"] = self.paused
        self.pause_button.configure(text="Continuar" if self.paused else "Pausar"); self.engine.wake_event.set()

    def _settings_snapshot(self):
        return {
            "interval": self.interval.get(),
            "timeout": self.timeout.get(),
            "failures": self.failures.get(),
            "sound": self.sound_enabled.get(),
            "notifications": self.notifications_enabled.get(),
            "minimize_on_close": self.minimize_on_close.get(),
            "start_minimized": self.start_minimized.get(),
            "start_with_windows": self.start_with_windows.get(),
            "dark_mode": self.dark_mode.get(),
            "audio": self.audio.path,
        }

    def export_settings(self):
        path = filedialog.asksaveasfilename(
            title="Exportar configurações",
            defaultextension=".json",
            filetypes=[("Configuração MonitorPing", "*.json"), ("JSON", "*.json")],
        )
        if not path:
            return
        try:
            payload = {
                "format": "MonitorPingConfig",
                "version": 1,
                "exported_at": now_text(),
                "settings": self._settings_snapshot(),
                "equipamentos": self.db.all_equipment(),
            }
            with open(path, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2, ensure_ascii=False)
            self.db.event(None, None, "EXPORTAÇÃO", os.path.basename(path))
            messagebox.showinfo("Configurações", "Configurações exportadas com sucesso.", parent=self.root)
        except Exception as exc:
            logger.exception("Falha ao exportar configurações: %s", exc)
            messagebox.showerror("Exportação", f"Não foi possível exportar:\n{exc}", parent=self.root)

    def import_settings(self):
        path = filedialog.askopenfilename(
            title="Importar configurações",
            filetypes=[("Configuração MonitorPing", "*.json"), ("JSON", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            if not isinstance(payload, dict) or payload.get("format") != "MonitorPingConfig":
                raise ValueError("Este arquivo não é uma configuração válida do MonitorPing.")
            settings = payload.get("settings", {})
            equipments = payload.get("equipamentos", [])
            if not isinstance(settings, dict) or not isinstance(equipments, list):
                raise ValueError("Estrutura de configuração inválida.")
            import ipaddress
            valid = []
            for item in equipments:
                if not isinstance(item, dict):
                    continue
                ip = str(item.get("ip", "")).strip()
                ipaddress.ip_address(ip)
                valid.append(item)
            if not messagebox.askyesno("Importar configurações", f"Importar {len(valid)} equipamentos e substituir as preferências atuais?", parent=self.root):
                return
            for key, variable in (("interval", self.interval), ("timeout", self.timeout), ("failures", self.failures)):
                if key in settings:
                    variable.set(settings[key])
            for key, variable in (("sound", self.sound_enabled), ("notifications", self.notifications_enabled), ("minimize_on_close", self.minimize_on_close), ("start_minimized", self.start_minimized), ("dark_mode", self.dark_mode)):
                if key in settings:
                    variable.set(bool(settings[key]))
            self.audio.path = str(settings.get("audio", ""))
            for item in valid:
                old = self.db.equipment(item["ip"])
                if old:
                    item = {**old, "nome": str(item.get("nome", old["nome"])), "grupo": str(item.get("grupo", old["grupo"]))}
                else:
                    item = {"ip": item["ip"], "nome": str(item.get("nome", item["ip"])), "grupo": str(item.get("grupo", "Outros")), "habilitado": int(item.get("habilitado", 1)), "status": "AGUARDANDO", "ping_ms": None, "ultima_queda": None, "ultimo_retorno": None, "inicio_offline": None, "falhas": 0, "quedas": 0, "total_offline": 0, "total_online": 0, "soma_ping": 0, "pings": 0}
                self.db.save_equipment(item)
            self.save_settings()
            self.db.event(None, None, "IMPORTAÇÃO", os.path.basename(path))
            self.apply_theme()
            self._load_rows()
            messagebox.showinfo("Configurações", "Configurações importadas com sucesso.", parent=self.root)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.exception("Configuração inválida: %s", exc)
            messagebox.showerror("Importação", f"Arquivo inválido ou inacessível:\n{exc}", parent=self.root)
        except Exception as exc:
            logger.exception("Falha ao importar configurações: %s", exc)
            messagebox.showerror("Importação", f"Não foi possível importar:\n{exc}", parent=self.root)

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path: return
        count = 0
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    ip, name, group = row.get("ip", "").strip(), row.get("nome", "").strip(), row.get("grupo", "Outros").strip() or "Outros"
                    import ipaddress; ipaddress.ip_address(ip)
                    old = self.db.equipment(ip); data = old or {"ip":ip,"nome":name or ip,"grupo":group,"habilitado":1,"status":"AGUARDANDO","ping_ms":None,"ultima_queda":None,"ultimo_retorno":None,"inicio_offline":None,"falhas":0,"quedas":0,"total_offline":0,"total_online":0,"soma_ping":0,"pings":0}; data.update({"nome":name or ip,"grupo":group}); self.db.save_equipment(data); count += 1
            self.db.event(None, None, "IMPORTAÇÃO", f"{count} equipamentos"); self._load_rows()
        except Exception as exc: logger.exception("Importação CSV: %s", exc); messagebox.showerror("Importação", f"Não foi possível importar o arquivo:\n{exc}", parent=self.root)

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        rows = self.db.all_equipment()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["nome", "ip", "grupo"]); writer.writeheader(); writer.writerows({k: x[k] for k in writer.fieldnames} for x in rows)
        except Exception as exc: messagebox.showerror("Exportação", str(exc), parent=self.root)

    def show_history(self):
        win = tk.Toplevel(self.root); win.title("Histórico"); win.geometry("850x500")
        tree = ttk.Treeview(win, columns=("data", "nome", "ip", "tipo", "detalhe"), show="headings")
        for c in tree["columns"]: tree.heading(c, text=c.upper()); tree.column(c, width=150)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for x in self.db.events(): tree.insert("", "end", values=(x["data"], x["nome"] or "", x["ip"] or "", x["tipo"], x["detalhe"] or ""))
        ttk.Button(win, text="Limpar histórico", command=lambda: (self.db.clear_events(), win.destroy())).pack(pady=5)

    def _create_tray(self):
        if not pystray: return
        try:
            image = Image.new("RGB", (64, 64), "white"); draw = ImageDraw.Draw(image); draw.ellipse((8, 8, 56, 56), fill="green"); draw.text((25, 20), "P", fill="white")
            menu = pystray.Menu(pystray.MenuItem("Abrir MonitorPing", lambda icon, item: self.root.after(0, self.show_window), default=True), pystray.MenuItem("Testar alerta", lambda icon, item: threading.Thread(target=self.audio.play, daemon=True).start()), pystray.MenuItem("Sair", lambda icon, item: self.root.after(0, self.exit_program)))
            self.tray = pystray.Icon(APP_NAME, image, APP_NAME, menu); threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception as exc: logger.warning("Bandeja indisponível: %s", exc)

    def minimize_to_tray(self): self.root.withdraw()
    def show_window(self): self.root.deiconify(); self.root.lift(); self.root.focus_force()

    def on_close(self):
        """O X nunca encerra o processo: apenas oculta a janela.

        O motor de monitoramento, os alertas e as notificações continuam
        ativos. O encerramento real ocorre exclusivamente pelo menu Sair
        da bandeja do sistema.
        """
        self.minimize_to_tray()

    def exit_program(self):
        if self.shutting_down: return
        self.shutting_down = True; logger.info("Encerrando MonitorPing"); self.db.event(None, None, "ENCERRAMENTO"); self.engine.stop(); self.audio.close()
        try:
            if self.tray: self.tray.stop()
        except Exception: pass
        self.db.close(); self.root.destroy()


def main():
    try:
        root = tk.Tk(); MonitorPingApp(root); root.mainloop()
    except Exception as exc:
        logger.exception("Erro fatal: %s", exc)
        try: messagebox.showerror(APP_NAME, f"O MonitorPing encontrou um erro:\n\n{exc}")
        except Exception: pass


if __name__ == "__main__":
    main()
