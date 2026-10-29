"""AGCI — schema + capability induction.

Given an AssetDescriptor, the LLM induces model-specific capabilities (predict,
explain, uncertainty, adapt, ...) grounded ONLY in the discovered functions,
the card, and the examples. Output is a structured capability list that feeds MCG.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from typing import Any

from ..llm import LLMClient, extract_json

SYSTEM = (
    "You are a model-asset analyst. From a trained model's discovered inference "
    "functions, model card, and example I/O, induce the concrete capabilities this "
    "model can expose as an interactive agent. Ground every capability in an actual "
    "discovered function — do NOT invent capabilities the model cannot execute. "
    "Map each capability to the function that implements it. Note input/output schema, "
    "dependencies on other capabilities, and failure boundaries. "
    "Output ONLY one JSON object, with NO preamble, no prose, no markdown fence."
)


@dataclass
class Capability:
    name: str
    description: str
    entry_function: str
    input_schema: dict
    output_schema: dict
    depends_on: list = field(default_factory=list)
    failure_boundary: str = ""


def _build_prompt(descriptor, examples_json: str) -> str:
    fn_lines = "\n".join(
        f"- {f['name']}({', '.join(f['arg_names'])}) -> {f['return_annotation'] or 'any'}: {f['docstring']}"
        for f in descriptor.functions if f.get("is_callable", True)
    )
    return (
        f"ASSET:\n"
        f"name: {descriptor.name}\nframework: {descriptor.framework}\n"
        f"task_family: {descriptor.task_family}\nmodel_id: {descriptor.model_id}\n"
        f"license: {descriptor.license}\n\n"
        f"MODEL CARD:\n{descriptor.card_text[:2500]}\n\n"
        f"DISCOVERED (executable) FUNCTIONS:\n{fn_lines}\n\n"
        f"EXAMPLE I/O KEYS:\n{examples_json}\n\n"
        f"EVIDENCE: weights_sha256={descriptor.evidence.get('weights_sha256')} "
        f"manifest_vs_ast={descriptor.evidence.get('manifest_vs_ast')}\n\n"
        "Induce capabilities. Return JSON: {\"capabilities\":[{\"name\",\"description\","
        "\"entry_function\",\"input_schema\":{},\"output_schema\":{},\"depends_on\":[],"
        "\"failure_boundary\":\"\"}]}"
    )


def induce_capabilities(descriptor, llm: LLMClient) -> list[Capability]:
    """Asset-grounded capability induction (LLM-named, evidence-constrained)."""
    import pathlib, json as _j
    examples = _j.loads(pathlib.Path(descriptor.bundle_dir).joinpath(
        descriptor.manifest.get("examples", "examples.json")).read_text(encoding="utf-8"))
    # Only send a compact preview of examples to keep tokens bounded.
    ex_preview = {}
    for k, v in examples.items():
        ex_preview[k] = (v[:2] if isinstance(v, list) else v)
    msg = _build_prompt(descriptor, json.dumps(ex_preview, ensure_ascii=False)[:2000])
    raw = llm.chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
        temperature=0.0, max_tokens=3000, json_mode=True,
    )
    data = extract_json(raw)
    if not isinstance(data, dict):
        data = {"capabilities": [], "_parse_error": (raw or "")[:500]}
    caps = []
    valid_fn = {f["name"] for f in descriptor.functions
                if f.get("is_callable", True) and not f["name"].startswith("_")}
    for c in data.get("capabilities", []):
        # Grounded constraint: drop any capability whose entry_function isn't actually executable.
        if c.get("entry_function") in valid_fn:
            caps.append(Capability(
                name=c["name"], description=c.get("description", ""),
                entry_function=c["entry_function"],
                input_schema=c.get("input_schema", {}), output_schema=c.get("output_schema", {}),
                depends_on=c.get("depends_on", []), failure_boundary=c.get("failure_boundary", ""),
            ))
    return caps


def capabilities_to_dict(caps: list[Capability]) -> list[dict]:
    return [asdict(c) for c in caps]
