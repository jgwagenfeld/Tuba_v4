"""A supplied STL component placed beside an authored DN100 line and joined at a confirmed port.

The component import is parameterised (STEP or STL, any placement), so the model is built by
``examples/imported_component_mixed_system.py``; this project fixes the gallery's inputs.
"""

from pathlib import Path

from examples.imported_component_mixed_system import build_model

# Relative on purpose, as the gallery has always recorded it: the path is published in the bundle,
# and the browser preview resolves it from the gallery root. A shared package opened anywhere
# else finds the file beside this script instead.
SOURCE = Path("examples/imported_component_mixed_demo/imported_component_demo.stl")
if not SOURCE.exists():
    SOURCE = Path(__file__).resolve().parent / SOURCE.name

model = build_model(SOURCE)
