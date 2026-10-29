"""Statistics module public API."""
from .analysis import (load_records, paired_compare, cluster_bootstrap_ci, descriptive_only)
__all__ = ["load_records", "paired_compare", "cluster_bootstrap_ci", "descriptive_only"]
