"""Shared section geometry for the standard library and authored scene snapshots."""

from __future__ import annotations

import re
from typing import Any

from tuba.model import IBeamSection, PipeSection, TubaModel
from tuba.sections import SectionCatalog


def profile_catalog() -> dict[str, Any]:
    """Export bundled profiles with derived geometry, without project or solver state."""
    from tuba.visualization.builders._objects import _section_profile_metadata

    catalog = []
    sections = SectionCatalog.default()
    for row in sections.list_ibeam_profiles():
        family = re.sub(r"\d.*", "", row.name)
        if family == "HE":
            family += row.name[-1]
        section = IBeamSection(row.name, row.name, dict(row.properties))
        catalog.append({"name": row.name, "family": family,
                        "profile": _section_profile_metadata(section)})
    for row in sections.list_pipe_profiles():
        section = PipeSection(row.name, row.OD, row.WT)
        catalog.append({"name": row.name, "family": "Pipe", "dn": row.dn,
                        "nps": row.nps, "schedule": row.schedule,
                        "profile": _section_profile_metadata(section),
                        "source": "ASME B36.10 — InfraBuild pipe chart (October 2022, page 3). Nominal dimensions in mm; manufacturing tolerances and corrosion allowance are excluded.",
                        "source_url": "https://www.infrabuild.com/wp-content/uploads/sites/8/2019/05/IBSC_Pipe-Fittings-Data-Charts_A4_Oct22_24pp.pdf"})
    return {"ok": True, "catalog": catalog,
            "source": "Tuba bundled IBeam.input / IBeam.output",
            "source_note": "Imported profile tables; original geometry source and Code_Aster version are not recorded."}


def model_sections(model: TubaModel | None) -> list[dict[str, Any]]:
    """Snapshot every declared section, including sections not assigned to an element."""
    from tuba.visualization.builders._objects import _section_profile_metadata

    return [{"name": section.name, "profile_name": getattr(section, "profile_name", None),
             "source_line": section.source_line, "profile": _section_profile_metadata(section)}
            for section in (model.sections.values() if model is not None else ())]
