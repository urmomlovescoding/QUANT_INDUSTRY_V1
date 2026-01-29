"""
Reinforcement Learning Module
=============================
Industry-grade RL for trading with PyTorch.
"""

from .env import TradingEnv, MultiAssetTradingEnv, TradingEnvConfig, Action
from .agent import PPOAgent, A2CAgent, DQNAgent, AgentConfig
from .trainer import RLTrainer, TrainerConfig, train_trading_agent

__all__ = [
    # Environments
    'TradingEnv',
    'MultiAssetTradingEnv',
    'TradingEnvConfig',
    'Action',
    # Agents
    'PPOAgent',
    'A2CAgent',
    'DQNAgent',
    'AgentConfig',
    # Training
    'RLTrainer',
    'TrainerConfig',
    'train_trading_agent',
]
