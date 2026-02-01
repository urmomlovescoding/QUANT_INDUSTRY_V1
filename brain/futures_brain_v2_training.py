"""
FUTURES BRAIN V2 TRAINING - Advanced Training & Online Learning
================================================================
Training system for FuturesBrainV2 with:

1. Curriculum Learning - Gradual complexity increase
2. Adversarial Training - Robustness to distribution shifts
3. Online Adaptation - MAML-style fast adaptation
4. Regime-Aware Training - Different strategies per regime
5. Experience Replay - Prioritized sampling of important trades
6. Multi-Task Learning - Joint prediction of signals, position, regime

Author: QuantBrain Futures V2
Version: 2.0.0
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts, OneCycleLR
from torch.cuda.amp import autocast, GradScaler
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
import sqlite3
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta
import pickle
import copy
import random

logger = logging.getLogger("FUTURES_TRAINING_V2")

# Import brain
try:
    from brain.futures_brain_v2 import (
        FuturesBrainV2, FuturesBrainV2Config, DEVICE, USE_AMP
    )
except ImportError:
    from futures_brain_v2 import (
        FuturesBrainV2, FuturesBrainV2Config, DEVICE, USE_AMP
    )

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
WEIGHTS_DIR = ROOT / "weights" / "futures_brain_v2"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TrainingExample:
    """Single training example with features and labels."""
    features: np.ndarray  # (seq_len, n_features)
    static_features: np.ndarray  # (n_static,)
    signal_label: int  # 0=BUY, 1=HOLD, 2=SELL
    position_label: float  # Optimal position fraction
    regime_label: int  # Market regime
    profit_pips: float  # Actual profit (for weighting)
    timestamp: datetime
    symbol: str
    
    def to_tensor(self) -> Dict[str, torch.Tensor]:
        return {
            'features': torch.tensor(self.features, dtype=torch.float32),
            'static': torch.tensor(self.static_features, dtype=torch.float32),
            'signal_label': torch.tensor(self.signal_label, dtype=torch.long),
            'position_label': torch.tensor([self.position_label], dtype=torch.float32),
            'regime_label': torch.tensor(self.regime_label, dtype=torch.long),
            'weight': torch.tensor([abs(self.profit_pips) + 0.1], dtype=torch.float32)
        }


@dataclass
class TrainingMetrics:
    """Tracking metrics during training."""
    epoch: int = 0
    train_loss: float = 0.0
    val_loss: float = 0.0
    signal_accuracy: float = 0.0
    regime_accuracy: float = 0.0
    position_mae: float = 0.0
    learning_rate: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# PRIORITIZED EXPERIENCE REPLAY
# =============================================================================

class PrioritizedReplayBuffer:
    """
    Experience replay buffer with prioritized sampling.
    Samples important trades (high profit/loss) more frequently.
    """
    
    def __init__(self, capacity: int = 100000, alpha: float = 0.6, beta: float = 0.4):
        self.capacity = capacity
        self.alpha = alpha  # Priority exponent
        self.beta = beta  # Importance sampling
        self.beta_increment = 0.001
        
        self.buffer = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.position = 0
        self.max_priority = 1.0
    
    def add(self, example: TrainingExample):
        """Add example with max priority."""
        if len(self.buffer) < self.capacity:
            self.buffer.append(example)
        else:
            self.buffer[self.position] = example
        
        self.priorities[self.position] = self.max_priority
        self.position = (self.position + 1) % self.capacity
    
    def sample(self, batch_size: int) -> Tuple[List[TrainingExample], np.ndarray, np.ndarray]:
        """Sample batch with priorities."""
        n = len(self.buffer)
        if n == 0:
            return [], np.array([]), np.array([])
        
        # Calculate sampling probabilities
        priorities = self.priorities[:n] ** self.alpha
        probs = priorities / priorities.sum()
        
        # Sample indices
        indices = np.random.choice(n, size=min(batch_size, n), p=probs, replace=False)
        
        # Calculate importance sampling weights
        self.beta = min(1.0, self.beta + self.beta_increment)
        weights = (n * probs[indices]) ** (-self.beta)
        weights /= weights.max()  # Normalize
        
        examples = [self.buffer[i] for i in indices]
        return examples, indices, weights
    
    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """Update priorities based on TD errors."""
        for idx, td_error in zip(indices, td_errors):
            priority = abs(td_error) + 0.01  # Small epsilon to avoid zero
            self.priorities[idx] = priority
            self.max_priority = max(self.max_priority, priority)
    
    def __len__(self):
        return len(self.buffer)


# =============================================================================
# CURRICULUM LEARNING
# =============================================================================

class CurriculumScheduler:
    """
    Curriculum learning scheduler.
    Gradually increases difficulty of training examples.
    """
    
    def __init__(self, total_epochs: int, warmup_epochs: int = 10):
        self.total_epochs = total_epochs
        self.warmup_epochs = warmup_epochs
        self.current_epoch = 0
        
        # Difficulty levels: 0 = easy, 1 = medium, 2 = hard
        self.difficulty_thresholds = [0.3, 0.6, 1.0]
    
    def get_difficulty_weights(self) -> Dict[str, float]:
        """Get sampling weights for each difficulty level."""
        progress = min(1.0, self.current_epoch / max(1, self.total_epochs - self.warmup_epochs))
        
        if self.current_epoch < self.warmup_epochs:
            # Warmup: focus on easy examples
            return {'easy': 0.7, 'medium': 0.25, 'hard': 0.05}
        
        # Gradually shift to harder examples
        easy_weight = max(0.1, 0.6 * (1 - progress))
        hard_weight = min(0.5, 0.1 + 0.4 * progress)
        medium_weight = 1.0 - easy_weight - hard_weight
        
        return {'easy': easy_weight, 'medium': medium_weight, 'hard': hard_weight}
    
    def classify_example(self, example: TrainingExample) -> str:
        """Classify example difficulty based on volatility, regime, etc."""
        # Higher profit variance = harder
        profit_difficulty = min(1.0, abs(example.profit_pips) / 20)
        
        # Volatile regimes are harder
        regime_difficulty = {0: 0.3, 1: 0.2, 2: 0.8, 3: 0.1}.get(example.regime_label, 0.5)
        
        combined = 0.6 * profit_difficulty + 0.4 * regime_difficulty
        
        if combined < self.difficulty_thresholds[0]:
            return 'easy'
        elif combined < self.difficulty_thresholds[1]:
            return 'medium'
        else:
            return 'hard'
    
    def step(self):
        """Move to next epoch."""
        self.current_epoch += 1


# =============================================================================
# ADVERSARIAL TRAINING
# =============================================================================

class AdversarialPerturbation:
    """
    Generates adversarial perturbations for robust training.
    Uses Fast Gradient Sign Method (FGSM) and random noise.
    """
    
    def __init__(self, epsilon: float = 0.01, noise_std: float = 0.02):
        self.epsilon = epsilon
        self.noise_std = noise_std
    
    def fgsm_perturbation(self, model: nn.Module, features: torch.Tensor, 
                         labels: torch.Tensor, loss_fn: nn.Module) -> torch.Tensor:
        """Generate FGSM adversarial perturbation."""
        features = features.clone().detach().requires_grad_(True)
        
        outputs = model(features)
        if isinstance(outputs, dict):
            outputs = outputs['signal_logits']
        
        loss = loss_fn(outputs.view(-1, 3), labels.view(-1))
        loss.backward()
        
        # Get sign of gradient
        perturbation = self.epsilon * features.grad.sign()
        
        return features + perturbation
    
    def random_perturbation(self, features: torch.Tensor) -> torch.Tensor:
        """Add random Gaussian noise."""
        noise = torch.randn_like(features) * self.noise_std
        return features + noise
    
    def temporal_shuffle(self, features: torch.Tensor, shuffle_prob: float = 0.1) -> torch.Tensor:
        """Randomly shuffle small portions of temporal sequence."""
        batch_size, seq_len, _ = features.shape
        
        for b in range(batch_size):
            if random.random() < shuffle_prob:
                # Shuffle a small window
                start = random.randint(0, seq_len - 5)
                end = start + random.randint(2, 5)
                indices = list(range(start, end))
                random.shuffle(indices)
                features[b, start:end] = features[b, indices]
        
        return features


# =============================================================================
# ONLINE LEARNING (MAML-style)
# =============================================================================

class OnlineLearner:
    """
    Online learning with fast adaptation.
    Inspired by MAML - learns to quickly adapt to new market conditions.
    """
    
    def __init__(self, model: FuturesBrainV2, inner_lr: float = 1e-4, 
                 inner_steps: int = 5, meta_lr: float = 1e-5):
        self.model = model
        self.inner_lr = inner_lr
        self.inner_steps = inner_steps
        self.meta_lr = meta_lr
        
        self.meta_optimizer = AdamW(model.parameters(), lr=meta_lr)
        
        # Track recent performance for adaptation triggers
        self.recent_accuracy = deque(maxlen=20)
        self.adaptation_threshold = 0.55  # Adapt if accuracy drops below
    
    def should_adapt(self) -> bool:
        """Check if model needs adaptation."""
        if len(self.recent_accuracy) < 10:
            return False
        return np.mean(list(self.recent_accuracy)) < self.adaptation_threshold
    
    def fast_adapt(self, support_examples: List[TrainingExample]) -> nn.Module:
        """
        Quick adaptation on support set.
        Returns adapted model copy (doesn't modify original).
        """
        # Clone model
        adapted_model = copy.deepcopy(self.model)
        adapted_model.train()
        
        # Create optimizer for inner loop
        inner_optimizer = torch.optim.SGD(adapted_model.parameters(), lr=self.inner_lr)
        
        # Convert examples to batches
        features = torch.stack([torch.tensor(ex.features, dtype=torch.float32) 
                               for ex in support_examples]).to(DEVICE)
        labels = torch.tensor([ex.signal_label for ex in support_examples], 
                            dtype=torch.long).to(DEVICE)
        
        # Inner loop adaptation
        criterion = nn.CrossEntropyLoss()
        
        for _ in range(self.inner_steps):
            inner_optimizer.zero_grad()
            outputs = adapted_model(features)
            loss = criterion(outputs['signal_logits'][:, -1, :], labels)
            loss.backward()
            inner_optimizer.step()
        
        return adapted_model
    
    def meta_update(self, query_examples: List[TrainingExample], 
                   adapted_model: nn.Module):
        """
        Meta-update using query set performance of adapted model.
        Updates the base model to be better at adaptation.
        """
        self.meta_optimizer.zero_grad()
        
        # Get query batch
        features = torch.stack([torch.tensor(ex.features, dtype=torch.float32) 
                               for ex in query_examples]).to(DEVICE)
        labels = torch.tensor([ex.signal_label for ex in query_examples], 
                            dtype=torch.long).to(DEVICE)
        
        # Forward through adapted model
        outputs = adapted_model(features)
        loss = F.cross_entropy(outputs['signal_logits'][:, -1, :], labels)
        
        # Backward through adaptation process
        loss.backward()
        
        # Update base model
        self.meta_optimizer.step()
        
        return loss.item()
    
    def update_accuracy(self, accuracy: float):
        """Track recent accuracy."""
        self.recent_accuracy.append(accuracy)


# =============================================================================
# MULTI-TASK LOSS
# =============================================================================

class MultiTaskLoss(nn.Module):
    """
    Multi-task loss with learnable task weights.
    Automatically balances signal, position, and regime losses.
    """
    
    def __init__(self, num_tasks: int = 3):
        super().__init__()
        
        # Learnable log variances for uncertainty weighting
        self.log_vars = nn.Parameter(torch.zeros(num_tasks))
        
        self.signal_loss = nn.CrossEntropyLoss(label_smoothing=0.1)
        self.position_loss = nn.MSELoss()
        self.regime_loss = nn.CrossEntropyLoss()
    
    def forward(self, outputs: Dict[str, torch.Tensor], 
               labels: Dict[str, torch.Tensor]) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute multi-task loss with uncertainty weighting.
        
        Returns: (total_loss, individual_losses_dict)
        """
        losses = {}
        
        # Signal prediction loss - use LAST timestep only (trading decision point)
        # signal_logits: (batch, seq_len, 3) -> take [:, -1, :] for final prediction
        signal_logits = outputs['signal_logits']
        if signal_logits.dim() == 3:
            # Take only the last timestep prediction
            signal_logits = signal_logits[:, -1, :]  # (batch, 3)
        signal_loss = self.signal_loss(signal_logits, labels['signal'])
        losses['signal'] = signal_loss
        
        # Position sizing loss - also use last timestep
        if 'position' in labels:
            pos_output = outputs['position_fraction']
            if pos_output.dim() == 3:
                pos_output = pos_output[:, -1, :].squeeze(-1)  # (batch, seq, 1) -> (batch,)
            elif pos_output.dim() == 2:
                pos_output = pos_output[:, -1]  # (batch, seq) -> (batch,)
            pos_loss = self.position_loss(pos_output, labels['position'])
            losses['position'] = pos_loss
        else:
            losses['position'] = torch.tensor(0.0, device=DEVICE)
        
        # Regime classification loss - use last timestep
        if 'regime' in labels:
            regime_probs = outputs['regime_probs']
            if regime_probs.dim() == 3:
                regime_probs = regime_probs[:, -1, :]  # (batch, 4)
            regime_loss = self.regime_loss(regime_probs, labels['regime'])
            losses['regime'] = regime_loss
        else:
            losses['regime'] = torch.tensor(0.0, device=DEVICE)
        
        # Uncertainty-weighted combination
        # L_total = sum(0.5 * exp(-log_var) * L_i + 0.5 * log_var)
        total_loss = 0
        for i, (name, loss) in enumerate(losses.items()):
            precision = torch.exp(-self.log_vars[i])
            total_loss += 0.5 * precision * loss + 0.5 * self.log_vars[i]
        
        # Add task weights to output
        losses['task_weights'] = {
            'signal': torch.exp(-self.log_vars[0]).item(),
            'position': torch.exp(-self.log_vars[1]).item(),
            'regime': torch.exp(-self.log_vars[2]).item()
        }
        
        return total_loss, {k: v.item() if isinstance(v, torch.Tensor) else v 
                          for k, v in losses.items()}


# =============================================================================
# DATASET
# =============================================================================

class FuturesTradingDataset(Dataset):
    """PyTorch dataset for futures trading examples."""
    
    def __init__(self, examples: List[TrainingExample], 
                 curriculum: CurriculumScheduler = None):
        self.examples = examples
        self.curriculum = curriculum
        
        # Classify examples by difficulty
        if curriculum:
            self.difficulty_groups = {'easy': [], 'medium': [], 'hard': []}
            for i, ex in enumerate(examples):
                difficulty = curriculum.classify_example(ex)
                self.difficulty_groups[difficulty].append(i)
    
    def __len__(self):
        return len(self.examples)
    
    def __getitem__(self, idx):
        return self.examples[idx].to_tensor()
    
    def get_curriculum_sampler(self) -> WeightedRandomSampler:
        """Get sampler that respects curriculum weights."""
        if not self.curriculum:
            return None
        
        weights = self.curriculum.get_difficulty_weights()
        sample_weights = np.zeros(len(self.examples))
        
        for difficulty, indices in self.difficulty_groups.items():
            for idx in indices:
                sample_weights[idx] = weights[difficulty] / max(1, len(indices))
        
        sample_weights /= sample_weights.sum()
        
        return WeightedRandomSampler(
            weights=sample_weights,
            num_samples=len(self.examples),
            replacement=True
        )


# =============================================================================
# TRAINING LOOP
# =============================================================================

class FuturesBrainV2Trainer:
    """
    Complete training system for FuturesBrainV2.
    """
    
    def __init__(self, model: FuturesBrainV2 = None, config: FuturesBrainV2Config = None):
        self.config = config or FuturesBrainV2Config()
        self.model = model or FuturesBrainV2(self.config).to(DEVICE)
        
        # Optimizers
        self.optimizer = AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )
        
        self.scheduler = OneCycleLR(
            self.optimizer,
            max_lr=self.config.learning_rate * 10,
            total_steps=10000,  # Will be updated
            pct_start=0.1
        )
        
        # Mixed precision
        self.scaler = GradScaler() if USE_AMP else None
        
        # Loss
        self.criterion = MultiTaskLoss()
        
        # Curriculum
        self.curriculum = CurriculumScheduler(total_epochs=100)
        
        # Adversarial
        self.adversarial = AdversarialPerturbation()
        
        # Online learner
        self.online_learner = OnlineLearner(self.model)
        
        # Replay buffer
        self.replay_buffer = PrioritizedReplayBuffer()
        
        # Training history
        self.history = []
        self.best_val_loss = float('inf')
        
        logger.info(f"FuturesBrainV2Trainer initialized on {DEVICE}")
    
    def train_epoch(self, dataloader: DataLoader, 
                   adversarial_prob: float = 0.2) -> TrainingMetrics:
        """Train for one epoch."""
        self.model.train()
        
        total_loss = 0
        signal_correct = 0
        regime_correct = 0
        total_samples = 0
        position_mae = 0
        
        for batch in dataloader:
            # Move to device
            features = batch['features'].to(DEVICE)
            static = batch['static'].to(DEVICE) if 'static' in batch else None
            labels = {
                'signal': batch['signal_label'].to(DEVICE),
                'position': batch['position_label'].to(DEVICE),
                'regime': batch['regime_label'].to(DEVICE)
            }
            
            # Apply adversarial perturbation with probability
            if random.random() < adversarial_prob:
                features = self.adversarial.random_perturbation(features)
            
            self.optimizer.zero_grad()
            
            with autocast(enabled=USE_AMP):
                outputs = self.model(features, static)
                loss, loss_dict = self.criterion(outputs, labels)
            
            # Backward
            if self.scaler:
                self.scaler.scale(loss).backward()
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.gradient_clip)
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.gradient_clip)
                self.optimizer.step()
            
            self.scheduler.step()
            
            # Metrics
            total_loss += loss.item()
            batch_size = features.size(0)
            total_samples += batch_size
            
            # Signal accuracy
            preds = outputs['signal_logits'][:, -1, :].argmax(dim=-1)
            signal_correct += (preds == labels['signal']).sum().item()
            
            # Regime accuracy
            regime_preds = outputs['regime_probs'][:, -1, :].argmax(dim=-1)
            regime_correct += (regime_preds == labels['regime']).sum().item()
            
            # Position MAE
            position_mae += torch.abs(
                outputs['position_fraction'][:, -1, 0] - labels['position'][:, 0]
            ).sum().item()
        
        # Update curriculum
        self.curriculum.step()
        
        return TrainingMetrics(
            epoch=self.curriculum.current_epoch,
            train_loss=total_loss / max(1, len(dataloader)),
            signal_accuracy=signal_correct / max(1, total_samples),
            regime_accuracy=regime_correct / max(1, total_samples),
            position_mae=position_mae / max(1, total_samples),
            learning_rate=self.optimizer.param_groups[0]['lr']
        )
    
    @torch.no_grad()
    def validate(self, dataloader: DataLoader) -> TrainingMetrics:
        """Validation pass."""
        self.model.eval()
        
        total_loss = 0
        signal_correct = 0
        regime_correct = 0
        total_samples = 0
        
        for batch in dataloader:
            features = batch['features'].to(DEVICE)
            static = batch['static'].to(DEVICE) if 'static' in batch else None
            labels = {
                'signal': batch['signal_label'].to(DEVICE),
                'position': batch['position_label'].to(DEVICE),
                'regime': batch['regime_label'].to(DEVICE)
            }
            
            outputs = self.model(features, static)
            loss, _ = self.criterion(outputs, labels)
            
            total_loss += loss.item()
            batch_size = features.size(0)
            total_samples += batch_size
            
            preds = outputs['signal_logits'][:, -1, :].argmax(dim=-1)
            signal_correct += (preds == labels['signal']).sum().item()
            
            regime_preds = outputs['regime_probs'][:, -1, :].argmax(dim=-1)
            regime_correct += (regime_preds == labels['regime']).sum().item()
        
        return TrainingMetrics(
            val_loss=total_loss / max(1, len(dataloader)),
            signal_accuracy=signal_correct / max(1, total_samples),
            regime_accuracy=regime_correct / max(1, total_samples)
        )
    
    def train(self, train_examples: List[TrainingExample], 
             val_examples: List[TrainingExample],
             epochs: int = 100, batch_size: int = 32,
             early_stopping_patience: int = 15) -> List[TrainingMetrics]:
        """
        Full training loop with curriculum learning and early stopping.
        """
        logger.info(f"Starting training: {len(train_examples)} train, {len(val_examples)} val")
        
        # Update curriculum
        self.curriculum.total_epochs = epochs
        
        # Create datasets
        train_dataset = FuturesTradingDataset(train_examples, self.curriculum)
        val_dataset = FuturesTradingDataset(val_examples)
        
        # Update scheduler
        total_steps = epochs * (len(train_examples) // batch_size + 1)
        self.scheduler = OneCycleLR(
            self.optimizer,
            max_lr=self.config.learning_rate * 10,
            total_steps=total_steps,
            pct_start=0.1
        )
        
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            # Get curriculum sampler
            sampler = train_dataset.get_curriculum_sampler()
            
            train_loader = DataLoader(
                train_dataset, batch_size=batch_size,
                sampler=sampler, num_workers=0
            )
            val_loader = DataLoader(
                val_dataset, batch_size=batch_size,
                shuffle=False, num_workers=0
            )
            
            # Train epoch
            train_metrics = self.train_epoch(train_loader)
            
            # Validate
            val_metrics = self.validate(val_loader)
            train_metrics.val_loss = val_metrics.val_loss
            
            self.history.append(train_metrics)
            
            # Logging
            if epoch % 5 == 0:
                logger.info(
                    f"Epoch {epoch}: Train Loss={train_metrics.train_loss:.4f}, "
                    f"Val Loss={train_metrics.val_loss:.4f}, "
                    f"Signal Acc={train_metrics.signal_accuracy:.2%}, "
                    f"LR={train_metrics.learning_rate:.2e}"
                )
            
            # Early stopping
            if val_metrics.val_loss < best_val_loss:
                best_val_loss = val_metrics.val_loss
                patience_counter = 0
                self.model.save()  # Save best model
            else:
                patience_counter += 1
            
            if patience_counter >= early_stopping_patience:
                logger.info(f"Early stopping at epoch {epoch}")
                break
            
            # Update online learner
            self.online_learner.update_accuracy(train_metrics.signal_accuracy)
        
        return self.history
    
    def online_update(self, recent_examples: List[TrainingExample], 
                     num_steps: int = 10):
        """
        Quick online update on recent examples.
        """
        if len(recent_examples) < 5:
            return
        
        self.model.train()
        
        # Add to replay buffer
        for ex in recent_examples:
            self.replay_buffer.add(ex)
        
        # Sample from replay buffer
        examples, indices, weights = self.replay_buffer.sample(min(32, len(self.replay_buffer)))
        
        if not examples:
            return
        
        # Quick training steps
        for _ in range(num_steps):
            features = torch.stack([torch.tensor(ex.features, dtype=torch.float32) 
                                   for ex in examples]).to(DEVICE)
            labels = {
                'signal': torch.tensor([ex.signal_label for ex in examples], 
                                      dtype=torch.long).to(DEVICE),
                'position': torch.tensor([[ex.position_label] for ex in examples],
                                        dtype=torch.float32).to(DEVICE),
                'regime': torch.tensor([ex.regime_label for ex in examples],
                                      dtype=torch.long).to(DEVICE)
            }
            
            self.optimizer.zero_grad()
            outputs = self.model(features)
            loss, _ = self.criterion(outputs, labels)
            
            # Weight by importance sampling
            sample_weights = torch.tensor(weights, dtype=torch.float32, device=DEVICE)
            loss = (loss * sample_weights.mean())
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
            self.optimizer.step()
        
        logger.debug(f"Online update completed: {len(examples)} examples, {num_steps} steps")


# =============================================================================
# DATA GENERATION FOR TESTING
# =============================================================================

def generate_synthetic_examples(n_examples: int = 1000, 
                               seq_len: int = 60,
                               n_features: int = 96) -> List[TrainingExample]:
    """Generate synthetic training examples for testing."""
    examples = []
    
    for i in range(n_examples):
        # Generate random features
        features = np.random.randn(seq_len, n_features).astype(np.float32)
        static = np.random.randn(8).astype(np.float32)
        
        # Generate labels based on simple rules
        trend = np.mean(features[-10:, 0])  # Use first feature as trend proxy
        
        if trend > 0.3:
            signal = 0  # BUY
        elif trend < -0.3:
            signal = 2  # SELL
        else:
            signal = 1  # HOLD
        
        regime = np.random.randint(0, 4)
        position = np.clip(abs(trend), 0, 1)
        profit = np.random.randn() * 10  # Random profit
        
        examples.append(TrainingExample(
            features=features,
            static_features=static,
            signal_label=signal,
            position_label=position,
            regime_label=regime,
            profit_pips=profit,
            timestamp=datetime.now() - timedelta(hours=i),
            symbol='MNQ'
        ))
    
    return examples


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test training system
    logger.info("Testing FuturesBrainV2 Training System...")
    
    # Generate synthetic data
    train_examples = generate_synthetic_examples(500)
    val_examples = generate_synthetic_examples(100)
    
    # Create trainer
    config = FuturesBrainV2Config()
    trainer = FuturesBrainV2Trainer(config=config)
    
    # Train
    history = trainer.train(
        train_examples, val_examples,
        epochs=10, batch_size=16
    )
    
    print("\nTraining completed!")
    print(f"Final train loss: {history[-1].train_loss:.4f}")
    print(f"Final val loss: {history[-1].val_loss:.4f}")
    print(f"Final signal accuracy: {history[-1].signal_accuracy:.2%}")
