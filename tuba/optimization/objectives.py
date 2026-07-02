"""Modular evaluation objectives for piping design optimization."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

from tuba.model import TubaModel
from tuba.solver.base import FEAResults
from tuba.geometry.collision import PipingCollisionChecker


class BaseObjective(ABC):
    """Abstract base class for a single optimization objective."""

    def __init__(self, weight: float = 1.0) -> None:
        self.weight = weight

    @abstractmethod
    def evaluate(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> float:
        """Evaluate the model and/or FEA results, returning a scalar penalty score.

        A score of 0.0 means perfect satisfaction. Higher scores denote worse compliance.
        """
        pass

    @abstractmethod
    def get_details(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> Dict[str, Any]:
        """Return diagnostic details of the evaluation."""
        pass


class StressObjective(BaseObjective):
    """Penalizes maximum stress ratio across elements."""

    def __init__(self, weight: float = 1.0, threshold: float = 1.0) -> None:
        super().__init__(weight)
        self.threshold = threshold

    def evaluate(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> float:
        if not results:
            return 0.0
        
        penalty = 0.0
        # Calculate stress ratio relative to allowable stress using compliance evaluator
        from tuba.compliance.asme_b313 import ASMEB313Evaluator
        evaluator = ASMEB313Evaluator()
        report = evaluator.evaluate(model, results)
        
        for res in report.results:
            # Stress ratio is the ratio of actual stress to allowable stress
            max_ratio = max(
                res.sustained_ratio,
                res.expansion_ratio
            )
            # If stress ratio exceeds our safety threshold, add exponential penalty
            if max_ratio > self.threshold:
                penalty += float((max_ratio - self.threshold) ** 2) * 100.0
            else:
                # Small linear penalty even below threshold to encourage minimizing stress
                penalty += float(max_ratio)
                
        return penalty * self.weight

    def get_details(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> Dict[str, Any]:
        if not results:
            return {"error": "No FEA results provided."}
        from tuba.compliance.asme_b313 import ASMEB313Evaluator
        report = ASMEB313Evaluator().evaluate(model, results)
        max_ratio = 0.0
        worst_element = None
        for res in report.results:
            ratio = max(res.sustained_ratio, res.expansion_ratio)
            if ratio > max_ratio:
                max_ratio = ratio
                worst_element = res.element_id
        return {
            "max_stress_ratio": max_ratio,
            "worst_element": worst_element,
            "pass": report.overall_pass
        }


class DeflectionObjective(BaseObjective):
    """Penalizes vertical sag or excessive displacement (default threshold 2.5mm)."""

    def __init__(self, weight: float = 1.0, max_deflection_m: float = 0.0025) -> None:
        super().__init__(weight)
        self.max_deflection_m = max_deflection_m

    def evaluate(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> float:
        if not results:
            return 0.0
        
        penalty = 0.0
        for nid, node_res in results.node_results.items():
            disp = node_res.displacement[:3] # Translation ux, uy, uz
            deflection = float(np.linalg.norm(disp))
            
            if deflection > self.max_deflection_m:
                # Heavy penalty if deflection exceeds industry standard 2.5mm limit
                penalty += ((deflection - self.max_deflection_m) / self.max_deflection_m) ** 2 * 50.0
            else:
                # Small penalty to encourage minimizing overall deflection
                penalty += deflection / self.max_deflection_m
                
        return penalty * self.weight

    def get_details(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> Dict[str, Any]:
        if not results:
            return {"error": "No FEA results."}
        max_defl = 0.0
        worst_node = None
        for nid, node_res in results.node_results.items():
            defl = float(np.linalg.norm(node_res.displacement[:3]))
            if defl > max_defl:
                max_defl = defl
                worst_node = nid
        return {
            "max_deflection_mm": max_defl * 1000.0,
            "worst_node": worst_node,
            "within_limit": max_defl <= self.max_deflection_m
        }


class SupportCostObjective(BaseObjective):
    """Penalizes the total number of supports and type complexity (e.g. spring hangers cost more than rests)."""

    def __init__(self, weight: float = 1.0, cost_map: Optional[Dict[str, float]] = None) -> None:
        super().__init__(weight)
        # Cost multipliers for support types
        self.cost_map = cost_map or {
            "rest": 1.0,
            "guide": 1.5,
            "anchor": 2.0,
            "spring": 4.0,
            "hanger": 3.0
        }

    def evaluate(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> float:
        total_cost = 0.0
        for sup in model.supports:
            cost = self.cost_map.get(sup.type, 1.0)
            total_cost += cost
        return total_cost * self.weight

    def get_details(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> Dict[str, Any]:
        counts = {}
        for s in model.supports:
            counts[s.type] = counts.get(s.type, 0) + 1
        return {
            "support_counts": counts,
            "total_supports": len(model.supports)
        }


class ClashObjective(BaseObjective):
    """Penalizes physical overlaps between pipe and obstacles. Supports deformed collision checks."""

    def __init__(self, weight: float = 1.0, check_deformed: bool = True) -> None:
        super().__init__(weight)
        self.check_deformed = check_deformed

    def evaluate(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> float:
        if not model.obstacles:
            return 0.0

        operating_clashes = self._operating_clashes(model, **context)
        if operating_clashes is not None:
            return len(operating_clashes) * 500.0 * self.weight
            
        try:
            checker = PipingCollisionChecker(model)
        except (ImportError, Exception):
            # Fallback if trimesh not present or fails to initialize
            return 0.0

        colliding_elements = []
        if self.check_deformed and results:
            # Check for deformed (hot) clashes
            if hasattr(checker, "check_deformed_collisions"):
                colliding_elements = checker.check_deformed_collisions(results)
            else:
                colliding_elements = checker.check_collisions()
        else:
            colliding_elements = checker.check_collisions()

        # Heavy penalty per clashing element
        return len(colliding_elements) * 500.0 * self.weight

    def get_details(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> Dict[str, Any]:
        operating_clashes = self._operating_clashes(model, **context)
        if operating_clashes is not None:
            return {
                "operating_clash_count": len(operating_clashes),
                "operating_clashes": [clash.to_dict() for clash in operating_clashes],
                "clean": len(operating_clashes) == 0,
            }
        try:
            checker = PipingCollisionChecker(model)
            if self.check_deformed and results and hasattr(checker, "check_deformed_collisions"):
                colliding = checker.check_deformed_collisions(results)
            else:
                colliding = checker.check_collisions()
        except Exception as e:
            return {"error": f"Collision engine error: {e}"}
            
        return {
            "colliding_elements": colliding,
            "collision_count": len(colliding),
            "clean": len(colliding) == 0
        }

    def _operating_clashes(self, model: TubaModel, **context: Any):
        result_state = context.get("result_state")
        geometry_state = context.get("geometry_state") or context.get("operating_state")
        if result_state is None or geometry_state is None:
            return None
        from tuba.analysis.states import create_cold_geometry_state
        from tuba.clash import ClashEngine

        cold_state = context.get("cold_state") or create_cold_geometry_state(model)
        return ClashEngine().check_operating_state(
            model,
            cold_state=cold_state,
            operating_state=geometry_state,
            result_state=result_state,
            envelope_type=context.get("envelope_type", "insulation"),
            clearance_m=context.get("clearance_m", 0.0),
            analysis_mesh=context.get("analysis_mesh"),
        )


class ObjectiveEvaluator:
    """Aggregates multiple objectives to score a piping design configuration."""

    def __init__(self, objectives: Optional[List[BaseObjective]] = None) -> None:
        self.objectives = objectives or [
            StressObjective(weight=1.0),
            DeflectionObjective(weight=1.5),
            SupportCostObjective(weight=0.1),
            ClashObjective(weight=2.0)
        ]

    def evaluate_model(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> float:
        """Returns the aggregate penalty score."""
        total_score = 0.0
        for obj in self.objectives:
            total_score += obj.evaluate(model, results, **context)
        return total_score

    def get_detailed_scores(self, model: TubaModel, results: Optional[FEAResults] = None, **context: Any) -> Dict[str, Any]:
        """Returns a breakdown of scores and diagnostic data."""
        breakdown = {}
        total = 0.0
        for obj in self.objectives:
            name = obj.__class__.__name__
            score = obj.evaluate(model, results, **context)
            total += score
            breakdown[name] = {
                "score": score,
                "details": obj.get_details(model, results, **context)
            }
        breakdown["TotalScore"] = total
        return breakdown
