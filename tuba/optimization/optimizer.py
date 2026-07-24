"""Base optimizer classes, solver-scored support searches, and LLM interfaces."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from tuba.model import TubaModel, Support
from tuba.solver.base import FEAResults
from tuba.optimization.objectives import ObjectiveEvaluator


class BasePipingOptimizer(ABC):
    """Abstract base class for piping optimization algorithms."""

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
                    "direction": s.direction,
                    "stiffness_matrix": s.stiffness_matrix,
                }
                for s in model.supports
            ],
            "evaluation": eval_report
        }
        return json.dumps(context, indent=2)

    def _spring_stiffness_matrix_from_suggestion(self, suggestion: Dict[str, Any]) -> Optional[List[float]]:
        """Return an explicit six-DOF spring matrix from an LLM suggestion."""
        matrix = suggestion.get("stiffness_matrix")
        if matrix is not None:
            if len(matrix) != 6:
                raise ValueError("stiffness_matrix must contain six values.")
            return [float(value) for value in matrix]

        v2_components = [suggestion.get(key, 0.0) for key in ("x", "y", "z", "rx", "ry", "rz")]
        if any(value not in (None, 0, 0.0) for value in v2_components):
            return [float(value or 0.0) for value in v2_components]

        stiffness = suggestion.get("stiffness")
        if stiffness is None:
            return None

        direction = suggestion.get("direction")
        if not direction:
            raise ValueError("spring stiffness requires stiffness_matrix, v2 components, or direction.")
        matrix = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        for idx, value in enumerate(direction[:3]):
            if abs(float(value)) > 1e-12:
                matrix[idx] = float(stiffness)
        return matrix

    def apply_llm_suggestions(self, model: TubaModel, suggestions_json: str) -> List[str]:
        """Applies a list of support updates suggested by the LLM.

        Example Suggestions JSON:
        [
            {"action": "ADD", "node": "N14", "type": "rest", "direction": [0.0, 1.0, 0.0]},
            {"action": "MODIFY", "node": "N5", "type": "spring", "stiffness_matrix": [0.0, 150000.0, 0.0, 0.0, 0.0, 0.0]},
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
            try:
                stiffness_matrix = self._spring_stiffness_matrix_from_suggestion(sug) if sup_type == "spring" else None
            except ValueError as e:
                logs.append(f"{action} spring support at node {node} rejected: {e}")
                continue

            if action == "ADD":
                if not node or not sup_type:
                    logs.append("ADD action requires node and type.")
                    continue
                # Ensure no duplicate support
                model.supports = [s for s in model.supports if s.node != node]
                model.add_support(node=node, type=sup_type, direction=direction, stiffness_matrix=stiffness_matrix)
                logs.append(f"Added {sup_type} support at node {node}")

            elif action == "MODIFY":
                found = False
                for s in model.supports:
                    if s.node == node:
                        if sup_type: s.type = sup_type
                        if direction: s.direction = direction
                        if stiffness_matrix:
                            s.stiffness = None
                            s.stiffness_matrix = stiffness_matrix
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
        """Return the model with fresh solver results.

        Layout changes from LLMs must arrive through explicit suggestions.
        This method only runs the configured solver and fails loudly if solver
        artifacts are unavailable.
        """
        try:
            results = model.solve()
        except Exception as exc:
            raise RuntimeError(
                "LLMSupportOptimizer requires a successful solver run; no support layout was optimized."
            ) from exc
        if results is None:
            raise RuntimeError("LLMSupportOptimizer did not receive solver results.")
            
        return model, results


class GeneticSupportPlacer(BasePipingOptimizer):
    """Genetic Algorithm optimizer for support type and location selection.

    Encodes support configurations as binary chromosomes where each candidate
    location can be: no support (0), rest (1), guide (2), or spring (3).
    Evolves a population over generations using tournament selection, uniform
    crossover, and random mutation to minimise the objective evaluator score.
    """

    DEFAULT_SUPPORT_GENES = [None, "rest", "guide"]

    def __init__(
        self,
        population_size: int = 20,
        generations: int = 30,
        mutation_rate: float = 0.15,
        tournament_size: int = 3,
        spring_stiffness_matrix: Sequence[float] | None = None,
    ) -> None:
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.spring_stiffness_matrix = self._validate_spring_stiffness_matrix(spring_stiffness_matrix)
        self.support_genes = list(self.DEFAULT_SUPPORT_GENES)
        if self.spring_stiffness_matrix is not None:
            self.support_genes.append("spring")

    @staticmethod
    def _validate_spring_stiffness_matrix(values: Sequence[float] | None) -> list[float] | None:
        if values is None:
            return None
        if len(values) != 6:
            raise ValueError("spring_stiffness_matrix must contain six values.")
        return [float(value) for value in values]

    def _get_candidate_nodes(self, model: TubaModel) -> List[str]:
        """Returns interior pipe nodes that are eligible for support placement."""
        anchor_nodes = {s.node for s in model.supports if s.type == "anchor"}
        pipe_nodes = []
        for elem in model.elements:
            if elem.type in ("pipe_straight", "pipe_bend"):
                for nid in (elem.n1, elem.n2):
                    if nid not in anchor_nodes and nid not in pipe_nodes:
                        pipe_nodes.append(nid)
        return pipe_nodes

    def _encode_chromosome(self, length: int) -> np.ndarray:
        """Random chromosome: array of ints in [0, 3]."""
        return np.random.randint(0, len(self.support_genes), size=length)

    def _apply_chromosome(
        self, model: TubaModel, candidate_nodes: List[str], chromosome: np.ndarray
    ) -> None:
        """Clear non-anchor supports, then apply chromosome encoding."""
        model.supports = [s for s in model.supports if s.type == "anchor"]
        supported = {s.node for s in model.supports}
        for i, gene in enumerate(chromosome):
            if int(gene) >= len(self.support_genes):
                raise ValueError(
                    f"Support gene {int(gene)} is not available. "
                    "Provide spring_stiffness_matrix to enable spring genes."
                )
            sup_type = self.support_genes[int(gene)]
            if sup_type is not None and candidate_nodes[i] not in supported:
                kwargs: Dict[str, Any] = {"node": candidate_nodes[i], "type": sup_type}
                if sup_type == "rest":
                    kwargs["direction"] = [0.0, 1.0, 0.0]
                elif sup_type == "guide":
                    kwargs["direction"] = [1.0, 0.0, 1.0]
                elif sup_type == "spring":
                    if self.spring_stiffness_matrix is None:
                        raise ValueError("Spring genes require an explicit spring_stiffness_matrix.")
                    kwargs["stiffness_matrix"] = list(self.spring_stiffness_matrix)
                model.add_support(**kwargs)

    def _tournament_select(
        self, population: List[np.ndarray], scores: List[float]
    ) -> np.ndarray:
        """Select a parent via tournament selection."""
        indices = np.random.choice(len(population), size=self.tournament_size, replace=False)
        best = min(indices, key=lambda i: scores[i])
        return population[best].copy()

    def _crossover(self, p1: np.ndarray, p2: np.ndarray) -> np.ndarray:
        """Uniform crossover."""
        mask = np.random.randint(0, 2, size=len(p1)).astype(bool)
        child = np.where(mask, p1, p2)
        return child

    def _mutate(self, chromosome: np.ndarray) -> np.ndarray:
        """Random gene mutation."""
        for i in range(len(chromosome)):
            if np.random.random() < self.mutation_rate:
                chromosome[i] = np.random.randint(0, len(self.support_genes))
        return chromosome

    def optimize(
        self,
        model: TubaModel,
        evaluator: ObjectiveEvaluator,
        **kwargs,
    ) -> Tuple[TubaModel, Optional[FEAResults]]:
        """Run the genetic algorithm optimisation loop.

        Returns the model configured with the best-scoring support layout and
        the corresponding FEA results.
        """
        import copy

        candidate_nodes = self._get_candidate_nodes(model)
        n_genes = len(candidate_nodes)
        if n_genes == 0:
            return model, None

        # Initialise population
        population = [self._encode_chromosome(n_genes) for _ in range(self.population_size)]
        best_chromosome = population[0].copy()
        best_score = float("inf")
        best_results: Optional[FEAResults] = None
        history: List[float] = []

        for gen in range(self.generations):
            scores: List[float] = []

            for chromosome in population:
                temp_model = copy.deepcopy(model)
                self._apply_chromosome(temp_model, candidate_nodes, chromosome)

                try:
                    results = temp_model.solve()
                except Exception:
                    scores.append(float("inf"))
                    continue
                if results is None:
                    scores.append(float("inf"))
                    continue

                score = evaluator.evaluate_model(temp_model, results)
                scores.append(score)

                if score < best_score:
                    best_score = score
                    best_chromosome = chromosome.copy()
                    best_results = results

            history.append(best_score)

            # Breed next generation
            next_pop: List[np.ndarray] = [best_chromosome.copy()]  # elitism
            while len(next_pop) < self.population_size:
                p1 = self._tournament_select(population, scores)
                p2 = self._tournament_select(population, scores)
                child = self._crossover(p1, p2)
                child = self._mutate(child)
                next_pop.append(child)

            population = next_pop

        if best_results is None or not np.isfinite(best_score):
            raise RuntimeError("GeneticSupportPlacer found no solver-backed candidate; model was not modified.")

        # Apply best configuration to the original model
        self._apply_chromosome(model, candidate_nodes, best_chromosome)
        self._history = history
        return model, best_results
