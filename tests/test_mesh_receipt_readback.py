"""Portable receipt-corruption regressions, not solver-result qualification."""
import h5py
import meshio
import numpy as np
import pytest

from tuba.analysis.mesh import AnalysisMesh, MeshElementSource
from tuba.visualization.preview.mesh import atomic_json, digest, validate_artifact


FAMILIES = {
    "hexahedron20": ("H20", "volume_cell", 20, (0, 3, 2, 1, 4, 7, 6, 5, 9, 13, 11, 8, 17, 19, 18, 16, 10, 15, 14, 12)),
    "tetra10": ("T10", "volume_cell", 10, (0, 2, 1, 3, 6, 5, 4, 7, 8, 9)),
    "quad8": ("QU8", "volume_skin", 8, tuple(range(8))),
    "triangle6": ("TR6", "volume_skin", 6, tuple(range(6))),
    "triangle": ("TR3", "shell_cell", 3, tuple(range(3))),
    "line3": ("SE3", "native_element", 3, tuple(range(3))),
    "line": ("SE2", "native_element", 2, tuple(range(2))),
    "vertex": ("PO1", "reference_carrier", 1, (0,)),
}


def receipt(directory):
    atomic_json(directory / "manifest.json", {
        "schema": "tuba.mesh-job.v1", "identity": "fixture", "result_status": "mesh_only", "artifact": "mesh.med",
        "sha256": {name: digest(directory / name) for name in ("mesh.med", "analysis_mesh.json")},
    })


def geometry(file):
    return next(iter(next(iter(file["ENS_MAA"].values())).values()))


@pytest.fixture
def med_record(tmp_path):
    # Sparse tags, reversed native node order, two cells per family and reversed
    # cell order. Order-based hydration would either reject this or misidentify it.
    nodes = {f"VN{i * 10}": (i * .01, (i % 3) * .02, (i % 7) * .03) for i in range(1, 21)}
    node_ids = list(nodes)
    native_ids = list(reversed(node_ids))
    indices = {label: index for index, label in enumerate(native_ids)}
    elements, sources, blocks, native_tags = {}, {}, [], {}
    for index, (family, (_, role, count, order)) in enumerate(FAMILIES.items()):
        labels = [f"VM{100 + index * 10 + offset}" for offset in (1, 2)]
        for label in labels:
            elements[label] = tuple(node_ids[:count])
            sources[label] = MeshElementSource(label, "element:fixture", role)
        blocks.append((family, [[indices[elements[label][i]] for i in order] for label in reversed(labels)]))
        native_tags[family] = [int(label[2:]) for label in reversed(labels)]
    record = AnalysisMesh("fixture", 0, "Code_Aster", nodes, elements, {}, {}, sources,
                          mesh_review={"schema": "tuba.mesh-review.v1", "quality": {"invalid_count": 0}})
    meshio.write(tmp_path / "mesh.med", meshio.Mesh([nodes[label] for label in native_ids], blocks), file_format="med")
    with h5py.File(tmp_path / "mesh.med", "r+") as file:
        frame = geometry(file)
        frame["NOE"].create_dataset("NUM", data=[int(label[2:]) for label in native_ids])
        for family, (med_type, *_) in FAMILIES.items():
            frame["MAI"][med_type].create_dataset("NUM", data=native_tags[family])
    atomic_json(tmp_path / "analysis_mesh.json", record.to_dict())
    receipt(tmp_path)
    return tmp_path, record


def test_native_id_mapping_preserves_sparse_reordered_mixed_families(med_record):
    directory, record = med_record
    actual = validate_artifact(directory, "fixture")
    assert actual.nodes == record.nodes
    assert actual.elements == record.elements


@pytest.mark.parametrize("corruption", ["translated", "midside", "fractional", "node_tag", "cell_tag", "duplicate_tag", "missing_tags", "family", "missing_cell", "names_disagree", "extra_frame"])
def test_matching_hashes_cannot_promote_a_mismatched_med_record(med_record, corruption):
    directory, _ = med_record
    with h5py.File(directory / "mesh.med", "r+") as file:
        frame = geometry(file)
        if corruption == "translated":
            frame["NOE"]["COO"][:] += 100
        elif corruption == "midside":
            # Keep the node set unchanged; swap a TETRA10 corner with a midside.
            values = frame["MAI"]["T10"]["NOD"][:].reshape((2, 10), order="F")
            values[:, [0, 4]] = values[:, [4, 0]]
            frame["MAI"]["T10"]["NOD"][:] = values.ravel(order="F")
        elif corruption == "fractional":
            group = frame["MAI"]["SE3"]
            values = group["NOD"][:].astype(float) + .25
            attrs = dict(group["NOD"].attrs)
            del group["NOD"]
            dataset = group.create_dataset("NOD", data=values)
            for key, value in attrs.items():
                dataset.attrs[key] = value
        elif corruption == "node_tag":
            frame["NOE"]["NUM"][0] = 999
        elif corruption == "cell_tag":
            frame["MAI"]["SE3"]["NUM"][0] = 999
        elif corruption == "duplicate_tag":
            frame["NOE"]["NUM"][0] = frame["NOE"]["NUM"][1]
        elif corruption == "missing_tags":
            del frame["NOE"]["NUM"]
        elif corruption == "family":
            frame["MAI"].move("TR3", "QU4")
            # Supply actual QUAD4 arity, keeping MED readable but changing family.
            group = frame["MAI"]["QU4"]
            del group["NOD"]
            nod = group.create_dataset("NOD", data=np.array([1, 1, 2, 2, 3, 3, 4, 4]))
            nod.attrs["NBR"] = 2
        elif corruption == "missing_cell":
            del frame["MAI"]["SE2"]
        elif corruption == "extra_frame":
            file.copy(frame, frame.parent, name="another_geometry_frame")
        else:
            names = np.array([list(str(i).ljust(16).encode()) for i in range(1, 21)], dtype=np.int8)
            frame["NOE"].create_dataset("NOM", data=names)
    receipt(directory)  # Deliberately refresh the digest: readback must still reject.
    with pytest.raises(ValueError, match="MED"):
        validate_artifact(directory, "fixture")


def test_numeric_names_alone_preserve_native_id_mapping(med_record):
    directory, _ = med_record
    with h5py.File(directory / "mesh.med", "r+") as file:
        frame = geometry(file)
        for group in [frame["NOE"], *frame["MAI"].values()]:
            names = np.array([list(str(int(tag)).ljust(16).encode()) for tag in group["NUM"][:]], dtype=np.int8)
            group.create_dataset("NOM", data=names)
            del group["NUM"]
    receipt(directory)
    assert validate_artifact(directory, "fixture").nodes


def test_file_changes_during_readback_are_rejected(med_record, monkeypatch):
    directory, _ = med_record
    read = meshio.read
    def changing_read(path):
        native = read(path)
        # Same topology and coordinates, different bytes after the initial hash.
        with h5py.File(path, "r+") as file:
            file.attrs["external_writer"] = "changed during readback"
        return native
    monkeypatch.setattr(meshio, "read", changing_read)
    with pytest.raises(ValueError, match="changed during verified import"):
        validate_artifact(directory, "fixture")
