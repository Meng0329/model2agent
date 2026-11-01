"""Build the frozen Model2ScientistBench task set and hidden oracles.

Two domains:
  protein_science  — ESM-2 zero-shot ranking of DMS single mutants (ProteinGym real fitness)
  agriculture      — rice genomic selection of high-GRWT100 lines (real measured trait)

Guarantees:
  * task ids are unique
  * hidden measurements live only in m2a_data/research/hidden (mode 0700)
  * candidate pools contain ids only, never labels
  * success rules are pre-registered and machine-checkable by the runner
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROT = ROOT / "m2a_data" / "research" / "datasets" / "proteingym" / "dms_sub_0.parquet"
RICE = ROOT / "m2a_data" / "research" / "datasets" / "rice"
HIDDEN = ROOT / "m2a_data" / "research" / "hidden"
INPUTS = ROOT / "m2a_data" / "research" / "inputs"
FROZEN = ROOT / "results" / "frozen" / "scientist_tasks.json"

PROT_DMS = "SDA_BACSU_Tsuboyama_2023_1PV0"
PROT_SEQ = "MRKLSDELLIESYFKATEMNLNRDFIELIENEIKRRSLGHIISV"


def _mkdirs() -> None:
    HIDDEN.mkdir(parents=True, exist_ok=True)
    os.chmod(HIDDEN, stat.S_IRWXU)  # 0700
    INPUTS.mkdir(parents=True, exist_ok=True)
    FROZEN.parent.mkdir(parents=True, exist_ok=True)


def _write_hidden(name: str, payload: dict) -> None:
    p = HIDDEN / name
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.chmod(p, 0o600)


def build_protein() -> list[dict]:
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    t = pq.read_table(PROT)
    rows = t.filter(pc.equal(t["DMS_id"], PROT_DMS)).to_pylist()
    single = {}
    for r in rows:
        m = r["mutant"]
        if re.fullmatch(r"[A-Z]\d+[A-Z]", m) and r["DMS_score"] is not None:
            single[m] = float(r["DMS_score"])
    mutants = sorted(single)
    _write_hidden("protein_sda.json", single)
    (INPUTS / "protein_candidates.json").write_text(
        json.dumps({"model": "esm2_variant", "sequence": PROT_SEQ,
                    "candidates": mutants}, ensure_ascii=False), encoding="utf-8")

    tasks = []
    base = dict(
        domain="protein_science", scientific_model="esm2_variant",
        input_resources={"candidate_file": str(INPUTS / "protein_candidates.json"),
                         "sequence": PROT_SEQ},
        allowed_knowledge=["model_card", "scientific_profile", "domain_knowledge/esm2_notes.md"],
        available_tools=["run_model", "query_evidence_oracle", "record_evidence"],
        permitted_actions=["score_variant", "query_evidence_oracle", "record_evidence"],
        hidden_reference="protein_sda.json", execution_oracle="reference_exec",
        evidence_oracle="historical",
        scientific_constraints=["single substitutions only", "same protein sequence"],
        # Method-independent contract: every method must produce a real evidence ledger and
        # its ranked answer. Conclusions are a scored channel (SEV), not an SISR gate, so
        # baselines without the SMSC conclusion tool are not penalised for a missing artifact.
        expected_artifacts=["evidence.jsonl", "final_selection.json"],
        failure_conditions=["claims a measured effect without an E3 record"],
    )
    tasks.append({**base, "task_id": "protein-P1-novel",
                  "split": "novel", "capability_level": "L4",
                  "scientific_question": (
                      "You are a protein scientist. Using ESM-2 zero-shot scores, rank the "
                      "single mutants in the candidate file by likely fitness. Within at most 16 "
                      "real measurement queries, identify the 5 mutants most likely to have high "
                      "measured fitness. Record evidence and state limitations."),
                  "experimental_budget": {"oracle_queries": 16, "max_model_calls": 80,
                                          "max_tokens": 2_000_000, "max_usd": 2.0,
                                          "max_wall_seconds": 1800},
                  "success_criteria": ["final top-5 contains >=3 true top-quartile mutants"],
                  "input_resources": {**base["input_resources"],
                                      "success_rule": {"type": "topk_quartile", "k": 5,
                                                       "min_hits": 3, "quartile": 0.75}}})
    tasks.append({**base, "task_id": "protein-P2-closed-loop",
                  "split": "closed_loop", "capability_level": "L5",
                  "scientific_question": (
                      "You are a protein scientist. Run a closed-loop investigation: score "
                      "candidates with ESM-2, query real measurements in two or more rounds, "
                      "revise your selection after each round, and finish with the 5 mutants most "
                      "likely to have high measured fitness. Do not exceed 24 measurement queries."),
                  "experimental_budget": {"oracle_queries": 24, "max_model_calls": 120,
                                          "max_tokens": 3_000_000, "max_usd": 3.0,
                                          "max_wall_seconds": 2400},
                  "success_criteria": ["final top-5 contains >=3 true top-quartile mutants",
                                       "at least one hypothesis revision after feedback"],
                  "input_resources": {**base["input_resources"],
                                      "success_rule": {"type": "topk_quartile", "k": 5,
                                                       "min_hits": 3, "quartile": 0.75}}})
    tasks.append({**base, "task_id": "protein-P3-rediscovery",
                  "split": "insight_rediscovery", "capability_level": "L6",
                  "scientific_question": (
                      "You are a protein scientist. Without knowing the answer in advance, use "
                      "ESM-2 and at most 20 real measurements to rediscover the single mutant with "
                      "the highest measured fitness in the candidate set. Justify your conclusion "
                      "with evidence and state uncertainty."),
                  "experimental_budget": {"oracle_queries": 20, "max_model_calls": 100,
                                          "max_tokens": 2_500_000, "max_usd": 2.5,
                                          "max_wall_seconds": 2400},
                  "success_criteria": ["final top-1 equals the true highest-fitness mutant"],
                  "input_resources": {**base["input_resources"],
                                      "success_rule": {"type": "rediscovery", "k": 1}}})
    return tasks


def build_agriculture() -> list[dict]:
    split = json.loads((ROOT / "model_assets" / "rice_gs" / "split.json").read_text())
    pool_ids = split["pool_ids"]
    traits = pd.read_csv(RICE / "traits.csv", index_col=0)
    measured = {i: float(traits.loc[i, "GRWT100"]) for i in pool_ids
                if i in traits.index and pd.notna(traits.loc[i, "GRWT100"])}
    pool_ids = sorted(measured)
    _write_hidden("rice_grwt100.json", measured)
    (INPUTS / "rice_candidates.json").write_text(
        json.dumps({"model": "rice_gs", "trait": "GRWT100", "candidates": pool_ids},
                   ensure_ascii=False), encoding="utf-8")

    base = dict(
        domain="agriculture", scientific_model="rice_gs",
        input_resources={"candidate_file": str(INPUTS / "rice_candidates.json")},
        allowed_knowledge=["model_card", "scientific_profile", "domain_knowledge/rice_gs.md"],
        available_tools=["run_model", "query_evidence_oracle", "record_evidence"],
        permitted_actions=["predict_by_ids", "rank_candidates", "query_evidence_oracle",
                           "record_evidence"],
        hidden_reference="rice_grwt100.json", execution_oracle="reference_exec",
        evidence_oracle="historical",
        scientific_constraints=["single environment", "GRWT100 only", "no unseen markers"],
        # Method-independent contract: every method must produce a real evidence ledger and
        # its ranked answer. Conclusions are a scored channel (SEV), not an SISR gate, so
        # baselines without the SMSC conclusion tool are not penalised for a missing artifact.
        expected_artifacts=["evidence.jsonl", "final_selection.json"],
        failure_conditions=["claims a measured phenotype without an E3 record"],
    )
    tasks = []
    tasks.append({**base, "task_id": "rice-R1-novel",
                  "split": "novel", "capability_level": "L4",
                  "scientific_question": (
                      "You are a rice breeding scientist. Using the genomic prediction model, "
                      "rank candidate lines and, within at most 20 real phenotyping queries, "
                      "identify the 10 lines most likely to be in the high-grain-weight quartile. "
                      "Record evidence and limitations."),
                  "experimental_budget": {"oracle_queries": 20, "max_model_calls": 80,
                                          "max_tokens": 2_000_000, "max_usd": 2.0,
                                          "max_wall_seconds": 1800},
                  "success_criteria": ["final top-10 contains >=6 true top-quartile lines"],
                  "input_resources": {**base["input_resources"],
                                      "success_rule": {"type": "topk_quartile", "k": 10,
                                                       "min_hits": 6, "quartile": 0.75}}})
    tasks.append({**base, "task_id": "rice-R2-closed-loop",
                  "split": "closed_loop", "capability_level": "L5",
                  "scientific_question": (
                      "You are a rice breeding scientist. Run a closed-loop selection: predict, "
                      "query real phenotype measurements in two or more rounds, revise the ranking "
                      "after each round, and finish with the 10 lines most likely to be in the "
                      "high-grain-weight quartile. At most 30 phenotyping queries."),
                  "experimental_budget": {"oracle_queries": 30, "max_model_calls": 120,
                                          "max_tokens": 3_000_000, "max_usd": 3.0,
                                          "max_wall_seconds": 2400},
                  "success_criteria": ["final top-10 contains >=6 true top-quartile lines",
                                       "at least one hypothesis revision after feedback"],
                  "input_resources": {**base["input_resources"],
                                      "success_rule": {"type": "topk_quartile", "k": 10,
                                                       "min_hits": 6, "quartile": 0.75}}})
    tasks.append({**base, "task_id": "rice-R3-rediscovery",
                  "split": "insight_rediscovery", "capability_level": "L6",
                  "scientific_question": (
                      "You are a rice breeding scientist. Without knowing the answer, use the "
                      "genomic prediction model and at most 20 real phenotype measurements to "
                      "rediscover the single line with the highest measured 100-grain weight in "
                      "the candidate set. State uncertainty and limitations."),
                  "experimental_budget": {"oracle_queries": 20, "max_model_calls": 100,
                                          "max_tokens": 2_500_000, "max_usd": 2.5,
                                          "max_wall_seconds": 2400},
                  "success_criteria": ["final top-1 equals the true highest-GRWT100 line"],
                  "input_resources": {**base["input_resources"],
                                      "success_rule": {"type": "rediscovery", "k": 1}}})
    return tasks


def main() -> None:
    _mkdirs()
    tasks = build_protein() + build_agriculture()
    ids = [t["task_id"] for t in tasks]
    assert len(ids) == len(set(ids)), f"duplicate task ids: {ids}"
    # leakage check: no task may embed a known measured value
    hidden = {}
    for p in HIDDEN.glob("*.json"):
        hidden[p.name] = json.loads(p.read_text())
    for t in tasks:
        blob = json.dumps(t, ensure_ascii=False)
        ref = hidden.get(t["hidden_reference"], {})
        leaked = [k for k in list(ref)[:200] if f'"{k}"' in blob and k not in ("A16C",)]
        assert not leaked, f"{t['task_id']} leaks hidden keys: {leaked[:3]}"
        t["scientific_question"] += (
            " Write your final ranked answer to final_selection.json as "
            '{"top_ids": [...]} — your final top-k candidates in order.')
        # Pre-registered per-task turn allowance (shared by M and every baseline).
        # Closed-loop/rediscovery tasks need more turns than a single-pass ranking.
        t.setdefault("experimental_budget", {})["max_turns"] = (
            60 if t.get("capability_level") == "L4" else 100)
    FROZEN.write_text(json.dumps({"frozen": True, "n_tasks": len(tasks), "tasks": tasks},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"frozen": str(FROZEN), "n_tasks": len(tasks),
                      "domains": sorted({t["domain"] for t in tasks}),
                      "hidden": sorted(hidden)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
