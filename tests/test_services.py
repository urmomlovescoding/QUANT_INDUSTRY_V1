"""
QUANT_INDUSTRY_V1 Services Module Tests

Tests for self-grading and monitoring services.
"""

import pytest
import numpy as np


class TestGrading:
    """Test grading types and utilities."""

    def test_grade_levels(self):
        """Test grade level values."""
        from services import GradeLevel

        assert GradeLevel.A_PLUS.value == "A+"
        assert GradeLevel.F.value == "F"

    def test_grading_dimensions(self):
        """Test grading dimensions."""
        from services import GradingDimension

        assert GradingDimension.RETURNS.value == "returns"
        assert GradingDimension.RISK_ADJUSTED.value == "risk_adjusted"

    def test_dimension_grade(self):
        """Test dimension grade creation."""
        from services import DimensionGrade, GradingDimension, GradeLevel

        grade = DimensionGrade(
            dimension=GradingDimension.RETURNS,
            score=85.0,
            grade=GradeLevel.A_MINUS,
            weight=1.5,
            metrics={'total_return': 0.15}
        )

        assert grade.score == 85.0
        assert grade.grade == GradeLevel.A_MINUS


class TestDimensionGraders:
    """Test individual dimension graders."""

    def test_returns_grader(self):
        """Test returns grader."""
        from services import ReturnsGrader

        grader = ReturnsGrader()

        # Good returns
        metrics = {
            'total_return': 0.20,
            'benchmark_return': 0.10
        }
        grade = grader.grade(metrics)

        assert grade.score > 70  # Should be good grade
        assert 'Significant alpha generation' in grade.strengths

    def test_returns_grader_negative(self):
        """Test returns grader with negative returns."""
        from services import ReturnsGrader

        grader = ReturnsGrader()

        metrics = {
            'total_return': -0.10,
            'benchmark_return': 0.05
        }
        grade = grader.grade(metrics)

        assert 'Negative total return' in grade.weaknesses
        assert 'Underperforming benchmark' in grade.weaknesses

    def test_risk_adjusted_grader(self):
        """Test risk-adjusted grader."""
        from services import RiskAdjustedGrader

        grader = RiskAdjustedGrader()

        # Good risk-adjusted metrics
        metrics = {
            'sharpe_ratio': 1.5,
            'sortino_ratio': 2.0,
            'calmar_ratio': 1.0
        }
        grade = grader.grade(metrics)

        assert grade.score > 60

    def test_drawdown_grader(self):
        """Test drawdown grader."""
        from services import DrawdownGrader

        grader = DrawdownGrader()

        # Low drawdown is good
        metrics = {
            'max_drawdown': 0.05,
            'avg_drawdown': 0.02,
            'avg_recovery_days': 10
        }
        grade = grader.grade(metrics)

        assert grade.score > 70

    def test_consistency_grader(self):
        """Test consistency grader."""
        from services import ConsistencyGrader

        grader = ConsistencyGrader()

        metrics = {
            'win_rate': 0.55,
            'profit_factor': 1.5,
            'monthly_positive_pct': 0.7
        }
        grade = grader.grade(metrics)

        assert grade.score > 50

    def test_model_performance_grader(self):
        """Test model performance grader."""
        from services import ModelPerformanceGrader

        grader = ModelPerformanceGrader()

        # Good model metrics
        metrics = {
            'model_accuracy': 0.58,
            'model_precision': 0.55,
            'model_recall': 0.52,
            'drift_detected': False
        }
        grade = grader.grade(metrics)

        assert grade.score > 50

    def test_model_performance_with_drift(self):
        """Test model grader with drift detected."""
        from services import ModelPerformanceGrader

        grader = ModelPerformanceGrader()

        metrics = {
            'model_accuracy': 0.58,
            'model_precision': 0.55,
            'model_recall': 0.52,
            'drift_detected': True
        }
        grade = grader.grade(metrics)

        assert 'Model drift detected' in grade.weaknesses

    def test_system_health_grader(self):
        """Test system health grader."""
        from services import SystemHealthGrader

        grader = SystemHealthGrader()

        metrics = {
            'uptime_pct': 99.9,
            'error_rate': 0.1,
            'latency_p99_ms': 100
        }
        grade = grader.grade(metrics)

        assert grade.score > 80


class TestRemediationGenerator:
    """Test remediation generator."""

    def test_generate_remediations(self):
        """Test remediation generation."""
        from services import (
            RemediationGenerator, DimensionGrade,
            GradingDimension, GradeLevel
        )

        generator = RemediationGenerator()

        # Create weak grades
        weak_grades = {
            GradingDimension.RETURNS: DimensionGrade(
                dimension=GradingDimension.RETURNS,
                score=40.0,
                grade=GradeLevel.F,
                weaknesses=['Negative total return']
            ),
            GradingDimension.RISK_ADJUSTED: DimensionGrade(
                dimension=GradingDimension.RISK_ADJUSTED,
                score=65.0,
                grade=GradeLevel.C_PLUS,
                weaknesses=['Low Sharpe ratio']
            ),
        }

        remediations = generator.generate(weak_grades)

        assert len(remediations) > 0
        assert remediations[0].priority.value in ['critical', 'high']

    def test_remediation_priority_sorting(self):
        """Test remediations are sorted by priority."""
        from services import (
            RemediationGenerator, DimensionGrade,
            GradingDimension, GradeLevel, RemediationPriority
        )

        generator = RemediationGenerator()

        weak_grades = {
            GradingDimension.RETURNS: DimensionGrade(
                dimension=GradingDimension.RETURNS,
                score=30.0,
                grade=GradeLevel.F,
            ),
            GradingDimension.SYSTEM_HEALTH: DimensionGrade(
                dimension=GradingDimension.SYSTEM_HEALTH,
                score=50.0,
                grade=GradeLevel.D,
            ),
        }

        remediations = generator.generate(weak_grades)

        if len(remediations) >= 2:
            priority_order = {
                RemediationPriority.CRITICAL: 0,
                RemediationPriority.HIGH: 1,
                RemediationPriority.MEDIUM: 2,
                RemediationPriority.LOW: 3,
            }

            for i in range(len(remediations) - 1):
                assert (priority_order[remediations[i].priority] <=
                        priority_order[remediations[i + 1].priority])


class TestSelfGradingEngine:
    """Test self-grading engine."""

    def test_grade_report(self):
        """Test generating grade report."""
        from services import SelfGradingEngine

        engine = SelfGradingEngine()

        metrics = {
            'total_return': 0.12,
            'benchmark_return': 0.08,
            'sharpe_ratio': 1.2,
            'sortino_ratio': 1.5,
            'calmar_ratio': 0.8,
            'max_drawdown': 0.10,
            'avg_drawdown': 0.05,
            'avg_recovery_days': 15,
            'win_rate': 0.52,
            'profit_factor': 1.3,
            'monthly_positive_pct': 0.6,
            'model_accuracy': 0.55,
            'model_precision': 0.52,
            'model_recall': 0.50,
            'drift_detected': False,
            'uptime_pct': 99.5,
            'error_rate': 0.5,
            'latency_p99_ms': 150,
        }

        report = engine.grade(metrics)

        assert report.overall_score > 0
        assert report.overall_grade is not None
        assert len(report.dimension_grades) > 0

    def test_trend_calculation(self):
        """Test trend calculation over time."""
        from services import SelfGradingEngine

        engine = SelfGradingEngine()

        # Generate improving reports
        for i in range(5):
            metrics = {
                'total_return': 0.05 + i * 0.02,
                'benchmark_return': 0.05,
                'sharpe_ratio': 0.5 + i * 0.2,
                'sortino_ratio': 0.7 + i * 0.2,
                'calmar_ratio': 0.4 + i * 0.1,
                'max_drawdown': 0.15 - i * 0.02,
                'win_rate': 0.50 + i * 0.01,
                'profit_factor': 1.0 + i * 0.1,
            }
            engine.grade(metrics)

        assert engine._calculate_trend() == 'improving'

    def test_improvement_roadmap(self):
        """Test improvement roadmap generation."""
        from services import SelfGradingEngine

        engine = SelfGradingEngine()

        metrics = {
            'total_return': 0.05,
            'benchmark_return': 0.10,  # Underperforming
            'sharpe_ratio': 0.3,  # Low
            'max_drawdown': 0.25,  # High
            'win_rate': 0.48,  # Below 50%
        }

        engine.grade(metrics)
        roadmap = engine.get_improvement_roadmap()

        assert len(roadmap) > 0
        assert roadmap[0]['priority'] == 1
        assert 'weaknesses' in roadmap[0]

    def test_historical_summary(self):
        """Test historical summary."""
        from services import SelfGradingEngine

        engine = SelfGradingEngine()

        # Generate some reports
        for _ in range(3):
            engine.grade({
                'total_return': 0.10,
                'sharpe_ratio': 1.0,
            })

        summary = engine.get_historical_summary()

        assert summary['total_reports'] == 3
        assert 'average_score' in summary
        assert 'best_score' in summary

    def test_grade_report_serialization(self):
        """Test grade report to_dict."""
        from services import SelfGradingEngine

        engine = SelfGradingEngine()

        report = engine.grade({
            'total_return': 0.15,
            'sharpe_ratio': 1.5,
        })

        report_dict = report.to_dict()

        assert 'overall_score' in report_dict
        assert 'overall_grade' in report_dict
        assert 'dimension_grades' in report_dict
        assert 'remediations' in report_dict

    def test_benchmark_comparison(self):
        """Test benchmark comparison."""
        from services import SelfGradingEngine

        engine = SelfGradingEngine()

        # Above benchmark
        report = engine.grade({
            'sharpe_ratio': 1.5,  # Benchmark is 0.5
        })

        assert report.comparison_to_benchmark > 0  # Outperforming


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
