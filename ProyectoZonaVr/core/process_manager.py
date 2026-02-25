# core/process_manager.py
# ZonaVRLauncher — Gestión de procesos de juego (EXE y Steam)

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import Game

# Importación opcional de psutil (puede no estar instalado)
try:
    import psutil  # type: ignore
    PS_OK = True
except ImportError:
    PS_OK = False

import config


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades internas
# ─────────────────────────────────────────────────────────────────────────────

def _creationflags() -> int:
    """Devuelve CREATE_NO_WINDOW en Windows para no mostrar consola al lanzar."""
    try:
        return subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    except AttributeError:
        return 0


def _pid_alive(pid: int) -> bool:
    """Devuelve True si el PID existe en el sistema."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}"],
            text=True,
            stderr=subprocess.DEVNULL
        )
        return str(pid) in out
    except Exception:
        return False


def _kill_tree(pid: int) -> None:
    """Mata un proceso y todos sus hijos usando taskkill."""
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10
        )
    except Exception as e:
        config.LOG("WARN _kill_tree pid", pid, ":", e)


def _taskkill_image(img_name: str) -> None:
    """Mata todos los procesos con ese nombre de imagen (ej: 'juego.exe')."""
    if not img_name:
        return
    try:
        subprocess.run(
            ["taskkill", "/IM", img_name, "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10
        )
        config.LOG("taskkill /IM", img_name)
    except Exception as e:
        config.LOG("WARN _taskkill_image", img_name, ":", e)


def _tasklist_images() -> set[str]:
    """Devuelve el conjunto de nombres de imagen activos (en minusculas)."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True,
            errors="ignore",
            stderr=subprocess.DEVNULL
        )
        imgs: set[str] = set()
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = [p.strip().strip('"') for p in line.split(",")]
            if parts:
                imgs.add(parts[0].lower())
        return imgs
    except Exception:
        return set()


# Procesos que Steam lanza como soporte y que NO son el juego en si.
# Filtramos estos para no confundirlos con el proceso del juego real.
_STEAM_SUPPORT_PROCS: set[str] = {
    "steam.exe",
    "steamwebhelper.exe",
    "crashhandler.exe",
    "vrcompositor.exe",
    "vrserver.exe",
    "vrmonitor.exe",
    "steamerrorreporter.exe",
    "steamservice.exe",
    "eac_launcherv2.exe",
    "eac_launcher.exe",
    "start_protected_game.exe",
    "battleyelauncher.exe",
    "steamvr_desktop_game_theater.exe",
    "steamtours.exe",
}


# ─────────────────────────────────────────────────────────────────────────────
# _SteamTrackedProc  (clase interna, no usar desde fuera de este modulo)
# ─────────────────────────────────────────────────────────────────────────────

class _SteamTrackedProc:
    """
    Simula la interfaz de subprocess.Popen para juegos de Steam.

    Steam no da un Popen directo, asi que rastreamos el proceso del juego
    por PID (cuando lo encontramos) o por nombre de imagen (fallback).

    Uso interno exclusivo de ProcessManager.
    """

    def __init__(self, pid: int = 0, img: str = "") -> None:
        self._img: str = (img or "").strip().lower()
        self._alive: bool = True

        # Si nos dieron un PID y sigue vivo, lo usamos. Si no, arrancamos sin el
        # y esperamos a que un watcher lo localice mas tarde.
        if pid and _pid_alive(pid):
            self.pid: int | None = pid
        else:
            self.pid = None

    def attach_pid(self, pid: int, img_hint: str = "") -> None:
        """
        Engancha el PID real del juego cuando el watcher lo localiza
        tras el lanzamiento (util para juegos UE4/VR que tardan en arrancar).
        """
        if pid and _pid_alive(pid):
            self.pid = pid
            if img_hint:
                self._img = img_hint.lower()
            self._alive = True
            config.LOG("_SteamTrackedProc: PID adjuntado:", pid, self._img)

    def poll(self) -> int | None:
        """
        Devuelve None si el proceso sigue vivo, 0 si ha terminado.
        Equivalente a Popen.poll().
        """
        if not self._alive:
            return 0

        if self.pid is not None:
            self._alive = _pid_alive(self.pid)
        # Si no tenemos PID todavia, asumimos que sigue vivo
        # (el watcher lo localizara o terminate() lo matara por imagen)

        return None if self._alive else 0

    def wait(self) -> int:
        """Bloquea hasta que el proceso termine. Equivalente a Popen.wait()."""
        while self.poll() is None:
            time.sleep(0.25)
        return 0

    def terminate(self) -> None:
        """
        Intenta cerrar el proceso.
        1) Por PID (incluye procesos hijos).
        2) Por nombre de imagen como red de seguridad.
        """
        if self.pid is not None:
            _kill_tree(self.pid)

        if self._img:
            _taskkill_image(self._img)

        self._alive = False


# ─────────────────────────────────────────────────────────────────────────────
# GameProcess  (interfaz publica unificada)
# ─────────────────────────────────────────────────────────────────────────────

class GameProcess:
    """
    Interfaz unificada para un proceso de juego, independientemente
    de si se lanzo como EXE (subprocess.Popen) o Steam (_SteamTrackedProc).

    Desde fuera del modulo siempre trabajas con GameProcess,
    nunca con Popen ni _SteamTrackedProc directamente.

    Ejemplo:
        proc = manager.launch(game)
        while proc.poll() is None:
            time.sleep(0.5)
        print("juego cerrado")
    """

    def __init__(self, inner: subprocess.Popen | _SteamTrackedProc) -> None:
        self._inner = inner

    @property
    def pid(self) -> int | None:
        """PID del proceso, o None si aun no se ha localizado (Steam)."""
        return getattr(self._inner, "pid", None)

    def poll(self) -> int | None:
        """None = sigue corriendo. Entero = codigo de salida (ya termino)."""
        return self._inner.poll()

    def wait(self) -> int:
        """Bloquea hasta que el proceso termine y devuelve el codigo de salida."""
        return self._inner.wait()

    def terminate(self) -> None:
        """Intenta cerrar el proceso limpiamente."""
        try:
            self._inner.terminate()
        except Exception as e:
            config.LOG("WARN GameProcess.terminate:", e)


# ─────────────────────────────────────────────────────────────────────────────
# Deteccion de procesos Steam (funciones auxiliares internas)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_proc_psutil(t0: float, timeout_s: int) -> tuple[int, str]:
    """
    Usa psutil para encontrar el proceso del juego lanzado a partir de t0.
    Busca el .exe mas pesado en memoria que haya aparecido despues de t0
    y que no sea un proceso de soporte de Steam.

    Devuelve (pid, nombre_imagen) o (0, "") si no encuentra nada.
    """
    if not PS_OK:
        return (0, "")

    end = time.time() + timeout_s
    best_pid, best_name, best_rss = 0, "", 0

    while time.time() < end:
        try:
            for p in psutil.process_iter(attrs=["pid", "name", "create_time", "memory_info"]):
                name: str = (p.info.get("name") or "").lower()

                if not name.endswith(".exe"):
                    continue
                if name in _STEAM_SUPPORT_PROCS:
                    continue

                # Solo procesos que arrancaron despues del lanzamiento
                ctime: float = p.info.get("create_time") or 0
                if ctime + 0.5 < t0:
                    continue

                rss = 0
                try:
                    mi = p.info.get("memory_info")
                    rss = getattr(mi, "rss", 0) or 0
                except Exception:
                    pass

                # El mejor candidato es el que mas memoria consume
                if rss >= best_rss:
                    best_pid = p.info["pid"]
                    best_name = name
                    best_rss = rss

        except Exception:
            pass

        if best_pid:
            config.LOG("psutil detecto proceso Steam:", best_pid, best_name)
            return (best_pid, best_name)

        time.sleep(1.0)

    return (0, "")


def _detect_proc_tasklist(baseline: set[str], timeout_s: int) -> str:
    """
    Fallback cuando psutil no esta disponible.
    Compara la lista de procesos antes y despues del lanzamiento
    y devuelve el nombre del nuevo .exe que no sea soporte de Steam.

    Devuelve el nombre de imagen o "" si no encuentra nada.
    """
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        now = _tasklist_images()
        new = now - baseline
        new = {n for n in new if n.endswith(".exe")}
        new = {n for n in new if n not in _STEAM_SUPPORT_PROCS}

        if len(new) == 1:
            found = next(iter(new))
            config.LOG("tasklist detecto proceso Steam:", found)
            return found

        if len(new) > 1:
            # Si hay varios, descarta lanzadores y updaters
            prefer = [
                n for n in new
                if "launcher" not in n
                and "setup" not in n
                and "updater" not in n
                and "install" not in n
            ]
            if len(prefer) == 1:
                config.LOG(
                    "tasklist detecto proceso Steam (filtrado):", prefer[0])
                return prefer[0]

        time.sleep(1.0)

    return ""


def _steam_attach_watcher(
    proc_obj: _SteamTrackedProc,
    t0: float,
    img_hint: str,
    timeout: int
) -> None:
    """
    Hilo daemon que intenta localizar y adjuntar el PID real del juego Steam
    cuando el lanzamiento tarda en arrancar el proceso (juegos UE4/VR).

    Se lanza como daemon thread y no bloquea el flujo principal.
    """
    if proc_obj.pid is not None:
        return  # ya tiene PID, no hace falta buscar

    end = time.time() + timeout
    while time.time() < end:
        if proc_obj.poll() is not None:
            return  # el proceso ya termino (o fue matado)

        pid, img = _detect_proc_psutil(t0, timeout_s=3)
        if pid:
            proc_obj.attach_pid(pid, img_hint or img)
            return

        time.sleep(1.0)

    config.LOG("WARN steam_attach_watcher: timeout sin localizar PID")


# ─────────────────────────────────────────────────────────────────────────────
# ProcessManager  (clase principal, usa esta desde el resto de la app)
# ─────────────────────────────────────────────────────────────────────────────

class ProcessManager:
    """
    Punto unico para lanzar y matar procesos de juego.

    Uso tipico:
        manager = ProcessManager()

        # Lanzar
        proc = manager.launch(game)

        # Comprobar si sigue corriendo
        if manager.is_running():
            ...

        # Matar
        manager.kill_current()

    Internamente decide si usar EXE o Steam segun game.is_steam.
    Tambien gestiona los extra_apps del juego (apps auxiliares de arranque).
    """

    def __init__(self) -> None:
        self._current_proc: GameProcess | None = None
        self._extra_procs: list[subprocess.Popen] = []

    # ── API publica ───────────────────────────────────────────────────────

    def launch(self, game: "Game") -> GameProcess:
        """
        Lanza el juego. Decide automaticamente si es EXE o Steam.
        Tambien lanza los extra_apps definidos en el juego.

        Devuelve un GameProcess que puedes usar para poll()/wait()/terminate().

        Lanza ValueError si faltan datos obligatorios (exe o steam_app_id).
        Lanza FileNotFoundError si el .exe no existe en disco.
        Lanza RuntimeError si Steam no se puede lanzar.
        """
        if game.is_steam:
            proc = self._launch_steam(game)
        else:
            proc = self._launch_exe(game)

        self._current_proc = proc
        self._launch_extra_apps(game)

        config.LOG("ProcessManager: lanzado juego:", game.name)
        return proc

    def kill_current(self) -> None:
        """
        Mata el proceso activo y todos los extra_apps.
        No hace nada si no hay proceso activo.
        """
        if self._current_proc is not None:
            config.LOG("ProcessManager: matando proceso activo")
            self._current_proc.terminate()
            self._current_proc = None

        self._kill_extra_apps()

    def is_running(self) -> bool:
        """Devuelve True si hay un proceso activo que sigue en ejecucion."""
        if self._current_proc is None:
            return False
        return self._current_proc.poll() is None

    @property
    def current_proc(self) -> GameProcess | None:
        """Acceso de solo lectura al proceso activo actual."""
        return self._current_proc

    # ── Lanzamiento EXE ──────────────────────────────────────────────────

    def _launch_exe(self, game: "Game") -> GameProcess:
        """Lanza un juego como ejecutable directo (.exe)."""
        exe = game.exe_path.strip()

        if not exe:
            raise ValueError(
                f"El juego '{game.name}' no tiene ruta de ejecutable.")

        exe_path = Path(exe)
        if not exe_path.exists():
            raise FileNotFoundError(f"No se encuentra el ejecutable: {exe}")

        # Directorio de trabajo: el que dijo el usuario o la carpeta del exe
        cwd = game.working_dir.strip() or str(exe_path.parent)

        # Argumentos: separar por espacios
        # Nota: si necesitas args con espacios en su interior usa shlex.split
        args = game.args.strip().split() if game.args.strip() else []
        cmd = [str(exe_path)] + args

        config.LOG("Lanzando EXE:", cmd, "cwd:", cwd)

        try:
            popen = subprocess.Popen(
                cmd,
                cwd=cwd,
                creationflags=_creationflags()
            )
        except Exception as e:
            raise RuntimeError(f"Error al lanzar '{game.name}': {e}") from e

        return GameProcess(popen)

    # ── Lanzamiento Steam ─────────────────────────────────────────────────

    def _launch_steam(self, game: "Game") -> GameProcess:
        """
        Lanza un juego de Steam por AppID.
        Intenta encontrar steam.exe; si no lo encuentra usa el protocolo steam://.
        Despues intenta localizar el PID real del proceso del juego.
        """
        app_id = game.steam_app_id.strip()
        if not app_id:
            raise ValueError(f"El juego '{game.name}' no tiene Steam App ID.")

        kill_img = (game.steam_proc_name or "").strip().lower()

        # Referencia de tiempo y procesos antes de lanzar
        t0 = time.time()
        baseline_imgs = _tasklist_images()

        # Intentar lanzar Steam
        launched = self._launch_steam_exe(app_id)
        if not launched:
            launched = self._launch_steam_protocol(app_id)
        if not launched:
            raise RuntimeError(
                f"No se pudo lanzar el juego Steam '{game.name}' "
                f"(AppID: {app_id}). Comprueba que Steam esta instalado."
            )

        # Intentar localizar el PID del juego con psutil
        pid, detected_img = _detect_proc_psutil(
            t0, timeout_s=config.STEAM_DETECT_TIMEOUT)

        if pid:
            proc = _SteamTrackedProc(pid=pid, img=kill_img or detected_img)
        else:
            # Fallback: buscar por diferencia de tasklist
            if not kill_img:
                kill_img = _detect_proc_tasklist(
                    baseline_imgs,
                    timeout_s=config.STEAM_DETECT_TIMEOUT
                )
            proc = _SteamTrackedProc(pid=0, img=kill_img)

        # Watcher para enganche tardio (juegos UE4/VR que tardan en arrancar)
        if proc.pid is None:
            t = threading.Thread(
                target=_steam_attach_watcher,
                args=(proc, t0, kill_img, 90),
                daemon=True
            )
            t.start()

        return GameProcess(proc)

    def _launch_steam_exe(self, app_id: str) -> bool:
        """Intenta lanzar el juego usando steam.exe directamente."""
        steam_paths = [
            r"C:\Program Files (x86)\Steam\steam.exe",
            r"C:\Program Files\Steam\steam.exe",
        ]
        for path_str in steam_paths:
            if Path(path_str).exists():
                try:
                    subprocess.Popen(
                        [path_str, "-applaunch", app_id],
                        creationflags=_creationflags()
                    )
                    config.LOG(
                        "Steam lanzado via steam.exe -applaunch", app_id)
                    return True
                except Exception as e:
                    config.LOG("WARN steam.exe fallo:", e)
        return False

    def _launch_steam_protocol(self, app_id: str) -> bool:
        """Fallback: lanza el juego usando el protocolo steam://."""
        try:
            url = f"steam://rungameid/{app_id}"
            os.startfile(url)  # type: ignore[attr-defined]
            config.LOG("Steam lanzado via protocolo:", url)
            return True
        except Exception as e:
            config.LOG("ERROR protocolo Steam:", e)
            return False

    # ── Extra apps ────────────────────────────────────────────────────────

    def _launch_extra_apps(self, game: "Game") -> None:
        """
        Lanza las aplicaciones auxiliares definidas en game.extra_apps.
        Son apps que deben correr junto al juego (ej: overlays VR).
        Los errores al lanzar una extra_app se loguean pero no detienen el flujo.
        """
        self._extra_procs.clear()

        for app_path_str in (game.extra_apps or []):
            app_path_str = app_path_str.strip()
            if not app_path_str:
                continue
            if not Path(app_path_str).exists():
                config.LOG("WARN extra_app no existe:", app_path_str)
                continue
            try:
                p = subprocess.Popen(
                    [app_path_str],
                    creationflags=_creationflags()
                )
                self._extra_procs.append(p)
                config.LOG("Extra app lanzada:", app_path_str)
            except Exception as e:
                config.LOG("WARN extra_app fallo:", app_path_str, ":", e)

    def _kill_extra_apps(self) -> None:
        """Mata todas las aplicaciones auxiliares activas."""
        for p in self._extra_procs:
            try:
                if p.poll() is None:
                    _kill_tree(p.pid)
            except Exception as e:
                config.LOG("WARN al matar extra_app:", e)
        self._extra_procs.clear()
