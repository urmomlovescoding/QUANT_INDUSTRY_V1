"""
Tests for Broker Reconciliation System
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from reconciliation.broker_reconciliation import (
    BrokerReconciliation,
    Position,
    Transaction,
    Discrepancy,
    DiscrepancyType,
    DiscrepancySeverity,
    ReconciliationStatus,
    MockBrokerAdapter,
    ReconciliationScheduler
)


class TestPositionReconciliation:
    """Test position reconciliation"""
    
    def test_matching_positions(self):
        """Test that matching positions reconcile"""
        engine = BrokerReconciliation()
        
        internal = [
            Position(
                symbol="AAPL",
                quantity=Decimal("100"),
                cost_basis=Decimal("15000"),
                market_value=Decimal("17500"),
                source="internal",
                as_of_date=date.today()
            )
        ]
        
        broker = [
            Position(
                symbol="AAPL",
                quantity=Decimal("100"),
                cost_basis=Decimal("15000"),
                market_value=Decimal("17500"),
                source="broker",
                as_of_date=date.today()
            )
        ]
        
        comparisons, discrepancies = engine.reconcile_positions(
            internal, broker, date.today(), "TestBroker"
        )
        
        assert len(discrepancies) == 0
        assert comparisons[0]["status"] == ReconciliationStatus.MATCHED.value
    
    def test_quantity_discrepancy(self):
        """Test quantity mismatch detection"""
        engine = BrokerReconciliation()
        
        internal = [
            Position("AAPL", Decimal("100"), Decimal("15000"), Decimal("17500"), "internal", date.today())
        ]
        
        broker = [
            Position("AAPL", Decimal("95"), Decimal("14250"), Decimal("16625"), "broker", date.today())
        ]
        
        comparisons, discrepancies = engine.reconcile_positions(
            internal, broker, date.today(), "TestBroker"
        )
        
        assert len(discrepancies) >= 1
        assert any(d.discrepancy_type == DiscrepancyType.POSITION_QUANTITY for d in discrepancies)
    
    def test_missing_internal_position(self):
        """Test detection of position missing from internal records"""
        engine = BrokerReconciliation()
        
        internal = []
        broker = [
            Position("AAPL", Decimal("100"), Decimal("15000"), Decimal("17500"), "broker", date.today())
        ]
        
        comparisons, discrepancies = engine.reconcile_positions(
            internal, broker, date.today(), "TestBroker"
        )
        
        assert len(discrepancies) == 1
        assert discrepancies[0].discrepancy_type == DiscrepancyType.EXTRA_POSITION
    
    def test_missing_broker_position(self):
        """Test detection of position missing from broker"""
        engine = BrokerReconciliation()
        
        internal = [
            Position("AAPL", Decimal("100"), Decimal("15000"), Decimal("17500"), "internal", date.today())
        ]
        broker = []
        
        comparisons, discrepancies = engine.reconcile_positions(
            internal, broker, date.today(), "TestBroker"
        )
        
        assert len(discrepancies) == 1
        assert discrepancies[0].discrepancy_type == DiscrepancyType.MISSING_POSITION
    
    def test_cost_basis_discrepancy(self):
        """Test cost basis mismatch detection"""
        engine = BrokerReconciliation(tolerance_cost_basis_pct=Decimal("0.001"))
        
        internal = [
            Position("AAPL", Decimal("100"), Decimal("15000"), Decimal("17500"), "internal", date.today())
        ]
        
        broker = [
            Position("AAPL", Decimal("100"), Decimal("15500"), Decimal("17500"), "broker", date.today())
        ]
        
        comparisons, discrepancies = engine.reconcile_positions(
            internal, broker, date.today(), "TestBroker"
        )
        
        assert any(d.discrepancy_type == DiscrepancyType.POSITION_COST_BASIS for d in discrepancies)


class TestTransactionReconciliation:
    """Test transaction reconciliation"""
    
    def test_matching_transactions(self):
        """Test that matching transactions reconcile"""
        engine = BrokerReconciliation()
        
        today = date.today()
        
        internal = [
            Transaction(
                transaction_id="INT-001",
                symbol="AAPL",
                transaction_type="buy",
                quantity=Decimal("100"),
                price=Decimal("150"),
                amount=Decimal("15010"),
                fees=Decimal("10"),
                trade_date=today,
                settlement_date=today + timedelta(days=1),
                source="internal"
            )
        ]
        
        broker = [
            Transaction(
                transaction_id="BRK-001",
                symbol="AAPL",
                transaction_type="buy",
                quantity=Decimal("100"),
                price=Decimal("150"),
                amount=Decimal("15010"),
                fees=Decimal("10"),
                trade_date=today,
                settlement_date=today + timedelta(days=1),
                source="broker"
            )
        ]
        
        comparisons, discrepancies = engine.reconcile_transactions(
            internal, broker, today - timedelta(days=5), today, "TestBroker"
        )
        
        assert len(discrepancies) == 0
        assert comparisons[0]["status"] == ReconciliationStatus.MATCHED.value
    
    def test_amount_discrepancy(self):
        """Test transaction amount mismatch"""
        engine = BrokerReconciliation()
        
        today = date.today()
        
        internal = [
            Transaction("INT-001", "AAPL", "buy", Decimal("100"), Decimal("150"),
                       Decimal("15010"), Decimal("10"), today, today + timedelta(days=1), "internal")
        ]
        
        broker = [
            Transaction("BRK-001", "AAPL", "buy", Decimal("100"), Decimal("150"),
                       Decimal("15050"), Decimal("50"), today, today + timedelta(days=1), "broker")
        ]
        
        comparisons, discrepancies = engine.reconcile_transactions(
            internal, broker, today - timedelta(days=5), today, "TestBroker"
        )
        
        assert any(d.discrepancy_type == DiscrepancyType.TRANSACTION_AMOUNT for d in discrepancies)
    
    def test_missing_transaction(self):
        """Test detection of transaction not at broker"""
        engine = BrokerReconciliation()
        
        today = date.today()
        
        internal = [
            Transaction("INT-001", "AAPL", "buy", Decimal("100"), Decimal("150"),
                       Decimal("15010"), Decimal("10"), today, today + timedelta(days=1), "internal")
        ]
        broker = []
        
        comparisons, discrepancies = engine.reconcile_transactions(
            internal, broker, today - timedelta(days=5), today, "TestBroker"
        )
        
        assert len(discrepancies) == 1
        assert discrepancies[0].discrepancy_type == DiscrepancyType.TRANSACTION_MISSING
    
    def test_extra_transaction(self):
        """Test detection of transaction only at broker"""
        engine = BrokerReconciliation()
        
        today = date.today()
        
        internal = []
        broker = [
            Transaction("BRK-001", "AAPL", "buy", Decimal("100"), Decimal("150"),
                       Decimal("15010"), Decimal("10"), today, today + timedelta(days=1), "broker")
        ]
        
        comparisons, discrepancies = engine.reconcile_transactions(
            internal, broker, today - timedelta(days=5), today, "TestBroker"
        )
        
        assert len(discrepancies) == 1
        assert discrepancies[0].discrepancy_type == DiscrepancyType.TRANSACTION_EXTRA
    
    def test_date_tolerance_matching(self):
        """Test fuzzy date matching within tolerance"""
        engine = BrokerReconciliation(transaction_date_tolerance_days=1)
        
        today = date.today()
        
        internal = [
            Transaction("INT-001", "AAPL", "buy", Decimal("100"), Decimal("150"),
                       Decimal("15010"), Decimal("10"), today, today + timedelta(days=1), "internal")
        ]
        
        broker = [
            Transaction("BRK-001", "AAPL", "buy", Decimal("100"), Decimal("150"),
                       Decimal("15010"), Decimal("10"), today + timedelta(days=1),
                       today + timedelta(days=2), "broker")
        ]
        
        comparisons, discrepancies = engine.reconcile_transactions(
            internal, broker, today - timedelta(days=5), today + timedelta(days=1), "TestBroker"
        )
        
        # Should match with date discrepancy noted
        assert comparisons[0]["status"] == ReconciliationStatus.PARTIAL_MATCH.value


class TestCashReconciliation:
    """Test cash balance reconciliation"""
    
    def test_matching_cash(self):
        """Test matching cash balances"""
        engine = BrokerReconciliation()
        
        matched, discrepancies = engine.reconcile_cash(
            internal_cash=Decimal("50000"),
            broker_cash=Decimal("50000"),
            pending_settlements=[],
            broker_name="TestBroker"
        )
        
        assert matched is True
        assert len(discrepancies) == 0
    
    def test_cash_within_tolerance(self):
        """Test cash within tolerance matches"""
        engine = BrokerReconciliation(tolerance_amount=Decimal("0.01"))
        
        matched, discrepancies = engine.reconcile_cash(
            internal_cash=Decimal("50000.00"),
            broker_cash=Decimal("50000.005"),
            pending_settlements=[],
            broker_name="TestBroker"
        )
        
        assert matched is True
    
    def test_cash_discrepancy(self):
        """Test cash discrepancy detection"""
        engine = BrokerReconciliation()
        
        matched, discrepancies = engine.reconcile_cash(
            internal_cash=Decimal("50000"),
            broker_cash=Decimal("50500"),
            pending_settlements=[],
            broker_name="TestBroker"
        )
        
        assert matched is False
        assert len(discrepancies) == 1
        assert discrepancies[0].discrepancy_type == DiscrepancyType.CASH_BALANCE
    
    def test_cash_with_pending_settlements(self):
        """Test cash reconciliation with pending settlements"""
        engine = BrokerReconciliation()
        
        matched, discrepancies = engine.reconcile_cash(
            internal_cash=Decimal("50000"),
            broker_cash=Decimal("50000"),
            pending_settlements=[{"amount": 5000}],
            broker_name="TestBroker"
        )
        
        # Should still match (pending is informational)
        assert matched is True


class TestFullReconciliation:
    """Test full reconciliation flow"""
    
    def test_full_reconciliation_matched(self):
        """Test complete reconciliation with matching data"""
        engine = BrokerReconciliation()
        adapter = MockBrokerAdapter()
        
        today = date.today()
        
        # Set up matching data
        position = Position("AAPL", Decimal("100"), Decimal("15000"),
                          Decimal("17500"), "broker", today)
        adapter.set_positions([position])
        adapter.set_cash(Decimal("50000"))
        
        internal_positions = [
            Position("AAPL", Decimal("100"), Decimal("15000"),
                    Decimal("17500"), "internal", today)
        ]
        
        report = engine.run_full_reconciliation(
            internal_positions=internal_positions,
            internal_transactions=[],
            internal_cash=Decimal("50000"),
            broker_adapter=adapter,
            reconciliation_date=today
        )
        
        assert report.status == ReconciliationStatus.MATCHED
        assert report.positions_matched == 1
        assert report.cash_matched is True
    
    def test_full_reconciliation_discrepancy(self):
        """Test complete reconciliation with discrepancies"""
        engine = BrokerReconciliation()
        adapter = MockBrokerAdapter()
        
        today = date.today()
        
        # Set up mismatched data
        adapter.set_positions([
            Position("AAPL", Decimal("100"), Decimal("15000"),
                    Decimal("17500"), "broker", today)
        ])
        adapter.set_cash(Decimal("50000"))
        
        # Internal has different quantity
        internal_positions = [
            Position("AAPL", Decimal("90"), Decimal("13500"),
                    Decimal("15750"), "internal", today)
        ]
        
        report = engine.run_full_reconciliation(
            internal_positions=internal_positions,
            internal_transactions=[],
            internal_cash=Decimal("50000"),
            broker_adapter=adapter,
            reconciliation_date=today
        )
        
        assert report.status != ReconciliationStatus.MATCHED
        assert report.positions_discrepancies > 0
    
    def test_audit_trail_export(self):
        """Test audit trail generation"""
        engine = BrokerReconciliation()
        adapter = MockBrokerAdapter()
        
        today = date.today()
        adapter.set_cash(Decimal("50000"))
        
        report = engine.run_full_reconciliation(
            internal_positions=[],
            internal_transactions=[],
            internal_cash=Decimal("50000"),
            broker_adapter=adapter,
            reconciliation_date=today
        )
        
        audit = engine.export_audit_trail(report)
        
        assert "RECONCILIATION AUDIT TRAIL" in audit
        assert report.report_id in audit
        assert "SUMMARY" in audit


class TestReconciliationScheduler:
    """Test reconciliation scheduling"""
    
    def test_broker_registration(self):
        """Test registering brokers"""
        engine = BrokerReconciliation()
        scheduler = ReconciliationScheduler(engine)
        
        adapter = MockBrokerAdapter("TestBroker")
        scheduler.register_broker("test", adapter)
        
        assert "test" in scheduler.brokers
    
    def test_scheduled_reconciliation(self):
        """Test running scheduled reconciliation"""
        engine = BrokerReconciliation()
        scheduler = ReconciliationScheduler(engine)
        
        adapter = MockBrokerAdapter("TestBroker")
        adapter.set_cash(Decimal("50000"))
        scheduler.register_broker("test", adapter)
        
        reports = scheduler.run_scheduled_reconciliation(
            internal_positions=[],
            internal_transactions=[],
            internal_cash=Decimal("50000")
        )
        
        assert len(reports) == 1
        assert reports[0].broker == "TestBroker"
    
    def test_discrepancy_resolution(self):
        """Test resolving discrepancies"""
        engine = BrokerReconciliation()
        scheduler = ReconciliationScheduler(engine)
        
        adapter = MockBrokerAdapter("TestBroker")
        adapter.set_positions([
            Position("AAPL", Decimal("100"), Decimal("15000"),
                    Decimal("17500"), "broker", date.today())
        ])
        adapter.set_cash(Decimal("50000"))
        scheduler.register_broker("test", adapter)
        
        # Run with discrepancy
        scheduler.run_scheduled_reconciliation(
            internal_positions=[],  # Missing position
            internal_transactions=[],
            internal_cash=Decimal("50000")
        )
        
        if scheduler.unresolved_discrepancies:
            disc_id = list(scheduler.unresolved_discrepancies.keys())[0]
            result = scheduler.resolve_discrepancy(disc_id, "Manually verified")
            assert result is True
            assert disc_id not in scheduler.unresolved_discrepancies
    
    def test_alert_callback(self):
        """Test alert callback for critical discrepancies"""
        engine = BrokerReconciliation()
        scheduler = ReconciliationScheduler(engine)
        
        alerts_received = []
        
        def on_alert(report, discrepancies):
            alerts_received.extend(discrepancies)
        
        scheduler.add_alert_callback(on_alert)
        
        adapter = MockBrokerAdapter("TestBroker")
        # Large cash discrepancy will be critical
        adapter.set_cash(Decimal("100000"))
        scheduler.register_broker("test", adapter)
        
        scheduler.run_scheduled_reconciliation(
            internal_positions=[],
            internal_transactions=[],
            internal_cash=Decimal("50000")  # $50k difference
        )
        
        # Alert should have been triggered
        assert len(alerts_received) > 0


class TestDiscrepancySeverity:
    """Test discrepancy severity classification"""
    
    def test_small_cash_discrepancy_warning(self):
        """Test small cash discrepancy is warning"""
        engine = BrokerReconciliation()
        
        matched, discrepancies = engine.reconcile_cash(
            internal_cash=Decimal("50000"),
            broker_cash=Decimal("50050"),
            pending_settlements=[],
            broker_name="TestBroker"
        )
        
        assert discrepancies[0].severity == DiscrepancySeverity.WARNING
    
    def test_large_cash_discrepancy_error(self):
        """Test larger cash discrepancy is error"""
        engine = BrokerReconciliation()
        
        matched, discrepancies = engine.reconcile_cash(
            internal_cash=Decimal("50000"),
            broker_cash=Decimal("50500"),
            pending_settlements=[],
            broker_name="TestBroker"
        )
        
        assert discrepancies[0].severity == DiscrepancySeverity.ERROR
    
    def test_huge_cash_discrepancy_critical(self):
        """Test huge cash discrepancy is critical"""
        engine = BrokerReconciliation()
        
        matched, discrepancies = engine.reconcile_cash(
            internal_cash=Decimal("50000"),
            broker_cash=Decimal("75000"),
            pending_settlements=[],
            broker_name="TestBroker"
        )
        
        assert discrepancies[0].severity == DiscrepancySeverity.CRITICAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
