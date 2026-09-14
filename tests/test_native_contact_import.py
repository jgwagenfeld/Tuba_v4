"""Synthetic parser regressions and an opt-in real public Code_Aster solve."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from test_code_aster_friction import friction_model
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.base import FEAResults, NodeResult
from tuba.solver.contact_results import read_contact_history


PATH = ['Cold', 'Hot', 'Cold', 'Lift', 'Cold']


class NativeContactImport(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = friction_model()
        self.parser = CodeAsterSolver(pipe_modelization='POU_D_T', load_path=PATH)
        self.study = self.parser.export_analysis_study(self.model, 'Cold', self.root)
        self.times = [0., .123456789012345, 1., 2., 3., 4., 5.]
        self.rows = [dict(support_id='shoe', instant=t, N=-10000., VY=1000., VZ=0.,
                          slip_y=t*1e-5, slip_z=0., status=0) for t in self.times]

    def read(self, rows=None, *, times=None):
        (self.root/'study_contact.json').write_text(json.dumps(self.rows if rows is None else rows))
        (self.root/'study_depl.csv').write_text('INST,DX\n'+''.join(
            f'{t:.16E},0\n' for t in (self.times if times is None else times)))
        def frame(model, root, *, instant):
            result = FEAResults('Code_Aster', 'Cold')
            for node in model.nodes:
                result.node_results[node] = NodeResult(node, np.array([instant*1e-4, -1e-6, 0., 0., 0., 0.]), np.zeros(6))
            return result
        with patch.object(self.parser, '_parse_results', side_effect=frame):
            return read_contact_history(self.model, self.root, self.study, self.parser)

    def test_shuffled_records_preserve_native_variables_and_full_precision_instants(self):
        frames = self.read(list(reversed(self.rows)))
        self.assertEqual([frame.metadata['pseudo_time'] for frame in frames], self.times)
        native = frames[1].contact_results['shoe']
        self.assertEqual(native.status_source, 'solver')
        self.assertEqual(native.normal_force, 10000.)
        self.assertEqual(native.tangential_force, (-1000., 0., 0.))
        self.assertAlmostEqual(native.slip[0], self.times[1]*1e-5, places=18)
        self.assertNotEqual(native.slip, native.relative_displacement)
        self.assertEqual(frames[1].metadata['contact_variable_mapping']['V5'], 'local y slip')
        self.assertEqual(frames[-1].load_case, 'Cold')

    def test_multiple_supports_at_one_node_are_mapped_by_id_not_row_order(self):
        self.model.add_support(node='N1', type='rest', id='shoe2', direction=[0., 0., 1.], friction_coefficient=.3)
        rows = self.rows + [{**row, 'support_id':'shoe2', 'VY':-2000.} for row in self.rows]
        frames = self.read(list(reversed(rows)))
        for frame in frames:
            self.assertEqual(set(frame.contact_results), {'shoe','shoe2'})
            self.assertEqual(frame.contact_results['shoe'].tangential_force[0], -1000.)
            self.assertEqual(frame.contact_results['shoe2'].tangential_force[0], 2000.)

    def test_frictionless_reseating_does_not_trust_stale_native_open_flag(self):
        self.model.supports[-1].friction_coefficient = 0.
        frames = self.read([{**row, 'VY':0., 'status':2.} for row in self.rows])
        contact = frames[-1].contact_results['shoe']
        self.assertEqual(contact.status, 'indeterminate')
        self.assertEqual(contact.status_source, 'derived')
        self.assertIsNone(contact.utilization)
        self.assertEqual(frames[-1].metadata['native_contact_status']['shoe'], 2.)

    def test_missing_malformed_nonfinite_duplicate_and_unknown_records_fail(self):
        bad_rows = [{}, [], self.rows + [self.rows[0]]]
        for key, value in [('N', float('nan')), ('VY', float('inf')), ('status', 7), ('support_id', 'unknown')]:
            bad_rows.append([{**self.rows[0], key:value}, *self.rows[1:]])
        missing = dict(self.rows[0]); del missing['slip_y']
        bad_rows.append([missing, *self.rows[1:]])
        for rows in bad_rows:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.read(rows)
        (self.root/'study_contact.json').write_text('{invalid')
        with self.assertRaises(json.JSONDecodeError):
            read_contact_history(self.model, self.root, self.study, self.parser)

    def test_missing_stage_support_and_displacement_increment_fail(self):
        for rows in (self.rows[1:], self.rows[:-1], [row for row in self.rows if row['instant'] != 3.]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, 'incomplete|stage'):
                self.read(rows)
        with self.assertRaisesRegex(ValueError, 'different increments'):
            self.read(times=self.times[:-1])
        node = self.model.add_node([3., 0., 0.])
        self.model.add_support(node=node, type='rest', id='shoe2', friction_coefficient=.3)
        with self.assertRaisesRegex(ValueError, 'Missing support'):
            self.read()

    def test_vector_coulomb_bound_and_tensile_normal_force_fail(self):
        for changes in ({'N':10000.}, {'VY':2500., 'VZ':2500.}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'force bounds'):
                self.read([{**self.rows[0], **changes}, *self.rows[1:]])
        frames = self.read([{**row, 'N':0., 'VY':0., 'status':2} for row in self.rows])
        self.assertTrue(all(frame.contact_results['shoe'].utilization is None for frame in frames))

    def test_csv_increment_filter_does_not_mix_nearby_converged_times(self):
        path = self.root/'precision.csv'
        path.write_text('INST,DX\n1.0000000000000000E+00,1\n1.0000000500000000E+00,2\n')
        self.parser._result_time = 1.
        self.assertEqual([row['DX'] for row in self.parser._parse_result_table(path)], ['1'])

    def test_open_contact_cannot_publish_nonzero_contact_force(self):
        with self.assertRaises(ValueError):
            self.read([{**row, 'status':2} for row in self.rows])


@unittest.skipUnless(os.environ.get('TUBA_RUN_CODE_ASTER_INTEGRATION') == '1', 'requires real Code_Aster')
class PublicNativeContactSolve(unittest.TestCase):
    def test_public_beam_cycle_has_verified_native_history_and_equilibrium(self):
        for label, normal in [('horizontal', [0., 1., 0.]), ('inclined', [0., 1., 1.])]:
            with self.subTest(normal=normal):
                self._check_public_cycle(label, normal)

    def test_rigid_rotation_preserves_native_contact_with_initial_gap(self):
        axis = np.array([1.,2.,3.]); axis /= np.linalg.norm(axis)
        x,y,z = axis
        skew = np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
        angle = .7
        rotation = np.eye(3)+np.sin(angle)*skew+(1.-np.cos(angle))*(skew@skew)
        np.testing.assert_allclose(rotation.T@rotation,np.eye(3),atol=1e-14)
        runs = []
        for label, transform in [("gap",np.eye(3)),("gap-rotated",rotation)]:
            model = friction_model()
            for node in model.nodes.values():
                node.coords = transform@node.coords
            model.supports[-1].direction = (transform@np.array([0.,1.,0.])).tolist()
            model.supports[-1].gap = .001
            for case in model.load_cases.values():
                case.gravity = False
                for load in case.nodal_forces:
                    load.components = [*(transform@load.components[:3]),*(transform@load.components[3:])]
            root = Path(f".build/public-native-import-{label}").resolve()
            solver = CodeAsterSolver(pipe_modelization="POU_D_T",load_path=PATH,work_dir=root,timeout_seconds=240)
            study = solver.export_analysis_study(model,"Cold",root)
            run = solver.solve_exported_study(model,study,force=True)
            run.validate_for_publication(model)
            first = run.result_states[0].contact_results["shoe"]
            self.assertAlmostEqual(first.gap,.001,delta=1e-12)
            self.assertAlmostEqual(first.normal_force,0.,delta=1e-6)
            self.assertEqual(first.status,"open")
            self.assertTrue(any(c.normal_force>1000. and c.gap<0.
                                for state in run.result_states for c in state.contact_results.values()))
            runs.append({round(state.metadata["pseudo_time"],10):state for state in run.result_states})
        common = sorted(runs[0].keys() & runs[1].keys())
        self.assertTrue(set(range(6)) <= set(common))
        peak_force_error = peak_displacement_error = 0.
        for time in common:
            base, rotated = [run[time] for run in runs]
            a,b = base.contact_results["shoe"],rotated.contact_results["shoe"]
            self.assertEqual(a.status,b.status)
            self.assertAlmostEqual(a.normal_force,b.normal_force,delta=.05)
            self.assertAlmostEqual(a.gap,b.gap,delta=1e-8)
            for field in ("normal","tangential_force","relative_displacement","slip"):
                expected = rotation@np.array(getattr(a,field))
                np.testing.assert_allclose(getattr(b,field),expected,rtol=1e-5,
                                           atol=.05 if field=="tangential_force" else 1e-8)
            peak_force_error = max(peak_force_error,abs(a.normal_force-b.normal_force),
                float(np.linalg.norm(np.array(b.tangential_force)-rotation@a.tangential_force)))
            for node in ("N0","N1"):
                for field in ("node_displacements","node_reactions"):
                    av = np.array(getattr(base,field)[node]); bv = np.array(getattr(rotated,field)[node])
                    expected = np.r_[rotation@av[:3],rotation@av[3:]]
                    np.testing.assert_allclose(bv,expected,rtol=1e-5,atol=.1 if field=="node_reactions" else 1e-8)
                    if field=="node_displacements":
                        peak_displacement_error=max(peak_displacement_error,float(np.linalg.norm(bv[:3]-expected[:3])))
        print(f"Rigid rotation, 1 mm gap: {len(common)} matched increments, force error {peak_force_error:.6g} N, displacement error {peak_displacement_error:.6g} m")

    def _check_public_cycle(self, label, normal):
        model = friction_model()
        model.supports[-1].direction = normal
        root = Path(f'.build/public-native-import-{label}').resolve()
        solver = CodeAsterSolver(pipe_modelization='POU_D_T', load_path=PATH, work_dir=root,
                                 timeout_seconds=240)
        study = solver.export_analysis_study(model, 'Cold', root)
        run = solver.solve_exported_study(model, study, force=True)
        run.validate_for_publication(model)
        self.assertGreater(len(run.result_states), len(PATH))
        self.assertEqual(run.result_state, run.result_states[-1])
        contacts = [state.contact_results['shoe'] for state in run.result_states]
        self.assertTrue({'sticking','sliding','open'} <= {c.status for c in contacts})
        previous = None
        for state, contact in zip(run.result_states, contacts):
            self.assertEqual(state.solver_input_identity, study.solver_input_identity)
            self.assertEqual(contact.status_source, 'solver')
            np.testing.assert_allclose(contact.normal, np.array(normal)/np.linalg.norm(normal), atol=1e-12)
            self.assertAlmostEqual(float(np.dot(contact.normal, contact.tangential_force)), 0., delta=1e-8)
            self.assertIn('study_contact.json', state.metadata['solve_attestation']['artifacts'])
            self.assertEqual(state.metadata['contact_variable_mapping']['V6'], 'local z slip')
            tol = max(1., .001*abs(contact.normal_force))
            self.assertGreaterEqual(contact.normal_force, -tol)
            self.assertLessEqual(np.linalg.norm(contact.tangential_force), contact.friction_limit+tol)
            if contact.status == 'open':
                self.assertLessEqual(abs(contact.normal_force), tol)
                self.assertLessEqual(np.linalg.norm(contact.tangential_force), tol)
            if previous is not None and contact.status == 'sliding':
                delta = np.array(contact.slip)-previous
                self.assertLessEqual(float(np.dot(contact.tangential_force, delta)), tol*1e-9)
            previous = np.array(contact.slip)
        def endpoint(time):
            return next(state.contact_results['shoe'] for state in run.result_states if abs(state.metadata['pseudo_time']-time)<1e-10)
        self.assertLess(endpoint(2.).tangential_force[0]*endpoint(3.).tangential_force[0], 0.)
        self.assertEqual(endpoint(4.).status, 'open')
        self.assertNotEqual(endpoint(5.).status, 'open')
        area = np.pi*(.1143**2-(.1143-2*.006)**2)/4
        weight = 7850.*area*2.*9.81
        applied_endpoints = [0., -10000., -10000., -10000., 10000., -10000.]
        for state in run.result_states:
            time = state.metadata['pseudo_time']
            contact = state.contact_results['shoe']
            support_force = contact.normal_force*np.array(contact.normal)+contact.tangential_force
            anchor_force = np.array(state.node_reactions['N0'][:3])
            applied_y = np.interp(time, range(6), applied_endpoints)
            residual = anchor_force+support_force+np.array([0., applied_y, -weight*min(time, 1.)])
            self.assertLess(np.linalg.norm(residual), 10.)



if __name__ == '__main__':
    unittest.main()
