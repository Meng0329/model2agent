"""MCG — Model Capability Graph.

Nodes = induced capabilities; edges = composition dependencies (e.g. `similarity`
depends on `embed`). Serialized to JSON for provenance and for the builder to consume.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class MCGEdge:
    src: str  # capability name (dependent)
    dst: str  # capability name (dependency)
    kind: str = "depends_on"


@dataclass
class ModelCapabilityGraph:
    slug: str
    nodes: list  # list[Capability dict]
    edges: list  # list[MCGEdge dict]
    root_capabilities: list = field(default_factory=list)  # entrypoints the user can call directly

    def to_dict(self) -> dict:
        return asdict(self)

    def adjacency(self) -> dict:
        adj = {n["name"]: [] for n in self.nodes}
        for e in self.edges:
            adj.setdefault(e["src"], []).append(e["dst"])
        return adj


def build_mcg(slug: str, capabilities: list) -> ModelCapabilityGraph:
    """Build the MCG from induced capabilities.

    Edges come from each capability's `depends_on`. Root capabilities are those
    that no other capability lists as a dependency (user-facing entrypoints).
    """
    nodes = [c if isinstance(c, dict) else asdict(c) for c in capabilities]
    names = {n["name"] for n in nodes}
    edges = []
    for n in nodes:
        for dep in n.get("depends_on", []):
            if dep in names and dep != n["name"]:
                edges.append(asdict(MCGEdge(src=n["name"], dst=dep, kind="depends_on")))
    depended = {e["dst"] for e in edges}
    roots = [n["name"] for n in nodes if n["name"] not in depended]
    if not roots:
        roots = [n["name"] for n in nodes]
    return ModelCapabilityGraph(slug=slug, nodes=nodes, edges=[asdict(MCGEdge(**e)) if isinstance(e, dict) else asdict(e) for e in edges], root_capabilities=roots)


def save_mcg(mcg: ModelCapabilityGraph, path) -> None:
    Path(path).write_text(json.dumps(mcg.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_mcg(path) -> ModelCapabilityGraph:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return ModelCapabilityGraph(**d)
