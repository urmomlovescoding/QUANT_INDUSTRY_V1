"""
QUANT_INDUSTRY_V1 Hashing Utilities

Provides consistent hashing for reproducibility tracking.
"""

import hashlib
import json
from typing import Dict, Any, Optional
from pathlib import Path
import pandas as pd
import numpy as np


def hash_dict(data: Dict[str, Any], length: int = 16) -> str:
    """
    Create reproducible hash from dictionary.

    Args:
        data: Dictionary to hash
        length: Length of hash string (default 16)

    Returns:
        Hex hash string
    """
    # Sort keys and convert to JSON for consistent ordering
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()[:length]


def hash_dataframe(df: pd.DataFrame, length: int = 16) -> str:
    """
    Create reproducible hash from DataFrame.

    Args:
        df: DataFrame to hash
        length: Length of hash string

    Returns:
        Hex hash string
    """
    # Use pandas hash_pandas_object for consistent hashing
    if df.empty:
        return '0' * length

    # Combine column names and data
    col_hash = hashlib.sha256('|'.join(df.columns).encode()).hexdigest()

    # Hash values (handle NaN consistently)
    values = df.fillna('__NAN__').values
    if isinstance(values, np.ndarray):
        data_hash = hashlib.sha256(values.tobytes()).hexdigest()
    else:
        data_hash = hashlib.sha256(str(values).encode()).hexdigest()

    combined = f"{col_hash}|{data_hash}"
    return hashlib.sha256(combined.encode()).hexdigest()[:length]


def hash_file(path: Path, length: int = 16) -> str:
    """
    Create hash of file contents.

    Args:
        path: Path to file
        length: Length of hash string

    Returns:
        Hex hash string
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)

    return hasher.hexdigest()[:length]


def hash_model_config(
    model_type: str,
    hyperparams: Dict[str, Any],
    feature_names: list,
    length: int = 16
) -> str:
    """
    Create hash for model configuration.

    Used for model versioning and comparison.

    Args:
        model_type: Type of model
        hyperparams: Model hyperparameters
        feature_names: List of feature names
        length: Length of hash string

    Returns:
        Hex hash string
    """
    config = {
        'model_type': model_type,
        'hyperparams': hyperparams,
        'features': sorted(feature_names),
    }
    return hash_dict(config, length)


def hash_dataset(
    df: pd.DataFrame,
    target_col: Optional[str] = None,
    length: int = 16
) -> str:
    """
    Create hash for training dataset.

    Used for reproducibility tracking.

    Args:
        df: Training data DataFrame
        target_col: Name of target column (if any)
        length: Length of hash string

    Returns:
        Hex hash string
    """
    metadata = {
        'shape': list(df.shape),
        'columns': sorted(df.columns.tolist()),
        'dtypes': {c: str(dt) for c, dt in df.dtypes.items()},
        'target_col': target_col,
    }

    metadata_hash = hash_dict(metadata)
    data_hash = hash_dataframe(df, length=16)

    combined = f"{metadata_hash}|{data_hash}"
    return hashlib.sha256(combined.encode()).hexdigest()[:length]


def verify_hash(data: Any, expected_hash: str, hash_func: callable = None) -> bool:
    """
    Verify that data matches expected hash.

    Args:
        data: Data to verify
        expected_hash: Expected hash value
        hash_func: Function to compute hash (default: hash_dict for dict, hash_dataframe for DataFrame)

    Returns:
        True if hash matches, False otherwise
    """
    if hash_func is None:
        if isinstance(data, dict):
            hash_func = hash_dict
        elif isinstance(data, pd.DataFrame):
            hash_func = hash_dataframe
        else:
            raise ValueError(f"No default hash function for type {type(data)}")

    actual_hash = hash_func(data, length=len(expected_hash))
    return actual_hash == expected_hash
