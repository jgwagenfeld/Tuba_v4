import tempfile
import unittest
from pathlib import Path

import numpy as np

from tuba.analysis.rmed import read_rmed_mesh_summary


class TestRmedArtifacts(unittest.TestCase):
    def test_missing_h5py_error_is_actionable_or_summary_loads(self):
        try:
            import h5py
        except ImportError:
            with self.assertRaisesRegex(ImportError, "h5py"):
                read_rmed_mesh_summary("missing.rmed")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "study.rmed"
            with h5py.File(path, "w") as f:
                mesh_root = f.create_group("ENS_MAA")
                mesh = mesh_root.create_group("mesh")
                mesh.attrs["ESP"] = 3
                noe = mesh.create_group("NOE")
                coo = noe.create_dataset("COO", data=np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0]))
                coo.attrs["NBR"] = 2
                mai = mesh.create_group("MAI")
                seg2 = mai.create_group("SE2")
                nod = seg2.create_dataset("NOD", data=np.array([1, 2]))
                nod.attrs["NBR"] = 1
                seg2.create_dataset("NUM", data=np.array([10]))

            summary = read_rmed_mesh_summary(path)

        self.assertEqual(summary["node_count"], 2)
        self.assertEqual(summary["element_count"], 1)
        self.assertEqual(summary["element_types"], {"SE2": 1})
