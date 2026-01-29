"""
ML Models for Order Flow Prediction
===================================
Various model architectures for predicting price movements from order flow.
"""

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Callable
from enum import Enum
import logging
import pickle
import json
from pathlib import Path
from abc import ABC, abstractmethod

from .order_flow_features import FeatureSet, FeatureNormalizer

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Supported model types."""
    LINEAR = "linear"
    RIDGE = "ridge"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOST = "gradient_boost"
    NEURAL_NET = "neural_net"
    LSTM = "lstm"
    ENSEMBLE = "ensemble"


class PredictionTarget(Enum):
    """What the model predicts."""
    DIRECTION = "direction"  # Up/Down classification
    RETURN = "return"  # Actual return regression
    VOLATILITY = "volatility"  # Future volatility
    SPREAD = "spread"  # Spread direction


@dataclass
class ModelPrediction:
    """Model prediction result."""
    timestamp: datetime
    symbol: str
    target: PredictionTarget
    
    # Classification output
    direction: Optional[str] = None  # "up", "down", "neutral"
    direction_confidence: float = 0.0
    
    # Regression output
    predicted_return: float = 0.0
    return_std: float = 0.0  # Prediction uncertainty
    
    # Feature importance for this prediction
    top_features: List[Tuple[str, float]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "target": self.target.value,
            "direction": self.direction,
            "direction_confidence": self.direction_confidence,
            "predicted_return": self.predicted_return,
            "return_std": self.return_std,
            "top_features": self.top_features,
        }


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    
    # Regression metrics
    mse: float = 0.0
    mae: float = 0.0
    r_squared: float = 0.0
    
    # Trading metrics
    hit_rate: float = 0.0  # % of correct direction predictions
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    
    # Calibration
    calibration_error: float = 0.0  # How well confidence matches accuracy
    
    num_samples: int = 0
    evaluation_period: str = ""


class FlowModel(ABC):
    """Abstract base class for flow prediction models."""
    
    def __init__(
        self,
        model_type: ModelType,
        target: PredictionTarget,
        horizon_seconds: int = 5,
    ):
        self.model_type = model_type
        self.target = target
        self.horizon_seconds = horizon_seconds
        self.is_trained = False
        self.feature_names = FeatureSet.feature_names()
        self.normalizer = FeatureNormalizer()
        
    @abstractmethod
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
    ) -> ModelMetrics:
        """Train the model."""
        pass
    
    @abstractmethod
    def predict(self, features: FeatureSet) -> ModelPrediction:
        """Make a prediction from features."""
        pass
    
    @abstractmethod
    def save(self, path: Path):
        """Save model to disk."""
        pass
    
    @abstractmethod
    def load(self, path: Path):
        """Load model from disk."""
        pass
    
    def _prepare_features(self, features: FeatureSet) -> np.ndarray:
        """Prepare and normalize features."""
        return self.normalizer.fit_transform(features)


class LinearFlowModel(FlowModel):
    """
    Simple linear model for order flow prediction.
    Fast to train and interpret, good baseline.
    """
    
    def __init__(
        self,
        target: PredictionTarget = PredictionTarget.DIRECTION,
        horizon_seconds: int = 5,
        regularization: float = 0.01,
    ):
        super().__init__(ModelType.LINEAR, target, horizon_seconds)
        self.regularization = regularization
        self.weights: Optional[np.ndarray] = None
        self.bias: float = 0.0
        self.feature_importance: Dict[str, float] = {}
        
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
    ) -> ModelMetrics:
        """Train linear model using closed-form solution with regularization."""
        n_samples = X.shape[0]
        split_idx = int(n_samples * (1 - validation_split))
        
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # Add bias term
        X_train_bias = np.column_stack([np.ones(X_train.shape[0]), X_train])
        
        # Ridge regression closed form: (X'X + λI)^(-1) X'y
        n_features = X_train_bias.shape[1]
        reg_matrix = self.regularization * np.eye(n_features)
        reg_matrix[0, 0] = 0  # Don't regularize bias
        
        try:
            XtX = X_train_bias.T @ X_train_bias
            XtY = X_train_bias.T @ y_train
            self.weights = np.linalg.solve(XtX + reg_matrix, XtY)
            self.bias = self.weights[0]
            self.weights = self.weights[1:]
        except np.linalg.LinAlgError:
            logger.error("Linear algebra error in training")
            self.weights = np.zeros(X.shape[1])
            self.bias = 0.0
            
        # Feature importance
        for i, name in enumerate(self.feature_names):
            self.feature_importance[name] = abs(self.weights[i])
            
        self.is_trained = True
        
        # Evaluate on validation set
        return self._evaluate(X_val, y_val)
    
    def _evaluate(self, X: np.ndarray, y: np.ndarray) -> ModelMetrics:
        """Evaluate model performance."""
        predictions = X @ self.weights + self.bias
        
        metrics = ModelMetrics(num_samples=len(y))
        
        if self.target == PredictionTarget.DIRECTION:
            # Classification metrics
            pred_direction = np.sign(predictions)
            true_direction = np.sign(y)
            
            correct = (pred_direction == true_direction) | (true_direction == 0)
            metrics.accuracy = np.mean(correct)
            metrics.hit_rate = metrics.accuracy
            
        else:
            # Regression metrics
            metrics.mse = np.mean((predictions - y) ** 2)
            metrics.mae = np.mean(np.abs(predictions - y))
            
            ss_res = np.sum((y - predictions) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            metrics.r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
        return metrics
    
    def predict(self, features: FeatureSet) -> ModelPrediction:
        """Make prediction."""
        if not self.is_trained:
            raise RuntimeError("Model not trained")
            
        X = self._prepare_features(features).reshape(1, -1)
        raw_prediction = float(X @ self.weights + self.bias)
        
        prediction = ModelPrediction(
            timestamp=features.timestamp,
            symbol=features.symbol,
            target=self.target,
        )
        
        if self.target == PredictionTarget.DIRECTION:
            if raw_prediction > 0.1:
                prediction.direction = "up"
                prediction.direction_confidence = min(abs(raw_prediction), 1.0)
            elif raw_prediction < -0.1:
                prediction.direction = "down"
                prediction.direction_confidence = min(abs(raw_prediction), 1.0)
            else:
                prediction.direction = "neutral"
                prediction.direction_confidence = 1.0 - abs(raw_prediction)
        else:
            prediction.predicted_return = raw_prediction
            
        # Top contributing features
        feature_contributions = X[0] * self.weights
        sorted_features = sorted(
            zip(self.feature_names, feature_contributions),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        prediction.top_features = sorted_features[:5]
        
        return prediction
    
    def save(self, path: Path):
        """Save model."""
        data = {
            "weights": self.weights.tolist() if self.weights is not None else None,
            "bias": self.bias,
            "feature_importance": self.feature_importance,
            "target": self.target.value,
            "horizon_seconds": self.horizon_seconds,
            "regularization": self.regularization,
        }
        path.write_text(json.dumps(data, indent=2))
        
    def load(self, path: Path):
        """Load model."""
        data = json.loads(path.read_text())
        self.weights = np.array(data["weights"]) if data["weights"] else None
        self.bias = data["bias"]
        self.feature_importance = data["feature_importance"]
        self.target = PredictionTarget(data["target"])
        self.horizon_seconds = data["horizon_seconds"]
        self.regularization = data["regularization"]
        self.is_trained = self.weights is not None


class GradientBoostFlowModel(FlowModel):
    """
    Gradient boosting model for order flow prediction.
    Handles non-linear relationships and feature interactions.
    """
    
    def __init__(
        self,
        target: PredictionTarget = PredictionTarget.DIRECTION,
        horizon_seconds: int = 5,
        n_estimators: int = 100,
        max_depth: int = 5,
        learning_rate: float = 0.1,
    ):
        super().__init__(ModelType.GRADIENT_BOOST, target, horizon_seconds)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.model = None
        self.feature_importance: Dict[str, float] = {}
        
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
    ) -> ModelMetrics:
        """Train gradient boosting model."""
        try:
            from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
            from sklearn.model_selection import train_test_split
        except ImportError:
            logger.error("scikit-learn not installed")
            return ModelMetrics()
            
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, shuffle=False
        )
        
        if self.target == PredictionTarget.DIRECTION:
            # Convert to classes
            y_train_cls = np.sign(y_train).astype(int) + 1  # 0, 1, 2
            y_val_cls = np.sign(y_val).astype(int) + 1
            
            self.model = GradientBoostingClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                random_state=42,
            )
            self.model.fit(X_train, y_train_cls)
            
            # Metrics
            predictions = self.model.predict(X_val)
            metrics = ModelMetrics(
                accuracy=np.mean(predictions == y_val_cls),
                num_samples=len(y_val),
            )
            metrics.hit_rate = metrics.accuracy
            
        else:
            self.model = GradientBoostingRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                random_state=42,
            )
            self.model.fit(X_train, y_train)
            
            predictions = self.model.predict(X_val)
            metrics = ModelMetrics(
                mse=np.mean((predictions - y_val) ** 2),
                mae=np.mean(np.abs(predictions - y_val)),
                num_samples=len(y_val),
            )
            
        # Feature importance
        for i, name in enumerate(self.feature_names):
            self.feature_importance[name] = float(self.model.feature_importances_[i])
            
        self.is_trained = True
        return metrics
    
    def predict(self, features: FeatureSet) -> ModelPrediction:
        """Make prediction."""
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model not trained")
            
        X = self._prepare_features(features).reshape(1, -1)
        
        prediction = ModelPrediction(
            timestamp=features.timestamp,
            symbol=features.symbol,
            target=self.target,
        )
        
        if self.target == PredictionTarget.DIRECTION:
            proba = self.model.predict_proba(X)[0]
            cls = np.argmax(proba)
            
            if cls == 0:
                prediction.direction = "down"
            elif cls == 2:
                prediction.direction = "up"
            else:
                prediction.direction = "neutral"
                
            prediction.direction_confidence = float(proba[cls])
            
        else:
            prediction.predicted_return = float(self.model.predict(X)[0])
            
        # Top features
        sorted_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        prediction.top_features = sorted_features[:5]
        
        return prediction
    
    def save(self, path: Path):
        """Save model."""
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'feature_importance': self.feature_importance,
                'target': self.target.value,
                'horizon_seconds': self.horizon_seconds,
            }, f)
            
    def load(self, path: Path):
        """Load model."""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.feature_importance = data['feature_importance']
            self.target = PredictionTarget(data['target'])
            self.horizon_seconds = data['horizon_seconds']
            self.is_trained = True


class NeuralNetFlowModel(FlowModel):
    """
    Simple neural network for order flow prediction.
    Can capture complex non-linear patterns.
    """
    
    def __init__(
        self,
        target: PredictionTarget = PredictionTarget.DIRECTION,
        horizon_seconds: int = 5,
        hidden_layers: List[int] = None,
        dropout: float = 0.2,
        learning_rate: float = 0.001,
    ):
        super().__init__(ModelType.NEURAL_NET, target, horizon_seconds)
        self.hidden_layers = hidden_layers or [64, 32]
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.model = None
        
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
        epochs: int = 100,
        batch_size: int = 32,
    ) -> ModelMetrics:
        """Train neural network."""
        try:
            import torch
            import torch.nn as nn
            from torch.utils.data import DataLoader, TensorDataset
        except ImportError:
            logger.error("PyTorch not installed")
            return ModelMetrics()
            
        # Build model
        layers = []
        input_size = X.shape[1]
        
        for hidden_size in self.hidden_layers:
            layers.extend([
                nn.Linear(input_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(self.dropout),
            ])
            input_size = hidden_size
            
        if self.target == PredictionTarget.DIRECTION:
            layers.append(nn.Linear(input_size, 3))  # 3 classes
        else:
            layers.append(nn.Linear(input_size, 1))
            
        self.model = nn.Sequential(*layers)
        
        # Prepare data
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        X_train_t = torch.FloatTensor(X_train)
        X_val_t = torch.FloatTensor(X_val)
        
        if self.target == PredictionTarget.DIRECTION:
            y_train_t = torch.LongTensor(np.sign(y_train).astype(int) + 1)
            y_val_t = torch.LongTensor(np.sign(y_val).astype(int) + 1)
            criterion = nn.CrossEntropyLoss()
        else:
            y_train_t = torch.FloatTensor(y_train).unsqueeze(1)
            y_val_t = torch.FloatTensor(y_val).unsqueeze(1)
            criterion = nn.MSELoss()
            
        train_dataset = TensorDataset(X_train_t, y_train_t)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        
        # Training loop
        for epoch in range(epochs):
            self.model.train()
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                
        # Evaluation
        self.model.eval()
        with torch.no_grad():
            val_outputs = self.model(X_val_t)
            
            if self.target == PredictionTarget.DIRECTION:
                predictions = torch.argmax(val_outputs, dim=1).numpy()
                metrics = ModelMetrics(
                    accuracy=np.mean(predictions == y_val_t.numpy()),
                    num_samples=len(y_val),
                )
                metrics.hit_rate = metrics.accuracy
            else:
                predictions = val_outputs.numpy().flatten()
                metrics = ModelMetrics(
                    mse=np.mean((predictions - y_val) ** 2),
                    mae=np.mean(np.abs(predictions - y_val)),
                    num_samples=len(y_val),
                )
                
        self.is_trained = True
        return metrics
    
    def predict(self, features: FeatureSet) -> ModelPrediction:
        """Make prediction."""
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model not trained")
            
        try:
            import torch
        except ImportError:
            raise RuntimeError("PyTorch not installed")
            
        X = self._prepare_features(features).reshape(1, -1)
        X_t = torch.FloatTensor(X)
        
        self.model.eval()
        with torch.no_grad():
            output = self.model(X_t)
            
        prediction = ModelPrediction(
            timestamp=features.timestamp,
            symbol=features.symbol,
            target=self.target,
        )
        
        if self.target == PredictionTarget.DIRECTION:
            proba = torch.softmax(output, dim=1).numpy()[0]
            cls = np.argmax(proba)
            
            if cls == 0:
                prediction.direction = "down"
            elif cls == 2:
                prediction.direction = "up"
            else:
                prediction.direction = "neutral"
                
            prediction.direction_confidence = float(proba[cls])
        else:
            prediction.predicted_return = float(output.numpy()[0, 0])
            
        return prediction
    
    def save(self, path: Path):
        """Save model."""
        try:
            import torch
            torch.save({
                'model_state': self.model.state_dict() if self.model else None,
                'hidden_layers': self.hidden_layers,
                'target': self.target.value,
                'horizon_seconds': self.horizon_seconds,
            }, path)
        except ImportError:
            logger.error("PyTorch not installed")
            
    def load(self, path: Path):
        """Load model."""
        try:
            import torch
            import torch.nn as nn
            
            data = torch.load(path)
            self.hidden_layers = data['hidden_layers']
            self.target = PredictionTarget(data['target'])
            self.horizon_seconds = data['horizon_seconds']
            
            # Rebuild model architecture
            # (would need input size stored or inferred)
            if data['model_state']:
                self.is_trained = True
        except ImportError:
            logger.error("PyTorch not installed")


class OrderFlowPredictor:
    """
    High-level predictor that manages multiple models.
    """
    
    def __init__(self):
        self.models: Dict[str, FlowModel] = {}
        self.active_model: Optional[str] = None
        
    def add_model(self, name: str, model: FlowModel):
        """Add a model."""
        self.models[name] = model
        if self.active_model is None:
            self.active_model = name
            
    def set_active_model(self, name: str):
        """Set the active model for predictions."""
        if name not in self.models:
            raise ValueError(f"Model {name} not found")
        self.active_model = name
        
    def train_all(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
    ) -> Dict[str, ModelMetrics]:
        """Train all models and return metrics."""
        results = {}
        for name, model in self.models.items():
            logger.info(f"Training {name}...")
            metrics = model.train(X, y, validation_split)
            results[name] = metrics
            logger.info(f"{name}: accuracy={metrics.accuracy:.3f}, mse={metrics.mse:.6f}")
        return results
    
    def predict(self, features: FeatureSet) -> ModelPrediction:
        """Make prediction using active model."""
        if not self.active_model:
            raise RuntimeError("No active model set")
        return self.models[self.active_model].predict(features)
    
    def predict_ensemble(
        self,
        features: FeatureSet,
        weights: Optional[Dict[str, float]] = None,
    ) -> ModelPrediction:
        """
        Make ensemble prediction from all trained models.
        """
        predictions = {}
        for name, model in self.models.items():
            if model.is_trained:
                predictions[name] = model.predict(features)
                
        if not predictions:
            raise RuntimeError("No trained models")
            
        # Default equal weights
        if weights is None:
            weights = {name: 1.0 / len(predictions) for name in predictions}
            
        # Combine predictions
        if all(p.direction for p in predictions.values()):
            # Classification: weighted voting
            direction_scores = {"up": 0.0, "down": 0.0, "neutral": 0.0}
            total_weight = 0.0
            
            for name, pred in predictions.items():
                w = weights.get(name, 0)
                direction_scores[pred.direction] += w * pred.direction_confidence
                total_weight += w
                
            # Normalize
            for d in direction_scores:
                direction_scores[d] /= max(total_weight, 1e-6)
                
            best_direction = max(direction_scores, key=direction_scores.get)
            
            return ModelPrediction(
                timestamp=features.timestamp,
                symbol=features.symbol,
                target=PredictionTarget.DIRECTION,
                direction=best_direction,
                direction_confidence=direction_scores[best_direction],
            )
            
        else:
            # Regression: weighted average
            total_return = 0.0
            total_weight = 0.0
            
            for name, pred in predictions.items():
                w = weights.get(name, 0)
                total_return += w * pred.predicted_return
                total_weight += w
                
            return ModelPrediction(
                timestamp=features.timestamp,
                symbol=features.symbol,
                target=PredictionTarget.RETURN,
                predicted_return=total_return / max(total_weight, 1e-6),
            )
    
    def get_best_model(self, metric: str = "accuracy") -> Tuple[str, FlowModel]:
        """Get the best performing model by metric."""
        # Would need to track metrics from training
        # For now, return first trained model
        for name, model in self.models.items():
            if model.is_trained:
                return name, model
        raise RuntimeError("No trained models")
