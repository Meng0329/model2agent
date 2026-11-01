"""Deterministic oracles for Model-to-Scientist evaluation.

Two independent evidence sources:
  * execution_oracle  — re-executes the ORIGINAL model and compares numerically.
  * historical_oracle — replays REAL, traceable measurements and counts queries.

Neither oracle may invent a value. A missing measurement is returned as
UNOBSERVABLE, never filled with a proxy or a simulation.
"""
