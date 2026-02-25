from dataclasses import dataclass, field
from typing import List
from config import COLA_TURN_DURATION


@dataclass
class QueueEntry:
    id: str                    # identificador único del grupo
    group_name: str            # nombre del grupo (editable)
    num_players: int           # número de personas (editable)
    map_name: str              # mapa que van a jugar
    position: int              # orden en la cola (0 = en máquina)

    # ── Estado del timer ───────────────────────────────────────────────────
    timer_state: str = "idle"
    # Valores posibles: "idle" | "running" | "paused" | "finished"

    elapsed_sec: int = 0       # segundos transcurridos del turno actual
    duration_sec: int = COLA_TURN_DURATION  # duración asignada al turno


@dataclass
class Machine:
    id: str               # identificador único
    name: str             # nombre visible (ej: "Arena 1", "Racing")
    queue: List[QueueEntry] = field(default_factory=list)
    # la cola ordenada por posición; index 0 = turno activo
