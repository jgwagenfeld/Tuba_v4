"""Write the standard profile library as JSON for every viewer surface."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuba.visualization.profile_catalog import profile_catalog


if __name__ == "__main__":
    sys.stdout.buffer.write(json.dumps(profile_catalog(), allow_nan=False).encode("utf-8"))
