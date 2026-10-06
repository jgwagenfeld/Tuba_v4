"""Optional RMED/HDF5 inspection helpers for Code_Aster artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _require_h5py():
    try:
        import h5py
    except ImportError as exc:
        raise ImportError("h5py is required for RMED inspection. Install tuba[code-aster-rmed].") from exc
    return h5py


def read_rmed_mesh_summary(path: str | Path) -> dict[str, Any]:
    h5py = _require_h5py()
    with h5py.File(path, "r") as f:
        mesh_root = f["ENS_MAA"]
        mesh_name = next(iter(mesh_root.keys()))
        mesh = mesh_root[mesh_name]
        # MED 3/4 put geometry inside a time-step group. Older exports put
        # NOE/MAI directly under the named mesh. Do not confuse field groups
        # with geometry or silently pick a frame from a moving mesh.
        if "NOE" not in mesh:
            frames = [group for group in mesh.values() if isinstance(group, h5py.Group) and "NOE" in group]
            if len(frames) != 1:
                raise ValueError("RMED mesh summary requires exactly one geometry frame.")
            mesh = frames[0]
        node_count = int(mesh["NOE"]["COO"].attrs["NBR"])
        element_types = {}
        element_count = 0
        if "MAI" in mesh:
            for med_type, group in mesh["MAI"].items():
                count = int(group["NOD"].attrs["NBR"])
                element_types[med_type] = count
                element_count += count
        return {
            "mesh_name": mesh_name,
            "node_count": node_count,
            "element_count": element_count,
            "element_types": element_types,
        }
