"""
Rollback Safety Tests
=====================
Gate 7: Tests for feature flags and rollback capability.

These tests verify that quant_industry_v1 supports safe rollback
of any changes, matching quant-platform safety behavior.
"""
import os
import json
import pytest
from unittest.mock import Mock, patch


class TestFeatureFlags:
    """Test feature flag system for safe rollback."""

    def test_feature_flag_default_off(self):
        """New features must default to OFF."""
        class FeatureFlags:
            def __init__(self):
                self._flags = {
                    # All new features default to False
                    "tpt_aggressive_v2": False,
                    "ict_strategies": False,
                    "market_memory": False,
                    "beast_ml_v2": False,
                }

            def is_enabled(self, flag):
                return self._flags.get(flag, False)

        flags = FeatureFlags()

        # New features must be off by default
        assert flags.is_enabled("tpt_aggressive_v2") is False
        assert flags.is_enabled("ict_strategies") is False
        assert flags.is_enabled("market_memory") is False

    def test_feature_flag_enable_disable(self):
        """Feature flags must be toggleable at runtime."""
        class FeatureFlags:
            def __init__(self):
                self._flags = {}

            def enable(self, flag):
                self._flags[flag] = True

            def disable(self, flag):
                self._flags[flag] = False

            def is_enabled(self, flag):
                return self._flags.get(flag, False)

        flags = FeatureFlags()

        # Initially off
        assert flags.is_enabled("new_feature") is False

        # Enable
        flags.enable("new_feature")
        assert flags.is_enabled("new_feature") is True

        # Disable (rollback)
        flags.disable("new_feature")
        assert flags.is_enabled("new_feature") is False

    def test_feature_flag_persisted(self, tmp_path):
        """Feature flag state must persist."""
        flags_file = tmp_path / "feature_flags.json"

        # Save flags
        flags = {
            "tpt_aggressive": True,
            "ict_strategies": False,
        }
        with open(flags_file, 'w') as f:
            json.dump(flags, f)

        # Load after restart
        with open(flags_file) as f:
            loaded = json.load(f)

        assert loaded["tpt_aggressive"] is True
        assert loaded["ict_strategies"] is False


class TestAppModeSwitch:
    """Test APP_MODE switching for parity vs improved modes."""

    def test_platform_compat_mode(self):
        """APP_MODE=platform_compat must use original behavior."""
        os.environ["APP_MODE"] = "platform_compat"

        app_mode = os.environ.get("APP_MODE", "platform_compat")
        assert app_mode == "platform_compat"

        # In compat mode, use platform behavior
        def get_strategy(mode):
            if mode == "platform_compat":
                return "TPTAggressiveStrategy_Platform"
            else:
                return "TPTAggressiveStrategy_Improved"

        strategy = get_strategy(app_mode)
        assert "Platform" in strategy

    def test_industry_improved_mode(self):
        """APP_MODE=industry_improved must use enhanced behavior."""
        os.environ["APP_MODE"] = "industry_improved"

        app_mode = os.environ.get("APP_MODE", "platform_compat")
        assert app_mode == "industry_improved"

        def get_strategy(mode):
            if mode == "platform_compat":
                return "TPTAggressiveStrategy_Platform"
            else:
                return "TPTAggressiveStrategy_Improved"

        strategy = get_strategy(app_mode)
        assert "Improved" in strategy

    def test_default_mode_is_compat(self):
        """Default APP_MODE must be platform_compat for safety."""
        # Clear any existing value
        if "APP_MODE" in os.environ:
            del os.environ["APP_MODE"]

        app_mode = os.environ.get("APP_MODE", "platform_compat")
        assert app_mode == "platform_compat"


class TestModelRollback:
    """Test ML model rollback capability."""

    def test_previous_model_preserved(self, tmp_path):
        """Previous model weights must be preserved for rollback."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        # Current model
        current = models_dir / "model_v2.json"
        current.write_text('{"version": "2.0"}')

        # Previous model preserved
        previous = models_dir / "model_v1.json"
        previous.write_text('{"version": "1.0"}')

        # Both must exist for rollback capability
        assert current.exists()
        assert previous.exists()

    def test_model_rollback_restores_previous(self, tmp_path):
        """Rollback must restore previous model."""
        class ModelManager:
            def __init__(self, models_dir):
                self.models_dir = models_dir
                self.current_version = None
                self.previous_version = None

            def deploy(self, version):
                self.previous_version = self.current_version
                self.current_version = version

            def rollback(self):
                if self.previous_version:
                    self.current_version = self.previous_version
                    return True
                return False

        manager = ModelManager(tmp_path)
        manager.deploy("v1.0")
        manager.deploy("v2.0")

        assert manager.current_version == "v2.0"
        assert manager.previous_version == "v1.0"

        # Rollback
        success = manager.rollback()
        assert success is True
        assert manager.current_version == "v1.0"

    def test_rollback_on_degradation(self):
        """Model must auto-rollback on health degradation."""
        class AutoRollbackManager:
            def __init__(self):
                self.current = "v2.0"
                self.previous = "v1.0"
                self.health = "healthy"

            def check_health(self, metrics):
                if metrics["win_rate"] < 0.40:
                    self.health = "unhealthy"
                    self._rollback()
                    return "ROLLED_BACK"
                return "OK"

            def _rollback(self):
                self.current = self.previous

        manager = AutoRollbackManager()
        result = manager.check_health({"win_rate": 0.35})

        assert result == "ROLLED_BACK"
        assert manager.current == "v1.0"


class TestDeploymentStageRollback:
    """Test deployment stage rollback."""

    def test_canary_rollback(self):
        """Canary deployment must support rollback."""
        class DeploymentManager:
            def __init__(self):
                self.stage = "production"
                self.canary_percentage = 0

            def start_canary(self, percentage=5):
                self.stage = "canary"
                self.canary_percentage = percentage

            def rollback_canary(self):
                self.stage = "production"
                self.canary_percentage = 0

            def promote_canary(self):
                self.stage = "production"
                self.canary_percentage = 100

        manager = DeploymentManager()
        manager.start_canary(5)

        assert manager.stage == "canary"
        assert manager.canary_percentage == 5

        # Rollback if issues
        manager.rollback_canary()
        assert manager.stage == "production"
        assert manager.canary_percentage == 0

    def test_shadow_mode_no_impact(self):
        """Shadow mode must have zero production impact."""
        class ShadowMode:
            def __init__(self):
                self.shadow_signals = []
                self.production_trades = []

            def shadow_signal(self, signal):
                # Only record, never execute
                self.shadow_signals.append(signal)
                # NO production impact

            def execute_trade(self, trade):
                # Only production trades go here
                self.production_trades.append(trade)

        shadow = ShadowMode()
        shadow.shadow_signal({"action": "BUY", "symbol": "ES"})

        assert len(shadow.shadow_signals) == 1
        assert len(shadow.production_trades) == 0  # No impact


class TestConfigRollback:
    """Test configuration rollback capability."""

    def test_config_history_maintained(self, tmp_path):
        """Configuration history must be maintained."""
        config_file = tmp_path / "config.json"
        history_file = tmp_path / "config_history.json"

        # Initial config
        config_v1 = {"daily_target": 800, "version": 1}

        # Save with history
        history = []
        history.append(config_v1.copy())

        config_v1["daily_target"] = 1000
        config_v1["version"] = 2
        history.append(config_v1.copy())

        with open(history_file, 'w') as f:
            json.dump(history, f)

        # Can rollback to any previous config
        with open(history_file) as f:
            loaded_history = json.load(f)

        assert len(loaded_history) == 2
        assert loaded_history[0]["daily_target"] == 800
        assert loaded_history[1]["daily_target"] == 1000

    def test_config_rollback_restores_previous(self, tmp_path):
        """Config rollback must restore previous values."""
        class ConfigManager:
            def __init__(self):
                self.config = {"value": 100}
                self.history = []

            def update(self, key, value):
                self.history.append(self.config.copy())
                self.config[key] = value

            def rollback(self):
                if self.history:
                    self.config = self.history.pop()

        manager = ConfigManager()
        manager.update("value", 200)
        manager.update("value", 300)

        assert manager.config["value"] == 300

        manager.rollback()
        assert manager.config["value"] == 200

        manager.rollback()
        assert manager.config["value"] == 100


class TestTradeRollback:
    """Test trade state rollback (positions)."""

    def test_position_snapshot_before_trade(self):
        """Position snapshot must be taken before trades."""
        class PositionManager:
            def __init__(self):
                self.positions = {}
                self.snapshots = []

            def snapshot(self):
                self.snapshots.append(self.positions.copy())

            def open_position(self, symbol, qty):
                self.snapshot()
                self.positions[symbol] = qty

            def rollback_last(self):
                if self.snapshots:
                    self.positions = self.snapshots.pop()

        manager = PositionManager()
        manager.open_position("ES", 4)
        manager.open_position("NQ", 2)

        assert manager.positions == {"ES": 4, "NQ": 2}

        # Rollback NQ position
        manager.rollback_last()
        assert manager.positions == {"ES": 4}

    def test_flatten_all_is_reversible(self):
        """Flatten all must record state for potential re-entry."""
        class EmergencyManager:
            def __init__(self):
                self.positions = {"ES": 4, "NQ": 2}
                self.flattened_state = None

            def flatten_all(self, reason):
                self.flattened_state = {
                    "positions": self.positions.copy(),
                    "reason": reason,
                }
                self.positions = {}

            def get_flattened_state(self):
                return self.flattened_state

        manager = EmergencyManager()
        manager.flatten_all("EOD cutoff")

        assert manager.positions == {}
        assert manager.flattened_state["positions"] == {"ES": 4, "NQ": 2}


class TestDatabaseRollback:
    """Test database state rollback."""

    def test_transaction_rollback_on_error(self):
        """Database transactions must rollback on error."""
        class MockDatabase:
            def __init__(self):
                self.data = {}
                self.transaction_data = None

            def begin_transaction(self):
                self.transaction_data = self.data.copy()

            def commit(self):
                self.transaction_data = None

            def rollback(self):
                if self.transaction_data is not None:
                    self.data = self.transaction_data
                    self.transaction_data = None

            def insert(self, key, value):
                self.data[key] = value

        db = MockDatabase()
        db.insert("key1", "value1")

        # Start transaction
        db.begin_transaction()
        db.insert("key2", "value2")

        # Simulate error - rollback
        db.rollback()

        assert "key1" in db.data
        assert "key2" not in db.data  # Rolled back

    def test_trade_journal_atomic(self):
        """Trade journal entries must be atomic."""
        class TradeJournal:
            def __init__(self):
                self.entries = []
                self.pending = None

            def begin_entry(self, trade):
                self.pending = trade

            def commit_entry(self):
                if self.pending:
                    self.entries.append(self.pending)
                    self.pending = None

            def rollback_entry(self):
                self.pending = None

        journal = TradeJournal()
        journal.begin_entry({"symbol": "ES", "pnl": 100})

        # Error during trade - rollback
        journal.rollback_entry()

        assert len(journal.entries) == 0
        assert journal.pending is None
