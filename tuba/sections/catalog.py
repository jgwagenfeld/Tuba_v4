"""Catalogs for structural section profile data."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class IBeamProfile:
    """I-beam profile dimensions and solver properties in SI units."""

    name: str
    dimensions: dict[str, float]
    properties: dict[str, float]


@dataclass(frozen=True)
class PipeProfile:
    """Nominal pipe size with explicit outside diameter and wall in metres."""

    name: str
    dn: int
    nps: str
    schedule: str
    OD: float
    WT: float


class SectionCatalog:
    """Deep module for section profile lookup."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._ibeam_profiles: dict[str, IBeamProfile] | None = None
        self._pipe_profiles: dict[str, PipeProfile] | None = None

    @classmethod
    def default(cls) -> "SectionCatalog":
        return cls(Path(__file__).parent / "data")

    def list_ibeam_profiles(self) -> tuple[IBeamProfile, ...]:
        """All available profiles in the catalog's engineering size order."""
        return tuple(self._load_ibeam_profiles().values())

    def list_pipe_profiles(self) -> tuple[PipeProfile, ...]:
        """ASME B36.10 dimensions from InfraBuild's October 2022 chart, page 3.

        Blank schedule cells are unavailable; STD and XS stay distinct from
        Sch 40 and Sch 80 because they diverge at larger nominal sizes.
        https://www.infrabuild.com/wp-content/uploads/sites/8/2019/05/IBSC_Pipe-Fittings-Data-Charts_A4_Oct22_24pp.pdf
        """
        if self._pipe_profiles is None:
            profiles = {}
            with (self.data_dir / "Pipe.input").open(encoding="utf-8") as stream:
                for row in csv.DictReader(stream):
                    dn, od = int(row["DN"]), round(float(row["OD"]) / 1000, 8)
                    for schedule, value in row.items():
                        if schedule in {"DN", "NPS", "OD"} or not value:
                            continue
                        wt = round(float(value) / 1000, 8)
                        name = f"DN{dn}_{'SCH' if schedule.isdigit() else ''}{schedule}"
                        if not (dn > 0 and math.isfinite(od) and math.isfinite(wt) and 0 < 2 * wt < od):
                            raise ValueError(f"Invalid pipe dimensions for {name}: expected finite OD > 2 * WT > 0.")
                        if name in profiles:
                            raise ValueError(f"Duplicate pipe profile {name} in section catalog.")
                        profiles[name] = PipeProfile(name, dn, row["NPS"], schedule, od, wt)
            self._pipe_profiles = profiles
        return tuple(self._pipe_profiles.values())

    def get_pipe_profile(self, profile_name: str) -> PipeProfile:
        self.list_pipe_profiles()
        try:
            return self._pipe_profiles[profile_name]
        except KeyError as exc:
            raise ValueError(f"Pipe profile {profile_name!r} not found in section catalog.") from exc

    def get_ibeam_profile(self, profile_name: str) -> IBeamProfile:
        profiles = self._load_ibeam_profiles()
        try:
            return profiles[profile_name]
        except KeyError as exc:
            raise ValueError(f"I-beam profile {profile_name!r} not found in section catalog.") from exc

    def _load_ibeam_profiles(self) -> Mapping[str, IBeamProfile]:
        if self._ibeam_profiles is None:
            self._ibeam_profiles = _load_ibeam_profiles(self.data_dir)
        return self._ibeam_profiles


def _load_ibeam_profiles(data_dir: Path) -> dict[str, IBeamProfile]:
    dimensions_by_name = _load_ibeam_dimensions(data_dir / "IBeam.input")
    properties_by_name = _load_ibeam_properties(data_dir / "IBeam.output")
    profiles = {}
    for name, dimensions in dimensions_by_name.items():
        properties = {}
        properties.update(dimensions)
        properties.update(properties_by_name.get(name, {}))
        profiles[name] = IBeamProfile(name=name, dimensions=dimensions, properties=properties)
    return profiles


def _load_ibeam_dimensions(path: Path) -> dict[str, dict[str, float]]:
    profiles: dict[str, dict[str, float]] = {}
    with path.open(mode="r", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            name = row["NAME"]
            profiles[name] = {
                "H": float(row["H"]) * 1e-3,
                "B": float(row["B"]) * 1e-3,
                "Tw": float(row["Tw"]) * 1e-3,
                "Tf": float(row["Tf"]) * 1e-3,
                "R": float(row["R"]) * 1e-3,
            }
    return profiles


def _load_ibeam_properties(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}

    conversions = {
        "A": 1e-6,
        "IY": 1e-12,
        "IZ": 1e-12,
        "AY": 1.0,
        "AZ": 1.0,
        "EY": 1e-3,
        "EZ": 1e-3,
        "JX": 1e-12,
        "JG": 1e-12,
        "IYR2": 1e-12,
        "IZR2": 1e-12,
        "RY": 1e-3,
        "RZ": 1e-3,
        "RT": 1e-3,
        "ALPHA": 1.0,
    }
    profiles: dict[str, dict[str, float]] = {}
    with path.open(mode="r", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            name = row["NAME"]
            properties = {}
            for key, value in row.items():
                if key == "NAME":
                    continue
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    continue
                if key in conversions:
                    numeric_value *= conversions[key]
                    properties[key] = numeric_value
            profiles[name] = properties
    return profiles
