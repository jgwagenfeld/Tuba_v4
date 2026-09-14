"""Data interchange for externally evaluated stress checks. No code calculations."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ElementComplianceResult:
    """Compliance evaluation result for one element end."""

    element_id: str
    node_id: str

    # Sustained stress
    sustained_stress: float  # [Pa]
    sustained_allowable: float  # S_h [Pa]
    sustained_ratio: float  # S_L / S_h
    sustained_pass: bool

    # Expansion stress
    expansion_stress: float  # [Pa]
    expansion_allowable: float  # S_A [Pa]
    expansion_ratio: float  # S_E / S_A
    expansion_pass: bool

    # ---- Intermediate values stored for traceability ----
    pressure: float = 0.0
    Do: float = 0.0
    t: float = 0.0
    Z: float = 0.0
    i_i: float = 1.0
    i_o: float = 1.0
    k: float = 1.0
    h: float = 0.0
    M_i: float = 0.0
    M_o: float = 0.0
    M_t: float = 0.0
    moment_basis: str = "resultant_in_plane"
    S_h: float = 0.0
    S_c: float = 0.0
    f: float = 1.0


@dataclass
class ComplianceReport:
    """User-supplied stress-check results; Tuba does not evaluate a piping standard."""

    results: List[ElementComplianceResult] = field(default_factory=list)
    load_case: Optional[str] = None
    code_name: str = "User-defined checks"
    code_edition: str = ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def overall_pass(self) -> Optional[bool]:
        """Verdict, or ``None`` when no element ends were evaluated."""
        if not self.results:
            return None
        return all(r.sustained_pass and r.expansion_pass for r in self.results)

    @property
    def worst_sustained_ratio(self) -> Optional[float]:
        if not self.results:
            return None
        return max(r.sustained_ratio for r in self.results)

    @property
    def worst_expansion_ratio(self) -> Optional[float]:
        if not self.results:
            return None
        return max(r.expansion_ratio for r in self.results)
