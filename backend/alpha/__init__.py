# QUANT INDUSTRY Alpha Module
# Alpha-generating strategies and signals

from .cross_asset_momentum import (
    CrossAssetMomentum,
    CrossAssetConfig,
    MomentumSignal,
    AssetClass,
    LeadLagDetector,
    create_momentum_strategy,
    quick_momentum_signal,
)

__all__ = [
    "CrossAssetMomentum",
    "CrossAssetConfig",
    "MomentumSignal",
    "AssetClass",
    "LeadLagDetector",
    "create_momentum_strategy",
    "quick_momentum_signal",
]
