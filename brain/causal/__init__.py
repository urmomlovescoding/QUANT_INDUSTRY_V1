"""
Causal Inference Module - Bayesian Networks and Decision Explanation

This module provides causal modeling capabilities for understanding
why the trading system makes particular decisions.

Components:
- BayesianNetwork: Pyro-based causal model
- DecisionTrace: Decision explanation and audit trail

Usage:
    from brain.causal import CausalBayesianNetwork, DecisionTracer
"""

from .bayesian_network import CausalBayesianNetwork, CausalConfig
from .decision_trace import DecisionTracer, DecisionExplanation

__all__ = [
    'CausalBayesianNetwork',
    'CausalConfig',
    'DecisionTracer',
    'DecisionExplanation',
]
