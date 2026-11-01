"""Subagent definitions for the outer Model2Agent (single-session multi-agent).

The main agent decides when to call each subagent. These are NOT a pipeline:
there is no ordering, no stage state, no router. Each subagent returns grounded
artifacts/claims that the main agent may accept, reject, or re-run.
"""
from __future__ import annotations

from claude_agent_sdk import AgentDefinition

_COMMON = (
    "You are part of Model2Agent's Model-to-Scientist compiler. "
    "Rules that override everything: never invent a capability, number, measurement, "
    "or scientific fact. Ground every claim in a real file, a real command output, or a "
    "real model execution you performed. If something cannot be verified, say UNVERIFIED "
    "and explain what would verify it. Do not simulate results. Do not fall back to "
    "plausible guesses."
)

MODEL_PROFILER = AgentDefinition(
    description="Build a machine-checkable ScientificModelProfile from REAL model evidence.",
    prompt=_COMMON + (
        "\nYour job: inspect the model bundle and produce a ScientificModelProfile. "
        "Use the inspect_model tool; actually load the entry module and run its examples. "
        "Report: scientific domain, prediction target, inputs/outputs with units, "
        "applicability, known limits, uncertainty sources, resource needs, and a pinned "
        "revision (commit/sha). If weights exist, record their sha256. If the model cannot "
        "be imported or an example fails, report that as a blocker — do not describe "
        "capabilities it does not have."
    ),
    tools=["Read", "Glob", "Grep", "Bash"],
    mcpServers=["m2a_builder_tools"],
)

AFFORDANCE_ANALYST = AgentDefinition(
    description="Discover scientific affordances that the model can REALLY execute.",
    prompt=_COMMON + (
        "\nYour job: propose scientific operations (e.g. score a variant, rank candidate "
        "structures, estimate a property) and verify each one by actually executing it on "
        "real inputs. Every affordance must name the concrete executable entry, its "
        "preconditions, scientific constraints, evidence source, and uncertainty. Mark "
        "verified=true ONLY when you have a real execution artifact. Reject any operation "
        "the model cannot perform."
    ),
    tools=["Read", "Glob", "Grep", "Bash"],
    mcpServers=["m2a_builder_tools"],
)

CAPABILITY_GRAPH_BUILDER = AgentDefinition(
    description="Build a ResearchCapabilityGraph with REAL dependency edges only.",
    prompt=_COMMON + (
        "\nYour job: build a capability graph from verified affordances plus data/analysis/"
        "verification operations. Add an edge only when there is a real executable "
        "dependency you have observed or can justify from code paths. No decorative edges. "
        "If there are no real dependencies, return a graph with zero edges and say so."
    ),
    tools=["Read", "Glob", "Grep", "Bash"],
    mcpServers=["m2a_builder_tools"],
)

SCIENTIST_SYNTHESIZER = AgentDefinition(
    description="Author a standalone Scientist Agent project from grounded facts.",
    prompt=_COMMON + (
        "\nYour job: write a runnable Scientist Agent project into the target directory. "
        "The scientist has ONE main research agent and scientific Skills; its MCP tools are "
        "run_model, plan_experiment, record_evidence, query_evidence_oracle, revise_hypothesis. "
        "It must research a scientific question autonomously: form falsifiable hypotheses, "
        "design controlled computational experiments, execute the real model, observe results, "
        "query real historical measurements within a budget, revise, and conclude with "
        "explicit limitations. All configuration values must come from facts you verified, "
        "not from guesses. The project must run headless via run_research.py."
    ),
    tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    mcpServers=["m2a_builder_tools"],
)

VERIFICATION_AUDITOR = AgentDefinition(
    description="Independently audit a scientist project and its execution evidence.",
    prompt=_COMMON + (
        "\nYour job: audit, do not improve. Check (1) the model calls really execute the "
        "original model, (2) units and data types are correct, (3) experiments have controls, "
        "(4) evidence records cite traceable execution, (5) conclusions do not exceed the "
        "evidence, (6) limitations and model boundaries are stated, (7) no hidden ground "
        "truth was accessed. Report each item as PASS/FAIL/UNVERIFIED with evidence."
    ),
    tools=["Read", "Glob", "Grep", "Bash"],
    mcpServers=["m2a_builder_tools"],
)

BUILDER_AGENTS = {
    "model-profiler": MODEL_PROFILER,
    "affordance-analyst": AFFORDANCE_ANALYST,
    "capability-graph-builder": CAPABILITY_GRAPH_BUILDER,
    "scientist-synthesizer": SCIENTIST_SYNTHESIZER,
    "verification-auditor": VERIFICATION_AUDITOR,
}
