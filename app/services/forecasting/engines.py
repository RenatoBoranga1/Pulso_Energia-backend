from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd

from app.core.config import Settings
from app.utils.months import timestamp_to_reference_month


@dataclass(slots=True)
class ForecastPointData:
    mes_referencia: str
    predicted_kwh: Decimal
    lower_bound_kwh: Decimal
    upper_bound_kwh: Decimal


@dataclass(slots=True)
class ForecastComputationResult:
    model_used: str
    explanation: str
    forecasts: list[ForecastPointData]


class BaseForecaster:
    model_name: str

    def generate(self, *, series: pd.DataFrame, settings: Settings) -> ForecastComputationResult:
        raise NotImplementedError


class DeterministicFallbackForecaster(BaseForecaster):
    model_name = "moving_average_linear_trend"

    def generate(self, *, series: pd.DataFrame, settings: Settings) -> ForecastComputationResult:
        horizon = settings.forecast_horizon_months
        y = series["y"].to_numpy(dtype=float) if not series.empty else np.array([], dtype=float)
        ds = series["ds"] if not series.empty else pd.Series(dtype="datetime64[ns]")

        if len(y) == 0:
            forecast_dates = pd.date_range(pd.Timestamp.today().replace(day=1), periods=horizon, freq="MS")
            forecasts = [
                ForecastPointData(
                    mes_referencia=timestamp_to_reference_month(date_value),
                    predicted_kwh=Decimal("0.000"),
                    lower_bound_kwh=Decimal("0.000"),
                    upper_bound_kwh=Decimal("0.000"),
                )
                for date_value in forecast_dates
            ]
            return ForecastComputationResult(
                model_used=self.model_name,
                explanation="Nao havia historico utilizavel, entao o modelo deterministico retornou uma linha de base zerada.",
                forecasts=forecasts,
            )

        x = np.arange(len(y), dtype=float)
        if len(y) >= 2:
            slope, intercept = np.polyfit(x, y, 1)
        else:
            slope, intercept = 0.0, float(y[0])

        moving_average_window = min(3, len(y))
        recent_moving_average = float(pd.Series(y).rolling(window=moving_average_window).mean().iloc[-1])

        if len(y) >= 3:
            fitted = intercept + slope * x
            residual_std = float(np.std(y - fitted, ddof=1))
        elif len(y) == 2:
            residual_std = abs(float(y[1] - y[0])) / 2
        else:
            residual_std = 0.0

        start_date = ds.iloc[-1] + pd.DateOffset(months=1)
        forecast_dates = pd.date_range(start=start_date, periods=horizon, freq="MS")
        forecasts: list[ForecastPointData] = []

        for step, date_value in enumerate(forecast_dates, start=1):
            trend_prediction = intercept + slope * (len(y) - 1 + step)
            predicted = max(0.0, (0.65 * trend_prediction) + (0.35 * recent_moving_average))
            interval_width = settings.forecast_interval_zscore * residual_std * np.sqrt(1 + (0.25 * step))
            lower = max(0.0, predicted - interval_width)
            upper = max(predicted, predicted + interval_width)
            forecasts.append(
                ForecastPointData(
                    mes_referencia=timestamp_to_reference_month(date_value),
                    predicted_kwh=Decimal(str(round(predicted, 3))),
                    lower_bound_kwh=Decimal(str(round(lower, 3))),
                    upper_bound_kwh=Decimal(str(round(upper, 3))),
                )
            )

        direction = "de alta" if slope > 0 else "de queda" if slope < 0 else "estavel"
        explanation = (
            "Previsao gerada pelo fallback deterministico, combinando tendencia linear e media movel curta. "
            f"A serie recente sugere uma linha de base {direction}."
        )
        return ForecastComputationResult(
            model_used=self.model_name,
            explanation=explanation,
            forecasts=forecasts,
        )


class ProphetForecaster(BaseForecaster):
    model_name = "prophet"
    MIN_POINTS_FOR_YEARLY_SEASONALITY = 24

    def generate(self, *, series: pd.DataFrame, settings: Settings) -> ForecastComputationResult:
        from prophet import Prophet

        dataframe = pd.DataFrame({"ds": series["ds"], "y": series["y"]})
        enable_yearly_seasonality = len(dataframe) >= self.MIN_POINTS_FOR_YEARLY_SEASONALITY
        model = Prophet(
            interval_width=0.95,
            yearly_seasonality=enable_yearly_seasonality,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.08,
            seasonality_prior_scale=6.0 if enable_yearly_seasonality else 0.1,
            n_changepoints=max(1, min(8, len(dataframe) - 2)),
        )
        model.fit(dataframe)

        future = model.make_future_dataframe(periods=settings.forecast_horizon_months, freq="MS", include_history=False)
        prediction = model.predict(future)
        prediction = prediction[["ds", "yhat", "yhat_lower", "yhat_upper"]]

        forecasts: list[ForecastPointData] = []
        for row in prediction.itertuples(index=False):
            predicted = max(0.0, float(row.yhat))
            lower = max(0.0, float(row.yhat_lower))
            upper = max(predicted, float(row.yhat_upper))
            forecasts.append(
                ForecastPointData(
                    mes_referencia=timestamp_to_reference_month(pd.Timestamp(row.ds)),
                    predicted_kwh=Decimal(str(round(predicted, 3))),
                    lower_bound_kwh=Decimal(str(round(lower, 3))),
                    upper_bound_kwh=Decimal(str(round(upper, 3))),
                )
            )

        if enable_yearly_seasonality:
            explanation = "Previsao gerada com Prophet considerando tendencia e sazonalidade anual do historico mensal."
        else:
            explanation = (
                "Previsao gerada com Prophet em configuracao conservadora para historico mensal curto, "
                "priorizando tendencia sobre sazonalidade anual."
            )
        return ForecastComputationResult(
            model_used=self.model_name,
            explanation=explanation,
            forecasts=forecasts,
        )
