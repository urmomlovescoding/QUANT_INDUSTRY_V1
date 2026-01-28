"""
QUANT_INDUSTRY_V1 Deep Learning Ensemble

Combines TFT, WaveNet, and AttentionFlow networks for robust predictions.

Features:
- Weighted ensemble with dynamic weight adjustment
- Uncertainty-aware prediction fusion
- Disagreement detection
- Multi-model calibration
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field

from brain.deep_learning.temporal_fusion import TemporalFusionTransformer, TFTConfig
from brain.deep_learning.wavenet import WaveNetModel, WaveNetConfig
from brain.deep_learning.attention_flow import AttentionFlowNetwork, AttentionFlowConfig

logger = logging.getLogger(__name__)


@dataclass
class EnsembleConfig:
    """Deep Learning Ensemble configuration."""
    # Model configs
    tft_config: TFTConfig = field(default_factory=TFTConfig)
    wavenet_config: WaveNetConfig = field(default_factory=WaveNetConfig)
    attention_flow_config: AttentionFlowConfig = field(default_factory=AttentionFlowConfig)

    # Ensemble settings
    initial_weights: Dict[str, float] = field(default_factory=lambda: {
        'tft': 0.4,
        'wavenet': 0.35,
        'attention_flow': 0.25,
    })
    temperature: float = 1.5  # Softmax temperature for ensemble
    min_confidence: float = 0.5
    disagreement_threshold: float = 0.3


class DeepLearningEnsemble:
    """
    Ensemble of deep learning models for financial prediction.

    Combines:
    1. Temporal Fusion Transformer - Multi-horizon with interpretability
    2. WaveNet - Multi-scale temporal patterns
    3. Attention Flow Network - Order flow analysis
    """

    def __init__(self, config: EnsembleConfig = None):
        self.config = config or EnsembleConfig()

        # Initialize models
        self.tft = TemporalFusionTransformer(self.config.tft_config)
        self.wavenet = WaveNetModel(self.config.wavenet_config)
        self.attention_flow = AttentionFlowNetwork(self.config.attention_flow_config)

        # Ensemble weights
        self.weights = self.config.initial_weights.copy()

        # Performance tracking
        self.model_performance = {
            'tft': {'correct': 0, 'total': 0, 'returns': []},
            'wavenet': {'correct': 0, 'total': 0, 'returns': []},
            'attention_flow': {'correct': 0, 'total': 0, 'returns': []},
            'ensemble': {'correct': 0, 'total': 0, 'returns': []},
        }

        self.training = False

    def predict(
        self,
        features: np.ndarray,
        price_data: np.ndarray = None,
        volume_data: np.ndarray = None,
    ) -> Dict[str, Any]:
        """
        Ensemble prediction.

        Args:
            features: Main feature array [batch, seq, features]
            price_data: OHLC data for attention flow [batch, seq, 4]
            volume_data: Volume data [batch, seq]

        Returns:
            Dictionary with ensemble prediction and analysis
        """
        predictions = {}

        # TFT prediction
        try:
            tft_output = self.tft.forward(features)
            # TFT returns quantile predictions, use median
            tft_pred = tft_output['predictions'][:, -1, 1] if tft_output['predictions'].ndim > 2 else tft_output['predictions']
            # Convert to class probabilities (simplified)
            tft_probs = self._regression_to_probs(tft_pred)
            predictions['tft'] = {
                'probabilities': tft_probs,
                'prediction': np.argmax(tft_probs, axis=-1),
                'confidence': np.max(tft_probs, axis=-1),
                'raw': tft_pred,
            }
        except Exception as e:
            logger.warning(f"TFT prediction failed: {e}")
            predictions['tft'] = None

        # WaveNet prediction
        try:
            wavenet_output = self.wavenet.forward(features)
            predictions['wavenet'] = {
                'probabilities': wavenet_output['final_probabilities'],
                'prediction': wavenet_output['prediction'],
                'confidence': wavenet_output['confidence'],
            }
        except Exception as e:
            logger.warning(f"WaveNet prediction failed: {e}")
            predictions['wavenet'] = None

        # Attention Flow prediction
        try:
            if price_data is not None and volume_data is not None:
                af_output = self.attention_flow.analyze_flow(price_data, volume_data)
            else:
                # Use features directly
                n_price = self.config.attention_flow_config.price_features
                n_vol = self.config.attention_flow_config.volume_features
                price_feat = features[:, :, :n_price]
                vol_feat = features[:, :, n_price:n_price+n_vol]
                af_output = self.attention_flow.forward(price_feat, vol_feat)

            predictions['attention_flow'] = {
                'probabilities': af_output['probabilities'],
                'prediction': af_output['prediction'],
                'confidence': af_output['confidence'],
            }
        except Exception as e:
            logger.warning(f"AttentionFlow prediction failed: {e}")
            predictions['attention_flow'] = None

        # Ensemble combination
        ensemble_result = self._combine_predictions(predictions)

        return {
            'prediction': ensemble_result['prediction'],
            'probabilities': ensemble_result['probabilities'],
            'confidence': ensemble_result['confidence'],
            'model_predictions': predictions,
            'weights_used': self.weights.copy(),
            'disagreement': ensemble_result.get('disagreement', 0),
            'interpretability': self._get_interpretability(predictions),
        }

    def _regression_to_probs(self, pred: np.ndarray) -> np.ndarray:
        """Convert regression predictions to class probabilities."""
        # Map continuous prediction to [short, flat, long]
        if pred.ndim == 1:
            batch_size = pred.shape[0]
        else:
            batch_size = pred.shape[0]
            pred = pred.flatten()

        probs = np.zeros((batch_size, 3))

        for i in range(batch_size):
            if pred[i] > 0.5:
                probs[i] = [0.1, 0.2, 0.7]  # Long
            elif pred[i] < -0.5:
                probs[i] = [0.7, 0.2, 0.1]  # Short
            else:
                probs[i] = [0.2, 0.6, 0.2]  # Flat

            # Scale by magnitude
            strength = min(abs(pred[i]), 1.0)
            probs[i] = probs[i] * strength + np.array([0.33, 0.34, 0.33]) * (1 - strength)

        return probs

    def _combine_predictions(self, predictions: Dict[str, Any]) -> Dict[str, Any]:
        """Combine predictions from multiple models."""
        active_models = {k: v for k, v in predictions.items() if v is not None}

        if not active_models:
            # Fallback to neutral
            return {
                'prediction': np.array([1]),  # Flat
                'probabilities': np.array([[0.33, 0.34, 0.33]]),
                'confidence': np.array([0.34]),
            }

        # Collect probabilities and weights
        all_probs = []
        all_weights = []

        for model_name, pred in active_models.items():
            probs = pred['probabilities']
            weight = self.weights.get(model_name, 0.33)
            all_probs.append(probs)
            all_weights.append(weight)

        # Stack and normalize weights
        all_probs = np.array(all_probs)  # [n_models, batch, n_classes]
        all_weights = np.array(all_weights)
        all_weights = all_weights / np.sum(all_weights)

        # Weighted average with temperature scaling
        weighted_probs = np.tensordot(all_weights, all_probs, axes=1)

        # Temperature scaling
        temp = self.config.temperature
        scaled_probs = np.exp(np.log(weighted_probs + 1e-10) / temp)
        scaled_probs = scaled_probs / np.sum(scaled_probs, axis=-1, keepdims=True)

        # Calculate disagreement
        disagreement = self._calculate_disagreement(all_probs)

        # Reduce confidence if models disagree
        confidence = np.max(scaled_probs, axis=-1)
        confidence = confidence * (1 - disagreement * 0.5)

        return {
            'prediction': np.argmax(scaled_probs, axis=-1),
            'probabilities': scaled_probs,
            'confidence': confidence,
            'disagreement': disagreement,
        }

    def _calculate_disagreement(self, probs: np.ndarray) -> float:
        """Calculate disagreement between models."""
        n_models = probs.shape[0]
        if n_models < 2:
            return 0.0

        # Average pairwise KL divergence
        total_div = 0
        count = 0

        for i in range(n_models):
            for j in range(i + 1, n_models):
                kl = np.sum(probs[i] * np.log((probs[i] + 1e-10) / (probs[j] + 1e-10)), axis=-1)
                total_div += np.mean(np.abs(kl))
                count += 1

        return min(total_div / count if count > 0 else 0, 1.0)

    def _get_interpretability(self, predictions: Dict[str, Any]) -> Dict[str, Any]:
        """Get interpretability information from models."""
        interp = {}

        if predictions.get('tft') is not None:
            interp['tft_variable_importance'] = self.tft.get_feature_importance()

        if hasattr(self.attention_flow, 'attention_weights'):
            interp['attention_analysis'] = self.attention_flow.get_attention_analysis()

        if hasattr(self.wavenet, 'config'):
            interp['wavenet_receptive_field'] = self.wavenet.config.receptive_field

        return interp

    def update_weights(self, actual_direction: int) -> None:
        """Update ensemble weights based on actual outcome."""
        # Track performance for each model
        for model_name in ['tft', 'wavenet', 'attention_flow']:
            if hasattr(self, f'_last_{model_name}_pred'):
                pred = getattr(self, f'_last_{model_name}_pred')
                correct = (pred == actual_direction)
                self.model_performance[model_name]['correct'] += int(correct)
                self.model_performance[model_name]['total'] += 1

        # Recalculate weights based on accuracy
        total_correct = sum(m['correct'] for m in self.model_performance.values() if m['total'] > 0)

        if total_correct > 0:
            for model_name in ['tft', 'wavenet', 'attention_flow']:
                perf = self.model_performance[model_name]
                if perf['total'] > 10:  # Minimum samples for weight update
                    accuracy = perf['correct'] / perf['total']
                    # Smooth weight update
                    old_weight = self.weights[model_name]
                    new_weight = 0.9 * old_weight + 0.1 * accuracy
                    self.weights[model_name] = max(0.1, min(0.6, new_weight))

            # Normalize weights
            total = sum(self.weights.values())
            self.weights = {k: v / total for k, v in self.weights.items()}

    def get_model_stats(self) -> Dict[str, Any]:
        """Get performance statistics for all models."""
        stats = {}
        for model_name, perf in self.model_performance.items():
            if perf['total'] > 0:
                stats[model_name] = {
                    'accuracy': perf['correct'] / perf['total'],
                    'total_predictions': perf['total'],
                    'current_weight': self.weights.get(model_name, 0),
                }
        return stats

    def train_mode(self):
        """Set all models to training mode."""
        self.training = True
        self.tft.train()
        self.wavenet.train_mode()
        self.attention_flow.train_mode()

    def eval_mode(self):
        """Set all models to evaluation mode."""
        self.training = False
        self.tft.eval()
        self.wavenet.eval_mode()
        self.attention_flow.eval_mode()

    def save(self, path: str) -> None:
        """Save ensemble."""
        import pickle
        state = {
            'config': self.config,
            'weights': self.weights,
            'performance': self.model_performance,
        }
        with open(path, 'wb') as f:
            pickle.dump(state, f)

        # Save individual models
        self.tft.save(path.replace('.pkl', '_tft.pkl'))
        self.wavenet.save(path.replace('.pkl', '_wavenet.pkl'))
        self.attention_flow.save(path.replace('.pkl', '_attnflow.pkl'))

        logger.info(f"Ensemble saved to {path}")

    def load(self, path: str) -> None:
        """Load ensemble."""
        import pickle
        with open(path, 'rb') as f:
            state = pickle.load(f)

        self.config = state['config']
        self.weights = state['weights']
        self.model_performance = state['performance']

        # Load individual models
        self.tft.load(path.replace('.pkl', '_tft.pkl'))
        self.wavenet.load(path.replace('.pkl', '_wavenet.pkl'))
        self.attention_flow.load(path.replace('.pkl', '_attnflow.pkl'))

        logger.info(f"Ensemble loaded from {path}")


__all__ = ['DeepLearningEnsemble', 'EnsembleConfig']
