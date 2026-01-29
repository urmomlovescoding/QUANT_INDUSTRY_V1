"""Initial prop firm tables

Revision ID: 001
Revises: 
Create Date: 2026-01-29 07:20:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create prop_traders table
    op.create_table(
        'prop_traders',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('timezone', sa.String(50), default='UTC'),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('two_factor_enabled', sa.Boolean(), default=False),
        sa.Column('two_factor_secret', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('kyc_verified', sa.Boolean(), default=False),
        sa.Column('kyc_documents', sa.JSON(), nullable=True),
        sa.Column('profit_split_percentage', sa.Float(), default=80.0),
        sa.Column('badges', sa.JSON(), default=list),
        sa.Column('xp_points', sa.Integer(), default=0),
        sa.Column('rank', sa.String(50), default='Rookie'),
        sa.Column('referral_code', sa.String(20), nullable=True),
        sa.Column('referred_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('referral_code'),
        sa.ForeignKeyConstraint(['referred_by'], ['prop_traders.id']),
    )
    op.create_index('ix_prop_traders_email', 'prop_traders', ['email'])
    op.create_index('ix_prop_traders_username', 'prop_traders', ['username'])

    # Create prop_challenges table
    op.create_table(
        'prop_challenges',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trader_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('phase', sa.String(20), default='phase_1'),
        sa.Column('starting_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('current_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('profit_target_pct', sa.Float(), nullable=False),
        sa.Column('profit_target_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('max_daily_drawdown_pct', sa.Float(), default=5.0),
        sa.Column('max_total_drawdown_pct', sa.Float(), default=10.0),
        sa.Column('max_daily_drawdown_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('max_total_drawdown_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('current_pnl', sa.Numeric(15, 2), default=0),
        sa.Column('current_pnl_pct', sa.Float(), default=0),
        sa.Column('peak_balance', sa.Numeric(15, 2), nullable=True),
        sa.Column('current_drawdown', sa.Numeric(15, 2), default=0),
        sa.Column('current_drawdown_pct', sa.Float(), default=0),
        sa.Column('daily_pnl', sa.Numeric(15, 2), default=0),
        sa.Column('daily_drawdown', sa.Numeric(15, 2), default=0),
        sa.Column('min_trading_days', sa.Integer(), default=5),
        sa.Column('max_trading_days', sa.Integer(), default=30),
        sa.Column('trading_days_completed', sa.Integer(), default=0),
        sa.Column('max_position_size_pct', sa.Float(), default=10.0),
        sa.Column('max_lots', sa.Float(), nullable=True),
        sa.Column('allowed_instruments', sa.JSON(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('result', sa.String(20), default='pending'),
        sa.Column('failed_reason', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('fee_paid', sa.Numeric(10, 2), default=0),
        sa.Column('fee_refunded', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['trader_id'], ['prop_traders.id']),
    )

    # Create prop_evaluations table
    op.create_table(
        'prop_evaluations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('challenge_id', sa.BigInteger(), nullable=False),
        sa.Column('trader_id', sa.BigInteger(), nullable=False),
        sa.Column('evaluation_date', sa.DateTime(), nullable=False),
        sa.Column('start_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('end_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('daily_pnl', sa.Numeric(15, 2), default=0),
        sa.Column('daily_pnl_pct', sa.Float(), default=0),
        sa.Column('cumulative_pnl', sa.Numeric(15, 2), default=0),
        sa.Column('cumulative_pnl_pct', sa.Float(), default=0),
        sa.Column('daily_drawdown', sa.Numeric(15, 2), default=0),
        sa.Column('daily_drawdown_pct', sa.Float(), default=0),
        sa.Column('max_drawdown', sa.Numeric(15, 2), default=0),
        sa.Column('max_drawdown_pct', sa.Float(), default=0),
        sa.Column('trades_count', sa.Integer(), default=0),
        sa.Column('winning_trades', sa.Integer(), default=0),
        sa.Column('losing_trades', sa.Integer(), default=0),
        sa.Column('win_rate', sa.Float(), default=0),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('profit_factor', sa.Float(), nullable=True),
        sa.Column('avg_win', sa.Numeric(15, 2), nullable=True),
        sa.Column('avg_loss', sa.Numeric(15, 2), nullable=True),
        sa.Column('largest_win', sa.Numeric(15, 2), nullable=True),
        sa.Column('largest_loss', sa.Numeric(15, 2), nullable=True),
        sa.Column('rules_violated', sa.JSON(), nullable=True),
        sa.Column('is_trading_day', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['challenge_id'], ['prop_challenges.id']),
        sa.ForeignKeyConstraint(['trader_id'], ['prop_traders.id']),
    )

    # Create prop_accounts table
    op.create_table(
        'prop_accounts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trader_id', sa.BigInteger(), nullable=False),
        sa.Column('challenge_id', sa.BigInteger(), nullable=True),
        sa.Column('account_number', sa.String(50), nullable=False),
        sa.Column('account_type', sa.String(50), default='funded'),
        sa.Column('initial_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('current_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('buying_power', sa.Numeric(15, 2), nullable=True),
        sa.Column('scale_level', sa.Integer(), default=1),
        sa.Column('next_scale_target', sa.Numeric(15, 2), nullable=True),
        sa.Column('max_daily_loss', sa.Numeric(15, 2), nullable=False),
        sa.Column('max_total_drawdown', sa.Numeric(15, 2), nullable=False),
        sa.Column('max_position_size', sa.Numeric(15, 2), nullable=True),
        sa.Column('daily_pnl', sa.Numeric(15, 2), default=0),
        sa.Column('total_pnl', sa.Numeric(15, 2), default=0),
        sa.Column('total_payouts', sa.Numeric(15, 2), default=0),
        sa.Column('pending_payout', sa.Numeric(15, 2), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_paused', sa.Boolean(), default=False),
        sa.Column('pause_reason', sa.Text(), nullable=True),
        sa.Column('broker', sa.String(50), nullable=True),
        sa.Column('broker_account_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_trade_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_number'),
        sa.ForeignKeyConstraint(['trader_id'], ['prop_traders.id']),
        sa.ForeignKeyConstraint(['challenge_id'], ['prop_challenges.id']),
    )

    # Create prop_trades table
    op.create_table(
        'prop_trades',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trader_id', sa.BigInteger(), nullable=False),
        sa.Column('challenge_id', sa.BigInteger(), nullable=True),
        sa.Column('account_id', sa.BigInteger(), nullable=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('entry_price', sa.Numeric(15, 6), nullable=False),
        sa.Column('exit_price', sa.Numeric(15, 6), nullable=True),
        sa.Column('stop_loss', sa.Numeric(15, 6), nullable=True),
        sa.Column('take_profit', sa.Numeric(15, 6), nullable=True),
        sa.Column('realized_pnl', sa.Numeric(15, 2), nullable=True),
        sa.Column('unrealized_pnl', sa.Numeric(15, 2), nullable=True),
        sa.Column('commission', sa.Numeric(10, 4), default=0),
        sa.Column('entry_time', sa.DateTime(), nullable=False),
        sa.Column('exit_time', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('is_open', sa.Boolean(), default=True),
        sa.Column('close_reason', sa.String(50), nullable=True),
        sa.Column('risk_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('risk_reward_ratio', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['trader_id'], ['prop_traders.id']),
        sa.ForeignKeyConstraint(['challenge_id'], ['prop_challenges.id']),
        sa.ForeignKeyConstraint(['account_id'], ['prop_accounts.id']),
    )
    op.create_index('ix_prop_trades_symbol', 'prop_trades', ['symbol'])

    # Create prop_performance_metrics table
    op.create_table(
        'prop_performance_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trader_id', sa.BigInteger(), nullable=False),
        sa.Column('total_trades', sa.Integer(), default=0),
        sa.Column('winning_trades', sa.Integer(), default=0),
        sa.Column('losing_trades', sa.Integer(), default=0),
        sa.Column('win_rate', sa.Float(), default=0),
        sa.Column('total_pnl', sa.Numeric(15, 2), default=0),
        sa.Column('avg_daily_pnl', sa.Numeric(15, 2), default=0),
        sa.Column('best_day', sa.Numeric(15, 2), nullable=True),
        sa.Column('worst_day', sa.Numeric(15, 2), nullable=True),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('sortino_ratio', sa.Float(), nullable=True),
        sa.Column('profit_factor', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('avg_risk_reward', sa.Float(), nullable=True),
        sa.Column('profitable_days', sa.Integer(), default=0),
        sa.Column('total_trading_days', sa.Integer(), default=0),
        sa.Column('consistency_score', sa.Float(), nullable=True),
        sa.Column('current_win_streak', sa.Integer(), default=0),
        sa.Column('max_win_streak', sa.Integer(), default=0),
        sa.Column('current_loss_streak', sa.Integer(), default=0),
        sa.Column('max_loss_streak', sa.Integer(), default=0),
        sa.Column('global_rank', sa.Integer(), nullable=True),
        sa.Column('monthly_rank', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trader_id'),
        sa.ForeignKeyConstraint(['trader_id'], ['prop_traders.id']),
    )

    # Create prop_payouts table
    op.create_table(
        'prop_payouts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trader_id', sa.BigInteger(), nullable=False),
        sa.Column('account_id', sa.BigInteger(), nullable=False),
        sa.Column('gross_profit', sa.Numeric(15, 2), nullable=False),
        sa.Column('trader_share_pct', sa.Float(), nullable=False),
        sa.Column('trader_amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('firm_amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('payment_reference', sa.String(100), nullable=True),
        sa.Column('requested_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['trader_id'], ['prop_traders.id']),
        sa.ForeignKeyConstraint(['account_id'], ['prop_accounts.id']),
    )

    # Create prop_badges table
    op.create_table(
        'prop_badges',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(100), nullable=True),
        sa.Column('xp_reward', sa.Integer(), default=0),
        sa.Column('criteria', sa.JSON(), nullable=True),
        sa.Column('rarity', sa.String(20), default='common'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )


def downgrade() -> None:
    op.drop_table('prop_badges')
    op.drop_table('prop_payouts')
    op.drop_table('prop_performance_metrics')
    op.drop_index('ix_prop_trades_symbol', 'prop_trades')
    op.drop_table('prop_trades')
    op.drop_table('prop_accounts')
    op.drop_table('prop_evaluations')
    op.drop_table('prop_challenges')
    op.drop_index('ix_prop_traders_username', 'prop_traders')
    op.drop_index('ix_prop_traders_email', 'prop_traders')
    op.drop_table('prop_traders')
