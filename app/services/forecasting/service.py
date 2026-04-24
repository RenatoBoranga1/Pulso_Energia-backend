from __future__ import annotations

from app.core.config import Settings
from app.services.forecasting.engines import (
    BaseForecaster,
    DeterministicFallbackForecaster,
    ForecastComputationResult,
    ProphetForecaster,
)


class ConsumptionForecastService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fallback_forecaster: BaseForecaster = DeterministicFallbackForecaster()
        self.prophet_forecaster: BaseForecaster = ProphetForecaster()

    def generate(self, series) -> ForecastComputationResult:
        if self._should_use_prophet(series):
            try:
                prophet_result = self.prophet_forecaster.generate(series=series, settings=self.settings)
                if not self.is_forecast_trustworthy(series=series, forecasts=prophet_result.forecasts):
                    return self.fallback_forecaster.generate(series=series, settings=self.settings)
                return prophet_result
            except Exception:
                return self.fallback_forecaster.generate(series=series, settings=self.settings)
        return self.fallback_forecaster.generate(series=series, settings=self.settings)

    def _should_use_prophet(self, series) -> bool:
        return self.settings.enable_prophet and len(series) >= self.settings.prophet_min_history_points

    def is_forecast_trustworthy(self, *, series, forecasts) -> bool:
        if not forecasts:
            return False

        recent_history = series["y"].tail(min(6, len(series)))
        recent_average = float(recent_history.mean()) if len(recent_history) else 0.0
        predictions = [float(item.predicted_kwh) for item in forecasts]
        zero_like_count = sum(value <= 1.0 for value in predictions)
        if recent_average >= 80 and zero_like_count >= max(2, len(predictions) // 4):
            return False

        if self._has_extreme_alternating_profile(predictions, recent_average):
            return False

        return True

    @staticmethod
    def _has_extreme_alternating_profile(predictions: list[float], recent_average: float) -> bool:
        if len(predictions) < 4 or recent_average <= 0:
            return False

        low_threshold = recent_average * 0.15
        high_threshold = recent_average * 0.55
        alternating_pairs = 0
        for current, following in zip(predictions, predictions[1:], strict=False):
            if (current <= low_threshold and following >= high_threshold) or (
                current >= high_threshold and following <= low_threshold
            ):
                alternating_pairs += 1

        return alternating_pairs >= len(predictions) // 2
