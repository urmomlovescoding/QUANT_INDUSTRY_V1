"""
Neural Network Module Demo
==========================
Demonstrates the PyTorch neural network components for trading:
- LSTM, Transformer, TCN architectures
- RL agents (PPO, A2C, DQN)
- Training pipelines
"""

import numpy as np
import torch
import sys
sys.path.insert(0, '..')

# Import our neural network modules
from brain.nn import (
    LSTMPredictor, LSTMConfig,
    TransformerPredictor, TransformerConfig,
    TCNPredictor, TCNConfig,
    AttentionPredictor,
)
from brain.nn.attention import AttentionConfig
from brain.nn.transformer import TemporalTransformer
from brain.nn.tcn import WaveNet

from brain.rl import (
    TradingEnv, TradingEnvConfig,
    PPOAgent, A2CAgent, DQNAgent, AgentConfig,
    RLTrainer, TrainerConfig,
)


def generate_synthetic_data(n_samples: int = 5000, n_features: int = 10) -> np.ndarray:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    
    # Random walk for price
    returns = np.random.randn(n_samples) * 0.02
    close = 100 * np.exp(np.cumsum(returns))
    
    # Generate OHLCV
    high = close * (1 + np.abs(np.random.randn(n_samples)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(n_samples)) * 0.01)
    open_price = np.roll(close, 1)
    open_price[0] = close[0]
    volume = np.random.randint(1000, 10000, n_samples).astype(float)
    
    # Additional features (technical indicators - simulated)
    extra_features = np.random.randn(n_samples, n_features - 5) * 0.1
    
    data = np.column_stack([open_price, high, low, close, volume, extra_features])
    return data.astype(np.float32)


def demo_lstm():
    """Demonstrate LSTM model."""
    print("\n" + "="*60)
    print("LSTM Predictor Demo")
    print("="*60)
    
    config = LSTMConfig(
        input_dim=10,
        hidden_dim=128,
        output_dim=1,
        num_layers=2,
        bidirectional=True,
        dropout=0.2,
        task="regression"
    )
    
    model = LSTMPredictor(config)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Test forward pass
    batch = torch.randn(32, 60, 10)  # [batch, seq_len, features]
    output = model(batch)
    print(f"Input shape: {batch.shape}")
    print(f"Output shape: {output.shape}")


def demo_transformer():
    """Demonstrate Transformer model."""
    print("\n" + "="*60)
    print("Transformer Predictor Demo")
    print("="*60)
    
    config = TransformerConfig(
        input_dim=10,
        hidden_dim=64,
        output_dim=1,
        num_layers=4,
        num_heads=4,
        ff_dim=256,
        dropout=0.1,
        task="regression"
    )
    
    model = TransformerPredictor(config)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Test forward pass
    batch = torch.randn(32, 60, 10)
    output = model(batch)
    print(f"Input shape: {batch.shape}")
    print(f"Output shape: {output.shape}")
    
    # Get attention maps for interpretability
    attn_maps = model.get_attention_maps(batch[:4])
    print(f"Attention maps: {len(attn_maps)} layers, shape {attn_maps[0].shape}")


def demo_tcn():
    """Demonstrate TCN model."""
    print("\n" + "="*60)
    print("TCN Predictor Demo")
    print("="*60)
    
    config = TCNConfig(
        input_dim=10,
        hidden_dim=64,
        output_dim=1,
        num_layers=6,
        kernel_size=3,
        dilation_base=2,
        dropout=0.2,
        task="regression"
    )
    
    model = TCNPredictor(config)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"Receptive field: {model.receptive_field} timesteps")
    
    # Test forward pass
    batch = torch.randn(32, 60, 10)
    output = model(batch)
    print(f"Input shape: {batch.shape}")
    print(f"Output shape: {output.shape}")


def demo_attention():
    """Demonstrate pure attention model."""
    print("\n" + "="*60)
    print("Attention Predictor Demo")
    print("="*60)
    
    config = AttentionConfig(
        input_dim=10,
        hidden_dim=64,
        output_dim=1,
        num_layers=3,
        num_heads=4,
        ff_dim=128,
        use_cross_attention=True,
        num_features_secondary=5,
        task="regression"
    )
    
    model = AttentionPredictor(config)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Test forward pass (with optional secondary input)
    batch_primary = torch.randn(32, 60, 10)
    batch_secondary = torch.randn(32, 60, 5)  # Cross-attention context
    
    output = model(batch_primary, batch_secondary)
    print(f"Primary input shape: {batch_primary.shape}")
    print(f"Secondary input shape: {batch_secondary.shape}")
    print(f"Output shape: {output.shape}")
    
    # Get feature importance
    importance = model.get_feature_importance(batch_primary[:4])
    print(f"Feature importance shape: {importance.shape}")


def demo_trading_env():
    """Demonstrate trading environment."""
    print("\n" + "="*60)
    print("Trading Environment Demo")
    print("="*60)
    
    # Generate data
    data = generate_synthetic_data(2000, 10)
    
    config = TradingEnvConfig(
        initial_balance=100_000,
        max_position=1.0,
        transaction_cost=0.001,
        lookback_window=60,
        max_episode_steps=252,
    )
    
    env = TradingEnv(data, config=config)
    
    print(f"Observation space: {env.observation_space.shape}")
    print(f"Action space: {env.action_space}")
    
    # Run a few steps
    obs, info = env.reset()
    print(f"\nInitial observation shape: {obs.shape}")
    print(f"Initial info: {info}")
    
    total_reward = 0
    for i in range(10):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if terminated or truncated:
            break
    
    print(f"\nAfter 10 steps:")
    print(f"Total reward: {total_reward:.4f}")
    print(f"Portfolio value: ${info['portfolio_value']:,.2f}")
    print(f"Position: {info['position']:.2f}")


def demo_ppo_agent():
    """Demonstrate PPO agent."""
    print("\n" + "="*60)
    print("PPO Agent Demo")
    print("="*60)
    
    obs_dim = 300  # ~lookback * features + extras
    action_dim = 3  # Sell, Hold, Buy
    
    config = AgentConfig(
        hidden_dims=[256, 256],
        learning_rate=3e-4,
        clip_epsilon=0.2,
        batch_size=64,
    )
    
    agent = PPOAgent(obs_dim, action_dim, config)
    
    # Test action selection
    obs = np.random.randn(obs_dim).astype(np.float32)
    action, log_prob, value = agent.select_action(obs)
    
    print(f"Observation shape: {obs.shape}")
    print(f"Selected action: {action}")
    print(f"Log probability: {log_prob:.4f}")
    print(f"Value estimate: {value:.4f}")
    
    # Simulate collecting some experience
    for _ in range(100):
        next_obs = np.random.randn(obs_dim).astype(np.float32)
        reward = np.random.randn() * 0.01
        done = False
        action, log_prob, value = agent.select_action(obs)
        agent.store_transition(obs, action, reward, done, log_prob, value)
        obs = next_obs
    
    # Update
    stats = agent.update()
    print(f"\nUpdate stats: {stats}")


def demo_quick_training():
    """Quick training demo (minimal steps)."""
    print("\n" + "="*60)
    print("Quick Training Demo")
    print("="*60)
    
    # Generate data
    data = generate_synthetic_data(3000, 10)
    train_data = data[:2000]
    eval_data = data[2000:]
    
    # Create environments
    env_config = TradingEnvConfig(
        initial_balance=100_000,
        lookback_window=30,
        max_episode_steps=100,
    )
    
    train_env = TradingEnv(train_data, config=env_config)
    eval_env = TradingEnv(eval_data, config=env_config)
    
    # Create trainer
    trainer_config = TrainerConfig(
        total_timesteps=2000,  # Very short for demo
        rollout_length=256,
        eval_freq=1000,
        n_eval_episodes=3,
        log_dir="runs/demo",
    )
    
    agent_config = AgentConfig(
        hidden_dims=[64, 64],
        learning_rate=3e-4,
    )
    
    trainer = RLTrainer(
        env=train_env,
        agent_type="ppo",
        agent_config=agent_config,
        trainer_config=trainer_config,
        eval_env=eval_env,
    )
    
    print("Training PPO agent...")
    results = trainer.train()
    
    print(f"\nTraining results:")
    print(f"  Total steps: {results['total_steps']}")
    print(f"  Episodes: {results['total_episodes']}")
    print(f"  Final eval return: {results['final_eval_return']:.4f}")
    print(f"  Steps/second: {results['steps_per_second']:.1f}")


def main():
    """Run all demos."""
    print("QUANT_INDUSTRY_V1 Neural Network Module Demo")
    print("=" * 60)
    
    # Neural network architectures
    demo_lstm()
    demo_transformer()
    demo_tcn()
    demo_attention()
    
    # RL components
    demo_trading_env()
    demo_ppo_agent()
    
    # Optional: run quick training (takes ~30 seconds)
    import sys
    if "--train" in sys.argv:
        demo_quick_training()
    else:
        print("\n[Tip: Run with --train to see training demo]")
    
    print("\n" + "="*60)
    print("All demos completed successfully!")
    print("="*60)


if __name__ == "__main__":
    main()
