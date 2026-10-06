"""Native analysis-mesh generation."""

from tuba.meshing.policy import ResolvedMeshPolicy, resolve_mesh_policy

__all__ = ["GeneratedPipeVolumeMesh", "build_pipe_volume_mesh", "ResolvedMeshPolicy", "resolve_mesh_policy"]


# Mesh generation needs gmsh; the sizing policy does not. Every scene build reads
# the policy, including the browser preview, where gmsh does not exist - so the
# generator is imported when it is first asked for, not with the package.
def __getattr__(name):
    if name in {"GeneratedPipeVolumeMesh", "build_pipe_volume_mesh"}:
        from tuba.meshing import pipe_volume

        return getattr(pipe_volume, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
