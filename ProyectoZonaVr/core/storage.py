from collections.abc import Callable
import threading
from pathlib import Path


class Storage:
    """
    Gestiona la carga y guardado de cualquier archivo JSON de la app.
    Usa escritura atómica (.tmp → validar → rotar backups → reemplazar).
    Thread-safe mediante un Lock interno.
    """

    # ── Constantes ─────────────────────────────────────────────────────────
    LOCK: threading.Lock          # evita escrituras simultáneas
    MAX_BACKUPS: int = 2          # cuántos .bak mantener (.bak y .bak2)

    # ── Métodos ────────────────────────────────────────────────────────────
    @staticmethod
    def load(path: Path, default_factory: Callable) -> dict:
        """
        Carga el JSON en `path`. Si falla, intenta .bak y .bak2.
        Si todo falla, devuelve default_factory().
        """
    @staticmethod
    def save(path: Path, data: dict) -> None:
        """
        Guarda `data` en `path` de forma atómica.
        Escribe a .tmp → valida JSON → rota backups → os.replace().
        """
    @staticmethod
    def _rotate_backups(path: Path) -> None:
        """Mueve .bak -> .bak2 y el archivo actual -> .bak."""
    @staticmethod
    def _is_valid_json(path: Path) -> bool:
        """Devuelve True si el archivo existe y es JSON válido."""
