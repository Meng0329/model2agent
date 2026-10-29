"""Skills registry — the internal routing mechanism of the single orchestrator.

NOTE (alignment): Paper2Agent's own repo already uses Skills + MCP, so "Skills" here is
an implementation detail, NOT a research contribution. Model2Agent's contribution is
AGCI + MCG + reference-execution verification, not the skill abstraction.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Skill:
    name: str
    description: str
    fn: Callable
    tags: list = field(default_factory=list)


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, name, description, fn, tags=None):
        self._skills[name] = Skill(name, description, fn, tags or [])
        return fn

    def list(self):
        return [{"name": s.name, "description": s.description, "tags": s.tags}
                for s in self._skills.values()]

    def dispatch(self, name, **kwargs):
        if name not in self._skills:
            raise KeyError(f"unknown skill: {name}")
        return self._skills[name].fn(**kwargs)

    def route(self, intent: str) -> str:
        """Static keyword routing (A4 'static skill routing' ablation uses this path)."""
        intent = intent.lower()
        table = [
            ("scan", ["scan", "asset", "discover", "inspect"]),
            ("induce", ["capab", "induce", "semantic"]),
            ("build", ["build", "generate", "agent", "synthesize"]),
            ("verify", ["verify", "validate", "reference", "test"]),
            ("benchmark", ["bench", "evaluate", "task", "accuracy"]),
            ("robustness", ["fault", "robust", "inject", "repair"]),
        ]
        for name, keys in table:
            if any(k in intent for k in keys):
                return name
        return "scan"


def build_default_registry() -> SkillRegistry:
    from ..agci.asset_scanner import scan_bundle
    from ..agci.capability_inducer import induce_capabilities
    from ..mcg.graph import build_mcg
    from ..builder.agent_builder import build_agent
    from ..verification.reference_exec import run_reference, compare
    from ..benchmark.runner import run_benchmark
    from ..robustness.fault_injection import run_fault_injection

    reg = SkillRegistry()
    reg.register("scan", "Discover a model asset's inference entry, weights, schema, evidence",
                 lambda bundle_dir: scan_bundle(bundle_dir), ["agci"])
    reg.register("induce", "Induce capabilities grounded in discovered functions",
                 lambda descriptor, llm: induce_capabilities(descriptor, llm), ["agci"])
    reg.register("build", "Build the Model Capability Graph and standalone agent",
                 lambda descriptor, caps: build_agent(descriptor, build_mcg(descriptor.slug, caps)), ["mcg", "builder"])
    reg.register("verify", "Verify a capability against reference execution",
                 lambda bundle_dir, capability, args: _verify(bundle_dir, capability, args, run_reference, compare), ["verification"])
    reg.register("benchmark", "Run the frozen benchmark across methods",
                 lambda slugs, methods, reps, tasks_path, log_path: run_benchmark(slugs, methods=methods, reps=reps, tasks_path=tasks_path, log_path=log_path), ["benchmark"])
    reg.register("robustness", "Inject faults and measure detection/repair/consistency",
                 lambda slug, methods: run_fault_injection(slug, methods=methods), ["robustness"])
    return reg


def _verify(bundle_dir, capability, args, run_reference, compare):
    from ..verification.reference_exec import load_infer
    ref = run_reference(bundle_dir, capability, args)
    got = getattr(load_infer(bundle_dir), capability)(**args)
    return {"ok": compare(capability, ref, got), "ref": str(ref)[:200], "got": str(got)[:200]}
