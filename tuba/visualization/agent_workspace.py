"""Persistent, constrained Python workspace for agentic scene proposals."""

from __future__ import annotations

import ast
import contextlib
import io
from dataclasses import dataclass, field
from typing import Any

from tuba.model import TubaModel
from tuba.patches import AddElement, AddNode, AddSupport, AssignAttribute, CreateGroup, ModelPatch
from tuba.visualization.builders import build_visualization_scene
from tuba.visualization.live_preview import preview_json_patch
from tuba.visualization.scene import AgentProposal


@dataclass
class WorkspaceCellResult:
    code: str
    ok: bool
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    variables: dict[str, dict[str, str]] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_trace(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "ok": self.ok,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
            "diagnostics": list(self.diagnostics),
        }


@dataclass
class AgentWorkspaceSession:
    agent_id: str
    goal: str
    cells: list[WorkspaceCellResult] = field(default_factory=list)


class AgenticPythonWorkspace:
    """Run trusted small Python cells against a temporary model copy."""

    def __init__(self, model: TubaModel, *, agent_id: str, goal: str) -> None:
        self._committed_model = TubaModel.from_dict(model.to_dict())
        self.session = AgentWorkspaceSession(agent_id=agent_id, goal=goal)
        self.namespace: dict[str, Any] = {
            "__builtins__": _safe_builtins(),
            "model": TubaModel.from_dict(model.to_dict()),
            "ModelPatch": ModelPatch,
            "AddNode": AddNode,
            "AddElement": AddElement,
            "AddSupport": AddSupport,
            "CreateGroup": CreateGroup,
            "AssignAttribute": AssignAttribute,
            "build_visualization_scene": build_visualization_scene,
            "show_scene": self._show_scene,
        }

    def execute_cell(self, code: str) -> WorkspaceCellResult:
        diagnostic = _unsafe_diagnostic(code)
        if diagnostic is not None:
            result = WorkspaceCellResult(code=code, ok=False, diagnostics=[diagnostic])
            self.session.cells.append(result)
            return result

        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(compile(code, "<agent-workspace>", "exec"), self.namespace)
            result = WorkspaceCellResult(
                code=code,
                ok=True,
                stdout=stdout.getvalue(),
                stderr=stderr.getvalue(),
                variables=_variable_summary(self.namespace),
            )
        except Exception as exc:
            result = WorkspaceCellResult(
                code=code,
                ok=False,
                stdout=stdout.getvalue(),
                stderr=stderr.getvalue(),
                error=str(exc),
                variables=_variable_summary(self.namespace),
            )
        self.session.cells.append(result)
        return result

    def finalize_proposal(self, patch_variable: str, *, rationale: str) -> AgentProposal:
        patch = self.namespace[patch_variable]
        if isinstance(patch, dict):
            patch = ModelPatch.from_dict(patch)
        preview = preview_json_patch(self._committed_model, patch)
        preview_message = preview.messages[0] if preview.messages else {"type": "diagnostic"}
        created_refs = []
        if preview.scene and preview.scene.agent_proposals:
            created_refs = preview.scene.agent_proposals[0].created_entity_refs
        return AgentProposal(
            proposal_id=f"proposal:{self.session.agent_id}",
            agent_id=self.session.agent_id,
            goal=self.session.goal,
            rationale=rationale,
            model_patch=patch.to_dict(),
            created_entity_refs=created_refs,
            risks=[diagnostic.message for diagnostic in preview.diagnostics],
            extra={
                "execution_trace": [cell.to_trace() for cell in self.session.cells],
                "preview": preview_message,
            },
        )

    def _show_scene(self):
        scene = build_visualization_scene(self.namespace["model"])
        return {"scene_id": scene.scene_id, "object_count": len(scene.objects)}


def _unsafe_diagnostic(code: str) -> dict[str, Any] | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"severity": "error", "code": "agent_workspace.syntax_error", "message": str(exc)}
    blocked_names = {"open", "eval", "exec", "__import__", "compile", "input"}
    blocked_imports = {"os", "sys", "subprocess", "socket", "pathlib", "shutil"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_names = [alias.name.split(".", 1)[0] for alias in getattr(node, "names", [])]
            if isinstance(node, ast.ImportFrom) and node.module:
                module_names.append(node.module.split(".", 1)[0])
            if any(name in blocked_imports for name in module_names):
                return {"severity": "error", "code": "agent_workspace.unsafe_code", "message": "Blocked unsafe import."}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in blocked_names:
            return {"severity": "error", "code": "agent_workspace.unsafe_code", "message": f"Blocked call to {node.func.id}()."}
    return None


def _variable_summary(namespace: dict[str, Any]) -> dict[str, dict[str, str]]:
    blocked = {"model", "ModelPatch", "AddNode", "AddElement", "AddSupport", "CreateGroup", "AssignAttribute"}
    result: dict[str, dict[str, str]] = {}
    for name, value in namespace.items():
        if name.startswith("_") or name in blocked or callable(value):
            continue
        result[name] = {"type": type(value).__name__, "repr": repr(value)}
    return result


def _safe_builtins() -> dict[str, Any]:
    return {
        "abs": abs,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "print": print,
        "range": range,
        "repr": repr,
        "round": round,
        "set": set,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
