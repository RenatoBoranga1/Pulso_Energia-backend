from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

import numpy as np
import pandas as pd

from app.schemas.analytics import ConsumptionAnomaly, ConsumptionExtreme, MonthVariation


@dataclass(slots=True)
class AnalyticsComputationResult:
    history_points_used: int
    average_daily_kwh: float | None
    average_monthly_kwh: float | None
    latest_month_over_month_variation_pct: float | None
    month_over_month_variations: list[MonthVariation]
    highest_consumption: ConsumptionExtreme | None
    lowest_consumption: ConsumptionExtreme | None
    trend_direction: Literal["up", "down", "stable", "insufficient_data"]
    trend_summary: str
    seasonality_detected: bool
    seasonality_summary: str
    anomalies: list[ConsumptionAnomaly]


class ConsumptionAnalyticsCalculator:
    def calculate(self, series: pd.DataFrame) -> AnalyticsComputationResult:
        if series.empty:
            return AnalyticsComputationResult(
                history_points_used=0,
                average_daily_kwh=None,
                average_monthly_kwh=None,
                latest_month_over_month_variation_pct=None,
                month_over_month_variations=[],
                highest_consumption=None,
                lowest_consumption=None,
                trend_direction="insufficient_data",
                trend_summary="Ainda nao ha historico suficiente para determinar uma tendencia de consumo.",
                seasonality_detected=False,
                seasonality_summary="Ainda nao ha dados suficientes para inferir comportamento sazonal.",
                anomalies=[],
            )

        working = series.copy()
        history_points_used = len(working)
        average_daily = float(working["avg_daily_kwh"].dropna().mean()) if working["avg_daily_kwh"].notna().any() else None
        average_monthly = float(working["y"].mean())
        variations = self._calculate_variations(working)
        latest_variation = variations[-1].variation_pct if variations else None
        highest = self._build_extreme(working.loc[working["y"].idxmax()])
        lowest = self._build_extreme(working.loc[working["y"].idxmin()])
        trend_direction, trend_summary = self._calculate_trend(working)
        seasonality_detected, seasonality_summary = self._calculate_seasonality(working)
        anomalies = self._detect_anomalies(working)

        return AnalyticsComputationResult(
            history_points_used=history_points_used,
            average_daily_kwh=average_daily,
            average_monthly_kwh=average_monthly,
            latest_month_over_month_variation_pct=latest_variation,
            month_over_month_variations=variations,
            highest_consumption=highest,
            lowest_consumption=lowest,
            trend_direction=trend_direction,
            trend_summary=trend_summary,
            seasonality_detected=seasonality_detected,
            seasonality_summary=seasonality_summary,
            anomalies=anomalies,
        )

    def _calculate_variations(self, series: pd.DataFrame) -> list[MonthVariation]:
        variations: list[MonthVariation] = []
        for index in range(1, len(series)):
            previous = float(series.iloc[index - 1]["y"])
            current = float(series.iloc[index]["y"])
            variation = 0.0 if previous == 0 else ((current - previous) / previous) * 100
            variations.append(
                MonthVariation(
                    current_month=series.iloc[index]["mes_referencia"],
                    previous_month=series.iloc[index - 1]["mes_referencia"],
                    variation_pct=round(variation, 2),
                )
            )
        return variations

    def _build_extreme(self, row: pd.Series) -> ConsumptionExtreme:
        return ConsumptionExtreme(
            mes_referencia=str(row["mes_referencia"]),
            consumo_kwh=Decimal(str(round(float(row["y"]), 3))),
        )

    def _calculate_trend(self, series: pd.DataFrame) -> tuple[Literal["up", "down", "stable", "insufficient_data"], str]:
        if len(series) < 2:
            return "insufficient_data", "Ainda nao ha historico suficiente para calcular a tendencia."

        x = np.arange(len(series))
        y = series["y"].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        baseline = float(y.mean()) or 1.0
        normalized_slope = slope / baseline

        if normalized_slope > 0.02:
            direction: Literal["up", "down", "stable", "insufficient_data"] = "up"
            summary = f"O consumo mensal apresenta tendencia de alta, em torno de {slope:.1f} kWh por mes."
        elif normalized_slope < -0.02:
            direction = "down"
            summary = f"O consumo mensal apresenta tendencia de queda, em torno de {abs(slope):.1f} kWh por mes."
        else:
            direction = "stable"
            summary = "O consumo mensal permanece relativamente estavel no periodo observado."

        projected_delta = ((intercept + slope * (len(series) - 1)) - y[0]) / (y[0] or 1.0) * 100
        summary = f"{summary} A variacao liquida no periodo analisado foi de {projected_delta:.1f}%."
        return direction, summary

    def _calculate_seasonality(self, series: pd.DataFrame) -> tuple[bool, str]:
        if len(series) < 12:
            return False, "Ainda nao ha historico mensal suficiente para confirmar sazonalidade."

        working = series.copy()
        working["month_number"] = working["ds"].dt.month
        month_profile = working.groupby("month_number")["y"].mean()
        overall_std = float(working["y"].std(ddof=0))
        profile_std = float(month_profile.std(ddof=0))
        seasonality_detected = overall_std > 0 and profile_std / overall_std >= 0.35

        if seasonality_detected:
            peak_month = int(month_profile.idxmax())
            trough_month = int(month_profile.idxmin())
            summary = (
                f"Ha sinais de sazonalidade, com medias mais altas por volta do mes {peak_month:02d} "
                f"e medias mais baixas por volta do mes {trough_month:02d}."
            )
        else:
            summary = "O historico disponivel nao mostra evidencias fortes de variacoes sazonais recorrentes."
        return seasonality_detected, summary

    def _detect_anomalies(self, series: pd.DataFrame) -> list[ConsumptionAnomaly]:
        if len(series) < 4:
            return []

        x = np.arange(len(series))
        y = series["y"].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        trend = intercept + slope * x
        residuals = y - trend
        residual_std = float(np.std(residuals, ddof=1)) if len(series) > 2 else 0.0
        if residual_std == 0:
            return []

        anomalies: list[ConsumptionAnomaly] = []
        for index, residual in enumerate(residuals):
            deviation_pct = (residual / trend[index]) * 100 if trend[index] else 0.0
            if abs(residual) >= residual_std * 1.8 and abs(deviation_pct) >= 12:
                direction = "acima" if residual > 0 else "abaixo"
                anomalies.append(
                    ConsumptionAnomaly(
                        mes_referencia=series.iloc[index]["mes_referencia"],
                        consumo_kwh=Decimal(str(round(float(y[index]), 3))),
                        deviation_pct=round(float(deviation_pct), 2),
                        reason=f"O consumo ficou significativamente {direction} da tendencia linear local.",
                    )
                )
        return anomalies
