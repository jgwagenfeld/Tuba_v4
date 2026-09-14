import unittest

import numpy as np

from tuba import Model


class TestModelNodeApi(unittest.TestCase):
    def test_add_node_accepts_python_sequences_and_numpy_arrays(self):
        model = Model()

        list_node = model.add_node([1, 2, 3])
        tuple_node = model.add_node((4, 5, 6))
        array_node = model.add_node(np.array([7, 8, 9]))

        self.assertEqual(model.nodes[list_node].coords.tolist(), [1.0, 2.0, 3.0])
        self.assertEqual(model.nodes[tuple_node].coords.tolist(), [4.0, 5.0, 6.0])
        self.assertEqual(model.nodes[array_node].coords.tolist(), [7.0, 8.0, 9.0])


if __name__ == "__main__":
    unittest.main()
