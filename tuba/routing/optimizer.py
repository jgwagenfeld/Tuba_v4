"""Base optimizer classes, heuristic support placers, and LLM-AI interfaces."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from tuba.model import TubaModel, Support
from tuba.solver.base import FEAResults
from tuba.routing.objectives import ObjectiveEvaluator


class BasePipingOptimizer(ABC):
    """Abstract base class for piping optimization algorithms."""

    def __init__(self, solver_name: str = "code_aster") -> None:
        self.solver_name = solver_name

    @abstractmethod
    def optimize(
        self,
        model: TubaModel,
        evaluator: ObjectiveEvaluator,
        **kwargs,
    ) -> Tuple[TubaModel, Optional[FEAResults]]:
        """Run the optimization loop.

        Returns the optimized model and the associated FEA results.
        """
        pass


class RuleBasedSupportPlacer(BasePipingOptimizer):
    """Heuristic optimizer that places vertical rests and lateral guides at standard span intervals."""

    def __init__(self, solver_name: str = "code_aster", deflection_limit_m: float = 0.0025) -> None:
        super().__init__(solver_name)
        self.deflection_limit = deflection_limit_m

    def _calculate_max_span(self, model: TubaModel, section_name: str, material_name: str) -> float:
        """Calculates ASME B31.3 continuous beam span limit for a 2.5mm deflection limit.

        L = ((384 * E * I * delta) / (5 * w))^(1/4)
        """
        sec = model.sections.get(section_name)
        mat = model.materials.get(material_name)
        if not sec or not mat:
            return 6.0 # Fallback 6 meters standard span

        # Estimate weight per meter (steel density * area + water weight approximation)
        area = sec.area
        w_steel = area * mat.rho * 9.81
        w_fluid = (np.pi * (sec.ID / 2.0)**2) * 1000.0 * 9.81 if hasattr(sec, 'ID') else 0.0
        w_total = w_steel + w_fluid

        # Calculate max span
        E = mat.E
        I_val = sec.I if hasattr(sec, 'I') else (sec.area ** 2 / 12.0) # Approx
        
        numerator = 384.0 * E * I_val * self.deflection_limit
        denominator = 5.0 * w_total
        
        if denominator <= 0:
            return 6.0

        return float((numerator / denominator) ** 0.25)

    def optimize(
        self,
        model: TubaModel,
        evaluator: ObjectiveEvaluator,
        **kwargs,
    ) -> Tuple[TubaModel, Optional[FEAResults]]:
        """Algorithm:

        1. Clear existing non-anchor supports.
        2. Walk the pipe runs and place rests at L_max intervals.
        3. Walk the pipe runs and place guides at 2.5 * L_max intervals.
        4. Run FEA and check if deflection limit is satisfied.
        5. If deflection exceeds limit, reduce span limit and repeat up to 5 times.
        """
        if not model.elements:
            return model, None

        first_elem = model.elements[0]
        max_span = self._calculate_max_span(model, first_elem.section, first_elem.material)
        current_span = max_span
        
        # Deepcopy the original model to keep a pristine reference
        import copy
        best_model = copy.deepcopy(model)
        best_results = None
        best_score = float('inf')

        # Limit to 5 feedback loop iterations
        for iteration in range(5):
            # Clear non-anchor supports
            model.supports = [s for s in model.supports if s.type == "anchor"]
            supported_nodes = {s.node for s in model.supports}

            accumulated_length = 0.0
            guide_length = 0.0
            
            # Place supports
            for elem in model.elements:
                p1 = model.nodes[elem.n1].coords
                p2 = model.nodes[elem.n2].coords
                length = float(np.linalg.norm(p2 - p1))
                
                accumulated_length += length
                guide_length += length

                if accumulated_length >= current_span:
                    if elem.n2 not in supported_nodes:
                        model.add_support(node=elem.n2, type="rest", direction=[0.0, 1.0, 0.0])
                        supported_nodes.add(elem.n2)
                    accumulated_length = 0.0

                if guide_length >= (current_span * 2.5):
                    if elem.n2 not in supported_nodes:
                        model.add_support(node=elem.n2, type="guide", direction=[1.0, 0.0, 1.0])
                        supported_nodes.add(elem.n2)
                    guide_length = 0.0

            # Solve and evaluate
            results = None
            try:
                # Solve using the model's solve function (e.g. CodeAster or mock solver)
                # We specify the solver from self.solver_name
                results = model.solve(solver=self.solver_name)
            except Exception:
                # If solver fails or is not installed, we fallback to returning current state
                break

            if results:
                # Compute maximum deflection
                max_defl = 0.0
                for nid, node_res in results.node_results.items():
                    defl = float(np.linalg.norm(node_res.displacement[:3]))
                    if defl > max_defl:
                        max_defl = defl
                
                # Check score from evaluator
                score = evaluator.evaluate_model(model, results)
                if score < best_score:
                    best_score = score
                    best_results = results
                    best_model = copy.deepcopy(model)
                
                # If deflection is within limits, we are good!
                if max_defl <= self.deflection_limit:
                    break
                else:
                    # Deflection too high, scale down span based on ratio
                    ratio = self.deflection_limit / max_defl
                    scale = max(0.5, min(0.85, ratio))
                    current_span *= scale
            else:
                break

        # Restore the best model's supports and return it
        model.supports = best_model.supports
        return model, best_results


class LLMSupportOptimizer(BasePipingOptimizer):
    """Bridge for Large Language Models (LLMs) to optimize piping layout and supports.

    Provides JSON contexts representing the state, stress hotspots, and clashes,
    and consumes structured layout instructions from the LLM.
    """

    def get_llm_context(self, model: TubaModel, results: Optional[FEAResults] = None, evaluator: Optional[ObjectiveEvaluator] = None) -> str:
        """Serializes the piping system and stress status into a clean JSON context for LLMs."""
        eval_report = {}
        if evaluator:
            eval_report = evaluator.get_detailed_scores(model, results)

        context = {
            "project_name": model.project_name,
            "standard": model.standard,
            "nodes": {nid: n.coords.tolist() for nid, n in model.nodes.items()},
            "elements": [
                {
                    "id": e.id,
                    "type": e.type,
                    "n1": e.n1,
                    "n2": e.n2,
                    "section": e.section,
                    "material": e.material
                }
                for e in model.elements
            ],
            "supports": [
                {
                    "node": s.node,
                    "type": s.type,
                    "direction": s.direction
                }
                for s in model.supports
            ],
            "evaluation": eval_report
        }
        return json.dumps(context, indent=2)

    def apply_llm_suggestions(self, model: TubaModel, suggestions_json: str) -> List[str]:
        """Applies a list of support updates suggested by the LLM.

        Example Suggestions JSON:
        [
            {"action": "ADD", "node": "N14", "type": "rest", "direction": [0.0, 1.0, 0.0]},
            {"action": "MODIFY", "node": "N5", "type": "spring", "stiffness": 150000.0},
            {"action": "DELETE", "node": "N2"}
        ]
        """
        try:
            suggestions = json.loads(suggestions_json)
        except Exception as e:
            return [f"Failed to parse suggestions JSON: {e}"]

        logs = []
        for sug in suggestions:
            action = sug.get("action", "").upper()
            node = sug.get("node")
            sup_type = sug.get("type")
            direction = sug.get("direction")
            stiffness = sug.get("stiffness")

            if action == "ADD":
                if not node or not sup_type:
                    logs.append("ADD action requires node and type.")
                    continue
                # Ensure no duplicate support
                model.supports = [s for s in model.supports if s.node != node]
                model.add_support(node=node, type=sup_type, direction=direction, stiffness=stiffness)
                logs.append(f"Added {sup_type} support at node {node}")

            elif action == "MODIFY":
                found = False
                for s in model.supports:
                    if s.node == node:
                        if sup_type: s.type = sup_type
                        if direction: s.direction = direction
                        if stiffness: s.stiffness = stiffness
                        found = True
                        logs.append(f"Modified support at node {node}")
                        break
                if not found:
                    logs.append(f"Support at node {node} not found to modify.")

            elif action == "DELETE":
                model.supports = [s for s in model.supports if s.node != node]
                logs.append(f"Deleted support at node {node}")

        return logs

    def optimize(
        self,
        model: TubaModel,
        evaluator: ObjectiveEvaluator,
        **kwargs,
    ) -> Tuple[TubaModel, Optional[FEAResults]]:
        """LLMOptimizer works interactively.

        For automated execution, it can call a mocked heuristic or raise NotImplemented.
        """
        # Run solver to get current FEA results
        try:
            results = model.solve(solver=self.solver_name)
        except Exception:
            results = None
            
        return model, results
