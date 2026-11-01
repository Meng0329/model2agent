"""Core schemas for Model-to-Scientist (SMSC).

Everything the research loop observes or decides is represented here as typed,
validated data. Deterministic code may persist these structures and check them;
it must never fabricate their contents.

Evidence taxonomy (enforced):
  E1  model prediction          — proves only what the model output was
  E2  independent computation   — extra computational evidence (NOT a physical fact)
  E3  historical measurement    — real, traceable prior experimental measurement
  E4  new experiment            — only if an experiment was actually run
E1 may never be reported as E3/E4.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal, Optional

EvidenceType = Literal["E1", "E2", "E3", "E4"]
TaskSplit = Literal["tutorial", "novel", "closed_loop", "insight_rediscovery"]
CapabilityLevel = Literal["L1", "L2", "L3", "L4", "L5", "L6"]
RunStatus = Literal["OBSERVED", "INFERRED", "HYPOTHESIS", "NOT_TESTED", "BLOCKED", "FAILED"]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


# --------------------------------------------------------------------------- #
# Scientific model identity                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class ScientificModelProfile:
    """Machine-checkable description of what a model can and cannot do."""

    slug: str
    domain: str
    task_family: str
    framework: str
    model_id: str
    revision: str                      # pinned commit/sha, never a floating tag
    license: str
    input_spec: dict[str, Any]          # entity, shape, units
    output_spec: dict[str, Any]         # variable, shape, units, scientific meaning
    applicability: list[str]            # where the model is valid
    known_limits: list[str]
    uncertainty_sources: list[str]
    resources: dict[str, Any]           # gpu/disk/expected latency
    provenance: list[str]               # evidence paths: manifest, card, paper, code
    weights_sha256: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.revision) and self.revision not in ("latest", "main"),
                 "profile.revision must be pinned (no floating 'latest'/'main')")
        _require(bool(self.provenance), "profile.provenance must cite real evidence paths")


@dataclass
class ScientificAffordance:
    """A scientific *operation* the model can really execute (not an API guess)."""

    id: str
    model: str
    scientific_task: str
    input_spec: dict[str, Any]
    output_spec: dict[str, Any]
    preconditions: list[str]
    tool: str                          # concrete executable entry (e.g. infer.score_variant)
    scientific_constraints: list[str]
    evidence_source: str
    uncertainty: str
    verified: bool = False
    verification_evidence: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.tool), "affordance.tool must name a real executable entry")
        if self.verified:
            _require(bool(self.verification_evidence),
                     "verified affordance must carry verification_evidence")


@dataclass
class ResearchCapabilityNode:
    id: str
    kind: Literal["model_tool", "data_op", "analysis", "verification"]
    description: str
    io: dict[str, Any]
    preconditions: list[str] = field(default_factory=list)
    cost: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchCapabilityEdge:
    src: str
    dst: str
    kind: Literal["depends_on", "enables", "validates"] = "depends_on"

    def __post_init__(self) -> None:
        _require(self.src != self.dst, "self-loop capability edge is not a real dependency")


@dataclass
class ResearchCapabilityGraph:
    slug: str
    nodes: list[ResearchCapabilityNode]
    edges: list[ResearchCapabilityEdge]
    roots: list[str]

    def __post_init__(self) -> None:
        ids = {n.id for n in self.nodes}
        for e in self.edges:
            _require(e.src in ids and e.dst in ids,
                     f"capability edge references unknown node: {e.src}->{e.dst}")
        if self.edges:
            _require(bool(self.roots), "a graph with real edges must declare roots")


# --------------------------------------------------------------------------- #
# Research planning                                                          #
# --------------------------------------------------------------------------- #
@dataclass
class Hypothesis:
    id: str
    question: str
    statement: str
    testable: bool
    falsifier: str                     # what observation would refute it
    predicted_observation: str
    competing: list[str] = field(default_factory=list)
    evidence_expected: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require(bool(self.falsifier), "hypothesis must be falsifiable")
        _require(bool(self.predicted_observation),
                 "hypothesis must predict an observable outcome")


@dataclass
class ExperimentPlan:
    id: str
    hypothesis_id: str
    design: str
    controls: list[str]
    observation_metric: str
    expected_result: str
    refutation_condition: str
    estimated_cost: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(bool(self.hypothesis_id), "experiment must target a hypothesis")
        _require(bool(self.observation_metric), "experiment must define an observation metric")
        _require(bool(self.refutation_condition), "experiment must define a refutation condition")


@dataclass
class Observation:
    id: str
    experiment_id: str
    tool: str
    input_ref: str
    output: Any
    latency_ms: float
    evidence_type: EvidenceType
    oracle_feedback: Optional[Any] = None
    raw_artifact: Optional[str] = None

    def __post_init__(self) -> None:
        _require(self.evidence_type in ("E1", "E2", "E3", "E4"),
                 f"invalid evidence type: {self.evidence_type}")


@dataclass
class EvidenceRecord:
    """One auditable line of the Scientific Evidence Ledger."""

    id: str
    research_question: str
    hypothesis_id: str
    experiment_id: str
    model: str
    input_data: Any
    control_variables: list[str]
    execution_evidence: str
    observed_result: Any
    evidence_type: EvidenceType
    uncertainty: str
    hypothesis_revision: Optional[str]
    conclusion: Optional[str]
    limitations: list[str]
    timestamp: float

    def __post_init__(self) -> None:
        _require(self.evidence_type in ("E1", "E2", "E3", "E4"),
                 f"invalid evidence type: {self.evidence_type}")
        _require(bool(self.execution_evidence),
                 "evidence must cite how the execution is traceable")


# --------------------------------------------------------------------------- #
# Benchmark tasks                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class TaskSpec:
    task_id: str
    domain: str
    scientific_model: str
    scientific_question: str
    input_resources: dict[str, Any]
    allowed_knowledge: list[str]
    available_tools: list[str]
    experimental_budget: dict[str, Any]
    permitted_actions: list[str]
    hidden_reference: str              # path/key under the hidden oracle store
    execution_oracle: str              # oracle kind: reference_exec | historical
    evidence_oracle: str               # oracle kind for measured feedback
    success_criteria: list[str]
    scientific_constraints: list[str]
    expected_artifacts: list[str]
    failure_conditions: list[str]
    split: TaskSplit = "novel"
    capability_level: CapabilityLevel = "L4"

    def __post_init__(self) -> None:
        _require(bool(self.task_id), "task_id required")
        _require(bool(self.success_criteria), "task must declare success criteria")
        _require(bool(self.hidden_reference), "task must reference hidden ground truth")
        _require(self.execution_oracle in ("reference_exec", "historical"),
                 f"unknown execution oracle: {self.execution_oracle}")
        _require(self.evidence_oracle in ("historical", "reference_exec", "none"),
                 f"unknown evidence oracle: {self.evidence_oracle}")


# --------------------------------------------------------------------------- #
# Run record (every experiment run, immutable)                               #
# --------------------------------------------------------------------------- #
@dataclass
class RunRecord:
    experiment_id: str
    run_id: str
    protocol_version: str
    stage: str
    method_id: str
    method_revision: str
    scientific_domain: str
    scientific_model_id: str
    model_revision: str
    scientific_task_id: str
    task_difficulty: str
    repetition_id: int
    builder_commit: str
    generated_agent_commit: Optional[str]
    sdk_version: str
    llm_model_id: str
    prompt_revision: str
    skill_revision: str
    knowledge_bundle_hash: str
    dataset_revision: str
    oracle_revision: str
    random_seed: int
    resource_budget: dict[str, Any]
    model_call_count: int
    experiment_count: int
    token_usage: int
    cost: float
    latency: float
    agent_generation_status: RunStatus
    scientific_task_success: Optional[bool]
    hypothesis_validity: Optional[bool]
    experiment_validity: Optional[bool]
    evidence_validity: Optional[float]
    adaptation_success: Optional[bool]
    final_conclusion_validity: Optional[bool]
    failure_category: Optional[str]
    artifact_path: str

    def __post_init__(self) -> None:
        _require(bool(self.run_id), "run_id required")
        _require(self.agent_generation_status in
                 ("OBSERVED", "INFERRED", "HYPOTHESIS", "NOT_TESTED", "BLOCKED", "FAILED"),
                 "invalid run status")


SCHEMA_BY_NAME = {
    "ScientificModelProfile": ScientificModelProfile,
    "ScientificAffordance": ScientificAffordance,
    "ResearchCapabilityNode": ResearchCapabilityNode,
    "ResearchCapabilityEdge": ResearchCapabilityEdge,
    "ResearchCapabilityGraph": ResearchCapabilityGraph,
    "Hypothesis": Hypothesis,
    "ExperimentPlan": ExperimentPlan,
    "Observation": Observation,
    "EvidenceRecord": EvidenceRecord,
    "TaskSpec": TaskSpec,
    "RunRecord": RunRecord,
}


def to_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)
