from __future__ import annotations

from decimal import Decimal

import pandas as pd

from app.core.config import Settings
from app.services.forecasting.engines import ForecastComputationResult, ForecastPointData
from app.services.forecasting.service import ConsumptionForecastService


def _build_series(months: list[tuple[str, float, int]]) -> pd.DataFrame:
    records = []
    for mes_referencia, consumo_kwh, dias_faturados in months:
        records.append(
            {
                "mes_referencia": mes_referencia,
                "ds": pd.Timestamp(f"{mes_referencia}-01"),
                "y": consumo_kwh,
                "consumo_kwh": Decimal(str(consumo_kwh)),
                "dias_faturados": dias_faturados,
                "avg_daily_kwh": consumo_kwh / dias_faturados,
                "source": "test_fixture",
                "confirmed_source": True,
            }
        )
    return pd.DataFrame(records)


def test_forecast_service_uses_deterministic_fallback_for_short_history() -> None:
    settings = Settings(enable_prophet=True, prophet_min_history_points=12, forecast_horizon_months=8)
    service = ConsumptionForecastService(settings)
    series = _build_series(
        [
            ("2025-12", 301.0, 33),
            ("2026-01", 336.0, 29),
            ("2026-02", 267.0, 28),
            ("2026-03", 336.0, 32),
            ("2026-04", 252.0, 29),
        ]
    )

    result = service.generate(series)

    assert result.model_used == "moving_average_linear_trend"
    assert len(result.forecasts) == 8
    assert result.forecasts[0].mes_referencia == "2026-05"
    assert result.forecasts[-1].mes_referencia == "2026-12"
    assert all(point.predicted_kwh >= Decimal("0") for point in result.forecasts)
    assert all(point.lower_bound_kwh <= point.upper_bound_kwh for point in result.forecasts)


def test_forecast_service_falls_back_when_prophet_raises(monkeypatch) -> None:
    settings = Settings(enable_prophet=True, prophet_min_history_points=12, forecast_horizon_months=8)
    service = ConsumptionForecastService(settings)
    series = _build_series(
        [
            ("2025-04", 280.0, 28),
            ("2025-05", 230.0, 31),
            ("2025-06", 210.0, 29),
            ("2025-07", 270.0, 32),
            ("2025-08", 240.0, 31),
            ("2025-09", 260.0, 33),
            ("2025-10", 334.0, 29),
            ("2025-11", 218.0, 29),
            ("2025-12", 301.0, 33),
            ("2026-01", 336.0, 29),
            ("2026-02", 267.0, 28),
            ("2026-03", 336.0, 32),
            ("2026-04", 252.0, 29),
        ]
    )

    def _boom(*, series, settings):  # noqa: ARG001
        raise RuntimeError("prophet failed")

    def _fallback(*, series, settings):  # noqa: ARG001
        return ForecastComputationResult(
            model_used="moving_average_linear_trend",
            explanation="fallback used",
            forecasts=[
                ForecastPointData(
                    mes_referencia="2026-05",
                    predicted_kwh=Decimal("275.000"),
                    lower_bound_kwh=Decimal("240.000"),
                    upper_bound_kwh=Decimal("310.000"),
                )
            ],
        )

    monkeypatch.setattr(service.prophet_forecaster, "generate", _boom)
    monkeypatch.setattr(service.fallback_forecaster, "generate", _fallback)

    result = service.generate(series)

    assert result.model_used == "moving_average_linear_trend"
    assert result.explanation == "fallback used"
    assert result.forecasts[0].mes_referencia == "2026-05"


def test_forecast_service_uses_monthly_safe_prophet_without_zeroed_alternating_months() -> None:
    settings = Settings(enable_prophet=True, prophet_min_history_points=12, forecast_horizon_months=8)
    service = ConsumptionForecastService(settings)
    series = _build_series(
        [
            ("2025-04", 280.0, 28),
            ("2025-05", 230.0, 31),
            ("2025-06", 210.0, 29),
            ("2025-07", 270.0, 32),
            ("2025-08", 240.0, 31),
            ("2025-09", 260.0, 33),
            ("2025-10", 334.0, 29),
            ("2025-11", 218.0, 29),
            ("2025-12", 301.0, 33),
            ("2026-01", 336.0, 29),
            ("2026-02", 267.0, 28),
            ("2026-03", 336.0, 32),
            ("2026-04", 252.0, 29),
        ]
    )

    result = service.generate(series)

    assert result.model_used == "prophet"
    assert len(result.forecasts) == 8
    assert all(point.predicted_kwh > Decimal("0") for point in result.forecasts)
    assert all(point.lower_bound_kwh <= point.predicted_kwh <= point.upper_bound_kwh for point in result.forecasts)


def test_forecast_service_marks_alternating_zero_profile_as_untrustworthy() -> None:
    settings = Settings(enable_prophet=True, prophet_min_history_points=12, forecast_horizon_months=8)
    service = ConsumptionForecastService(settings)
    series = _build_series(
        [
            ("2025-11", 218.0, 29),
            ("2025-12", 301.0, 33),
            ("2026-01", 336.0, 29),
            ("2026-02", 267.0, 28),
            ("2026-03", 336.0, 32),
            ("2026-04", 252.0, 29),
        ]
    )
    suspicious_forecasts = [
        ForecastPointData("2026-05", Decimal("0"), Decimal("0"), Decimal("0")),
        ForecastPointData("2026-06", Decimal("92"), Decimal("89"), Decimal("94")),
        ForecastPointData("2026-07", Decimal("0"), Decimal("0"), Decimal("0")),
        ForecastPointData("2026-08", Decimal("182"), Decimal("176"), Decimal("188")),
        ForecastPointData("2026-09", Decimal("0"), Decimal("0"), Decimal("0")),
        ForecastPointData("2026-10", Decimal("326"), Decimal("315"), Decimal("337")),
        ForecastPointData("2026-11", Decimal("0"), Decimal("0"), Decimal("0")),
        ForecastPointData("2026-12", Decimal("213"), Decimal("197"), Decimal("228")),
    ]

    assert service.is_forecast_trustworthy(series=series, forecasts=suspicious_forecasts) is False
