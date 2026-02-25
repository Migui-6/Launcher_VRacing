from dataclasses import dataclass, field


@dataclass
class Game:
    # ── Identidad ──────────────────────────────────────────────────────────
    id: str                        # timestamp único como string, ej: "1714000000000"
    name: str                      # nombre visible en la tarjeta
    order: int = 0                 # posición en el catálogo
    visible: bool = True           # si se muestra en el catálogo

    # ── Lanzamiento ────────────────────────────────────────────────────────
    exe_path: str = ""             # ruta al .exe
    args: str = ""                 # argumentos de línea de comandos
    # directorio de trabajo (por defecto, carpeta del .exe)
    working_dir: str = ""

    # ── Steam (opcional) ───────────────────────────────────────────────────
    is_steam: bool = False
    steam_app_id: str = ""
    steam_proc_name: str = ""      # nombre del proceso para poder matarlo

    # ── Apariencia ─────────────────────────────────────────────────────────
    cover_path: str = ""           # ruta a la imagen de portada

    # ── Comportamiento ─────────────────────────────────────────────────────
    delay_sec: int = 0             # segundos de espera antes de lanzar
    session_limit_sec: int = 0     # 0 = sin límite de tiempo

    # ── Tutorial ───────────────────────────────────────────────────────────
    tutorial_enabled: bool = False
    tutorial_video_path: str = ""
    tutorial_duration_sec: int = 0

    # ── Extra: aplicaciones adicionales de arranque ─────────────────────────
    extra_apps: list[str] = field(default_factory=list)
    # lista de rutas .exe que se lanzan junto con el juego (ej: overlay VR)
