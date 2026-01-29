"""
Trading-Specific Loss Functions
===============================
Custom loss functions for training trading models.

Standard ML losses (MSE, cross-entropy) don't capture what matters in trading:
- Sharpe ratio
- Drawdown
- Directional accuracy
- Risk-adjusted returns

These losses align model optimization with trading objectives.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple


class SharpeLoss(nn.Module):
    """
    Differentiable Sharpe Ratio Loss.
    
    Sharpe = E[R] / std(R) * sqrt(252)
    
    Loss = -Sharpe (maximize Sharpe by minimizing negative)
    
    Uses soft approximation for differentiability.
    """
    
    def __init__(
        self,
        annualization: float = 252,
        epsilon: float = 1e-8
    ):
        super().__init__()
        self.annualization = annualization
        self.epsilon = epsilon
    
    def forward(
        self,
        returns: torch.Tensor,  # (batch,) or (batch, time)
        weights: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Compute negative Sharpe ratio.
        
        Args:
            returns: Period returns
            weights: Optional sample weights
        """
        if returns.dim() == 1:
            returns = returns.unsqueeze(0)
        
        if weights is not None:
            mean_return = (returns * weights).sum() / weights.sum()
            var_return = ((returns - mean_return) ** 2 * weights).sum() / weights.sum()
        else:
            mean_return = returns.mean()
            var_return = returns.var()
        
        std_return = torch.sqrt(var_return + self.epsilon)
        
        sharpe = mean_return / std_return * np.sqrt(self.annualization)
        
        return -sharpe


class SortinoLoss(nn.Module):
    """
    Differentiable Sortino Ratio Loss.
    
    Sortino = E[R] / downside_std(R)
    
    Only penalizes downside volatility, not upside.
    """
    
    def __init__(
        self,
        target: float = 0.0,
        annualization: float = 252,
        epsilon: float = 1e-8
    ):
        super().__init__()
        self.target = target
        self.annualization = annualization
        self.epsilon = epsilon
    
    def forward(self, returns: torch.Tensor) -> torch.Tensor:
        mean_return = returns.mean()
        
        # Downside deviation: only negative returns
        downside = F.relu(self.target - returns)
        downside_var = (downside ** 2).mean()
        downside_std = torch.sqrt(downside_var + self.epsilon)
        
        sortino = mean_return / downside_std * np.sqrt(self.annualization)
        
        return -sortino


class DrawdownLoss(nn.Module):
    """
    Maximum Drawdown Loss.
    
    MDD = max_t (peak_t - value_t) / peak_t
    
    Penalizes large drawdowns during training.
    """
    
    def __init__(self, penalty_weight: float = 1.0):
        super().__init__()
        self.penalty_weight = penalty_weight
    
    def forward(self, cumulative_returns: torch.Tensor) -> torch.Tensor:
        """
        Args:
            cumulative_returns: Cumulative return series (batch, time)
        """
        # Running maximum
        running_max = torch.cummax(cumulative_returns, dim=-1)[0]
        
        # Drawdown at each point
        drawdown = (running_max - cumulative_returns) / (running_max + 1e-8)
        
        # Maximum drawdown
        max_drawdown = drawdown.max(dim=-1)[0]
        
        return self.penalty_weight * max_drawdown.mean()


class CalmarLoss(nn.Module):
    """
    Calmar Ratio Loss.
    
    Calmar = Annual Return / Max Drawdown
    
    Balances return with drawdown risk.
    """
    
    def __init__(self, annualization: float = 252):
        super().__init__()
        self.annualization = annualization
    
    def forward(self, returns: torch.Tensor) -> torch.Tensor:
        # Cumulative returns
        cum_returns = torch.cumprod(1 + returns, dim=-1)
        
        # Annual return
        total_return = cum_returns[..., -1] - 1
        n_periods = returns.shape[-1]
        annual_return = (1 + total_return) ** (self.annualization / n_periods) - 1
        
        # Max drawdown
        running_max = torch.cummax(cum_returns, dim=-1)[0]
        drawdown = (running_max - cum_returns) / (running_max + 1e-8)
        max_drawdown = drawdown.max(dim=-1)[0]
        
        calmar = annual_return / (max_drawdown + 1e-8)
        
        return -calmar.mean()


class DirectionalLoss(nn.Module):
    """
    Directional Accuracy Loss.
    
    Penalizes wrong direction predictions more than magnitude errors.
    
    Loss = MSE + λ * (1 - sign_accuracy)
    """
    
    def __init__(
        self,
        direction_weight: float = 1.0,
        magnitude_weight: float = 0.1
    ):
        super().__init__()
        self.direction_weight = direction_weight
        self.magnitude_weight = magnitude_weight
    
    def forward(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        # Magnitude loss (MSE)
        mse = F.mse_loss(predictions, targets)
        
        # Directional loss
        pred_sign = torch.sign(predictions)
        target_sign = torch.sign(targets)
        
        # Soft sign accuracy (differentiable)
        sign_agreement = pred_sign * target_sign
        direction_loss = F.relu(-sign_agreement).mean()  # Penalize disagreement
        
        return self.magnitude_weight * mse + self.direction_weight * direction_loss


class ProfitFactorLoss(nn.Module):
    """
    Profit Factor Loss.
    
    PF = Gross Profits / Gross Losses
    
    Differentiable approximation using soft masks.
    """
    
    def __init__(self, epsilon: float = 1e-8):
        super().__init__()
        self.epsilon = epsilon
    
    def forward(self, returns: torch.Tensor) -> torch.Tensor:
        # Soft positive/negative masks
        positive_mask = torch.sigmoid(returns * 100)  # Soft step function
        negative_mask = 1 - positive_mask
        
        gross_profit = (returns * positive_mask).sum()
        gross_loss = (-returns * negative_mask).sum()
        
        profit_factor = gross_profit / (gross_loss + self.epsilon)
        
        # Maximize profit factor
        return -torch.log(profit_factor + 1)


class RiskAdjustedReturnLoss(nn.Module):
    """
    Combined Risk-Adjusted Return Loss.
    
    Combines multiple objectives:
    - Return maximization
    - Volatility minimization
    - Drawdown penalty
    - Tail risk (CVaR)
    """
    
    def __init__(
        self,
        return_weight: float = 1.0,
        sharpe_weight: float = 1.0,
        drawdown_weight: float = 0.5,
        cvar_weight: float = 0.5,
        alpha: float = 0.05  # CVaR tail
    ):
        super().__init__()
        self.return_weight = return_weight
        self.sharpe_weight = sharpe_weight
        self.drawdown_weight = drawdown_weight
        self.cvar_weight = cvar_weight
        self.alpha = alpha
        
        self.sharpe_loss = SharpeLoss()
        self.drawdown_loss = DrawdownLoss()
    
    def forward(self, returns: torch.Tensor) -> torch.Tensor:
        # Return component
        return_loss = -returns.mean() * self.return_weight
        
        # Sharpe component
        sharpe = self.sharpe_loss(returns) * self.sharpe_weight
        
        # Drawdown component
        cum_returns = torch.cumprod(1 + returns, dim=-1)
        drawdown = self.drawdown_loss(cum_returns) * self.drawdown_weight
        
        # CVaR component
        sorted_returns, _ = torch.sort(returns)
        n_tail = max(1, int(self.alpha * len(returns)))
        cvar = -sorted_returns[:n_tail].mean() * self.cvar_weight
        
        return return_loss + sharpe + drawdown + cvar


class PolicyGradientLoss(nn.Module):
    """
    Policy Gradient Loss for RL Trading.
    
    Uses proper advantage estimation and entropy regularization.
    
    L = -E[A * log π(a|s)] + β * H(π)
    """
    
    def __init__(
        self,
        entropy_weight: float = 0.01,
        value_weight: float = 0.5
    ):
        super().__init__()
        self.entropy_weight = entropy_weight
        self.value_weight = value_weight
    
    def forward(
        self,
        log_probs: torch.Tensor,      # Log probabilities of taken actions
        advantages: torch.Tensor,      # Advantage estimates (GAE)
        values: torch.Tensor,          # Value predictions
        returns: torch.Tensor,         # Actual returns (for value loss)
        entropy: torch.Tensor          # Policy entropy
    ) -> Tuple[torch.Tensor, dict]:
        
        # Policy loss: -A * log π
        policy_loss = -(advantages.detach() * log_probs).mean()
        
        # Value loss
        value_loss = F.mse_loss(values, returns.detach())
        
        # Entropy bonus (encourage exploration)
        entropy_bonus = -entropy.mean()
        
        total_loss = (
            policy_loss +
            self.value_weight * value_loss +
            self.entropy_weight * entropy_bonus
        )
        
        return total_loss, {
            'policy_loss': policy_loss.item(),
            'value_loss': value_loss.item(),
            'entropy': entropy.mean().item()
        }


class PPOClipLoss(nn.Module):
    """
    PPO Clipped Surrogate Loss.
    
    L_CLIP = min(r_t * A_t, clip(r_t, 1-ε, 1+ε) * A_t)
    
    Where r_t = π(a|s) / π_old(a|s) is the probability ratio.
    """
    
    def __init__(
        self,
        clip_epsilon: float = 0.2,
        entropy_weight: float = 0.01,
        value_weight: float = 0.5
    ):
        super().__init__()
        self.clip_epsilon = clip_epsilon
        self.entropy_weight = entropy_weight
        self.value_weight = value_weight
    
    def forward(
        self,
        log_probs: torch.Tensor,
        old_log_probs: torch.Tensor,
        advantages: torch.Tensor,
        values: torch.Tensor,
        returns: torch.Tensor,
        entropy: torch.Tensor
    ) -> Tuple[torch.Tensor, dict]:
        
        # Probability ratio
        ratio = torch.exp(log_probs - old_log_probs.detach())
        
        # Clipped surrogate
        surr1 = ratio * advantages
        surr2 = torch.clamp(
            ratio,
            1 - self.clip_epsilon,
            1 + self.clip_epsilon
        ) * advantages
        
        policy_loss = -torch.min(surr1, surr2).mean()
        
        # Value loss (also clipped for stability)
        value_loss = F.mse_loss(values, returns.detach())
        
        # Entropy
        entropy_loss = -entropy.mean()
        
        total_loss = (
            policy_loss +
            self.value_weight * value_loss +
            self.entropy_weight * entropy_loss
        )
        
        return total_loss, {
            'policy_loss': policy_loss.item(),
            'value_loss': value_loss.item(),
            'entropy': entropy.mean().item(),
            'approx_kl': (old_log_probs - log_probs).mean().item()
        }


class TradingRewardFunction:
    """
    Reward shaping for trading RL.
    
    Combines multiple reward signals properly scaled.
    """
    
    def __init__(
        self,
        pnl_scale: float = 100.0,
        sharpe_scale: float = 1.0,
        drawdown_penalty: float = 10.0,
        transaction_cost: float = 0.001,
        holding_penalty: float = 0.0001  # Small cost for holding
    ):
        self.pnl_scale = pnl_scale
        self.sharpe_scale = sharpe_scale
        self.drawdown_penalty = drawdown_penalty
        self.transaction_cost = transaction_cost
        self.holding_penalty = holding_penalty
        
        self.returns_history = []
        self.peak_value = 1.0
    
    def __call__(
        self,
        pnl: float,
        position_change: float,
        current_value: float,
        position: float
    ) -> float:
        """
        Compute shaped reward.
        
        Args:
            pnl: PnL from this step
            position_change: Change in position (for transaction cost)
            current_value: Current portfolio value
            position: Current position
        """
        reward = 0.0
        
        # PnL component
        reward += pnl * self.pnl_scale
        
        # Transaction cost
        reward -= abs(position_change) * self.transaction_cost * self.pnl_scale
        
        # Holding cost (encourage active trading if profitable)
        reward -= abs(position) * self.holding_penalty
        
        # Drawdown penalty
        if current_value > self.peak_value:
            self.peak_value = current_value
        else:
            drawdown = (self.peak_value - current_value) / self.peak_value
            if drawdown > 0.05:  # Penalize >5% drawdown
                reward -= drawdown * self.drawdown_penalty
        
        # Running Sharpe component
        self.returns_history.append(pnl)
        if len(self.returns_history) > 20:
            returns = np.array(self.returns_history[-20:])
            if returns.std() > 0:
                rolling_sharpe = returns.mean() / returns.std()
                reward += rolling_sharpe * self.sharpe_scale
        
        return reward
    
    def reset(self):
        """Reset for new episode."""
        self.returns_history = []
        self.peak_value = 1.0
