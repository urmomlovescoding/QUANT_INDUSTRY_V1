"""
QUANT_INDUSTRY_V1 UI Theme System - PROFESSIONAL EDITION

Modern institutional-grade UI design system.
Inspired by Bloomberg Terminal, TradingView Pro, and modern fintech apps.

Features:
- Modern gradient backgrounds
- Glassmorphism effects
- Professional color system
- Responsive typography
- Smooth animations support
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum


# =============================================================================
# SPACING SCALE (4px base unit)
# =============================================================================

class Spacing:
    """Spacing scale based on 4px grid."""
    NONE = 0
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32
    XXXL = 48

    PADDING_TIGHT = (XS, SM)
    PADDING_NORMAL = (SM, MD)
    PADDING_RELAXED = (MD, LG)
    PADDING_SECTION = (LG, XL)

    GUTTER_SM = SM
    GUTTER_MD = MD
    GUTTER_LG = LG


# =============================================================================
# TYPOGRAPHY SCALE
# =============================================================================

class FontSize:
    """Font size scale for consistent typography."""
    XS = 9
    SM = 10
    MD = 11
    LG = 12
    XL = 14
    XXL = 16
    XXXL = 20
    DISPLAY = 28
    HERO = 36

    CAPTION = XS
    BODY = MD
    SUBTITLE = LG
    TITLE = XL
    HEADING = XXL


class FontWeight:
    """Font weight constants."""
    LIGHT = "normal"
    NORMAL = "normal"
    MEDIUM = "bold"
    BOLD = "bold"


class FontFamily:
    """Modern font family definitions."""
    # Premium monospace for data
    MONO = ("JetBrains Mono", "Fira Code", "Consolas", "Monaco", "monospace")
    # Modern sans-serif
    SANS = ("Inter", "SF Pro Display", "Segoe UI", "Roboto", "sans-serif")
    SYSTEM = ("TkDefaultFont",)

    DATA = MONO
    UI = SANS
    DEFAULT = SYSTEM


# =============================================================================
# COLOR PALETTE - MODERN DARK THEME
# =============================================================================

class ColorScheme(Enum):
    """Available color schemes."""
    DARK = "dark"
    MIDNIGHT = "midnight"
    LIGHT = "light"
    BLOOMBERG = "bloomberg"
    TRADINGVIEW = "tradingview"


@dataclass
class ColorPalette:
    """
    Modern color palette with semantic meaning.
    Professional dark theme with vibrant accents.
    """

    # Background hierarchy (dark to light)
    bg_primary: str = "#0a0e17"       # Deep space black
    bg_secondary: str = "#0f1419"     # Panel background
    bg_tertiary: str = "#151b23"      # Card background
    bg_elevated: str = "#1c2432"      # Elevated surfaces
    bg_hover: str = "#242d3d"         # Hover state
    bg_active: str = "#2d3952"        # Active/pressed state
    bg_gradient_start: str = "#0a0e17"
    bg_gradient_end: str = "#1a1f2e"

    # Foreground hierarchy
    fg_primary: str = "#f0f4f8"       # Primary text (near white)
    fg_secondary: str = "#94a3b8"     # Secondary text
    fg_muted: str = "#64748b"         # Muted/disabled
    fg_inverse: str = "#0a0e17"       # Text on light bg

    # Trading colors - Vivid and clear
    bullish: str = "#22c55e"          # Vibrant green
    bullish_light: str = "#4ade80"    # Light green
    bullish_dark: str = "#15803d"     # Dark green
    bearish: str = "#ef4444"          # Vibrant red
    bearish_light: str = "#f87171"    # Light red
    bearish_dark: str = "#b91c1c"     # Dark red
    neutral: str = "#f59e0b"          # Amber

    # Status colors
    success: str = "#22c55e"
    error: str = "#ef4444"
    warning: str = "#f59e0b"
    info: str = "#3b82f6"

    # Accent colors - Modern vibrant
    accent_primary: str = "#3b82f6"   # Electric blue
    accent_secondary: str = "#8b5cf6" # Vivid purple
    accent_tertiary: str = "#06b6d4"  # Cyan
    accent_highlight: str = "#22d3ee" # Bright cyan
    accent_gold: str = "#fbbf24"      # Gold

    # Border colors
    border_subtle: str = "#1e293b"    # Very subtle
    border_light: str = "#334155"     # Light borders
    border_medium: str = "#475569"    # Standard borders
    border_strong: str = "#64748b"    # Emphasized
    border_focus: str = "#3b82f6"     # Focus ring
    border_glow: str = "#3b82f680"    # Glow effect

    # Chart colors - Professional palette
    chart_line: str = "#3b82f6"
    chart_line_alt: str = "#8b5cf6"
    chart_area: str = "#3b82f620"
    chart_grid: str = "#1e293b"
    chart_volume: str = "#475569"
    chart_candle_up: str = "#22c55e"
    chart_candle_down: str = "#ef4444"
    chart_wick: str = "#94a3b8"

    # Confidence/signal strength
    confidence_high: str = "#22c55e"
    confidence_mid: str = "#f59e0b"
    confidence_low: str = "#ef4444"

    # Regime colors
    regime_bull: str = "#22c55e"
    regime_bear: str = "#ef4444"
    regime_ranging: str = "#f59e0b"
    regime_volatile: str = "#8b5cf6"
    regime_crisis: str = "#dc2626"
    regime_recovery: str = "#06b6d4"

    # Glass effect colors
    glass_bg: str = "#ffffff08"
    glass_border: str = "#ffffff15"
    glass_highlight: str = "#ffffff20"

    # Gradient presets
    gradient_primary: Tuple[str, str] = ("#3b82f6", "#8b5cf6")
    gradient_success: Tuple[str, str] = ("#22c55e", "#06b6d4")
    gradient_danger: Tuple[str, str] = ("#ef4444", "#f59e0b")


# =============================================================================
# PRE-DEFINED PALETTES
# =============================================================================

DARK_PALETTE = ColorPalette()

MIDNIGHT_PALETTE = ColorPalette(
    bg_primary="#020617",
    bg_secondary="#0f172a",
    bg_tertiary="#1e293b",
    bg_elevated="#334155",
    accent_primary="#6366f1",
    accent_secondary="#a855f7",
)

TRADINGVIEW_PALETTE = ColorPalette(
    bg_primary="#131722",
    bg_secondary="#1e222d",
    bg_tertiary="#2a2e39",
    bg_elevated="#363a45",
    bullish="#26a69a",
    bearish="#ef5350",
    accent_primary="#2962ff",
    chart_line="#2962ff",
)

BLOOMBERG_PALETTE = ColorPalette(
    bg_primary="#000000",
    bg_secondary="#0d0d0d",
    bg_tertiary="#1a1a1a",
    bg_elevated="#262626",
    fg_primary="#ff8c00",
    fg_secondary="#ffffff",
    accent_primary="#ff8c00",
    accent_secondary="#ff6600",
    bullish="#00ff00",
    bearish="#ff0000",
)

LIGHT_PALETTE = ColorPalette(
    bg_primary="#f8fafc",
    bg_secondary="#ffffff",
    bg_tertiary="#f1f5f9",
    bg_elevated="#ffffff",
    bg_hover="#e2e8f0",
    bg_active="#cbd5e1",
    fg_primary="#0f172a",
    fg_secondary="#475569",
    fg_muted="#94a3b8",
    fg_inverse="#ffffff",
    border_subtle="#e2e8f0",
    border_light="#cbd5e1",
    border_medium="#94a3b8",
    chart_grid="#e2e8f0",
)


def get_palette(scheme: ColorScheme = ColorScheme.DARK) -> ColorPalette:
    """Get color palette for scheme."""
    palettes = {
        ColorScheme.DARK: DARK_PALETTE,
        ColorScheme.MIDNIGHT: MIDNIGHT_PALETTE,
        ColorScheme.LIGHT: LIGHT_PALETTE,
        ColorScheme.BLOOMBERG: BLOOMBERG_PALETTE,
        ColorScheme.TRADINGVIEW: TRADINGVIEW_PALETTE,
    }
    return palettes.get(scheme, DARK_PALETTE)


# =============================================================================
# THEME CONFIGURATION
# =============================================================================

@dataclass
class ThemeConfig:
    """Complete theme configuration with modern styling."""

    scheme: ColorScheme = ColorScheme.DARK
    colors: ColorPalette = field(default_factory=lambda: DARK_PALETTE)

    # Typography
    font_family_data: Tuple[str, ...] = FontFamily.MONO
    font_family_ui: Tuple[str, ...] = FontFamily.SANS
    font_size_base: int = FontSize.MD

    # Spacing
    padding_base: int = Spacing.SM
    margin_base: int = Spacing.MD
    border_radius: int = 8
    border_radius_sm: int = 4
    border_radius_lg: int = 12
    border_radius_xl: int = 16

    # Component sizes
    button_height: int = 32
    button_height_sm: int = 28
    button_height_lg: int = 40
    input_height: int = 36
    row_height: int = 32
    header_height: int = 48
    sidebar_width: int = 240
    card_padding: int = 16

    # Effects
    shadow_sm: str = "0 1px 2px rgba(0,0,0,0.3)"
    shadow_md: str = "0 4px 6px rgba(0,0,0,0.4)"
    shadow_lg: str = "0 10px 15px rgba(0,0,0,0.5)"
    shadow_glow: str = "0 0 20px rgba(59,130,246,0.3)"

    # Animation timing
    transition_fast: int = 100
    transition_normal: int = 200
    transition_slow: int = 300

    def get_font(
        self,
        size: int = None,
        weight: str = FontWeight.NORMAL,
        family: str = "data"
    ) -> Tuple:
        """Get font tuple for Tkinter."""
        size = size or self.font_size_base
        if family == "data":
            fam = self.font_family_data[0]
        else:
            fam = self.font_family_ui[0]
        return (fam, size, weight)

    @classmethod
    def from_scheme(cls, scheme: ColorScheme) -> 'ThemeConfig':
        """Create theme config from color scheme."""
        return cls(scheme=scheme, colors=get_palette(scheme))


# =============================================================================
# GLOBAL THEME MANAGEMENT
# =============================================================================

_current_theme: Optional[ThemeConfig] = None


def get_theme() -> ThemeConfig:
    """Get the current theme configuration."""
    global _current_theme
    if _current_theme is None:
        _current_theme = ThemeConfig()
    return _current_theme


def set_theme(theme: ThemeConfig) -> None:
    """Set the current theme configuration."""
    global _current_theme
    _current_theme = theme


def init_theme(scheme: ColorScheme = ColorScheme.DARK) -> ThemeConfig:
    """Initialize and return theme for scheme."""
    theme = ThemeConfig.from_scheme(scheme)
    set_theme(theme)
    return theme


# =============================================================================
# STYLE HELPERS
# =============================================================================

def get_pnl_color(value: float, colors: ColorPalette = None) -> str:
    """Get color for P&L value."""
    colors = colors or get_theme().colors
    if value > 0:
        return colors.bullish
    elif value < 0:
        return colors.bearish
    return colors.fg_secondary


def get_direction_color(direction: str, colors: ColorPalette = None) -> str:
    """Get color for trading direction."""
    colors = colors or get_theme().colors
    d = direction.upper()
    if d in ('LONG', 'BUY', 'BULLISH'):
        return colors.bullish
    elif d in ('SHORT', 'SELL', 'BEARISH'):
        return colors.bearish
    return colors.neutral


def get_confidence_color(confidence: float, colors: ColorPalette = None) -> str:
    """Get color for confidence level."""
    colors = colors or get_theme().colors
    if confidence >= 0.7:
        return colors.confidence_high
    elif confidence >= 0.5:
        return colors.confidence_mid
    return colors.confidence_low


def get_regime_color(regime: str, colors: ColorPalette = None) -> str:
    """Get color for market regime."""
    colors = colors or get_theme().colors
    r = regime.lower().replace(' ', '_')
    regime_map = {
        'bull_trend': colors.regime_bull,
        'bull': colors.regime_bull,
        'bullish': colors.regime_bull,
        'trending_up': colors.regime_bull,
        'bear_trend': colors.regime_bear,
        'bear': colors.regime_bear,
        'bearish': colors.regime_bear,
        'trending_down': colors.regime_bear,
        'ranging': colors.regime_ranging,
        'sideways': colors.regime_ranging,
        'high_volatility': colors.regime_volatile,
        'volatile': colors.regime_volatile,
        'crisis': colors.regime_crisis,
        'recovery': colors.regime_recovery,
        'risk_on': colors.bullish,
        'risk_off': colors.bearish,
    }
    return regime_map.get(r, colors.fg_secondary)


def get_severity_color(severity: str, colors: ColorPalette = None) -> str:
    """Get color for severity level."""
    colors = colors or get_theme().colors
    s = severity.lower()
    if s in ('error', 'critical', 'danger'):
        return colors.error
    elif s in ('warning', 'warn'):
        return colors.warning
    elif s in ('success', 'ok', 'good'):
        return colors.success
    return colors.info


def get_grade_color(grade: str, colors: ColorPalette = None) -> str:
    """Get color for grade level."""
    colors = colors or get_theme().colors
    g = grade.upper().replace('-', '_').replace('+', '_PLUS')
    if g.startswith('A'):
        return colors.bullish
    elif g.startswith('B'):
        return colors.accent_primary
    elif g.startswith('C'):
        return colors.warning
    elif g.startswith('D'):
        return colors.bearish_light
    else:
        return colors.bearish


def interpolate_color(color1: str, color2: str, factor: float) -> str:
    """Interpolate between two hex colors."""
    def hex_to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def rgb_to_hex(r, g, b):
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)

    r = r1 + (r2 - r1) * factor
    g = g1 + (g2 - g1) * factor
    b = b1 + (b2 - b1) * factor

    return rgb_to_hex(r, g, b)
