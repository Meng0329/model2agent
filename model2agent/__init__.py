"""Model2Agent — Model-to-Scientist compilation.

Converts ONE pretrained scientific model into a standalone, autonomous domain-scientist
agent. The outer compiler is a single Claude Agent SDK session with specialized
subagents; deterministic code only executes models, replays real measurements within
a budget, persists an evidence ledger, and scores runs.

There is no fixed pipeline, no keyword routing, no simulation, and no silent fallback.
"""
__version__ = "0.4.0"
