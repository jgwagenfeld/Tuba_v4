"""Reference figures for this example: solved response against cantilever beam theory.

The example already checks the solved tip against a Timoshenko cantilever
(``study.py``). These figures extend that check along the whole member and across all
three rolls, and commit the comparison next to the evidence so a reader sees the
agreement instead of taking the assertion in ``check_solved_response`` on trust.

Every analytical value here is closed-form cantilever beam theory for a uniform section
under a tip force, shear-corrected with the catalog shear areas so it matches the
``POU_D_T`` modelisation rather than an Euler-Bernoulli idealisation. The node path is
traced through the analysis mesh in the committed manifest, so the stations are the
solver's own mesh and not an assumed subdivision.

``scripts/build_study_cards.py`` calls :func:`reference_figures`. These are finite-element
comparisons, not code checks: no allowable stress and no standard is involved.
"""

from pathlib import Path

import numpy as np

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.geometry.section_mesh import beam_local_frame
from tuba.project import run_model_script
from tuba.reporting import FigureSeries

E_MODULUS = 2.0e11
POISSON = 0.3
SHEAR_MODULUS = E_MODULUS / (2.0 * (1.0 + POISSON))
TIP_FORCE = 500.0
#: Model node ids of the three cantilever roots, in the order ``model.py`` builds the rolls.
ROOT_NODE_IDS = ("N0", "N13", "N26")
#: Model node ids of the three cantilever tips, same order.
TIP_NODE_IDS = ("N12", "N25", "N38")


def _mesh_nodes(evidence_folder: Path) -> dict[str, list[float]]:
    """The analysis mesh's node coordinates, read from the committed manifest."""
    import json

    manifest = json.loads((evidence_folder / "study_manifest.json").read_text(encoding="utf-8"))
    return {node_id: list(coords) for node_id, coords in manifest["analysis_mesh"]["nodes"].items()}


def _node_adjacency(evidence_folder: Path) -> dict[str, list[str]]:
    """Node-to-node adjacency over the analysis mesh, from the committed manifest."""
    import json

    manifest = json.loads((evidence_folder / "study_manifest.json").read_text(encoding="utf-8"))
    adjacency: dict[str, list[str]] = {}
    for end_a, end_b in manifest["analysis_mesh"]["elements"].values():
        adjacency.setdefault(end_a, []).append(end_b)
        adjacency.setdefault(end_b, []).append(end_a)
    return adjacency


def _trace_path(adjacency: dict[str, list[str]], root: str, tip: str) -> list[str]:
    """Return the nodes from *root* to *tip* along the member, in order.

    Walks the member rather than assuming a subdivision: at an interior node the two
    element ends meet, so the next station is the neighbour that is not where we came
    from. A member that is not a simple chain is a mesh this example does not describe,
    and the walk raising is the honest outcome.
    """
    if root not in adjacency or tip not in adjacency:
        raise ValueError(f"Mesh has no member running from {root!r} to {tip!r}.")
    stations = [root]
    previous, current = None, root
    while current != tip:
        onward = [node for node in adjacency[current] if node != previous]
        if len(onward) != 1:
            raise ValueError(
                f"Node {current!r} on the member {root}..{tip} has {len(onward)} onward "
                "ends; this example expects a simple chain."
            )
        previous, current = current, onward[0]
        stations.append(current)
    return stations


def _station_arms(nodes: dict[str, list[float]], stations: list[str]) -> np.ndarray:
    """Cumulative distance from the first station to each station, in metres."""
    coordinates = np.asarray([nodes[node] for node in stations], dtype=float)
    steps = np.linalg.norm(np.diff(coordinates, axis=0), axis=1)
    return np.concatenate(([0.0], np.cumsum(steps)))


def _local_force(roll_deg: int) -> np.ndarray:
    """The 500 N tip force resolved in the rolled member's local axes."""
    basis = beam_local_frame([0, 0, 0], [1, 0, 0], twist_angle_deg=roll_deg)
    return basis @ np.array([0.0, 0.0, -TIP_FORCE])


def _analytical_local_translation(local_force: np.ndarray, arms: np.ndarray, properties, length: float) -> np.ndarray:
    """Timoshenko cantilever deflections at each arm, in the member's local axes.

    Bending follows ``P x^2 (3L - x) / (6 EI)`` and shear ``P x / (kappa G A)``, the same
    two terms ``study.py`` applies at the tip, generalised to every station. Local y
    bends about local z and local z about local y.
    """
    inertia = np.array([properties["IZ"], properties["IY"]])
    shear_area = np.array([properties["AY"], properties["AZ"]])
    bending = local_force[1:3] * arms[:, None] ** 2 * (3.0 * length - arms[:, None]) / (6.0 * E_MODULUS * inertia)
    shear = local_force[1:3] * arms[:, None] * shear_area / (SHEAR_MODULUS * properties["A"])
    return np.column_stack((np.zeros(len(arms)), bending + shear))


def _solved_local_translations(result_state, stations: list[str], roll_deg: int) -> np.ndarray:
    """The solved deflections at each station, in the member's local axes."""
    basis = beam_local_frame([0, 0, 0], [1, 0, 0], twist_angle_deg=roll_deg)
    return np.asarray([
        basis @ np.asarray(result_state.node_displacements[node], dtype=float)[:3] for node in stations
    ])


def _figure_labels(title: str, subtitle: str, xlabel: str, ylabel: str) -> dict[str, str]:
    return {"title": title, "subtitle": subtitle, "xlabel": xlabel, "ylabel": ylabel}


def _displacement_profile(project_root: Path, evidence_folder: Path) -> tuple[list[FigureSeries], dict[str, str]]:
    """The 90 degree cantilever's whole profile: solved against closed-form beam theory."""
    model = _model(project_root)
    state = _validated_state(model, evidence_folder)
    nodes = _mesh_nodes(evidence_folder)
    stations = _trace_path(_node_adjacency(evidence_folder), ROOT_NODE_IDS[2], TIP_NODE_IDS[2])
    arms = _station_arms(nodes, stations)
    length = float(arms[-1])
    local_force = _local_force(90)
    properties = model.sections["IPE100"].properties
    solved = _solved_local_translations(state, stations, 90)
    analytical = _analytical_local_translation(local_force, arms, properties, length)
    # The global -Z force deflects every roll in the same global direction, so the
    # deflected magnitude is the comparison a reader can read off a single axis.
    magnitude = np.linalg.norm(solved, axis=1)
    reference = np.linalg.norm(analytical, axis=1)
    worst = float(np.max(np.abs(magnitude - reference)))
    subtitle = (
        f"Code_Aster {state.load_case!r} case, POU_D_T, IPE100, {len(stations)} mesh stations. "
        f"Worst difference from closed-form beam theory: {worst:.2e} m."
    )
    series = [
        FigureSeries("Code_Aster DEPL", tuple(zip(arms.tolist(), magnitude.tolist())), "solved"),
        FigureSeries("Cantilever beam theory (Timoshenko)", tuple(zip(arms.tolist(), reference.tolist())), "reference"),
    ]
    return series, _figure_labels(
        "Displacement profile along the 90 deg cantilever",
        subtitle,
        "Station from the anchor (m)",
        "Solved displacement magnitude (m)",
    )


def _tip_response(project_root: Path, evidence_folder: Path) -> tuple[list[FigureSeries], dict[str, str]]:
    """Tip deflection at each roll: solved against closed-form beam theory."""
    model = _model(project_root)
    state = _validated_state(model, evidence_folder)
    properties = model.sections["IPE100"].properties
    rolls: list[float] = []
    solved_magnitudes: list[float] = []
    reference_magnitudes: list[float] = []
    for roll_deg, tip in zip((0, 45, 90), TIP_NODE_IDS):
        local_force = _local_force(roll_deg)
        length = float(_station_arms(_mesh_nodes(evidence_folder), [ROOT_NODE_IDS[(0, 45, 90).index(roll_deg)], tip])[-1])
        solved = _solved_local_translations(state, [tip], roll_deg)[0]
        analytical = _analytical_local_translation(local_force, np.array([length]), properties, length)[0]
        rolls.append(float(roll_deg))
        solved_magnitudes.append(float(np.linalg.norm(solved)))
        reference_magnitudes.append(float(np.linalg.norm(analytical)))
    worst = max(abs(solved - reference) for solved, reference in zip(solved_magnitudes, reference_magnitudes))
    subtitle = (
        f"Code_Aster {state.load_case!r} case, the same {TIP_FORCE:.0f} N tip force at every roll. "
        f"The spread is section orientation alone. Worst difference from beam theory: {worst:.2e} m."
    )
    series = [
        FigureSeries("Code_Aster DEPL", tuple(zip(rolls, solved_magnitudes)), "solved"),
        FigureSeries("Cantilever beam theory (Timoshenko)", tuple(zip(rolls, reference_magnitudes)), "reference"),
    ]
    return series, _figure_labels(
        "Tip deflection against rolled section orientation",
        subtitle,
        "Section roll (deg)",
        "Tip displacement magnitude (m)",
    )


def _model(project_root: Path):
    """The example's model, built by running its own ``model.py`` as the project does."""
    return run_model_script(project_root / "model.py")["model"]


def _validated_state(model, evidence_folder: Path):
    """Import the committed evidence and refuse it unless it still matches the model.

    A figure drawn from evidence that no longer describes the model would be a picture
    of the wrong solve, so the publication check runs before anything is drawn.
    """
    run = import_code_aster_artifacts(model=model, work_dir=evidence_folder)
    run.validate_for_publication(model)
    return run.result_state


def reference_figures(project_root: Path, evidence_folder: Path) -> dict[str, tuple]:
    """Return ``{filename: (series, labels)}`` for this example's committed evidence."""
    return {
        "reference_displacement_profile.svg": _displacement_profile(project_root, evidence_folder),
        "reference_tip_response.svg": _tip_response(project_root, evidence_folder),
    }
