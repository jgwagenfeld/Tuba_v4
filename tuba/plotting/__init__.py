"""tuba.plotting — interactive PyVista result plotting for notebooks.

NOTE: distinct from :mod:`tuba.visualization` (the headless scene/BIM engine).
THIS package is the small, notebook-facing layer: it builds PyVista meshes from a
:class:`~tuba.model.TubaModel` (mesh mode via :func:`~tuba.plotting.pipeline.build_mesh_from_model`,
geometry mode via :func:`~tuba.plotting.pipeline.build_3d_mesh_from_model`), colours
them by Code_Aster results, and renders interactive views (``results.plot_*`` helpers,
``build_model_scene``, PLY/glTF/HTML/Blender export).

For the headless scene / preview-server / web-export / BIM engine, see
:mod:`tuba.visualization`.
"""
