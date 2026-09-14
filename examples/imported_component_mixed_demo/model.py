"""A supplied STL component placed beside an authored DN100 line and joined at a confirmed port.

The component import is parameterised (STEP or STL, any placement), so the model is built by
``examples/imported_component_mixed_system.py``; this project fixes the gallery's inputs.
"""

from pathlib import Path

from examples.imported_component_mixed_system import build_model

# Relative on purpose, as the gallery has always recorded it: the path is published in the bundle.
SOURCE = Path("examples/assets/imported_component_demo.stl")

model = build_model(SOURCE)
