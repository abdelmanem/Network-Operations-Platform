"""Risk and compliance scoring."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.comparison.diff import Difference, DifferenceType
from backend.app.compliance.findings.severity import Severity, SeverityLevel
from backend.app.compliance.rules.base import Rule


@dataclass(slots=True)
class RiskCalculator:
    """Calculate per-rule risk scores and severities."""

    def score(self, rule: Rule, difference: Difference) -> int:
        """Return risk score from 0 to 100."""

        explicit = rule.expected_state.get("risk_score")
        if explicit is not None:
            return self._clamp(int(str(explicit)))
        weights = {
            DifferenceType.MISSING: 80,
            DifferenceType.CONFLICT: 85,
            DifferenceType.DUPLICATE: 75,
            DifferenceType.MODIFIED: 50,
            DifferenceType.UNEXPECTED: 45,
            DifferenceType.UNSUPPORTED: 15,
            DifferenceType.UNKNOWN: 25,
        }
        return weights.get(difference.difference_type, 25)

    def severity_for_score(self, score: int) -> Severity:
        """Return severity for a risk score."""

        score = self._clamp(score)
        if score >= 90:
            return Severity(SeverityLevel.CRITICAL, score=score, label="Critical")
        if score >= 70:
            return Severity(SeverityLevel.HIGH, score=score, label="High")
        if score >= 40:
            return Severity(SeverityLevel.MEDIUM, score=score, label="Medium")
        if score > 0:
            return Severity(SeverityLevel.LOW, score=score, label="Low")
        return Severity(SeverityLevel.INFO, score=0, label="Info")

    @staticmethod
    def _clamp(value: int) -> int:
        return max(0, min(100, value))


@dataclass(slots=True)
class ComplianceScoreCalculator:
    """Calculate aggregate compliance score."""

    def score(self, risk_scores: tuple[int, ...]) -> int:
        """Return compliance score from 0 to 100."""

        if not risk_scores:
            return 100
        average_risk = sum(risk_scores) / len(risk_scores)
        return max(0, min(100, round(100 - average_risk)))
