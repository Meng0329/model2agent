"""ESM-2 (650M) zero-shot variant-effect scoring.

Real model execution only. The scores here are MODEL PREDICTIONS (E1); they are
not experimental measurements and must never be reported as such.

GPU policy: GPU0 only.
"""
from __future__ import annotations

import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

import functools

import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer

MODEL_ID = "facebook/esm2_t33_650M_UR50D"
REVISION = "08e4846e537177426273712802403f7ba8261b6c"  # pinned
_DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"

_AA = "ACDEFGHIKLMNPQRSTVWY"


@functools.lru_cache(maxsize=1)
def _load():
    tok = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION)
    model = AutoModelForMaskedLM.from_pretrained(MODEL_ID, revision=REVISION)
    model.eval().to(_DEVICE)
    return tok, model


def _residue_logprobs(sequence: str, mask_positions: list[int]) -> list[dict[str, float]]:
    """Mask the given 0-based residue positions and return per-position logprobs."""
    tok, model = _load()
    chars = list(sequence)
    for p in mask_positions:
        if p < 0 or p >= len(chars):
            raise ValueError(f"position {p} out of range for sequence length {len(chars)}")
        chars[p] = tok.mask_token
    masked = "".join(chars)
    enc = tok(masked, return_tensors="pt").to(_DEVICE)
    with torch.no_grad():
        logits = model(**enc).logits[0]
    logp = torch.log_softmax(logits, dim=-1)
    # token index 0 is <cls>, so residue i sits at i+1
    out = []
    for p in mask_positions:
        row = logp[p + 1]
        out.append({aa: float(row[tok.convert_tokens_to_ids(aa)]) for aa in _AA})
    return out


def _parse_mutations(mutations: str) -> list[tuple[str, int, str]]:
    parsed = []
    for token in mutations.replace(",", ":").split(":"):
        token = token.strip()
        if not token:
            continue
        wt, mut = token[0], token[-1]
        pos = int(token[1:-1]) - 1  # 1-based -> 0-based
        if wt not in _AA or mut not in _AA:
            raise ValueError(f"invalid mutation token: {token}")
        parsed.append((wt, pos, mut))
    if not parsed:
        raise ValueError("no mutations supplied")
    return parsed


def score_variant(sequence: str, mutations: str) -> float:
    """Zero-shot masked-marginal delta log-likelihood for one or more mutations."""
    muts = _parse_mutations(mutations)
    wt_seq = sequence
    # validate reference residue matches the wild type
    for wt, pos, _ in muts:
        if pos >= len(wt_seq):
            raise ValueError(f"mutation at {pos + 1} beyond sequence length {len(wt_seq)}")
        if wt_seq[pos] != wt:
            raise ValueError(f"wild-type mismatch at {pos + 1}: expected {wt_seq[pos]}, got {wt}")
    mut_seq = list(wt_seq)
    for _, pos, mut in muts:
        mut_seq[pos] = mut
    wt_logp = _residue_logprobs(wt_seq, [p for _, p, _ in muts])
    mut_logp = _residue_logprobs("".join(mut_seq), [p for _, p, _ in muts])
    delta = 0.0
    for (wt, _, mut), w, m in zip(muts, wt_logp, mut_logp):
        delta += m[mut] - w[wt]
    return float(delta)


def score_sequence(sequence: str) -> float:
    """Mean per-residue log-likelihood of a sequence under ESM-2."""
    tok, model = _load()
    enc = tok(sequence, return_tensors="pt").to(_DEVICE)
    ids = enc["input_ids"][0]
    with torch.no_grad():
        logits = model(**enc).logits[0]
    logp = torch.log_softmax(logits, dim=-1)
    # predict residue t from position t-1 (autoregressive-style likelihood)
    total = 0.0
    n = 0
    for t in range(1, len(ids)):
        if t < len(ids) - 1:  # exclude <eos>
            total += float(logp[t - 1, ids[t]])
            n += 1
    if n == 0:
        raise ValueError("sequence too short")
    return total / n


def embed(sequence: str) -> list[float]:
    """Mean-pooled hidden representation (1280-dim)."""
    tok, model = _load()
    enc = tok(sequence, return_tensors="pt").to(_DEVICE)
    with torch.no_grad():
        out = model.esm(**enc)
    hidden = out.last_hidden_state[0][1:-1]
    return [float(x) for x in hidden.mean(dim=0)]
