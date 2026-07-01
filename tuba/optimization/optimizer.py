"""Base optimizer classes, heuristic support placers, and LLM-AI interfaces."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from tuba.model import TubaModel, Support
from tuba.solver.base import FEAResults
from tuba.optimization.objectives import ObjectiveEvaluator


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
        """LLMOptimizer works interactively.

        For automated execution, it can call a mocked heuristic or raise NotImplemented.
        """
        # Run solver to get current FEA results
        try:
            results = model.solve(solver=self.solver_name)
        except Exception:
            results = None
            
        return model, results


class GeneticSupportPlacer(BasePipingOptimizer):
    """Genetic Algorithm optimizer for support type and location selection.

    Encodes support configurations as binary chromosomes where each candidate
    location can be: no support (0), rest (1), guide (2), or spring (3).
    Evolves a population over generations using tournament selection, uniform
    crossover, and random mutation to minimise the objective evaluator score.
    """

    SUPPORT_GENES = [None, "rest", "guide", "spring"]

    def __init__(
        self,
        solver_name: str = "code_aster",
        population_size: int = 20,
        generations: int = 30,
        mutation_rate: float = 0.15,
        tournament_size: int = 3,
    ) -> None:
        super().__init__(solver_name)
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size

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
        return np.random.randint(0, len(self.SUPPORT_GENES), size=length)

    def _apply_chromosome(
        self, model: TubaModel, candidate_nodes: List[str], chromosome: np.ndarray
    ) -> None:
        """Clear non-anchor supports, then apply chromosome encoding."""
        model.supports = [s for s in model.supports if s.type == "anchor"]
        supported = {s.node for s in model.supports}
        for i, gene in enumerate(chromosome):
            sup_type = self.SUPPORT_GENES[gene]
            if sup_type is not None and candidate_nodes[i] not in supported:
                kwargs: Dict[str, Any] = {"node": candidate_nodes[i], "type": sup_type}
                if sup_type == "rest":
                    kwargs["direction"] = [0.0, 1.0, 0.0]
                elif sup_type == "guide":
                    kwargs["direction"] = [1.0, 0.0, 1.0]
                elif sup_type == "spring":
                    kwargs["stiffness_matrix"] = [0.0, 200_000.0, 0.0, 0.0, 0.0, 0.0]
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
                chromosome[i] = np.random.randint(0, len(self.SUPPORT_GENES))
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
                    results = temp_model.solve(solver=self.solver_name)
                except Exception:
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

        # Apply best configuration to the original model
        self._apply_chromosome(model, candidate_nodes, best_chromosome)
        self._history = history
        return model, best_results
