import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np

from tuba import Model
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.aster_contact import shoes
from tuba.solver.aster_volume import PipeVolumeStudyExporter
from tuba.solver.mixed_study import MixedCodeAsterStudyExporter


def friction_model():
    model = Model('Native friction')
    model.add_material('steel', E=2e11, nu=.3, rho=7850., alpha=1.2e-5)
    model.add_pipe_section('pipe', OD=.1143, WT=.006)
    a = model.add_node([0.,0.,0.])
    b = model.add_node([2.,0.,0.])
    model.add_element(id='pipe', type='pipe_straight', n1=a, n2=b, section='pipe', material='steel')
    model.add_support(node=a, type='anchor', id='anchor')
    model.add_support(node=b, type='rest', id='shoe', direction=[0.,1.,0.], friction_coefficient=.3)
    for name, temp, force in [('Cold',20.,-10000.),('Hot',120.,-10000.),('Lift',20.,10000.)]:
        case = model.define_load_case(name, gravity=True, pressure=0., temperature=temp, ref_temperature=20.)
        case.add_nodal_force(b, force=[0.,force,0.])
    return model


class FrictionCompilation(unittest.TestCase):
    def test_unqualified_formulation_cannot_silently_omit_friction(self):
        with TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, 'friction requires'):
                CodeAsterSolver().export_study(friction_model(), 'Hot', root)

    def test_native_law_and_stateful_path_are_emitted(self):
        model = friction_model()
        with TemporaryDirectory() as root:
            solver = CodeAsterSolver(pipe_modelization='POU_D_T',load_path=['Cold','Hot','Cold','Lift','Cold'])
            study = solver.export_analysis_study(model, 'Cold', root)
            comm = Path(root,'study.comm').read_text()
            self.assertIn("RELATION='DIS_CHOC'", comm)
            self.assertNotIn("FORMULATION='LIAISON_UNIL'", comm)
            self.assertEqual(comm.count('RESU = STAT_NON_LINE'),1)
            self.assertIn('study_contact.json', Path(root,'study.export').read_text())
            self.assertIn('load_path', study.metadata['compiler_inputs'])
            self.assertIn('DIRECTION=(0.,0.,-1.)', comm)

    def test_default_native_shoe_normal_is_global_up(self):
        model = friction_model()
        model.supports[-1].direction = None
        self.assertEqual(shoes(model, 'POU_D_T')[0].normal, (0., 0., 1.))

    def test_support_roundtrip_and_validation(self):
        model = friction_model()
        model.supports[-1].normal_stiffness = 1e9
        model.supports[-1].tangential_stiffness = 1e7
        model.supports[-1].gap = .001
        copy = Model.from_dict(model.to_dict())
        self.assertEqual(copy.supports[-1].gap, .001)
        self.assertEqual(copy.supports[-1].normal_stiffness,1e9)
        for coefficient in (-1., float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                model.add_support(node='N0',type='rest',friction_coefficient=coefficient)

    def test_contact_parameters_cannot_be_ignored(self):
        for field, value in (('gap',.001),('normal_stiffness',1e10),('tangential_stiffness',1e8)):
            for formulation, kind in (('TUYAU_3M','rest'),('POU_D_T','anchor'),('POU_D_T','guide')):
                with self.subTest(field=field, formulation=formulation, kind=kind), TemporaryDirectory() as root:
                    model=friction_model()
                    support=model.supports[-1]
                    support.friction_coefficient=0.
                    support.type=kind
                    setattr(support,field,value)
                    with self.assertRaisesRegex(ValueError,'gap/stiffness parameters require'):
                        CodeAsterSolver(pipe_modelization=formulation).export_study(model,'Cold',root)
                    self.assertFalse(Path(root,'study.comm').exists())
        model=friction_model()
        model.supports[-1].friction_coefficient=0.
        self.assertEqual(shoes(model,'TUYAU_3M'),[])

    def test_contact_helper_names_cannot_overwrite_authored_entities(self):
        for namespace in ('nodes','elements','groups','materials','sections'):
            for reserved in ('GROUND_1','CONTACT_1'):
                with self.subTest(namespace=namespace,reserved=reserved), TemporaryDirectory() as root:
                    model=friction_model()
                    if namespace=='elements':
                        model.add_element(id=reserved,type='beam',n1=model.supports[0].node,
                                          n2=model.supports[1].node,section='pipe',material='steel')
                    elif namespace=='nodes':
                        from tuba.model import Node
                        model.nodes[reserved]=Node(id=reserved,coords=np.array([1.,1.,1.]))
                    elif namespace=='groups':
                        model.groups[reserved]={'elements':['pipe']}
                    else:
                        mapping=getattr(model,namespace)
                        mapping[reserved]=next(iter(mapping.values()))
                    with self.assertRaisesRegex(ValueError,'helper names collide'):
                        CodeAsterSolver(pipe_modelization='POU_D_T').export_analysis_study(model,'Cold',root)
                    self.assertFalse(Path(root,'study.mail').exists())

    def test_volume_and_mixed_entrypoints_reject_friction_before_meshing(self):
        model=friction_model()
        model.supports[-1].type='anchor'
        with TemporaryDirectory() as root:
            calls=(
                lambda: PipeVolumeStudyExporter().export_analysis_study(model,'Cold',root,element_ids=['pipe'],max_element_size=.1),
                lambda: MixedCodeAsterStudyExporter().export_analysis_study(model,'Cold',root),
                lambda: CodeAsterSolver().export_volume_study(model,'Cold',root,element_ids=['pipe'],max_element_size=.1),
                lambda: CodeAsterSolver().export_mixed_analysis_study(model,'Cold',root),
            )
            for call in calls:
                with self.assertRaisesRegex(ValueError,'Native friction requires'):
                    call()
            self.assertEqual(list(Path(root).iterdir()),[])

    def test_volume_and_mixed_wrappers_reject_load_path(self):
        model=friction_model()
        solver=CodeAsterSolver(load_path=['Cold','Hot','Cold'])
        with TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'volume/mixed paths are unsupported'):
                solver.export_volume_study(model,'Cold',root,element_ids=['pipe'],max_element_size=.1)
            with self.assertRaisesRegex(ValueError,'volume/mixed paths are unsupported'):
                solver.export_mixed_analysis_study(model,'Cold',root)
            self.assertEqual(list(Path(root).iterdir()),[])

    def test_native_path_rejects_other_support_movement(self):
        model=friction_model()
        model.supports[0].imposed_displacement=[.01,0.,0.]
        with TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'prescribed support movement'):
                CodeAsterSolver(pipe_modelization='POU_D_T').export_analysis_study(model,'Cold',root)
            self.assertFalse(Path(root,'study.comm').exists())


if __name__ == '__main__':
    unittest.main()
