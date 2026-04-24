from __future__ import annotations

from decimal import Decimal

import pandas as pd

from app.core.enums import InsightType
from app.models.insight import Insight
from app.services.analytics.calculator import AnalyticsComputationResult
from app.services.forecasting.engines import ForecastComputationResult


class ConsumptionInsightBuilder:
    def build(
        self,
        *,
        series: pd.DataFrame,
        analytics: AnalyticsComputationResult,
        forecast: ForecastComputationResult,
    ) -> list[Insight]:
        insights: list[Insight] = []

        rolling_change = self._build_recent_change_insight(series)
        if rolling_change:
            insights.append(rolling_change)

        if analytics.seasonality_detected:
            insights.append(
                Insight(
                    insight_type=InsightType.SEASONALITY,
                    message=analytics.seasonality_summary,
                )
            )

        if analytics.anomalies:
            first_anomaly = analytics.anomalies[0]
            insights.append(
                Insight(
                    insight_type=InsightType.ANOMALY,
                    message=(
                        f"Foi detectado um possivel pico fora do padrao em {first_anomaly.mes_referencia}, "
                        f"com consumo {abs(first_anomaly.deviation_pct):.1f}% distante da tendencia."
                    ),
                )
            )

        if forecast.forecasts and analytics.average_monthly_kwh is not None:
            next_point = forecast.forecasts[0]
            baseline = analytics.average_monthly_kwh or 0.0
            if baseline > 0:
                delta_pct = ((float(next_point.predicted_kwh) - baseline) / baseline) * 100
                comparison = "acima" if delta_pct >= 0 else "abaixo"
                insights.append(
                    Insight(
                        insight_type=InsightType.FORECAST,
                        message=(
                            f"O proximo mes projetado tende a ficar {abs(delta_pct):.1f}% {comparison} da media historica mensal. "
                            f"Metodo usado: {forecast.model_used}."
                        ),
                    )
                )

        if not insights:
            insights.append(
                Insight(
                    insight_type=InsightType.GENERAL,
                    message="O historico disponivel ainda e limitado, entao o sistema gerou leituras basicas de consumo.",
                )
            )

        return insights[:4]

    def _build_recent_change_insight(self, series: pd.DataFrame) -> Insight | None:
        if len(series) < 6:
            return None

        recent = series.tail(3)
        previous = series.iloc[-6:-3]
        if recent.empty or previous.empty:
            return None

        recent_avg = recent["avg_daily_kwh"].dropna().mean()
        previous_avg = previous["avg_daily_kwh"].dropna().mean()
        if pd.isna(recent_avg) or pd.isna(previous_avg) or previous_avg == 0:
            return None

        delta_pct = ((recent_avg - previous_avg) / previous_avg) * 100
        direction = "aumentou" if delta_pct >= 0 else "reduziu"
        return Insight(
            insight_type=InsightType.TREND,
            message=f"O consumo medio diario {direction} {abs(delta_pct):.1f}% nos ultimos 3 meses em relacao aos 3 meses anteriores.",
        )
