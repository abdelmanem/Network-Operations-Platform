"""Historical analytics engine for immutable discovery history."""

from backend.app.analytics.aggregation import AggregationResult, aggregate_runs
from backend.app.analytics.anomalies import detect_anomalies
from backend.app.analytics.baseline import compare_to_baseline
from backend.app.analytics.comparison import build_comparison_points
from backend.app.analytics.context import (
    HistoricalAnalyticsContext,
    HistoricalFindingEntry,
    HistoricalRunEntry,
)
from backend.app.analytics.engine import HistoricalAnalyticsEngine
from backend.app.analytics.filtering import (
    filter_findings_by_severity,
    filter_runs_by_date,
)
from backend.app.analytics.forecasting import (
    linear_projection,
    moving_average,
    trend_projection,
)
from backend.app.analytics.grouping import (
    group_findings_by_severity,
    group_runs_by_vendor,
)
from backend.app.analytics.metadata import (
    AggregationBucket,
    AggregationGranularity,
    AnalyticsStatistics,
    BaselineComparison,
    BaselineDirection,
    ComparisonPoint,
    RiskAnalysis,
    TimelineEntry,
)
from backend.app.analytics.models import (
    AnalyticsAnomaly,
    AnalyticsRecommendation,
    AnalyticsRecommendationAction,
    AnalyticsRecommendationCategory,
    AnalyticsRecommendationPriority,
    AnalyticsReport,
    AnalyticsTimelineEntry,
)
from backend.app.analytics.recommendations import build_recommendations_from_risk
from backend.app.analytics.regression import fit_linear_regression
from backend.app.analytics.repository import HistoricalAnalyticsRepository
from backend.app.analytics.risk import calculate_risk_analysis
from backend.app.analytics.scoring import score_risk
from backend.app.analytics.service import HistoricalAnalyticsService
from backend.app.analytics.statistics import calculate_statistics
from backend.app.analytics.timeline import build_timeline

__all__ = [
    "AggregationBucket",
    "AggregationGranularity",
    "AggregationResult",
    "AnalyticsAnomaly",
    "AnalyticsRecommendation",
    "AnalyticsRecommendationAction",
    "AnalyticsRecommendationCategory",
    "AnalyticsRecommendationPriority",
    "AnalyticsReport",
    "AnalyticsStatistics",
    "AnalyticsTimelineEntry",
    "BaselineComparison",
    "BaselineDirection",
    "ComparisonPoint",
    "HistoricalAnalyticsContext",
    "HistoricalAnalyticsEngine",
    "HistoricalAnalyticsRepository",
    "HistoricalAnalyticsService",
    "HistoricalFindingEntry",
    "HistoricalRunEntry",
    "RiskAnalysis",
    "TimelineEntry",
    "aggregate_runs",
    "build_comparison_points",
    "build_recommendations_from_risk",
    "build_timeline",
    "calculate_risk_analysis",
    "calculate_statistics",
    "compare_to_baseline",
    "detect_anomalies",
    "filter_findings_by_severity",
    "filter_runs_by_date",
    "fit_linear_regression",
    "group_findings_by_severity",
    "group_runs_by_vendor",
    "linear_projection",
    "moving_average",
    "score_risk",
    "trend_projection",
]
