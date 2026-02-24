# ── Rutas ──────────────────────────────────────────────────────────────────
# APP_DIR: Path          # directorio del ejecutable
# DATA_DIR: Path         # datos persistentes (JSON, logs)
# ARENA_JSON: Path       # games data para Arena
# RACING_JSON: Path      # games data para Racing
# COLA_JSON: Path        # datos de máquinas y colas
# LOG_PATH: Path         # archivo de log

# ── Aplicación ─────────────────────────────────────────────────────────────
APP_NAME: str = "ZonaVRLauncher"
ADMIN_HOTKEY: str = "ctrl+a"          # atajo para abrir ajustes
CLOSE_HOTKEY: str = "ctrl+e"          # atajo para cerrar launcher
ESC_HOLD_SECONDS: int = 3             # segundos para cerrar juego con ESC

# ── Colores (tema compartido) ───────────────────────────────────────────────
COLOR_BG: str = "#154E93"             # azul fondo
COLOR_DARK: str = "#0F3D7A"           # azul oscuro (botones)
COLOR_WHITE: str = "#FFFFFF"
COLOR_YELLOW: str = "#FFF200"         # borde tarjeta seleccionada
COLOR_TEXT: str = "#FFFFFF"
COLOR_OVERLAY: str = "#00000088"      # negro semitransparente para timer overlay

# ── Tarjetas de juego ────────────────────────────────────────────────────────
CARD_W: int = 420                     # ancho tarjeta en px
CARD_H: int = 560                     # alto tarjeta en px
CARD_BORDER: int = 12
CARD_RADIUS: int = 28
CARDS_PER_ROW: int = 3                # tarjetas por fila (siempre 3)

# ── Racing ──────────────────────────────────────────────────────────────────
RACING_SESSION_OPTIONS: list[int] = [
    30 * 60, 60 * 60]   # 30 min y 1h en segundos
RACING_EXTEND_OPTIONS: list[int] = [
    30 * 60, 60 * 60]    # opciones para +tiempo

# ── Cola ────────────────────────────────────────────────────────────────────
# duración por defecto de un turno: 10 min en seg
COLA_TURN_DURATION: int = 10 * 60
COLA_SYNC_INTERVAL_MS: int = 1000    # cada cuánto se refresca la pantalla cliente

# prueba
