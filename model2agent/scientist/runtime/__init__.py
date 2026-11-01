"""Self-contained runtime for a generated Scientist Agent.

This package is copied verbatim into every generated scientist project so the
project runs independently (no model2agent import). It is infrastructure only:
model loading, ledger, budget, oracle client, and the headless research loop.
All scientific decisions belong to the agent, not to this code.
"""
