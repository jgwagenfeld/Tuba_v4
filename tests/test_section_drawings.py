import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs" / "site" / "assets" / "generate_section_drawings.py"


def _load():
    spec = importlib.util.spec_from_file_location("generate_section_drawings", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plate_and_details_render_from_real_dims(tmp_path):
    mod = _load()
    mod.main(out_dir=tmp_path)

    plate = tmp_path / "sections.svg"
    assert plate.exists() and plate.stat().st_size > 0
    ET.parse(plate)  # well-formed XML
    text = plate.read_text(encoding="utf-8")
    # data-driven: the real Tuba dimensions must appear as text in the drawing
    for token in [mod.DIA + "114.3", "HE200B", mod.DIA + "180", "240", "R40"]:
        assert token in text, f"plate missing {token!r}"

    for name in ["section_pipe.svg", "section_bar.svg", "section_cable.svg",
                 "section_rect.svg", "section_ibeam.svg", "bend_detail.svg",
                 "dataflow.svg"]:
        f = tmp_path / name
        assert f.exists() and f.stat().st_size > 0, name
        ET.parse(f)

    dataflow = (tmp_path / "dataflow.svg").read_text(encoding="utf-8")
    for token in ["Model", "Code_Aster", "ResultState"]:
        assert token in dataflow, f"dataflow missing {token!r}"
