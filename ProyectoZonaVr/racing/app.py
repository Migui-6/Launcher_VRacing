from dataclasses import dataclass
from ProyectoZonaVr.models.game import Game


@dataclass
class AppData:
    settings: dict        # configuración general {"fullscreen": True, ...}
    games: list[Game]     # catálogo de juegos
