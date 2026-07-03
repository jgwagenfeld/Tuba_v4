# tuba/geometry/importer.py
"""
tuba.geometry.importer — STEP CAD file importer using Gmsh & Trimesh.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional
import numpy as np

try:
    import gmsh
    _HAS_GMSH = True
except ImportError:
    _HAS_GMSH = False

try:
    import trimesh
    _HAS_TRIMESH = True
except ImportError:
    _HAS_TRIMESH = False


class StepGeometryImporter:
    """Imports STEP CAD files and converts them into simplified collision meshes."""

    def __init__(self):
        if not _HAS_GMSH:
            raise ImportError(
                "gmsh is required to import STEP files. Install it with: pip install gmsh"
            )
        if not _HAS_TRIMESH:
            raise ImportError(
                "trimesh is required for mesh representations. Install it with: pip install trimesh"
            )

        # Initialize Gmsh API headlessly
        if not gmsh.isInitialized():
            gmsh.initialize()
            gmsh.option.setNumber("General.Terminal", 0) # Suppress terminal output

    def __del__(self):
        # Gracefully release Gmsh if initialized
        try:
            if gmsh.isInitialized():
                gmsh.finalize()
        except Exception:
            pass

    def import_step(
        self,
        file_path: str,
        mesh_size_limit: float = 0.1,
    ) -> trimesh.Trimesh:
        """Load a STEP file, surface-mesh it, and return a Trimesh object.

        Parameters
        ----------
        file_path : str
            Path to the STEP file.
        mesh_size_limit : float
            Maximum element mesh size in meters.

        Returns
        -------
        trimesh.Trimesh
            The surface mesh of the imported STEP geometry.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"STEP file not found: {file_path}")

        # Add a unique model for this import
        model_name = f"step_import_{os.path.basename(file_path)}"
        gmsh.model.add(model_name)

        try:
            # Import using Open Cascade
            gmsh.model.occ.importShapes(file_path)
            gmsh.model.occ.synchronize()

            # Meshing configuration (2D surface triangulation only)
            gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_size_limit)
            gmsh.model.mesh.generate(2) # 2D boundary meshing

            # Extract mesh vertices and cells
            node_tags, coords, _ = gmsh.model.mesh.getNodes()
            vertices = np.array(coords).reshape(-1, 3)

            # Reindex nodes starting at 0 for trimesh
            node_map = {int(tag): idx for idx, tag in enumerate(node_tags)}

            elem_types, elem_tags, elem_node_tags = gmsh.model.mesh.getElements(dim=2)
            faces = []
            for etype, enodes in zip(elem_types, elem_node_tags):
                if etype == 2: # 3-node triangles
                    reindexed_nodes = [node_map[int(nid)] for nid in enodes]
                    faces = np.array(reindexed_nodes).reshape(-1, 3)
                    break

            if len(faces) == 0:
                # Fallback to empty mesh if no elements generated
                mesh = trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3)))
            else:
                mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

        finally:
            # Clean up the model in Gmsh to avoid memory bloat
            try:
                gmsh.model.remove()
            except Exception:
                pass

        return mesh
