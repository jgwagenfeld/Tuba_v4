import unittest

from tuba.project.script import GENERATED_HEADER, check_model_script, require_model_script_style


class TestModelScriptLint(unittest.TestCase):
    def test_builder_script_is_clean(self):
        text = (
            "from tuba import Model\n"
            'model = Model("P")\n'
            'with model.pipe(section="DN100", material="Steel") as p:\n'
            "    p.start([0.0, 0.0, 0.0])\n"
            "    p.run(2.0)\n"
            "    p.end([2.0, 0.0, 0.0])\n"
        )
        self.assertEqual(check_model_script(text), [])

    def test_loop_counts_once(self):
        text = (
            "from tuba import Model\n"
            'model = Model("P")\n'
            "for i in range(40):\n"
            "    model.add_node([float(i), 0.0, 0.0])\n"
        )
        self.assertEqual(check_model_script(text), [])

    def test_raw_dump_is_reported(self):
        calls = "".join(f"model.add_node([{i}.0, 0.0, 0.0])\n" for i in range(12))
        findings = check_model_script(calls)

        self.assertEqual(len(findings), 1)
        self.assertIn("12", findings[0])
        self.assertIn("assemble", findings[0])

    def test_a_unit_body_is_not_a_dump(self):
        text = (
            "from tuba import Model\n"
            "from tuba.assemblies import assemble\n"
            'model = Model("P")\n'
            "def tee(model, station=0.0):\n"
            "    hub = model.add_node([station, 0.0, 0.0])\n"
            "    for i in range(20):\n"
            "        other = model.add_node([station + float(i), 0.0, 0.0])\n"
            "        model.add_element(id=f'e{i}', type='beam', n1=hub, n2=other, section='S', material='M')\n"
            "assemble(model, 'tee')\n"
        )
        self.assertEqual(check_model_script(text), [])

    def test_generated_script_is_exempt(self):
        text = GENERATED_HEADER + "\n" + "".join(
            f"model.add_node([{i}.0, 0.0, 0.0])\n" for i in range(50)
        )
        self.assertEqual(check_model_script(text), [])

    def test_require_refuses_a_dump(self):
        calls = "".join(f"model.add_element(id='e{i}', type='beam', n1='a', n2='b', section='S', material='M')\n" for i in range(9))

        with self.assertRaises(ValueError):
            require_model_script_style(calls)

    def test_reference_layout_is_within_budget(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        text = (root / "examples" / "hydrogen-plant-layout" / "model.py").read_text(encoding="utf-8")
        self.assertEqual(check_model_script(text), [])


if __name__ == "__main__":
    unittest.main()
