"""tuba.solver.aster_mesh — Code_Aster mesh (.mail) + bend geometry.

Split out of tuba.solver.aster (behaviour-preserving). ``_MeshWriterMixin`` is
mixed into ``CodeAsterSolver`` so its methods keep ``self`` access to solver
state (``_BEND_SEGMENTS``, ``_ASTER_ENTITY_NAME_LEN``).
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

import numpy as np

from tuba.model import Element, TubaModel
from tuba.analysis import AnalysisMesh, MeshElementSource, MeshNodeSource
from tuba.refs import EntityRef
from tuba.solver.modelisation import PipeModelization, modelisation_assignments
from tuba.solver.aster_contact import shoes

logger = logging.getLogger(__name__)


class _SegmentMidpoint(NamedTuple):
    node_id: str
    start_node_id: str
    end_node_id: str
    source_element_id: str
    segment_index: int
    coords: np.ndarray



def _rotate_about_axis(vector: np.ndarray, unit_axis: np.ndarray, angle: float) -> np.ndarray:
    """Rodrigues rotation of ``vector`` about a unit axis through the origin."""
    cos_angle = np.cos(angle)
    return (
        vector * cos_angle
        + np.cross(unit_axis, vector) * np.sin(angle)
        + unit_axis * float(np.dot(unit_axis, vector)) * (1.0 - cos_angle)
    )


class _MeshWriterMixin:
    def _write_mail(
        self,
        model: TubaModel,
        path: Path,
        *,
        analysis_mesh_id: str | None = None,
        model_revision: int = 0,
        name_map: Callable[[str], str] | None = None,
    ) -> AnalysisMesh | None:
        """Generate the Code_Aster plain-text mesh file.

        Bends are discretised into circular-arc segments. Straight TUYAU
        pipes use SEG3; beams, beam-modelled pipes and cables use subdivided
        SEG2 spans so the solver can resolve curvature and cable sag.

        The mesh is written in the Aster native format
        (``FORMAT='ASTER'``) so that ``LIRE_MAILLAGE`` can read it
        directly.
        """
        lines: List[str] = []
        N = self._BEND_SEGMENTS  # shorthand
        map_name = name_map or (lambda value: value)
        contacts = shoes(model, self.pipe_modelization)

        # --- Ordered node / element lists ---------------------------------
        node_ids = list(model.nodes.keys())
        pipe_straights = [e for e in model.elements if e.type == "pipe_straight"]
        pipe_bends = [e for e in model.elements if e.type == "pipe_bend"]
        beam_elems = [e for e in model.elements if e.type == "beam"]
        bar_elems = [e for e in model.elements if e.type == "bar"]
        cable_elems = [e for e in model.elements if e.type == "cable"]

        straight_elems = pipe_straights + beam_elems + bar_elems + cable_elems
        bend_elems = pipe_bends

        # --- Compute intermediate bend-node coordinates via Gmsh ----------
        # Dict: elem.id → list of (node_name, coord_array) for the
        #        N-1 intermediate nodes along the arc.
        bend_intermediate: Dict[str, List[Tuple[str, np.ndarray]]] = {}

        if bend_elems:
            bend_intermediate = self._compute_bend_nodes(
                model, bend_elems, N
            )
        beam_pipes = self.pipe_modelization is PipeModelization.POU_D_T
        pipe_midpoints = {} if beam_pipes else self._pipe_straight_midpoint_nodes(model, pipe_straights)
        bend_segment_midpoints = {} if beam_pipes else self._pipe_bend_segment_midpoint_nodes(
            model,
            pipe_bends,
            bend_intermediate,
            N,
        )

        analysis_mesh = None
        if analysis_mesh_id is not None:
            analysis_mesh = self._build_analysis_mesh_from_mail_parts(
                model=model,
                mesh_id=analysis_mesh_id,
                model_revision=model_revision,
                node_ids=node_ids,
                pipe_straights=pipe_straights,
                pipe_bends=pipe_bends,
                beam_elems=beam_elems,
                bar_elems=bar_elems,
                cable_elems=cable_elems,
                bend_intermediate=bend_intermediate,
                pipe_midpoints=pipe_midpoints,
                bend_segment_midpoints=bend_segment_midpoints,
                mail_path=path,
                n_segments=N,
            )

        straight_pairs = {elem.id: self._straight_segment_node_pairs(elem) for elem in straight_elems}

        # --- COOR_3D ------------------------------------------------------
        lines.append("COOR_3D")
        for contact in contacts:
            xyz = model.nodes[contact.support.node].coords - (1. + contact.support.gap) * np.asarray(contact.normal)
            lines.append(f"  {map_name(contact.ground)} " + ' '.join(f'{v:+.10E}' for v in xyz))
        for nid in node_ids:
            n = model.nodes[nid]
            x, y, z = n.coords
            lines.append(f"  {map_name(nid)}  {x:+.10E}  {y:+.10E}  {z:+.10E}")

        for elem in straight_elems:
            pairs = straight_pairs[elem.id]
            start, end = (model.nodes[nid].coords for nid in (elem.n1, elem.n2))
            for index, (_, _, node_id) in enumerate(pairs[:-1], start=1):
                coord = start + (end - start) * index / len(pairs)
                lines.append(f"  {map_name(node_id)} " + " ".join(f"{v:+.10E}" for v in coord))

        for elem in bend_elems:
            for name, coord in bend_intermediate[elem.id]:
                lines.append(
                    f"  {map_name(name)}  {coord[0]:+.10E}  "
                    f"{coord[1]:+.10E}  {coord[2]:+.10E}"
                )
        for midpoint in pipe_midpoints.values():
            coord = midpoint.coords
            lines.append(
                f"  {map_name(midpoint.node_id)}  {coord[0]:+.10E}  "
                f"{coord[1]:+.10E}  {coord[2]:+.10E}"
            )
        for midpoint in bend_segment_midpoints.values():
            coord = midpoint.coords
            lines.append(
                f"  {map_name(midpoint.node_id)}  {coord[0]:+.10E}  "
                f"{coord[1]:+.10E}  {coord[2]:+.10E}"
            )
        lines.append("FINSF")
        lines.append("")

        if contacts:
            lines.append('SEG2')
            for contact in contacts:
                lines.append(f' {map_name(contact.group)} {map_name(contact.ground)} {map_name(contact.support.node)}')
            lines.append('FINSF')
            for contact in contacts:
                lines.extend([f'GROUP_MA NOM={map_name(contact.group)}', map_name(contact.group), 'FINSF',
                              f'GROUP_NO NOM={map_name(contact.ground)}', map_name(contact.ground), 'FINSF'])

        # --- SEG3 for pipe straights --------------------------------------
        if pipe_straights and not beam_pipes:
            lines.append("SEG3")
            for elem in pipe_straights:
                midpoint = pipe_midpoints[elem.id]
                lines.append(
                    f"  {map_name(elem.id)}  {map_name(elem.n1)}  {map_name(elem.n2)}  {map_name(midpoint.node_id)}"
                )
            lines.append("FINSF")
            lines.append("")

        # --- SEG2 for non-pipe line elements ------------------------------
        non_pipe_straights = beam_elems + bar_elems + cable_elems + (pipe_straights if beam_pipes else [])
        if non_pipe_straights:
            lines.append("SEG2")
            for elem in non_pipe_straights:
                for segment_id, start, end in straight_pairs[elem.id]:
                    lines.append(f"  {map_name(segment_id)}  {map_name(start)}  {map_name(end)}")
            lines.append("FINSF")
            lines.append("")

        # --- SEG3 for bend subdivisions -----------------------------------
        if bend_elems:
            lines.append("SEG2" if beam_pipes else "SEG3")
            for elem in bend_elems:
                for segment_id, start, end in self._bend_segment_node_pairs(elem, N):
                    if beam_pipes:
                        lines.append(f"  {map_name(segment_id)}  {map_name(start)}  {map_name(end)}")
                        continue
                    midpoint = bend_segment_midpoints[segment_id]
                    lines.append(
                        f"  {map_name(segment_id)}  {map_name(midpoint.start_node_id)}  "
                        f"{map_name(midpoint.end_node_id)}  {map_name(midpoint.node_id)}"
                    )
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=PipeStraights -----------------------------------
        if pipe_straights:
            lines.append(f"GROUP_MA NOM={map_name('PipeStraights')}")
            for elem in pipe_straights:
                lines.extend(f"  {map_name(sid)}" for sid, _, _ in straight_pairs[elem.id])
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=PipeElbows --------------------------------------
        if bend_elems:
            lines.append(f"GROUP_MA NOM={map_name('PipeElbows')}")
            for elem in bend_elems:
                for i in range(N):
                    lines.append(f"  {map_name(f'{elem.id}_s{i}')}")
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=AllPipes ----------------------------------------
        all_pipe_ids: List[str] = []
        for e in pipe_straights:
            all_pipe_ids.extend(sid for sid, _, _ in straight_pairs[e.id])
        for e in bend_elems:
            all_pipe_ids.extend([f"{e.id}_s{i}" for i in range(N)])

        if all_pipe_ids:
            lines.append(f"GROUP_MA NOM={map_name('AllPipes')}")
            for eid in all_pipe_ids:
                lines.append(f"  {map_name(eid)}")
            lines.append("FINSF")
            lines.append("")

        for elem in straight_elems:
            lines.append(f"GROUP_MA NOM={map_name(elem.id)}")
            lines.extend(f"  {map_name(sid)}" for sid, _, _ in straight_pairs[elem.id])
            lines.append("FINSF")
            lines.append("")

        pipe_orientation_nodes: list[str] = []
        for elem in pipe_straights:
            pipe_orientation_nodes.append(elem.n1)
        for elem in bend_elems:
            pipe_orientation_nodes.append(elem.n1)
        if pipe_orientation_nodes:
            lines.append(f"GROUP_NO NOM={map_name('PipeOrientationNodes')}")
            orientation_node = next(iter(dict.fromkeys(pipe_orientation_nodes)))
            lines.append(f"  {map_name(orientation_node)}")
            lines.append("FINSF")
            lines.append("")

        poutre_line_elems = pipe_straights + beam_elems
        section_group_members: dict[str, list[str]] = {}
        for elem in poutre_line_elems:
            section_group_members.setdefault(elem.section, []).extend(sid for sid, _, _ in self._straight_segment_node_pairs(elem))
        for section_name, element_ids in section_group_members.items():
            lines.append(f"GROUP_MA NOM={map_name(self._section_group_name(section_name))}")
            for element_id in element_ids:
                lines.append(f"  {map_name(element_id)}")
            lines.append("FINSF")
            lines.append("")

        material_group_members: dict[str, list[str]] = {}
        for elem in pipe_straights + beam_elems + bar_elems + cable_elems:
            material_group_members.setdefault(elem.material, []).extend(sid for sid, _, _ in self._straight_segment_node_pairs(elem))
        for elem in bend_elems:
            material_group_members.setdefault(elem.material, []).extend(
                f"{elem.id}_s{i}" for i in range(N)
            )
        for material_name, element_ids in material_group_members.items():
            lines.append(f"GROUP_MA NOM={map_name(self._material_group_name(material_name))}")
            for element_id in element_ids:
                lines.append(f"  {map_name(element_id)}")
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=G_TUBE (for beams) ------------------------------
        if beam_elems:
            lines.append(f"GROUP_MA NOM={map_name('G_TUBE')}")
            for elem in beam_elems:
                lines.extend(f"  {map_name(sid)}" for sid, _, _ in straight_pairs[elem.id])
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=G_BAR (for bars) --------------------------------
        if bar_elems:
            lines.append(f"GROUP_MA NOM={map_name('G_BAR')}")
            for elem in bar_elems:
                lines.extend(f"  {map_name(sid)}" for sid, _, _ in straight_pairs[elem.id])
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_MA NOM=G_CABLE (for cables) ----------------------------
        if cable_elems:
            lines.append(f"GROUP_MA NOM={map_name('G_CABLE')}")
            for elem in cable_elems:
                lines.extend(f"  {map_name(sid)}" for sid, _, _ in straight_pairs[elem.id])
            lines.append("FINSF")
            lines.append("")

        # --- Per-element groups (for COUDE assignment) --------------------
        for elem in bend_elems:
            lines.append(f"GROUP_MA NOM={map_name(elem.id)}")
            for i in range(N):
                lines.append(f"  {map_name(f'{elem.id}_s{i}')}")
            lines.append("FINSF")
            lines.append("")

        # --- GROUP_NO for supports and concentrated nodal loads -----------
        grouped_node_ids = sorted({sup.node for sup in model.supports} | _nodal_force_node_ids(model))
        for node_id in grouped_node_ids:
            grp_name = f"GN_{node_id}"
            lines.append(f"GROUP_NO NOM={map_name(grp_name)}")
            lines.append(f"  {map_name(node_id)}")
            lines.append("FINSF")
            lines.append("")

        # --- All support nodes group --------------------------------------
        if model.supports:
            lines.append(f"GROUP_NO NOM={map_name('AllSupports')}")
            for sup in model.supports:
                lines.append(f"  {map_name(sup.node)}")
            lines.append("FINSF")
            lines.append("")

        lines.append("FIN")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(
            "Wrote mesh: %s (%d nodes, %d elements)",
            path, len(node_ids), len(model.elements),
        )
        return analysis_mesh

    def _build_analysis_mesh_from_mail_parts(
        self,
        *,
        model: TubaModel,
        mesh_id: str,
        model_revision: int,
        node_ids: list[str],
        pipe_straights: list[Element],
        pipe_bends: list[Element],
        beam_elems: list[Element],
        bar_elems: list[Element],
        cable_elems: list[Element],
        bend_intermediate: dict[str, list[tuple[str, np.ndarray]]],
        pipe_midpoints: dict[str, _SegmentMidpoint],
        bend_segment_midpoints: dict[str, _SegmentMidpoint],
        mail_path: Path,
        n_segments: int,
    ) -> AnalysisMesh:
        nodes: dict[str, tuple[float, float, float]] = {}
        node_sources: dict[str, MeshNodeSource] = {}
        for node_id in node_ids:
            node = model.nodes[node_id]
            nodes[node_id] = tuple(float(value) for value in node.coords)
            node_sources[node_id] = MeshNodeSource(
                node_id=node_id,
                source_ref=EntityRef("node", node_id),
                role="native_node",
            )

        for elem in pipe_bends:
            bend_metadata = _bend_geometry_metadata(elem)
            for index, (node_id, coords) in enumerate(bend_intermediate.get(elem.id, []), start=1):
                nodes[node_id] = tuple(float(value) for value in coords)
                node_sources[node_id] = MeshNodeSource(
                    node_id=node_id,
                    source_ref=EntityRef("element", elem.id),
                    role="generated_bend_node",
                    parametric_t=index / n_segments,
                    segment_index=index,
                    metadata=bend_metadata,
                )

        for midpoint in pipe_midpoints.values():
            nodes[midpoint.node_id] = tuple(float(value) for value in midpoint.coords)
            node_sources[midpoint.node_id] = MeshNodeSource(
                node_id=midpoint.node_id,
                source_ref=EntityRef("element", midpoint.source_element_id),
                role="generated_pipe_mid_node",
                parametric_t=0.5,
                segment_index=0,
            )

        for midpoint in bend_segment_midpoints.values():
            nodes[midpoint.node_id] = tuple(float(value) for value in midpoint.coords)
            node_sources[midpoint.node_id] = MeshNodeSource(
                node_id=midpoint.node_id,
                source_ref=EntityRef("element", midpoint.source_element_id),
                role="generated_bend_mid_node",
                parametric_t=(midpoint.segment_index + 0.5) / n_segments,
                segment_index=midpoint.segment_index,
            )

        elements: dict[str, tuple[str, ...]] = {}
        element_sources: dict[str, MeshElementSource] = {}
        straight_elems = pipe_straights + beam_elems + bar_elems + cable_elems
        for elem in straight_elems:
            pairs = self._straight_segment_node_pairs(elem)
            start, end = (model.nodes[nid].coords for nid in (elem.n1, elem.n2))
            for index, (segment_id, n1, n2) in enumerate(pairs):
                elements[segment_id] = (n1, n2)
                element_sources[segment_id] = MeshElementSource(
                    element_id=segment_id,
                    source_ref=EntityRef("element", elem.id),
                    role="straight_segment" if len(pairs) > 1 else "native_element",
                    segment_index=index if len(pairs) > 1 else None,
                )
                if n2 != elem.n2:
                    t = (index + 1) / len(pairs)
                    nodes[n2] = tuple(float(v) for v in start + (end - start) * t)
                    node_sources[n2] = MeshNodeSource(
                        node_id=n2, source_ref=EntityRef("element", elem.id),
                        role="generated_straight_node", parametric_t=t, segment_index=index + 1,
                    )

        for elem in pipe_bends:
            segment_ids = []
            first_segment = f"{elem.id}_s0"
            elements[first_segment] = (elem.n1, f"{elem.id}_n1")
            segment_ids.append(first_segment)
            for index in range(1, n_segments - 1):
                segment_id = f"{elem.id}_s{index}"
                elements[segment_id] = (f"{elem.id}_n{index}", f"{elem.id}_n{index + 1}")
                segment_ids.append(segment_id)
            last_segment = f"{elem.id}_s{n_segments - 1}"
            elements[last_segment] = (f"{elem.id}_n{n_segments - 1}", elem.n2)
            segment_ids.append(last_segment)
            for segment_index, segment_id in enumerate(segment_ids):
                element_sources[segment_id] = MeshElementSource(
                    element_id=segment_id,
                    source_ref=EntityRef("element", elem.id),
                    role="bend_segment",
                    segment_index=segment_index,
                    metadata=_bend_geometry_metadata(elem),
                )

        groups: dict[str, tuple[str, ...]] = {}
        if pipe_straights:
            groups["PipeStraights"] = tuple(sid for elem in pipe_straights for sid, _, _ in self._straight_segment_node_pairs(elem))
        if pipe_bends:
            groups["PipeElbows"] = tuple(f"{elem.id}_s{index}" for elem in pipe_bends for index in range(n_segments))
        all_pipe_ids = [sid for elem in pipe_straights for sid, _, _ in self._straight_segment_node_pairs(elem)]
        all_pipe_ids.extend(f"{elem.id}_s{index}" for elem in pipe_bends for index in range(n_segments))
        if all_pipe_ids:
            groups["AllPipes"] = tuple(all_pipe_ids)
        for elem in straight_elems:
            groups[elem.id] = tuple(sid for sid, _, _ in self._straight_segment_node_pairs(elem))
        pipe_orientation_nodes = [elem.n1 for elem in pipe_straights]
        pipe_orientation_nodes.extend(elem.n1 for elem in pipe_bends)
        if pipe_orientation_nodes:
            groups["PipeOrientationNodes"] = (next(iter(dict.fromkeys(pipe_orientation_nodes))),)
        section_group_members: dict[str, list[str]] = {}
        for elem in pipe_straights + beam_elems:
            section_group_members.setdefault(elem.section, []).extend(sid for sid, _, _ in self._straight_segment_node_pairs(elem))
        for section_name, element_ids in section_group_members.items():
            groups[self._section_group_name(section_name)] = tuple(element_ids)
        material_group_members: dict[str, list[str]] = {}
        for elem in straight_elems:
            material_group_members.setdefault(elem.material, []).extend(sid for sid, _, _ in self._straight_segment_node_pairs(elem))
        for elem in pipe_bends:
            material_group_members.setdefault(elem.material, []).extend(
                f"{elem.id}_s{index}" for index in range(n_segments)
            )
        for material_name, element_ids in material_group_members.items():
            groups[self._material_group_name(material_name)] = tuple(element_ids)
        if beam_elems:
            groups["G_TUBE"] = tuple(sid for elem in beam_elems for sid, _, _ in self._straight_segment_node_pairs(elem))
        if bar_elems:
            groups["G_BAR"] = tuple(sid for elem in bar_elems for sid, _, _ in self._straight_segment_node_pairs(elem))
        if cable_elems:
            groups["G_CABLE"] = tuple(sid for elem in cable_elems for sid, _, _ in self._straight_segment_node_pairs(elem))
        for elem in pipe_bends:
            groups[elem.id] = tuple(f"{elem.id}_s{index}" for index in range(n_segments))
        for node_id in sorted({support.node for support in model.supports} | _nodal_force_node_ids(model)):
            groups[f"GN_{node_id}"] = (node_id,)
        if model.supports:
            groups["AllSupports"] = tuple(support.node for support in model.supports)

        for contact in shoes(model, self.pipe_modelization):
            nodes[contact.ground] = tuple(model.nodes[contact.support.node].coords - (1. + contact.support.gap) * np.asarray(contact.normal))
            node_sources[contact.ground] = MeshNodeSource(node_id=contact.ground, source_ref=EntityRef('support', contact.support.id), role='contact_ground')
            elements[contact.group] = (contact.ground, contact.support.node)
            element_sources[contact.group] = MeshElementSource(element_id=contact.group, source_ref=EntityRef('support', contact.support.id), role='contact_connector')
            groups[contact.ground] = (contact.ground,)
            groups[contact.group] = (contact.group,)
        return AnalysisMesh(
            id=mesh_id,
            model_revision=model_revision,
            solver_name=self.SOLVER_NAME,
            nodes=nodes,
            elements=elements,
            groups=groups,
            node_sources=node_sources,
            element_sources=element_sources,
            files={"mail": str(mail_path)},
            modelisations=modelisation_assignments(model, self.pipe_modelization),
        )

    def _pipe_straight_midpoint_nodes(
        self,
        model: TubaModel,
        pipe_straights: list[Element],
    ) -> dict[str, _SegmentMidpoint]:
        midpoints: dict[str, _SegmentMidpoint] = {}
        for elem in pipe_straights:
            start = self._analysis_node_coords(model, {}, elem.n1)
            end = self._analysis_node_coords(model, {}, elem.n2)
            midpoints[elem.id] = _SegmentMidpoint(
                node_id=self._generated_midpoint_node_id(elem.id),
                start_node_id=elem.n1,
                end_node_id=elem.n2,
                source_element_id=elem.id,
                segment_index=0,
                coords=(start + end) / 2.0,
            )
        return midpoints

    def _pipe_bend_segment_midpoint_nodes(
        self,
        model: TubaModel,
        pipe_bends: list[Element],
        bend_intermediate: dict[str, list[tuple[str, np.ndarray]]],
        n_segments: int,
    ) -> dict[str, _SegmentMidpoint]:
        midpoints: dict[str, _SegmentMidpoint] = {}
        for elem in pipe_bends:
            for segment_index, (segment_id, start_id, end_id) in enumerate(
                self._bend_segment_node_pairs(elem, n_segments)
            ):
                start = self._analysis_node_coords(model, bend_intermediate, start_id)
                end = self._analysis_node_coords(model, bend_intermediate, end_id)
                midpoints[segment_id] = _SegmentMidpoint(
                    node_id=self._generated_midpoint_node_id(segment_id),
                    start_node_id=start_id,
                    end_node_id=end_id,
                    source_element_id=elem.id,
                    segment_index=segment_index,
                    coords=(start + end) / 2.0,
                )
        return midpoints

    def _straight_segment_node_pairs(self, elem: Element) -> list[tuple[str, str, str]]:
        subdivide = elem.type in ("beam", "cable") or (
            elem.type == "pipe_straight" and self.pipe_modelization is PipeModelization.POU_D_T
        )
        if not subdivide or self.line_segments == 1:
            return [(elem.id, elem.n1, elem.n2)]
        return self._bend_segment_node_pairs(elem, self.line_segments)

    @staticmethod
    def _bend_segment_node_pairs(elem: Element, n_segments: int) -> list[tuple[str, str, str]]:
        pairs = [(f"{elem.id}_s0", elem.n1, f"{elem.id}_n1")]
        for index in range(1, n_segments - 1):
            pairs.append((f"{elem.id}_s{index}", f"{elem.id}_n{index}", f"{elem.id}_n{index + 1}"))
        pairs.append((f"{elem.id}_s{n_segments - 1}", f"{elem.id}_n{n_segments - 1}", elem.n2))
        return pairs

    @staticmethod
    def _generated_midpoint_node_id(base_id: str) -> str:
        node_id = f"{base_id}_mid"
        if len(node_id) <= 24:
            return node_id
        digest = hashlib.sha1(node_id.encode("utf-8")).hexdigest()[:8].upper()
        return f"N_{digest}"

    @staticmethod
    def _section_group_name(section_name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", section_name)
        group_name = f"SEC_{safe}"
        if len(group_name) <= 24:
            return group_name
        digest = hashlib.sha1(group_name.encode("utf-8")).hexdigest()[:8].upper()
        return f"SEC_{digest}"

    @staticmethod
    def _material_group_name(material_name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", material_name)
        group_name = f"MAT_{safe}"
        if len(group_name) <= 24:
            return group_name
        digest = hashlib.sha1(group_name.encode("utf-8")).hexdigest()[:8].upper()
        return f"MAT_{digest}"

    @staticmethod
    def _analysis_node_coords(
        model: TubaModel,
        generated_nodes: dict[str, list[tuple[str, np.ndarray]]],
        node_id: str,
    ) -> np.ndarray:
        if node_id in model.nodes:
            return np.asarray(model.nodes[node_id].coords, dtype=float)
        for nodes in generated_nodes.values():
            for generated_id, coords in nodes:
                if generated_id == node_id:
                    return np.asarray(coords, dtype=float)
        raise KeyError(f"Node {node_id!r} is not present in model or generated bend nodes.")

    # ------------------------------------------------------------------
    # Gmsh-based bend node computation
    # ------------------------------------------------------------------

    def _compute_bend_nodes(
        self,
        model: TubaModel,
        bend_elems: List[Element],
        n_segments: int,
    ) -> Dict[str, List[Tuple[str, np.ndarray]]]:
        """Discretise bend arcs into evenly spaced interior nodes.

        A transfinite curve on a circular arc is a uniform subdivision of the
        swept angle, so the interior nodes are the start radius rotated about
        the bend axis in equal steps. This used to ask Gmsh's OCC kernel for
        the same points; doing the rotation directly agrees with it to about
        1e-15 m and keeps the whole 1D solver handoff free of a compiled
        meshing dependency.

        Returns
        -------
        Dict mapping ``elem.id`` -> list of ``(node_name, coord_array)`` for
        the ``n_segments - 1`` interior nodes.
        """
        cache_key = (
            int(getattr(model, "revision", 0)),
            tuple(sorted(e.id for e in bend_elems)),
            int(n_segments),
        )
        cached = self._bend_node_cache.get(cache_key)
        if cached is not None:
            return cached

        result: Dict[str, List[Tuple[str, np.ndarray]]] = {}
        for elem in bend_elems:
            center, axis, r1, theta = self._get_bend_geometry(model, elem)
            norm = float(np.linalg.norm(axis))
            if norm <= 1e-12:
                raise ValueError(f"Bend {elem.id!r} has a degenerate rotation axis.")
            unit_axis = axis / norm

            # The arc must actually end on n2. A wrong axis sign would still
            # produce plausible interior points, on the far side of the circle.
            end = center + _rotate_about_axis(r1, unit_axis, theta)
            expected_end = np.asarray(model.nodes[elem.n2].coords, dtype=float)
            radius = float(np.linalg.norm(r1))
            if float(np.linalg.norm(end - expected_end)) > max(1e-9, 1e-9 * radius):
                raise ValueError(
                    f"Bend {elem.id!r} arc geometry does not close on its end node; "
                    "check the stored bend centre, normal and angle."
                )

            result[elem.id] = [
                (
                    f"{elem.id}_n{index}",
                    center + _rotate_about_axis(r1, unit_axis, theta * index / n_segments),
                )
                for index in range(1, n_segments)
            ]

        self._bend_node_cache[cache_key] = result
        return result

    @staticmethod
    def _get_bend_geometry(model: TubaModel, elem: Element) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        if elem.bend_geometry is not None:
            geometry = elem.bend_geometry
            center = np.asarray(geometry.center, dtype=float)
            normal = np.asarray(geometry.normal, dtype=float)
            if np.linalg.norm(normal) > 1e-12:
                normal = normal / np.linalg.norm(normal)
            p1 = model.nodes[elem.n1].coords
            r1 = p1 - center
            theta = np.radians(float(geometry.angle))
            return center, normal, r1, theta

        p1 = model.nodes[elem.n1].coords
        p2 = model.nodes[elem.n2].coords
        radius = elem.bend_radius
        angle_deg = elem.bend_angle

        d_in = None
        for e in model.elements:
            if e.id == elem.id:
                continue
            if e.n2 == elem.n1:
                v = model.nodes[e.n2].coords - model.nodes[e.n1].coords
                if np.linalg.norm(v) > 1e-9:
                    d_in = v / np.linalg.norm(v)
                    break
            elif e.n1 == elem.n1:
                v = model.nodes[e.n1].coords - model.nodes[e.n2].coords
                if np.linalg.norm(v) > 1e-9:
                    d_in = v / np.linalg.norm(v)
                    break

        d_out = None
        for e in model.elements:
            if e.id == elem.id:
                continue
            if e.n1 == elem.n2:
                v = model.nodes[e.n2].coords - model.nodes[e.n1].coords
                if np.linalg.norm(v) > 1e-9:
                    d_out = v / np.linalg.norm(v)
                    break
            elif e.n2 == elem.n2:
                v = model.nodes[e.n1].coords - model.nodes[e.n2].coords
                if np.linalg.norm(v) > 1e-9:
                    d_out = v / np.linalg.norm(v)
                    break

        if d_in is None and d_out is not None:
            d_in = d_out.copy()
        elif d_out is None and d_in is not None:
            d_out = d_in.copy()
        elif d_in is None and d_out is None:
            v = p2 - p1
            d_in = v / np.linalg.norm(v)
            d_out = d_in.copy()

        theta = np.radians(angle_deg)
        T = radius * np.tan(theta / 2.0)
        V = p1 + d_in * T

        v_bisect = d_out - d_in
        norm_bisect = np.linalg.norm(v_bisect)
        if norm_bisect > 1e-9:
            v_bisect_u = v_bisect / norm_bisect
        else:
            v_bisect_u = np.array([-d_in[1], d_in[0], 0.0])
            if np.linalg.norm(v_bisect_u) < 1e-9:
                v_bisect_u = np.array([0.0, -d_in[2], d_in[1]])
            v_bisect_u /= np.linalg.norm(v_bisect_u)

        L = radius / np.cos(theta / 2.0)
        C = V + v_bisect_u * L

        r1 = p1 - C
        r2 = p2 - C

        axis = np.cross(r1, r2)
        norm_axis = np.linalg.norm(axis)
        if norm_axis > 1e-9:
            axis /= norm_axis
        else:
            axis = np.array([0.0, 0.0, 1.0])

        return C, axis, r1, theta


def _bend_geometry_metadata(elem: Element) -> dict[str, Any]:
    if elem.bend_geometry is None:
        return {}
    return {"bend_geometry": elem.bend_geometry.to_dict()}


def _nodal_force_node_ids(model: TubaModel) -> set[str]:
    node_ids: set[str] = set()
    cases = list(getattr(model, "load_cases", {}).values()) + list(getattr(model, "operations", {}).values())
    for case in cases:
        for force in getattr(case, "nodal_forces", []):
            node_ids.add(force.node)
    return node_ids
