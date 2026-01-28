"""
Explainable AI Module
QUANT_INDUSTRY_V1

Industry Problem: ML models are black boxes. Regulators and compliance 
want to know WHY a model made a decision. "The AI said so" doesn't fly.

Our Solution:
- SHAP (SHapley Additive exPlanations) for feature importance
- Local explanations (why THIS prediction?)
- Global explanations (what does the model generally do?)
- Feature contribution tracking over time
- Compliance-ready reports
- Model behavior drift detection
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import json
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Optional SHAP import
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("shap not installed. Run: pip install shap")


class ExplanationType(Enum):
    """Types of model explanations."""
    LOCAL = "local"       # Single prediction
    GLOBAL = "global"     # Overall model behavior
    TEMPORAL = "temporal" # Changes over time
    COUNTERFACTUAL = "counterfactual"  # "What if" scenarios


@dataclass
class FeatureContribution:
    """Contribution of a single feature to a prediction."""
    feature_name: str
    feature_value: Any
    contribution: float  # SHAP value
    contribution_pct: float  # Percentage of total
    direction: str  # "positive" or "negative"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'feature': self.feature_name,
            'value': self.feature_value,
            'contribution': self.contribution,
            'contribution_pct': self.contribution_pct,
            'direction': self.direction
        }


@dataclass
class LocalExplanation:
    """Explanation for a single prediction."""
    prediction_id: str
    timestamp: datetime
    model_name: str
    
    # Prediction
    predicted_value: float
    predicted_class: Optional[str] = None
    confidence: float = 1.0
    
    # Base value (average prediction)
    base_value: float = 0.0
    
    # Feature contributions
    contributions: List[FeatureContribution] = field(default_factory=list)
    
    # Summary
    top_positive_features: List[str] = field(default_factory=list)
    top_negative_features: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        lines = [
            f"Prediction Explanation ({self.model_name})",
            f"=" * 50,
            f"Predicted: {self.predicted_value:.4f} (base: {self.base_value:.4f})",
            f"",
            f"Top factors pushing UP:"
        ]
        
        for feat in self.top_positive_features[:5]:
            contrib = next((c for c in self.contributions if c.feature_name == feat), None)
            if contrib:
                lines.append(f"  + {feat}: {contrib.contribution:+.4f} (value: {contrib.feature_value})")
                
        lines.append(f"")
        lines.append(f"Top factors pushing DOWN:")
        
        for feat in self.top_negative_features[:5]:
            contrib = next((c for c in self.contributions if c.feature_name == feat), None)
            if contrib:
                lines.append(f"  - {feat}: {contrib.contribution:+.4f} (value: {contrib.feature_value})")
                
        return "\n".join(lines)
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'prediction_id': self.prediction_id,
            'timestamp': self.timestamp.isoformat(),
            'model_name': self.model_name,
            'predicted_value': self.predicted_value,
            'predicted_class': self.predicted_class,
            'confidence': self.confidence,
            'base_value': self.base_value,
            'contributions': [c.to_dict() for c in self.contributions],
            'top_positive_features': self.top_positive_features,
            'top_negative_features': self.top_negative_features
        }


@dataclass
class GlobalExplanation:
    """Global explanation of model behavior."""
    model_name: str
    timestamp: datetime
    
    # Feature importance (mean absolute SHAP)
    feature_importance: Dict[str, float] = field(default_factory=dict)
    
    # Feature interactions
    top_interactions: List[Tuple[str, str, float]] = field(default_factory=list)
    
    # Summary statistics
    n_samples_analyzed: int = 0
    model_type: str = ""
    
    def __str__(self) -> str:
        lines = [
            f"Global Model Explanation ({self.model_name})",
            f"=" * 50,
            f"Based on {self.n_samples_analyzed} samples",
            f"",
            f"Feature Importance (mean |SHAP|):"
        ]
        
        sorted_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for feat, importance in sorted_features[:15]:
            bar = "█" * int(importance * 50 / max(self.feature_importance.values()))
            lines.append(f"  {feat:30} {bar} {importance:.4f}")
            
        if self.top_interactions:
            lines.append(f"")
            lines.append(f"Top Feature Interactions:")
            for f1, f2, strength in self.top_interactions[:5]:
                lines.append(f"  {f1} × {f2}: {strength:.4f}")
                
        return "\n".join(lines)
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_name': self.model_name,
            'timestamp': self.timestamp.isoformat(),
            'feature_importance': self.feature_importance,
            'top_interactions': [
                {'feature_1': f1, 'feature_2': f2, 'strength': s}
                for f1, f2, s in self.top_interactions
            ],
            'n_samples_analyzed': self.n_samples_analyzed,
            'model_type': self.model_type
        }


@dataclass
class ComplianceReport:
    """Compliance-ready explanation report."""
    report_id: str
    generated_at: datetime
    model_name: str
    model_version: str
    
    # Summary
    executive_summary: str = ""
    
    # Global explanation
    global_explanation: Optional[GlobalExplanation] = None
    
    # Sample local explanations
    sample_explanations: List[LocalExplanation] = field(default_factory=list)
    
    # Model metadata
    training_data_description: str = ""
    feature_descriptions: Dict[str, str] = field(default_factory=dict)
    
    # Risk factors
    risk_factors: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """Generate markdown compliance report."""
        md = f"""# Model Explanation Report

**Report ID:** {self.report_id}  
**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}  
**Model:** {self.model_name} (v{self.model_version})

## Executive Summary

{self.executive_summary}

## Model Overview

### Training Data
{self.training_data_description}

### Features Used
| Feature | Description |
|---------|-------------|
"""
        for feat, desc in self.feature_descriptions.items():
            md += f"| {feat} | {desc} |\n"
            
        md += f"""
## Feature Importance

The following features have the most influence on model predictions:

"""
        if self.global_explanation:
            sorted_features = sorted(
                self.global_explanation.feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for i, (feat, imp) in enumerate(sorted_features[:10], 1):
                md += f"{i}. **{feat}**: {imp:.4f}\n"
                
        md += f"""
## Sample Predictions Explained

"""
        for i, exp in enumerate(self.sample_explanations[:5], 1):
            md += f"""### Example {i}

**Prediction:** {exp.predicted_value:.4f}  
**Base Value:** {exp.base_value:.4f}

**Key Factors:**
"""
            for contrib in sorted(exp.contributions, key=lambda x: abs(x.contribution), reverse=True)[:5]:
                direction = "↑" if contrib.contribution > 0 else "↓"
                md += f"- {contrib.feature_name}: {direction} {abs(contrib.contribution):.4f}\n"
            md += "\n"
            
        md += f"""
## Risk Factors

"""
        for risk in self.risk_factors:
            md += f"- ⚠️ {risk}\n"
            
        md += f"""
## Limitations

"""
        for lim in self.limitations:
            md += f"- {lim}\n"
            
        return md


class ModelExplainer:
    """
    Explain ML model predictions using SHAP values.
    """
    
    def __init__(
        self,
        model: Any,
        model_name: str = "model",
        feature_names: Optional[List[str]] = None,
        model_type: str = "auto"  # "tree", "linear", "kernel", "deep", "auto"
    ):
        if not SHAP_AVAILABLE:
            raise ImportError("shap not installed. Run: pip install shap")
            
        self.model = model
        self.model_name = model_name
        self.feature_names = feature_names
        self.model_type = model_type
        
        self._explainer: Optional[shap.Explainer] = None
        self._background_data: Optional[np.ndarray] = None
        
    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        sample_size: int = 100
    ):
        """
        Fit the explainer on background data.
        
        Args:
            X: Background data for SHAP
            sample_size: Number of samples to use as background
        """
        if isinstance(X, pd.DataFrame):
            self.feature_names = self.feature_names or list(X.columns)
            X = X.values
            
        # Sample background data
        if len(X) > sample_size:
            idx = np.random.choice(len(X), sample_size, replace=False)
            self._background_data = X[idx]
        else:
            self._background_data = X
            
        # Create appropriate explainer
        self._explainer = self._create_explainer()
        
        logger.info(f"Explainer fitted with {len(self._background_data)} background samples")
        
    def _create_explainer(self) -> shap.Explainer:
        """Create appropriate SHAP explainer based on model type."""
        if self.model_type == "auto":
            # Try to detect model type
            model_class = type(self.model).__name__.lower()
            
            if any(t in model_class for t in ['tree', 'forest', 'xgb', 'lgb', 'catboost']):
                self.model_type = "tree"
            elif any(t in model_class for t in ['linear', 'logistic', 'ridge', 'lasso']):
                self.model_type = "linear"
            elif any(t in model_class for t in ['neural', 'nn', 'keras', 'torch']):
                self.model_type = "deep"
            else:
                self.model_type = "kernel"
                
        if self.model_type == "tree":
            return shap.TreeExplainer(self.model)
        elif self.model_type == "linear":
            return shap.LinearExplainer(self.model, self._background_data)
        elif self.model_type == "deep":
            return shap.DeepExplainer(self.model, self._background_data)
        else:
            return shap.KernelExplainer(self.model.predict, self._background_data)
            
    def explain_prediction(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        prediction_id: Optional[str] = None
    ) -> LocalExplanation:
        """
        Explain a single prediction.
        
        Args:
            X: Single sample to explain (1D array or single-row DataFrame)
            prediction_id: Optional ID for tracking
            
        Returns:
            LocalExplanation with SHAP values
        """
        if self._explainer is None:
            raise ValueError("Explainer not fitted. Call fit() first.")
            
        # Ensure 2D
        if isinstance(X, pd.DataFrame):
            feature_values = X.iloc[0].to_dict()
            X = X.values
        else:
            feature_values = {
                self.feature_names[i] if self.feature_names else f"feature_{i}": X[i]
                for i in range(len(X.flatten()))
            }
            
        if X.ndim == 1:
            X = X.reshape(1, -1)
            
        # Get SHAP values
        shap_values = self._explainer.shap_values(X)
        
        # Handle multi-output
        if isinstance(shap_values, list):
            shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]
            
        shap_values = shap_values.flatten()
        
        # Get prediction
        try:
            prediction = self.model.predict(X)[0]
            if hasattr(self.model, 'predict_proba'):
                proba = self.model.predict_proba(X)[0]
                confidence = max(proba)
            else:
                confidence = 1.0
        except:
            prediction = np.sum(shap_values) + self._explainer.expected_value
            confidence = 1.0
            
        # Get base value
        base_value = self._explainer.expected_value
        if isinstance(base_value, np.ndarray):
            base_value = base_value[0] if len(base_value) == 1 else base_value[1]
            
        # Create contributions
        contributions = []
        feature_names = self.feature_names or [f"feature_{i}" for i in range(len(shap_values))]
        
        total_abs_shap = np.sum(np.abs(shap_values))
        
        for i, (feat, shap_val) in enumerate(zip(feature_names, shap_values)):
            feat_val = list(feature_values.values())[i] if i < len(feature_values) else None
            
            contributions.append(FeatureContribution(
                feature_name=feat,
                feature_value=feat_val,
                contribution=float(shap_val),
                contribution_pct=abs(shap_val) / total_abs_shap * 100 if total_abs_shap > 0 else 0,
                direction="positive" if shap_val > 0 else "negative"
            ))
            
        # Sort for top features
        sorted_positive = sorted(
            [c for c in contributions if c.contribution > 0],
            key=lambda x: x.contribution,
            reverse=True
        )
        sorted_negative = sorted(
            [c for c in contributions if c.contribution < 0],
            key=lambda x: x.contribution
        )
        
        return LocalExplanation(
            prediction_id=prediction_id or f"pred_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            model_name=self.model_name,
            predicted_value=float(prediction),
            confidence=float(confidence),
            base_value=float(base_value),
            contributions=contributions,
            top_positive_features=[c.feature_name for c in sorted_positive[:5]],
            top_negative_features=[c.feature_name for c in sorted_negative[:5]]
        )
        
    def explain_global(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        sample_size: int = 500
    ) -> GlobalExplanation:
        """
        Generate global model explanation.
        
        Args:
            X: Data to analyze
            sample_size: Number of samples to use
            
        Returns:
            GlobalExplanation with feature importance
        """
        if self._explainer is None:
            raise ValueError("Explainer not fitted. Call fit() first.")
            
        if isinstance(X, pd.DataFrame):
            X = X.values
            
        # Sample if needed
        if len(X) > sample_size:
            idx = np.random.choice(len(X), sample_size, replace=False)
            X = X[idx]
            
        # Get SHAP values for all samples
        shap_values = self._explainer.shap_values(X)
        
        if isinstance(shap_values, list):
            shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]
            
        # Calculate mean absolute SHAP (feature importance)
        feature_importance = {}
        feature_names = self.feature_names or [f"feature_{i}" for i in range(shap_values.shape[1])]
        
        for i, feat in enumerate(feature_names):
            feature_importance[feat] = float(np.mean(np.abs(shap_values[:, i])))
            
        # Calculate feature interactions (approximate)
        top_interactions = self._calculate_interactions(X, shap_values, feature_names)
        
        return GlobalExplanation(
            model_name=self.model_name,
            timestamp=datetime.now(),
            feature_importance=feature_importance,
            top_interactions=top_interactions,
            n_samples_analyzed=len(X),
            model_type=self.model_type
        )
        
    def _calculate_interactions(
        self,
        X: np.ndarray,
        shap_values: np.ndarray,
        feature_names: List[str],
        top_k: int = 10
    ) -> List[Tuple[str, str, float]]:
        """Calculate top feature interactions."""
        interactions = []
        n_features = len(feature_names)
        
        # Simple approximation: correlation of SHAP values
        for i in range(n_features):
            for j in range(i + 1, n_features):
                corr = np.corrcoef(shap_values[:, i], shap_values[:, j])[0, 1]
                if not np.isnan(corr):
                    interactions.append((
                        feature_names[i],
                        feature_names[j],
                        abs(corr)
                    ))
                    
        # Sort by strength
        interactions.sort(key=lambda x: x[2], reverse=True)
        
        return interactions[:top_k]
        
    def generate_compliance_report(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        model_version: str = "1.0",
        training_data_description: str = "",
        feature_descriptions: Optional[Dict[str, str]] = None,
        sample_explanations: int = 5
    ) -> ComplianceReport:
        """
        Generate compliance-ready report.
        
        Args:
            X: Data to analyze
            model_version: Version string
            training_data_description: Description of training data
            feature_descriptions: Dict of feature -> description
            sample_explanations: Number of sample explanations to include
            
        Returns:
            ComplianceReport ready for regulatory review
        """
        # Generate global explanation
        global_exp = self.explain_global(X)
        
        # Generate sample local explanations
        if isinstance(X, pd.DataFrame):
            X_arr = X.values
        else:
            X_arr = X
            
        sample_idx = np.random.choice(len(X_arr), min(sample_explanations, len(X_arr)), replace=False)
        local_explanations = []
        
        for idx in sample_idx:
            sample = X_arr[idx:idx+1]
            local_explanations.append(self.explain_prediction(sample))
            
        # Generate executive summary
        top_features = sorted(
            global_exp.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        summary = f"""This report documents the decision-making process of the {self.model_name} model.
        
The model primarily relies on the following features for predictions:
{', '.join([f[0] for f in top_features])}.

Based on analysis of {global_exp.n_samples_analyzed} samples, the model shows consistent behavior
with the top feature ({top_features[0][0]}) having an average impact of {top_features[0][1]:.4f}."""
        
        # Identify risk factors
        risk_factors = []
        
        # Check for feature dominance
        if top_features[0][1] > sum(f[1] for f in top_features) * 0.5:
            risk_factors.append(f"High dependence on single feature: {top_features[0][0]}")
            
        # Check for low feature importance variance
        importances = list(global_exp.feature_importance.values())
        if np.std(importances) < 0.01:
            risk_factors.append("Low variance in feature importance - model may be underfitting")
            
        # Limitations
        limitations = [
            "Explanations are approximations and may not capture all model behavior",
            "Feature interactions may be more complex than represented",
            "Explanations assume feature independence which may not hold",
            f"Based on sample of {global_exp.n_samples_analyzed} observations"
        ]
        
        return ComplianceReport(
            report_id=f"compliance_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            generated_at=datetime.now(),
            model_name=self.model_name,
            model_version=model_version,
            executive_summary=summary,
            global_explanation=global_exp,
            sample_explanations=local_explanations,
            training_data_description=training_data_description,
            feature_descriptions=feature_descriptions or {},
            risk_factors=risk_factors,
            limitations=limitations
        )


class FeatureContributionTracker:
    """
    Track feature contributions over time for drift detection.
    """
    
    def __init__(self, feature_names: List[str]):
        self.feature_names = feature_names
        self.history: List[Dict[str, Any]] = []
        
    def record(self, explanation: LocalExplanation):
        """Record a local explanation for tracking."""
        record = {
            'timestamp': explanation.timestamp,
            'prediction': explanation.predicted_value,
            **{c.feature_name: c.contribution for c in explanation.contributions}
        }
        self.history.append(record)
        
    def get_contribution_timeseries(self, feature: str) -> pd.Series:
        """Get time series of contributions for a feature."""
        data = [(h['timestamp'], h.get(feature, 0)) for h in self.history]
        df = pd.DataFrame(data, columns=['timestamp', 'contribution'])
        return df.set_index('timestamp')['contribution']
        
    def detect_drift(
        self,
        window_size: int = 100,
        threshold_std: float = 2.0
    ) -> Dict[str, bool]:
        """
        Detect if feature contributions are drifting.
        
        Returns dict of {feature: is_drifting}
        """
        if len(self.history) < window_size * 2:
            return {f: False for f in self.feature_names}
            
        drifting = {}
        
        for feature in self.feature_names:
            ts = self.get_contribution_timeseries(feature)
            
            # Compare recent window to historical
            recent = ts.tail(window_size)
            historical = ts.head(len(ts) - window_size)
            
            recent_mean = recent.mean()
            hist_mean = historical.mean()
            hist_std = historical.std()
            
            if hist_std > 0:
                z_score = abs(recent_mean - hist_mean) / hist_std
                drifting[feature] = z_score > threshold_std
            else:
                drifting[feature] = False
                
        return drifting
        
    def get_drift_report(self) -> Dict[str, Any]:
        """Generate comprehensive drift report."""
        drifting = self.detect_drift()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_observations': len(self.history),
            'features_drifting': [f for f, d in drifting.items() if d],
            'drift_status': drifting,
            'summary': f"{sum(drifting.values())}/{len(drifting)} features showing drift"
        }
