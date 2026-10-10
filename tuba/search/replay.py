"""Compose read-only search records and native review bundles for viewer replay."""

from __future__ import annotations

import json
from pathlib import Path

from tuba.model import TubaModel
from tuba.visualization import SceneBuildOptions, SceneRequest, build_visualization_scene, write_scene_bundle

from .artifacts import atomic_json
from .export import _archive, _model_artifact, _new_output, export_history, write_candidate_review


def _preview(archive, row, output):
    if not row['build']:
        raise ValueError('No archived geometry: candidate did not build')
    if _model_artifact(archive, row['build'])['availability'] != 'available':
        raise ValueError('Archived geometry integrity check failed')
    model = TubaModel.from_dict(json.loads(archive.path(row['build']['model_ref']).read_text(encoding='utf-8')))
    scene = build_visualization_scene(SceneRequest(model, options=SceneBuildOptions(include_physical_envelopes=True),
                                                   scene_id=f"scene:search:preview:{row['id']}"))
    scene.extra['search'] = {'candidate_id': row['id'], 'result_status': 'unsolved_preview',
                              'scope': 'Archived reference geometry; no engineering result displayed'}
    write_scene_bundle(scene, output)


def write_search_replay(run_dir: Path, output_dir: Path) -> Path:
    """Create a new native viewer package; never modify the run or call a solver."""
    archive = _archive(run_dir)
    output = _new_output(output_dir)
    history_path = export_history(run_dir, output / 'history')
    payload = json.loads(history_path.read_text(encoding='utf-8'))
    payload.update(schema='tuba.search.viewer.v1', review_bundles_self_contained=True,
                   history_manifest='history/search_history.json', comparison_ranges={})
    for row in payload['candidates']:
        relative = f"previews/{row['id']}"
        try:
            _preview(archive, row, output / relative)
            row['preview'] = {'bundle': relative, 'availability': 'available', 'message': None}
        except (ValueError, FileNotFoundError, UnicodeError) as exc:
            row['preview'] = {'bundle': None, 'availability': 'unavailable', 'message': str(exc)}
        row['attempt_reviews'] = []
        for recovered in row['recovered_attempts']:
            reference = recovered['evidence_manifest_ref']
            inventory = next((item for item in payload['inventories'] if item['manifest']['path'] == reference), None)
            diagnostics = inventory['files'] if inventory else [item for item in payload['availability_diagnostics'] if item['path'] == reference]
            row['attempt_reviews'].append({'evaluation_id': None, 'attempt_id': recovered['attempt_id'],
                'bundle': None, 'availability': 'unavailable', 'artifact_diagnostics': diagnostics,
                'message': 'No evaluation was published before crash recovery; sealed execution evidence remains in the retained archive'})
        for evaluation in row['evaluations']:
            relative = f"reviews/{row['id']}/{evaluation['id']}"
            view = {'evaluation_id': evaluation['id'], 'attempt_id': evaluation['attempt_id'],
                    'bundle': None, 'availability': 'unavailable', 'message': None}
            try:
                scene_path = write_candidate_review(run_dir, row['id'], output / relative,
                                                    evaluation_id=evaluation['id'], include_decisions=False)
                view.update(bundle=relative, availability='available')
                scene = json.loads(scene_path.read_text(encoding='utf-8'))
                for field in scene.get('result_fields', ()):
                    if field.get('components') != ['magnitude'] or not field.get('range'):
                        continue
                    key = f"{field['id']}|{field['unit']}"
                    low, high = field['range']
                    current = payload['comparison_ranges'].get(key, [low, high])
                    payload['comparison_ranges'][key] = [min(current[0], low), max(current[1], high)]
            except (ValueError, FileNotFoundError, UnicodeError) as exc:
                view['message'] = str(exc)
            row['attempt_reviews'].append(view)
    atomic_json(output / 'search_replay.json', payload)
    return output / 'search_replay.json'
