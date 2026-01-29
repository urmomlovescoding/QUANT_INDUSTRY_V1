"""
Base Neural Network Classes
===========================
Foundation classes for all PyTorch models in the trading system.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from torch.utils.tensorboard import SummaryWriter
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple, Callable
from pathlib import Path
import logging
import json
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


def get_device() -> torch.device:
    """Get best available device (CUDA > MPS > CPU)."""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info(f"Using CUDA: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = torch.device("mps")
        logger.info("Using Apple MPS (Metal)")
    else:
        device = torch.device("cpu")
        logger.info("Using CPU")
    return device


@dataclass
class ModelConfig:
    """Base configuration for all models."""
    # Architecture
    input_dim: int = 64
    hidden_dim: int = 256
    output_dim: int = 3  # [sell, hold, buy] or regression
    num_layers: int = 3
    dropout: float = 0.2
    
    # Training
    learning_rate: float = 1e-4
    weight_decay: float = 1e-5
    batch_size: int = 64
    epochs: int = 100
    patience: int = 10  # Early stopping
    
    # Sequence
    seq_length: int = 60
    
    # Output
    task: str = "classification"  # or "regression"
    num_classes: int = 3
    
    # Regularization
    label_smoothing: float = 0.1
    gradient_clip: float = 1.0
    
    # Logging
    log_dir: str = "runs"
    checkpoint_dir: str = "checkpoints"
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class EarlyStopping:
    """Early stopping handler."""
    
    def __init__(self, patience: int = 10, min_delta: float = 1e-4, mode: str = 'min'):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_score = None
        self.should_stop = False
        
    def __call__(self, score: float) -> bool:
        if self.best_score is None:
            self.best_score = score
        elif self._is_improvement(score):
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
        return self.should_stop
    
    def _is_improvement(self, score: float) -> bool:
        if self.mode == 'min':
            return score < self.best_score - self.min_delta
        return score > self.best_score + self.min_delta


class BaseModel(nn.Module, ABC):
    """
    Base class for all trading models.
    
    Provides:
    - Device management (CPU/GPU)
    - Training loop with validation
    - Early stopping
    - Checkpointing
    - TensorBoard logging
    - Gradient clipping
    """
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        self.device = get_device()
        self.writer: Optional[SummaryWriter] = None
        self.best_val_loss = float('inf')
        self.training_history: List[Dict] = []
        
    @abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass - must be implemented by subclasses."""
        pass
    
    def _init_weights(self, module: nn.Module):
        """Initialize weights using Xavier/Kaiming."""
        if isinstance(module, nn.Linear):
            nn.init.kaiming_normal_(module.weight, nonlinearity='relu')
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.LSTM):
            for name, param in module.named_parameters():
                if 'weight_ih' in name:
                    nn.init.kaiming_normal_(param)
                elif 'weight_hh' in name:
                    nn.init.orthogonal_(param)
                elif 'bias' in name:
                    nn.init.zeros_(param)
        elif isinstance(module, nn.LayerNorm):
            nn.init.ones_(module.weight)
            nn.init.zeros_(module.bias)
    
    def count_parameters(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
    
    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        callbacks: Optional[List[Callable]] = None,
    ) -> Dict[str, List[float]]:
        """
        Train the model.
        
        Args:
            X_train: Training features [N, seq_len, features]
            y_train: Training targets [N] or [N, output_dim]
            X_val: Validation features
            y_val: Validation targets
            callbacks: Optional callbacks after each epoch
            
        Returns:
            Training history dict
        """
        self.to(self.device)
        
        # Setup logging
        log_path = Path(self.config.log_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.writer = SummaryWriter(log_path)
        logger.info(f"TensorBoard logs: {log_path}")
        
        # Create data loaders
        train_loader = self._create_dataloader(X_train, y_train, shuffle=True)
        val_loader = self._create_dataloader(X_val, y_val) if X_val is not None else None
        
        # Setup optimizer and scheduler
        optimizer = optim.AdamW(
            self.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5, verbose=True
        )
        
        # Loss function
        if self.config.task == "classification":
            criterion = nn.CrossEntropyLoss(label_smoothing=self.config.label_smoothing)
        else:
            criterion = nn.MSELoss()
        
        # Early stopping
        early_stopping = EarlyStopping(patience=self.config.patience)
        
        # Training loop
        history = {'train_loss': [], 'val_loss': [], 'lr': []}
        
        logger.info(f"Starting training: {self.count_parameters():,} parameters")
        logger.info(f"Device: {self.device}")
        
        for epoch in range(self.config.epochs):
            # Train
            train_loss = self._train_epoch(train_loader, optimizer, criterion)
            history['train_loss'].append(train_loss)
            
            # Validate
            val_loss = 0.0
            if val_loader:
                val_loss, val_metrics = self._validate(val_loader, criterion)
                history['val_loss'].append(val_loss)
                scheduler.step(val_loss)
            
            # Log
            current_lr = optimizer.param_groups[0]['lr']
            history['lr'].append(current_lr)
            
            self.writer.add_scalar('Loss/train', train_loss, epoch)
            if val_loader:
                self.writer.add_scalar('Loss/val', val_loss, epoch)
            self.writer.add_scalar('LR', current_lr, epoch)
            
            # Log progress
            if epoch % 10 == 0 or epoch == self.config.epochs - 1:
                msg = f"Epoch {epoch+1}/{self.config.epochs} | Train: {train_loss:.4f}"
                if val_loader:
                    msg += f" | Val: {val_loss:.4f}"
                msg += f" | LR: {current_lr:.2e}"
                logger.info(msg)
            
            # Checkpointing
            if val_loader and val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self._save_checkpoint(epoch, optimizer, val_loss)
            
            # Early stopping
            if val_loader and early_stopping(val_loss):
                logger.info(f"Early stopping at epoch {epoch+1}")
                break
            
            # Callbacks
            if callbacks:
                for cb in callbacks:
                    cb(self, epoch, history)
        
        self.writer.close()
        self.training_history = history
        
        # Load best model
        self._load_best_checkpoint()
        
        return history
    
    def _train_epoch(
        self,
        loader: DataLoader,
        optimizer: optim.Optimizer,
        criterion: nn.Module
    ) -> float:
        """Single training epoch."""
        self.train()
        total_loss = 0.0
        
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(self.device)
            batch_y = batch_y.to(self.device)
            
            optimizer.zero_grad()
            outputs = self(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(
                self.parameters(), 
                self.config.gradient_clip
            )
            
            optimizer.step()
            total_loss += loss.item()
        
        return total_loss / len(loader)
    
    def _validate(
        self,
        loader: DataLoader,
        criterion: nn.Module
    ) -> Tuple[float, Dict[str, float]]:
        """Validation pass."""
        self.eval()
        total_loss = 0.0
        all_preds = []
        all_targets = []
        
        with torch.no_grad():
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                
                outputs = self(batch_x)
                loss = criterion(outputs, batch_y)
                total_loss += loss.item()
                
                if self.config.task == "classification":
                    preds = outputs.argmax(dim=1)
                else:
                    preds = outputs
                
                all_preds.extend(preds.cpu().numpy())
                all_targets.extend(batch_y.cpu().numpy())
        
        avg_loss = total_loss / len(loader)
        
        # Calculate metrics
        metrics = {}
        if self.config.task == "classification":
            all_preds = np.array(all_preds)
            all_targets = np.array(all_targets)
            metrics['accuracy'] = (all_preds == all_targets).mean()
        
        return avg_loss, metrics
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions."""
        self.eval()
        self.to(self.device)
        
        X_tensor = torch.FloatTensor(X).to(self.device)
        
        with torch.no_grad():
            outputs = self(X_tensor)
            if self.config.task == "classification":
                preds = outputs.argmax(dim=1)
            else:
                preds = outputs
        
        return preds.cpu().numpy()
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Generate probability predictions (classification only)."""
        self.eval()
        self.to(self.device)
        
        X_tensor = torch.FloatTensor(X).to(self.device)
        
        with torch.no_grad():
            outputs = self(X_tensor)
            probs = torch.softmax(outputs, dim=1)
        
        return probs.cpu().numpy()
    
    def _create_dataloader(
        self,
        X: np.ndarray,
        y: np.ndarray,
        shuffle: bool = False
    ) -> DataLoader:
        """Create PyTorch DataLoader."""
        X_tensor = torch.FloatTensor(X)
        
        if self.config.task == "classification":
            y_tensor = torch.LongTensor(y)
        else:
            y_tensor = torch.FloatTensor(y)
        
        dataset = TensorDataset(X_tensor, y_tensor)
        return DataLoader(
            dataset,
            batch_size=self.config.batch_size,
            shuffle=shuffle,
            num_workers=0,
            pin_memory=True if self.device.type == 'cuda' else False
        )
    
    def _save_checkpoint(self, epoch: int, optimizer: optim.Optimizer, val_loss: float):
        """Save model checkpoint."""
        ckpt_dir = Path(self.config.checkpoint_dir)
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        
        ckpt_path = ckpt_dir / f"{self.__class__.__name__}_best.pt"
        
        torch.save({
            'epoch': epoch,
            'model_state_dict': self.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'val_loss': val_loss,
            'config': self.config.to_dict(),
        }, ckpt_path)
        
        logger.debug(f"Saved checkpoint: {ckpt_path}")
    
    def _load_best_checkpoint(self):
        """Load best checkpoint."""
        ckpt_path = Path(self.config.checkpoint_dir) / f"{self.__class__.__name__}_best.pt"
        
        if ckpt_path.exists():
            checkpoint = torch.load(ckpt_path, map_location=self.device)
            self.load_state_dict(checkpoint['model_state_dict'])
            logger.info(f"Loaded best model (val_loss: {checkpoint['val_loss']:.4f})")
    
    def save(self, path: str):
        """Save model to file."""
        torch.save({
            'model_state_dict': self.state_dict(),
            'config': self.config.to_dict(),
        }, path)
        logger.info(f"Model saved: {path}")
    
    @classmethod
    def load(cls, path: str, config: Optional[ModelConfig] = None):
        """Load model from file."""
        checkpoint = torch.load(path, map_location='cpu')
        
        if config is None:
            config = ModelConfig(**checkpoint['config'])
        
        model = cls(config)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.to(model.device)
        
        logger.info(f"Model loaded: {path}")
        return model
