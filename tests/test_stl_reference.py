"""Actual STL bytes, placement and reference-only registration."""

import math
import struct

import pytest

from tuba import Model


def write_ascii(path, triangles):
    lines = ["solid reference"]
    for triangle in triangles:
        lines.extend(["facet normal 0 0 1", "outer loop"])
        lines.extend("vertex " + " ".join(map(str, point)) for point in triangle)
        lines.extend(["endloop", "endfacet"])
    lines.append("endsolid reference")
    path.write_text("\n".join(lines), encoding="ascii")
    return path


def write_binary(path, triangles, header=b"solid binary reference"):
    payload = bytearray(header.ljust(80, b" ") + struct.pack("<I", len(triangles)))
    for triangle in triangles:
        payload.extend(struct.pack("<12fH", 0, 0, 1, *[v for p in triangle for v in p], 0))
    path.write_bytes(payload)
    return path


@pytest.mark.parametrize("writer", [write_ascii, write_binary])
def test_ascii_and_solid_binary_preserve_actual_local_triangle(tmp_path, writer):
    from tuba.geometry.stl_reference import inspect_stl_reference

    path = writer(tmp_path / "part.stl", [[[10, 20, 30], [12, 20, 30], [10, 23, 30]]])
    metadata = inspect_stl_reference(path)
    points = [metadata["mesh_vertices_local"][i] for i in metadata["mesh_faces"][0]]
    assert points == [[10, 20, 30], [12, 20, 30], [10, 23, 30]]
    assert metadata["local_bounds"] == [10, 20, 30, 12, 23, 30]
    assert metadata["inspection"] == dict(triangle_count=1, vertex_count=3,
        boundary_edges=3, nonmanifold_edges=0, degenerate_faces=0, closed_surface=False)


def test_topology_reports_degenerate_and_nonmanifold_faces(tmp_path):
    from tuba.geometry.stl_reference import inspect_stl_reference

    triangles = [[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                 [[1, 0, 0], [0, 0, 0], [0, 0, 1]],
                 [[0, 0, 0], [1, 0, 0], [0, -1, 0]],
                 [[2, 0, 0], [3, 0, 0], [4, 0, 0]]]
    metadata = inspect_stl_reference(write_ascii(tmp_path / "part.stl", triangles))
    assert metadata["inspection"]["nonmanifold_edges"] == 1
    assert metadata["inspection"]["degenerate_faces"] == 1
    assert metadata["inspection"]["closed_surface"] is False


def test_duplicate_triangles_do_not_masquerade_as_closed_shell(tmp_path):
    from tuba.geometry.stl_reference import inspect_stl_reference

    triangle = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    metadata = inspect_stl_reference(write_ascii(tmp_path / "duplicate.stl", [triangle, triangle]))
    assert metadata["inspection"]["boundary_edges"] == 0
    assert metadata["inspection"]["closed_surface"] is False


@pytest.mark.parametrize("payload", [b"", b"solid bad\nvertex 0 0 0\nendsolid bad",
    b"solid bad\nfacet normal 0 0 1\nouter loop\nvertex nan 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid bad",
    b"solid bad\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nendloop\nendfacet\nendsolid bad"])
def test_invalid_ascii_is_rejected(tmp_path, payload):
    from tuba.geometry.stl_reference import inspect_stl_reference

    path = tmp_path / "bad.stl"
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        inspect_stl_reference(path)


@pytest.mark.parametrize("corruption", ["truncated", "extra", "nonfinite", "count"])
def test_invalid_binary_is_rejected(tmp_path, corruption):
    from tuba.geometry.stl_reference import inspect_stl_reference

    path = write_binary(tmp_path / "bad.stl", [[[0, 0, 0], [1, 0, 0], [0, 1, 0]]])
    payload = bytearray(path.read_bytes())
    if corruption == "truncated":
        payload.pop()
    elif corruption == "extra":
        payload.extend(b"extra")
    elif corruption == "nonfinite":
        payload[96:100] = struct.pack("<f", float("inf"))
    else:
        payload[80:84] = struct.pack("<I", 100000000)
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        inspect_stl_reference(path)


def test_input_limit_rejects_instead_of_truncating(tmp_path, monkeypatch):
    import tuba.geometry.stl_reference as stl

    path = write_binary(tmp_path / "part.stl", [[[0, 0, 0], [1, 0, 0], [0, 1, 0]]])
    monkeypatch.setattr(stl, "MAX_STL_BYTES", 100)
    with pytest.raises(ValueError, match="limit"):
        stl.inspect_stl_reference(path)
    monkeypatch.setattr(stl, "MAX_STL_BYTES", 1000)
    monkeypatch.setattr(stl, "MAX_STL_TRIANGLES", 0)
    with pytest.raises(ValueError, match="triangle"):
        stl.inspect_stl_reference(path)


def test_reference_registration_preserves_scale_placement_digest_and_no_analysis(tmp_path):
    from tuba.geometry.stl_reference import import_stl_reference

    path = write_ascii(tmp_path / "part.stl", [[[0, 0, 0], [1000, 0, 0], [0, 1000, 0]]])
    model = Model(project_name="reference")
    component = import_stl_reference(model, path, id="vessel", unit_scale_to_m=.001,
        placement={"origin": [2, 3, 4], "rotation": [math.sqrt(.5), 0, 0, math.sqrt(.5)]})
    asset = model.cad_assets[component.asset.id]
    assert component.role == "reference"
    assert component.status == "reviewed"
    assert asset.source_format == "STL"
    assert asset.unit_scale_to_m == .001
    assert len(asset.content_digest) == 64
    assert asset.placement["origin"] == [2, 3, 4]
    assert asset.metadata["local_bounds"] == [0, 0, 0, 1000, 1000, 0]
    assert not model.analysis_regions and not model.ports
    assert Model.from_dict(model.to_dict()).cad_assets[asset.id].to_dict() == asset.to_dict()
    with pytest.raises(ValueError, match="already exists"):
        import_stl_reference(model, path, id="vessel", unit_scale_to_m=.001)


@pytest.mark.parametrize("scale", [0, -1, float("nan"), float("inf"), True, "0.001"])
def test_invalid_scale_does_not_mutate_model(tmp_path, scale):
    from tuba.geometry.stl_reference import import_stl_reference

    path = write_ascii(tmp_path / "part.stl", [[[0, 0, 0], [1, 0, 0], [0, 1, 0]]])
    model = Model(project_name="reference")
    with pytest.raises(ValueError, match="scale"):
        import_stl_reference(model, path, id="bad", unit_scale_to_m=scale)
    assert not model.cad_assets and not model.imported_components


def test_invalid_placement_does_not_leave_partial_asset(tmp_path):
    from tuba.geometry.stl_reference import import_stl_reference

    path = write_ascii(tmp_path / "part.stl", [[[0, 0, 0], [1, 0, 0], [0, 1, 0]]])
    model = Model(project_name="reference")
    with pytest.raises(ValueError):
        import_stl_reference(model, path, id="bad", unit_scale_to_m=1,
                             placement={"rotation": [0, 0, 0, 0]})
    assert not model.cad_assets and not model.imported_components


@pytest.mark.parametrize("scale,placement", [(1e308, None),
    (1, {"origin": [1e300, 1e300, 1e300]})])
def test_scale_and_placement_must_preserve_representable_actual_geometry(tmp_path, scale, placement):
    from tuba.geometry.stl_reference import import_stl_reference

    path = write_ascii(tmp_path / "part.stl", [[[0, 0, 0], [1000, 0, 0], [0, 1000, 0]]])
    model = Model(project_name="reference")
    with pytest.raises(ValueError, match="scale/placement"):
        import_stl_reference(model, path, id="bad", unit_scale_to_m=scale, placement=placement)
    assert not model.cad_assets and not model.imported_components
