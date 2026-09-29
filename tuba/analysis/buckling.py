"""Linear buckling results: the critical load factors and the mode shapes they came with.

A critical factor is the multiple of the load case's own prestress at which a buckling
mode appears. It is a *reference load*, not a design verdict. It comes from a
linearised idealisation of a perfect frame with no initial imperfection, and a real
column buckles at a fraction of it; Eurocode 3 reduces it by a reduction factor and
carries a buckling curve on top. The factors here are also built on a first-order
prestress, which understates column compression, so they are optimistic in a way that
compounds with the missing imperfection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence


def _finite(value: Any, what: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Buckling {what} must be a finite number, got {value!r}.")
    return number


@dataclass(frozen=True)
class BucklingMode:
    """One buckling mode: its load factor and, when exported, its nodal shape.

    ``critical_factor`` is the magnitude. ``raw_eigenvalue`` is what Code_Aster
    reported, which is negative because of the sign convention of the
    ``K phi = -lambda Kg phi`` pencil; it is kept so a reviewer can see that the
    reported value was not quietly re-signed.

    ``node_displacements`` maps a node id to its six mode-shape components
    ``(DX, DY, DZ, DRX, DRY, DRZ)``. Mode shapes are dimensionless and arbitrary in
    scale, so they are for shape only and must not be read as a displacement.
    """

    mode: int
    critical_factor: float
    raw_eigenvalue: float
    node_displacements: dict[str, tuple[float, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.mode, int) or isinstance(self.mode, bool) or self.mode < 1:
            raise ValueError(f"Buckling mode number must be a positive integer, got {self.mode!r}.")
        object.__setattr__(self, "critical_factor", _finite(self.critical_factor, "critical factor"))
        object.__setattr__(self, "raw_eigenvalue", _finite(self.raw_eigenvalue, "raw eigenvalue"))
        if self.critical_factor <= 0.0:
            raise ValueError(
                f"Buckling mode {self.mode} critical factor must be positive, "
                f"got {self.critical_factor!r}."
            )
        object.__setattr__(
            self,
            "node_displacements",
            {key: tuple(float(v) for v in value) for key, value in self.node_displacements.items()},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "critical_factor": self.critical_factor,
            "raw_eigenvalue": self.raw_eigenvalue,
            "node_displacements": {
                key: list(value) for key, value in sorted(self.node_displacements.items())
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BucklingMode":
        return cls(
            mode=int(data["mode"]),
            critical_factor=float(data["critical_factor"]),
            raw_eigenvalue=float(data["raw_eigenvalue"]),
            node_displacements={
                str(key): tuple(value)
                for key, value in (data.get("node_displacements") or {}).items()
            },
        )


@dataclass(frozen=True)
class BucklingResult:
    """The buckling eigenproblem solved for one load case.

    ``modes`` is ordered by the solver's own eigenvalue search, not re-sorted: the
    governing mode is the smallest factor, and re-ordering here would hide which end
    of the search it came from. Use :attr:`governing_factor` to ask that question.
    """

    modes: tuple[BucklingMode, ...] = ()
    requested_modes: int = 0
    method: str = "TRI_DIAG"
    #: Free-form solver notes, e.g. a warning that fewer modes exist than were asked for.
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "modes", tuple(self.modes))
        object.__setattr__(self, "notes", tuple(self.notes))
        seen = [mode.mode for mode in self.modes]
        if len(set(seen)) != len(seen):
            raise ValueError(f"Buckling mode numbers must be unique, got {seen!r}.")
        if self.requested_modes < 0:
            raise ValueError(
                f"Buckling requested_modes must not be negative, got {self.requested_modes!r}."
            )

    def __bool__(self) -> bool:
        return bool(self.modes)

    def __len__(self) -> int:
        return len(self.modes)

    @property
    def critical_factors(self) -> tuple[float, ...]:
        """The load factors in solver order."""
        return tuple(mode.critical_factor for mode in self.modes)

    @property
    def governing_factor(self) -> float | None:
        """The smallest load factor found: the first mode to buckle.

        This is the number a stability statement should quote, and it is only as
        good as the idealisation behind it.
        """
        if not self.modes:
            return None
        return min(mode.critical_factor for mode in self.modes)

    def governing_mode(self) -> BucklingMode | None:
        if not self.modes:
            return None
        return min(self.modes, key=lambda mode: mode.critical_factor)

    def to_dict(self) -> dict[str, Any]:
        return {
            "modes": [mode.to_dict() for mode in self.modes],
            "requested_modes": int(self.requested_modes),
            "method": str(self.method),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BucklingResult":
        modes: Sequence[Mapping[str, Any]] = data.get("modes") or ()
        return cls(
            modes=tuple(BucklingMode.from_dict(entry) for entry in modes),
            requested_modes=int(data.get("requested_modes", 0)),
            method=str(data.get("method", "TRI_DIAG")),
            notes=tuple(data.get("notes") or ()),
        )
