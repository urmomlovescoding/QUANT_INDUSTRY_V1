"""
Model Registry - Model Persistence, Versioning, and Lifecycle Management
QUANT_INDUSTRY_V1

Provides:
- Model serialization/deserialization
- Version control
- A/B testing support
- Model metadata tracking
- Automatic rollback
"""

import os
import json
import pickle
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    """Model lifecycle status."""
    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    FAILED = "failed"


class ModelType(str, Enum):
    """Supported model types."""
    SKLEARN = "sklearn"
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CUSTOM = "custom"


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    auc_roc: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ModelMetadata:
    """Complete model metadata."""
    model_id: str
    name: str
    version: str
    model_type: ModelType
    status: ModelStatus
    created_at: datetime
    updated_at: datetime
    created_by: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Training info
    training_data_hash: Optional[str] = None
    training_samples: Optional[int] = None
    training_duration_seconds: Optional[float] = None
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    
    # Performance
    metrics: Optional[ModelMetrics] = None
    validation_metrics: Optional[ModelMetrics] = None
    
    # Lineage
    parent_model_id: Optional[str] = None
    feature_columns: List[str] = field(default_factory=list)
    target_column: Optional[str] = None
    
    # Deployment
    deployed_at: Optional[datetime] = None
    endpoint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        if self.deployed_at:
            data['deployed_at'] = self.deployed_at.isoformat()
        data['model_type'] = self.model_type.value
        data['status'] = self.status.value
        if self.metrics:
            data['metrics'] = self.metrics.to_dict()
        if self.validation_metrics:
            data['validation_metrics'] = self.validation_metrics.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelMetadata':
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if data.get('deployed_at'):
            data['deployed_at'] = datetime.fromisoformat(data['deployed_at'])
        data['model_type'] = ModelType(data['model_type'])
        data['status'] = ModelStatus(data['status'])
        if data.get('metrics'):
            data['metrics'] = ModelMetrics(**data['metrics'])
        if data.get('validation_metrics'):
            data['validation_metrics'] = ModelMetrics(**data['validation_metrics'])
        return cls(**data)


class ModelSerializer:
    """Handles model serialization for different frameworks."""
    
    @staticmethod
    def save(model: Any, path: Path, model_type: ModelType) -> str:
        """
        Save model to disk.
        
        Returns: SHA256 hash of saved model
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if model_type == ModelType.PYTORCH:
            import torch
            torch.save(model.state_dict(), path)
        elif model_type == ModelType.TENSORFLOW:
            model.save(str(path))
        elif model_type == ModelType.XGBOOST:
            model.save_model(str(path))
        elif model_type == ModelType.LIGHTGBM:
            model.booster_.save_model(str(path))
        else:
            # Default: pickle
            with open(path, 'wb') as f:
                pickle.dump(model, f)
                
        # Calculate hash
        return ModelSerializer._calculate_hash(path)
    
    @staticmethod
    def load(path: Path, model_type: ModelType, model_class: Optional[type] = None) -> Any:
        """Load model from disk."""
        if model_type == ModelType.PYTORCH:
            import torch
            if model_class is None:
                raise ValueError("model_class required for PyTorch models")
            model = model_class()
            model.load_state_dict(torch.load(path))
            return model
        elif model_type == ModelType.TENSORFLOW:
            import tensorflow as tf
            return tf.keras.models.load_model(str(path))
        elif model_type == ModelType.XGBOOST:
            import xgboost as xgb
            model = xgb.XGBClassifier()
            model.load_model(str(path))
            return model
        elif model_type == ModelType.LIGHTGBM:
            import lightgbm as lgb
            return lgb.Booster(model_file=str(path))
        else:
            with open(path, 'rb') as f:
                return pickle.load(f)
    
    @staticmethod
    def _calculate_hash(path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256 = hashlib.sha256()
        
        if path.is_dir():
            for file_path in sorted(path.rglob('*')):
                if file_path.is_file():
                    with open(file_path, 'rb') as f:
                        sha256.update(f.read())
        else:
            with open(path, 'rb') as f:
                sha256.update(f.read())
                
        return sha256.hexdigest()


class ModelRegistry:
    """
    Central model registry for versioning and lifecycle management.
    
    Directory structure:
    registry_path/
    ├── models/
    │   └── {model_name}/
    │       └── {version}/
    │           ├── model.pkl (or .pt, .h5, etc.)
    │           └── metadata.json
    ├── production/
    │   └── {model_name} -> ../models/{model_name}/{version}
    └── registry.json
    """
    
    def __init__(self, registry_path: Union[str, Path] = "models/registry"):
        self.registry_path = Path(registry_path)
        self.models_path = self.registry_path / "models"
        self.production_path = self.registry_path / "production"
        
        # Create directories
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.production_path.mkdir(parents=True, exist_ok=True)
        
        # Load registry index
        self.index_path = self.registry_path / "registry.json"
        self._index = self._load_index()
        
    def _load_index(self) -> Dict[str, Any]:
        """Load registry index."""
        if self.index_path.exists():
            with open(self.index_path, 'r') as f:
                return json.load(f)
        return {"models": {}, "production": {}}
    
    def _save_index(self):
        """Save registry index."""
        with open(self.index_path, 'w') as f:
            json.dump(self._index, f, indent=2)
            
    def register(
        self,
        model: Any,
        name: str,
        model_type: ModelType,
        version: Optional[str] = None,
        description: str = "",
        tags: List[str] = None,
        metrics: Optional[ModelMetrics] = None,
        hyperparameters: Dict[str, Any] = None,
        feature_columns: List[str] = None,
        target_column: str = None,
        created_by: str = "system"
    ) -> ModelMetadata:
        """
        Register a new model version.
        
        Args:
            model: The trained model object
            name: Model name (e.g., "momentum_classifier")
            model_type: Type of model (sklearn, pytorch, etc.)
            version: Optional version string (auto-generated if not provided)
            description: Model description
            tags: List of tags for filtering
            metrics: Training metrics
            hyperparameters: Model hyperparameters
            feature_columns: List of input features
            target_column: Target variable name
            created_by: Creator identifier
            
        Returns:
            ModelMetadata for the registered model
        """
        # Generate version if not provided
        if version is None:
            version = self._generate_version(name)
            
        # Generate model ID
        model_id = f"{name}:{version}"
        
        # Create model directory
        model_dir = self.models_path / name / version
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine model file extension
        ext_map = {
            ModelType.PYTORCH: ".pt",
            ModelType.TENSORFLOW: "",  # TF saves as directory
            ModelType.XGBOOST: ".json",
            ModelType.LIGHTGBM: ".txt",
        }
        ext = ext_map.get(model_type, ".pkl")
        model_path = model_dir / f"model{ext}"
        
        # Save model
        model_hash = ModelSerializer.save(model, model_path, model_type)
        
        # Create metadata
        now = datetime.now()
        metadata = ModelMetadata(
            model_id=model_id,
            name=name,
            version=version,
            model_type=model_type,
            status=ModelStatus.DRAFT,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            description=description,
            tags=tags or [],
            hyperparameters=hyperparameters or {},
            metrics=metrics,
            feature_columns=feature_columns or [],
            target_column=target_column,
            training_data_hash=model_hash
        )
        
        # Save metadata
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)
            
        # Update index
        if name not in self._index["models"]:
            self._index["models"][name] = {"versions": [], "latest": None}
        self._index["models"][name]["versions"].append(version)
        self._index["models"][name]["latest"] = version
        self._save_index()
        
        logger.info(f"Registered model {model_id}")
        return metadata
    
    def _generate_version(self, name: str) -> str:
        """Generate next version number."""
        if name not in self._index["models"]:
            return "1.0.0"
            
        versions = self._index["models"][name]["versions"]
        if not versions:
            return "1.0.0"
            
        # Parse latest version and increment
        latest = sorted(versions)[-1]
        parts = latest.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    
    def load(
        self,
        name: str,
        version: Optional[str] = None,
        model_class: Optional[type] = None
    ) -> tuple[Any, ModelMetadata]:
        """
        Load a model from the registry.
        
        Args:
            name: Model name
            version: Version to load (latest if not specified)
            model_class: Required for PyTorch models
            
        Returns:
            Tuple of (model, metadata)
        """
        # Get version
        if version is None:
            version = self.get_latest_version(name)
            
        model_dir = self.models_path / name / version
        if not model_dir.exists():
            raise ValueError(f"Model {name}:{version} not found")
            
        # Load metadata
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'r') as f:
            metadata = ModelMetadata.from_dict(json.load(f))
            
        # Find model file
        model_files = list(model_dir.glob("model*"))
        if not model_files:
            raise ValueError(f"Model file not found for {name}:{version}")
        model_path = model_files[0]
        
        # Load model
        model = ModelSerializer.load(model_path, metadata.model_type, model_class)
        
        logger.info(f"Loaded model {name}:{version}")
        return model, metadata
    
    def load_production(
        self,
        name: str,
        model_class: Optional[type] = None
    ) -> tuple[Any, ModelMetadata]:
        """Load the production version of a model."""
        if name not in self._index["production"]:
            raise ValueError(f"No production model for {name}")
            
        version = self._index["production"][name]
        return self.load(name, version, model_class)
    
    def promote_to_staging(self, name: str, version: str) -> ModelMetadata:
        """Promote model to staging status."""
        return self._update_status(name, version, ModelStatus.STAGING)
    
    def promote_to_production(self, name: str, version: str) -> ModelMetadata:
        """Promote model to production."""
        # Archive current production
        if name in self._index["production"]:
            current_prod = self._index["production"][name]
            self._update_status(name, current_prod, ModelStatus.ARCHIVED)
            
        # Update new production
        metadata = self._update_status(name, version, ModelStatus.PRODUCTION)
        metadata.deployed_at = datetime.now()
        
        # Update index
        self._index["production"][name] = version
        self._save_index()
        
        # Save updated metadata
        self._save_metadata(name, version, metadata)
        
        logger.info(f"Promoted {name}:{version} to production")
        return metadata
    
    def rollback(self, name: str, to_version: Optional[str] = None) -> ModelMetadata:
        """
        Rollback production to previous version.
        
        Args:
            name: Model name
            to_version: Specific version to rollback to (previous if not specified)
        """
        if name not in self._index["production"]:
            raise ValueError(f"No production model for {name}")
            
        current = self._index["production"][name]
        versions = self._index["models"][name]["versions"]
        
        if to_version is None:
            # Find previous version
            idx = versions.index(current)
            if idx == 0:
                raise ValueError("No previous version to rollback to")
            to_version = versions[idx - 1]
            
        logger.info(f"Rolling back {name} from {current} to {to_version}")
        return self.promote_to_production(name, to_version)
    
    def _update_status(
        self,
        name: str,
        version: str,
        status: ModelStatus
    ) -> ModelMetadata:
        """Update model status."""
        model_dir = self.models_path / name / version
        metadata_path = model_dir / "metadata.json"
        
        with open(metadata_path, 'r') as f:
            metadata = ModelMetadata.from_dict(json.load(f))
            
        metadata.status = status
        metadata.updated_at = datetime.now()
        
        self._save_metadata(name, version, metadata)
        return metadata
    
    def _save_metadata(self, name: str, version: str, metadata: ModelMetadata):
        """Save metadata to disk."""
        model_dir = self.models_path / name / version
        metadata_path = model_dir / "metadata.json"
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)
    
    def get_latest_version(self, name: str) -> str:
        """Get latest version of a model."""
        if name not in self._index["models"]:
            raise ValueError(f"Model {name} not found")
        return self._index["models"][name]["latest"]
    
    def list_models(self) -> List[str]:
        """List all registered model names."""
        return list(self._index["models"].keys())
    
    def list_versions(self, name: str) -> List[str]:
        """List all versions of a model."""
        if name not in self._index["models"]:
            raise ValueError(f"Model {name} not found")
        return self._index["models"][name]["versions"]
    
    def get_metadata(self, name: str, version: Optional[str] = None) -> ModelMetadata:
        """Get model metadata."""
        if version is None:
            version = self.get_latest_version(name)
            
        model_dir = self.models_path / name / version
        metadata_path = model_dir / "metadata.json"
        
        with open(metadata_path, 'r') as f:
            return ModelMetadata.from_dict(json.load(f))
    
    def delete(self, name: str, version: str):
        """Delete a model version."""
        if name in self._index["production"] and self._index["production"][name] == version:
            raise ValueError("Cannot delete production model")
            
        model_dir = self.models_path / name / version
        if model_dir.exists():
            shutil.rmtree(model_dir)
            
        self._index["models"][name]["versions"].remove(version)
        if self._index["models"][name]["latest"] == version:
            versions = self._index["models"][name]["versions"]
            self._index["models"][name]["latest"] = versions[-1] if versions else None
        self._save_index()
        
        logger.info(f"Deleted model {name}:{version}")
    
    def compare_models(
        self,
        name: str,
        version_a: str,
        version_b: str
    ) -> Dict[str, Any]:
        """Compare two model versions."""
        meta_a = self.get_metadata(name, version_a)
        meta_b = self.get_metadata(name, version_b)
        
        comparison = {
            'version_a': version_a,
            'version_b': version_b,
            'hyperparameter_diff': {},
            'metric_diff': {}
        }
        
        # Compare hyperparameters
        all_params = set(meta_a.hyperparameters.keys()) | set(meta_b.hyperparameters.keys())
        for param in all_params:
            val_a = meta_a.hyperparameters.get(param)
            val_b = meta_b.hyperparameters.get(param)
            if val_a != val_b:
                comparison['hyperparameter_diff'][param] = {
                    'a': val_a,
                    'b': val_b
                }
                
        # Compare metrics
        if meta_a.metrics and meta_b.metrics:
            metrics_a = meta_a.metrics.to_dict()
            metrics_b = meta_b.metrics.to_dict()
            
            all_metrics = set(metrics_a.keys()) | set(metrics_b.keys())
            for metric in all_metrics:
                val_a = metrics_a.get(metric)
                val_b = metrics_b.get(metric)
                if val_a is not None and val_b is not None:
                    comparison['metric_diff'][metric] = {
                        'a': val_a,
                        'b': val_b,
                        'diff': val_b - val_a if isinstance(val_b, (int, float)) else None
                    }
                    
        return comparison


class ModelCheckpointer:
    """
    Automatic model checkpointing during training.
    
    Usage:
        checkpointer = ModelCheckpointer("momentum_model", save_every=10)
        
        for epoch in range(100):
            train_epoch(model)
            metrics = evaluate(model)
            checkpointer.checkpoint(model, epoch, metrics)
    """
    
    def __init__(
        self,
        name: str,
        checkpoint_dir: Union[str, Path] = "checkpoints",
        save_every: int = 10,
        keep_best: int = 3,
        monitor_metric: str = "val_loss",
        mode: str = "min"
    ):
        self.name = name
        self.checkpoint_dir = Path(checkpoint_dir) / name
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.save_every = save_every
        self.keep_best = keep_best
        self.monitor_metric = monitor_metric
        self.mode = mode
        
        self.best_metric = float('inf') if mode == 'min' else float('-inf')
        self.best_checkpoints: List[tuple[float, Path]] = []
        
    def checkpoint(
        self,
        model: Any,
        epoch: int,
        metrics: Dict[str, float],
        model_type: ModelType = ModelType.SKLEARN
    ) -> Optional[Path]:
        """
        Save checkpoint if conditions are met.
        
        Returns: Path to checkpoint if saved, None otherwise
        """
        metric_value = metrics.get(self.monitor_metric)
        
        # Check if we should save
        should_save = False
        is_best = False
        
        # Save every N epochs
        if epoch % self.save_every == 0:
            should_save = True
            
        # Save if best
        if metric_value is not None:
            if self.mode == 'min' and metric_value < self.best_metric:
                self.best_metric = metric_value
                is_best = True
                should_save = True
            elif self.mode == 'max' and metric_value > self.best_metric:
                self.best_metric = metric_value
                is_best = True
                should_save = True
                
        if not should_save:
            return None
            
        # Save checkpoint
        checkpoint_name = f"checkpoint_epoch{epoch}"
        if is_best:
            checkpoint_name = f"best_epoch{epoch}"
            
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_name}.pkl"
        
        checkpoint_data = {
            'epoch': epoch,
            'metrics': metrics,
            'model_type': model_type.value,
            'saved_at': datetime.now().isoformat()
        }
        
        # Save model
        ModelSerializer.save(model, checkpoint_path, model_type)
        
        # Save checkpoint metadata
        meta_path = self.checkpoint_dir / f"{checkpoint_name}_meta.json"
        with open(meta_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
            
        # Track best checkpoints
        if is_best and metric_value is not None:
            self.best_checkpoints.append((metric_value, checkpoint_path))
            self.best_checkpoints.sort(key=lambda x: x[0], reverse=(self.mode == 'max'))
            
            # Clean up old best checkpoints
            while len(self.best_checkpoints) > self.keep_best:
                _, old_path = self.best_checkpoints.pop()
                if old_path.exists():
                    old_path.unlink()
                    old_meta = old_path.with_name(old_path.stem + "_meta.json")
                    if old_meta.exists():
                        old_meta.unlink()
                        
        logger.info(f"Saved checkpoint: {checkpoint_path}")
        return checkpoint_path
    
    def load_best(self, model_class: Optional[type] = None) -> tuple[Any, Dict[str, Any]]:
        """Load the best checkpoint."""
        if not self.best_checkpoints:
            # Find best from disk
            best_checkpoints = list(self.checkpoint_dir.glob("best_*.pkl"))
            if not best_checkpoints:
                raise ValueError("No best checkpoint found")
            checkpoint_path = sorted(best_checkpoints)[-1]
        else:
            _, checkpoint_path = self.best_checkpoints[0]
            
        # Load metadata
        meta_path = checkpoint_path.with_name(checkpoint_path.stem + "_meta.json")
        with open(meta_path, 'r') as f:
            meta = json.load(f)
            
        model_type = ModelType(meta['model_type'])
        model = ModelSerializer.load(checkpoint_path, model_type, model_class)
        
        return model, meta
    
    def load_checkpoint(
        self,
        epoch: int,
        model_class: Optional[type] = None
    ) -> tuple[Any, Dict[str, Any]]:
        """Load a specific checkpoint by epoch."""
        checkpoint_path = self.checkpoint_dir / f"checkpoint_epoch{epoch}.pkl"
        if not checkpoint_path.exists():
            checkpoint_path = self.checkpoint_dir / f"best_epoch{epoch}.pkl"
            
        if not checkpoint_path.exists():
            raise ValueError(f"Checkpoint for epoch {epoch} not found")
            
        meta_path = checkpoint_path.with_name(checkpoint_path.stem + "_meta.json")
        with open(meta_path, 'r') as f:
            meta = json.load(f)
            
        model_type = ModelType(meta['model_type'])
        model = ModelSerializer.load(checkpoint_path, model_type, model_class)
        
        return model, meta


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_registry(path: Optional[str] = None) -> ModelRegistry:
    """Get or create global model registry."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry(path or "models/registry")
    return _registry
