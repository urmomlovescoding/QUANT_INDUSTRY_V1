"""
QUANT INDUSTRY - Model Confidence Calibration
==============================================
Track and calibrate model prediction confidence.

A model that says "80% confident" should be right ~80% of the time.
If not, the model is miscalibrated and you can't trust its confidence scores.

This module:
1. Tracks prediction vs outcome history
2. Calculates calibration curves
3. Adjusts raw model confidence to calibrated confidence
4. Detects confidence degradation over time

Without this, you're flying blind.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class PredictionRecord:
    """Single prediction record for calibration tracking"""
    timestamp: datetime
    symbol: str
    predicted_direction: int     # 1 = up, -1 = down, 0 = flat
    confidence: float            # Model's stated confidence [0, 1]
    actual_direction: Optional[int] = None  # What actually happened
    actual_return: Optional[float] = None   # Actual return
    was_correct: Optional[bool] = None


@dataclass
class CalibrationBin:
    """Statistics for one confidence bin"""
    bin_start: float
    bin_end: float
    n_predictions: int
    n_correct: int
    accuracy: float
    mean_confidence: float
    
    @property
    def calibration_error(self) -> float:
        """Gap between stated confidence and actual accuracy"""
        return self.mean_confidence - self.accuracy


@dataclass
class CalibrationReport:
    """Full calibration analysis report"""
    timestamp: datetime
    n_predictions: int
    overall_accuracy: float
    bins: List[CalibrationBin]
    
    # Calibration metrics
    expected_calibration_error: float  # ECE
    maximum_calibration_error: float   # MCE
    brier_score: float                 # Mean squared error
    
    # Reliability
    reliability_slope: float    # Should be ~1 for calibrated model
    reliability_intercept: float  # Should be ~0
    
    # Confidence quality
    confidence_auc: float       # AUC of reliability diagram
    overconfidence_ratio: float # How often confidence > accuracy
    
    def summary(self) -> str:
        status = "[OK] CALIBRATED" if self.expected_calibration_error < 0.1 else "[WARN]️ MISCALIBRATED"
        
        return f"""
Model Calibration Report
========================
{status}

Overall Accuracy: {self.overall_accuracy:.1%}
Predictions: {self.n_predictions:,}

Calibration Metrics:
  ECE (Expected Calibration Error): {self.expected_calibration_error:.3f}
  MCE (Maximum Calibration Error): {self.maximum_calibration_error:.3f}
  Brier Score: {self.brier_score:.4f}

Reliability:
  Slope: {self.reliability_slope:.3f} (ideal: 1.0)
  Intercept: {self.reliability_intercept:.3f} (ideal: 0.0)
  
Confidence Quality:
  AUC: {self.confidence_auc:.3f}
  Overconfidence Ratio: {self.overconfidence_ratio:.1%}

Bin Analysis:
"""
        + "\n".join([
            f"  [{b.bin_start:.0%}-{b.bin_end:.0%}]: "
            f"Acc={b.accuracy:.1%}, Conf={b.mean_confidence:.1%}, "
            f"Gap={b.calibration_error:+.1%}, n={b.n_predictions}"
            for b in self.bins
        ])


class ConfidenceCalibrator:
    """
    Track and calibrate model confidence scores.
    
    Usage:
    ------
    >>> calibrator = ConfidenceCalibrator()
    >>> 
    >>> # Record predictions as they happen
    >>> calibrator.record_prediction(
    ...     symbol="SPY",
    ...     predicted_direction=1,  # Up
    ...     confidence=0.75
    ... )
    >>>
    >>> # Later, record outcome
    >>> calibrator.record_outcome(
    ...     symbol="SPY",
    ...     actual_direction=1,
    ...     actual_return=0.02
    ... )
    >>>
    >>> # Get calibration report
    >>> report = calibrator.get_calibration_report()
    >>> print(report.summary())
    >>>
    >>> # Calibrate new predictions
    >>> raw_confidence = 0.80
    >>> calibrated = calibrator.calibrate(raw_confidence)
    """
    
    def __init__(
        self,
        n_bins: int = 10,
        history_window: int = 1000,
        min_samples_per_bin: int = 30,
        recalibrate_frequency: int = 100
    ):
        """
        Initialize calibrator.
        
        Args:
            n_bins: Number of confidence bins for calibration curve
            history_window: Number of predictions to track
            min_samples_per_bin: Minimum samples for reliable bin statistics
            recalibrate_frequency: Recalibrate every N predictions
        """
        self.n_bins = n_bins
        self.history_window = history_window
        self.min_samples_per_bin = min_samples_per_bin
        self.recalibrate_frequency = recalibrate_frequency
        
        # Prediction history
        self.predictions: deque = deque(maxlen=history_window)
        self.pending_predictions: Dict[str, PredictionRecord] = {}
        
        # Calibration mapping (raw -> calibrated)
        self.calibration_curve: Optional[np.ndarray] = None
        self._predictions_since_recalibration = 0
        
        # Tracking
        self.n_total_predictions = 0
        self.n_correct_predictions = 0
        
        logger.info(f"ConfidenceCalibrator initialized: {n_bins} bins, {history_window} history")
    
    def record_prediction(
        self,
        symbol: str,
        predicted_direction: int,
        confidence: float,
        timestamp: datetime = None
    ) -> str:
        """
        Record a new prediction.
        
        Args:
            symbol: Trading symbol
            predicted_direction: 1 (up), -1 (down), 0 (flat)
            confidence: Model's confidence [0, 1]
            timestamp: Prediction time (default: now)
            
        Returns:
            Prediction ID for tracking
        """
        timestamp = timestamp or datetime.now()
        
        record = PredictionRecord(
            timestamp=timestamp,
            symbol=symbol,
            predicted_direction=predicted_direction,
            confidence=confidence
        )
        
        # Generate unique ID
        pred_id = f"{symbol}_{timestamp.timestamp()}"
        self.pending_predictions[pred_id] = record
        
        self.n_total_predictions += 1
        self._predictions_since_recalibration += 1
        
        return pred_id
    
    def record_outcome(
        self,
        pred_id: str = None,
        symbol: str = None,
        actual_direction: int = None,
        actual_return: float = None
    ):
        """
        Record the outcome of a prediction.
        
        Args:
            pred_id: Prediction ID from record_prediction
            symbol: Symbol (used to find latest pending prediction)
            actual_direction: What actually happened
            actual_return: Actual return
        """
        # Find the prediction
        record = None
        
        if pred_id and pred_id in self.pending_predictions:
            record = self.pending_predictions.pop(pred_id)
        elif symbol:
            # Find most recent pending prediction for symbol
            for pid, rec in list(self.pending_predictions.items()):
                if rec.symbol == symbol:
                    record = self.pending_predictions.pop(pid)
                    break
        
        if record is None:
            logger.warning(f"No pending prediction found for {pred_id or symbol}")
            return
        
        # Update record
        record.actual_direction = actual_direction
        record.actual_return = actual_return
        
        # Determine if correct
        if record.predicted_direction != 0 and actual_direction is not None:
            record.was_correct = (record.predicted_direction == actual_direction)
            if record.was_correct:
                self.n_correct_predictions += 1
        
        # Add to history
        self.predictions.append(record)
        
        # Recalibrate if needed
        if self._predictions_since_recalibration >= self.recalibrate_frequency:
            self._recalibrate()
    
    def _recalibrate(self):
        """Update calibration curve from recent history"""
        completed = [p for p in self.predictions if p.was_correct is not None]
        
        if len(completed) < self.min_samples_per_bin * self.n_bins:
            logger.debug("Insufficient data for recalibration")
            return
        
        # Calculate calibration curve
        confidences = np.array([p.confidence for p in completed])
        correct = np.array([1 if p.was_correct else 0 for p in completed])
        
        # Bin edges
        bin_edges = np.linspace(0, 1, self.n_bins + 1)
        
        # Calculate accuracy per bin
        calibration = np.zeros(self.n_bins)
        for i in range(self.n_bins):
            mask = (confidences >= bin_edges[i]) & (confidences < bin_edges[i + 1])
            if mask.sum() >= self.min_samples_per_bin:
                calibration[i] = correct[mask].mean()
            else:
                # Interpolate from neighbors or use diagonal
                calibration[i] = (bin_edges[i] + bin_edges[i + 1]) / 2
        
        self.calibration_curve = calibration
        self._predictions_since_recalibration = 0
        
        logger.info("Calibration curve updated")
    
    def calibrate(self, raw_confidence: float) -> float:
        """
        Convert raw model confidence to calibrated confidence.
        
        Args:
            raw_confidence: Model's stated confidence [0, 1]
            
        Returns:
            Calibrated confidence [0, 1]
        """
        if self.calibration_curve is None:
            return raw_confidence
        
        # Find bin and return calibrated value
        bin_idx = int(raw_confidence * self.n_bins)
        bin_idx = min(bin_idx, self.n_bins - 1)
        
        return self.calibration_curve[bin_idx]
    
    def get_calibration_report(self) -> CalibrationReport:
        """Generate full calibration report"""
        completed = [p for p in self.predictions if p.was_correct is not None]
        
        if not completed:
            return CalibrationReport(
                timestamp=datetime.now(),
                n_predictions=0,
                overall_accuracy=0.0,
                bins=[],
                expected_calibration_error=1.0,
                maximum_calibration_error=1.0,
                brier_score=1.0,
                reliability_slope=0.0,
                reliability_intercept=0.0,
                confidence_auc=0.5,
                overconfidence_ratio=1.0
            )
        
        confidences = np.array([p.confidence for p in completed])
        correct = np.array([1.0 if p.was_correct else 0.0 for p in completed])
        
        # Calculate bins
        bin_edges = np.linspace(0, 1, self.n_bins + 1)
        bins = []
        
        for i in range(self.n_bins):
            mask = (confidences >= bin_edges[i]) & (confidences < bin_edges[i + 1])
            n = mask.sum()
            
            if n > 0:
                acc = correct[mask].mean()
                mean_conf = confidences[mask].mean()
            else:
                acc = 0.0
                mean_conf = (bin_edges[i] + bin_edges[i + 1]) / 2
            
            bins.append(CalibrationBin(
                bin_start=bin_edges[i],
                bin_end=bin_edges[i + 1],
                n_predictions=int(n),
                n_correct=int(correct[mask].sum()) if n > 0 else 0,
                accuracy=acc,
                mean_confidence=mean_conf
            ))
        
        # Expected Calibration Error (ECE)
        ece = 0.0
        for b in bins:
            if b.n_predictions > 0:
                ece += (b.n_predictions / len(completed)) * abs(b.calibration_error)
        
        # Maximum Calibration Error (MCE)
        mce = max(abs(b.calibration_error) for b in bins) if bins else 0.0
        
        # Brier Score
        brier = np.mean((confidences - correct) ** 2)
        
        # Reliability slope/intercept (linear regression)
        bin_confs = np.array([b.mean_confidence for b in bins if b.n_predictions >= self.min_samples_per_bin])
        bin_accs = np.array([b.accuracy for b in bins if b.n_predictions >= self.min_samples_per_bin])
        
        if len(bin_confs) >= 3:
            slope, intercept, _, _, _ = stats.linregress(bin_confs, bin_accs)
        else:
            slope, intercept = 1.0, 0.0
        
        # AUC of reliability diagram
        try:
            auc = np.trapz(bin_accs, bin_confs) if len(bin_confs) > 1 else 0.5
        except:
            auc = 0.5
        
        # Overconfidence ratio
        overconf = np.mean(confidences > correct) if len(confidences) > 0 else 0.5
        
        return CalibrationReport(
            timestamp=datetime.now(),
            n_predictions=len(completed),
            overall_accuracy=correct.mean(),
            bins=bins,
            expected_calibration_error=ece,
            maximum_calibration_error=mce,
            brier_score=brier,
            reliability_slope=slope,
            reliability_intercept=intercept,
            confidence_auc=auc,
            overconfidence_ratio=overconf
        )
    
    def should_trade(
        self,
        raw_confidence: float,
        min_calibrated_confidence: float = 0.55
    ) -> Tuple[bool, float]:
        """
        Determine if a signal should be traded based on calibrated confidence.
        
        Args:
            raw_confidence: Model's stated confidence
            min_calibrated_confidence: Minimum threshold for trading
            
        Returns:
            Tuple of (should_trade, calibrated_confidence)
        """
        calibrated = self.calibrate(raw_confidence)
        should_trade = calibrated >= min_calibrated_confidence
        
        return should_trade, calibrated


# ============== TEMPERATURE SCALING ==============

class TemperatureScaler:
    """
    Temperature scaling for neural network calibration.
    
    A simple but effective post-hoc calibration method.
    Scales logits by a learned temperature parameter.
    """
    
    def __init__(self, temperature: float = 1.0):
        """
        Initialize temperature scaler.
        
        Args:
            temperature: Initial temperature (>1 = more uncertain, <1 = more confident)
        """
        self.temperature = temperature
        self._calibration_data: List[Tuple[float, bool]] = []
    
    def add_calibration_sample(self, logit: float, was_correct: bool):
        """Add sample for temperature optimization"""
        self._calibration_data.append((logit, was_correct))
    
    def optimize_temperature(self):
        """Find optimal temperature using NLL minimization"""
        if len(self._calibration_data) < 100:
            return
        
        logits = np.array([x[0] for x in self._calibration_data])
        labels = np.array([1.0 if x[1] else 0.0 for x in self._calibration_data])
        
        # Grid search for best temperature
        best_nll = float('inf')
        best_temp = 1.0
        
        for temp in np.linspace(0.1, 5.0, 50):
            scaled_probs = 1 / (1 + np.exp(-logits / temp))
            nll = -np.mean(labels * np.log(scaled_probs + 1e-10) + 
                          (1 - labels) * np.log(1 - scaled_probs + 1e-10))
            
            if nll < best_nll:
                best_nll = nll
                best_temp = temp
        
        self.temperature = best_temp
        logger.info(f"Optimized temperature: {self.temperature:.3f}")
    
    def scale(self, logit: float) -> float:
        """Apply temperature scaling to logit"""
        scaled_logit = logit / self.temperature
        return 1 / (1 + np.exp(-scaled_logit))


# ============== SINGLETON ==============

_calibrator: Optional[ConfidenceCalibrator] = None


def get_confidence_calibrator() -> ConfidenceCalibrator:
    """Get or create singleton calibrator"""
    global _calibrator
    
    if _calibrator is None:
        _calibrator = ConfidenceCalibrator()
    
    return _calibrator
