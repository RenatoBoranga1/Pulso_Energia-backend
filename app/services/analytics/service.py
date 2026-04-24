from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pandas as pd
from fastapi import status
from sqlalchemy.orm import Session

from app.core.enums import BillExtractionStatus
from app.core.config import Settings
from app.core.errors import AppError
from app.models.forecast import Forecast
from app.models.insight import Insight
from app.repositories.forecast_repository import ForecastRepository
from app.repositories.insight_repository import InsightRepository
from app.repositories.utility_bill_repository import UtilityBillRepository
from app.schemas.analytics import BillAnalyticsResponse, BillForecastResponse, ConsumptionSeriesPoint
from app.schemas.forecast import ForecastRead
from app.schemas.insight import InsightRead
from app.services.analytics.calculator import ConsumptionAnalyticsCalculator
from app.services.analytics.insight_builder import ConsumptionInsightBuilder
from app.services.analytics.series_resolver import ConsumptionSeriesResolver
from app.services.forecasting.service import ConsumptionForecastService


class BillAnalyticsService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.bill_repository = UtilityBillRepository(session)
        self.forecast_repository = ForecastRepository(session)
        self.insight_repository = InsightRepository(session)
        self.series_resolver = ConsumptionSeriesResolver()
        self.analytics_calculator = ConsumptionAnalyticsCalculator()
        self.forecast_service = ConsumptionForecastService(settings)
        self.insight_builder = ConsumptionInsightBuilder()

    def get_analytics(self, *, bill_id: UUID, current_user_id: UUID) -> BillAnalyticsResponse:
        bill = self._load_confirmed_bill(bill_id=bill_id, current_user_id=current_user_id)
        series = self._resolve_series(bill)
        analytics = self.analytics_calculator.calculate(series)
        _, persisted_insights, _ = self._ensure_artifacts(bill=bill, series=series, analytics=analytics)

        return BillAnalyticsResponse(
            bill_id=bill.id,
            reference_month=bill.mes_referencia,
            history_points_used=analytics.history_points_used,
            average_daily_kwh=analytics.average_daily_kwh,
            average_monthly_kwh=analytics.average_monthly_kwh,
            latest_month_over_month_variation_pct=analytics.latest_month_over_month_variation_pct,
            month_over_month_variations=analytics.month_over_month_variations,
            highest_consumption=analytics.highest_consumption,
            lowest_consumption=analytics.lowest_consumption,
            trend_direction=analytics.trend_direction,
            trend_summary=analytics.trend_summary,
            seasonality_detected=analytics.seasonality_detected,
            seasonality_summary=analytics.seasonality_summary,
            anomalies=analytics.anomalies,
            insights=[InsightRead.model_validate(item) for item in persisted_insights],
            series=[
                ConsumptionSeriesPoint(
                    mes_referencia=str(row["mes_referencia"]),
                    consumo_kwh=Decimal(str(row["consumo_kwh"])),
                    dias_faturados=None if pd.isna(row["dias_faturados"]) else int(row["dias_faturados"]),
                    avg_daily_kwh=None if pd.isna(row["avg_daily_kwh"]) else float(row["avg_daily_kwh"]),
                    source=str(row["source"]),
                    confirmed_source=bool(row["confirmed_source"]),
                )
                for _, row in series.iterrows()
            ],
        )

    def get_forecast(self, *, bill_id: UUID, current_user_id: UUID) -> BillForecastResponse:
        bill = self._load_confirmed_bill(bill_id=bill_id, current_user_id=current_user_id)
        series = self._resolve_series(bill)
        analytics = self.analytics_calculator.calculate(series)
        confirmed_bills = self.bill_repository.list_confirmed_by_user_id(bill.user_id)
        persisted_forecasts, persisted_insights, explanation = self._ensure_artifacts(
            bill=bill,
            series=series,
            analytics=analytics,
        )

        model_used = persisted_forecasts[0].model_used if persisted_forecasts else "unavailable"
        reference_tariff = self._resolve_reference_tariff_brl_per_kwh(target_bill=bill, confirmed_bills=confirmed_bills)
        return BillForecastResponse(
            bill_id=bill.id,
            reference_month=bill.mes_referencia,
            model_used=model_used,
            horizon_months=self.settings.forecast_horizon_months,
            history_points_used=analytics.history_points_used,
            explanation=explanation,
            reference_tariff_brl_per_kwh=reference_tariff,
            generated_forecasts=[
                ForecastRead(
                    id=item.id,
                    bill_id=item.bill_id,
                    mes_referencia=item.mes_referencia,
                    predicted_kwh=item.predicted_kwh,
                    lower_bound_kwh=item.lower_bound_kwh,
                    upper_bound_kwh=item.upper_bound_kwh,
                    estimated_value_brl=self._estimate_value(item.predicted_kwh, reference_tariff),
                    lower_bound_value_brl=self._estimate_value(item.lower_bound_kwh, reference_tariff),
                    upper_bound_value_brl=self._estimate_value(item.upper_bound_kwh, reference_tariff),
                    model_used=item.model_used,
                    created_at=item.created_at,
                )
                for item in persisted_forecasts
            ],
            insights=[InsightRead.model_validate(item) for item in persisted_insights],
        )

    def refresh_artifacts_for_bill(self, *, bill_id: UUID, current_user_id: UUID) -> None:
        bill = self._load_confirmed_bill(bill_id=bill_id, current_user_id=current_user_id)
        series = self._resolve_series(bill)
        analytics = self.analytics_calculator.calculate(series)
        self._rebuild_and_persist_artifacts(bill=bill, series=series, analytics=analytics)

    def _ensure_artifacts(self, *, bill, series, analytics):
        existing_forecasts = self.forecast_repository.list_by_bill_id(bill.id)
        existing_insights = self.insight_repository.list_by_bill_id(bill.id)
        if (
            len(existing_forecasts) == self.settings.forecast_horizon_months
            and existing_insights
            and self.forecast_service.is_forecast_trustworthy(series=series, forecasts=existing_forecasts)
        ):
            explanation = (
                f"Previsao persistida com o metodo '{existing_forecasts[0].model_used}'. "
                "Os resultados continuam validos porque os artefatos derivados sao invalidados sempre que a conta e reextraida ou reconfirmada."
            )
            return existing_forecasts, existing_insights, explanation

        return self._rebuild_and_persist_artifacts(bill=bill, series=series, analytics=analytics)

    def _rebuild_and_persist_artifacts(self, *, bill, series, analytics) -> tuple[list[Forecast], list[Insight], str]:
        forecast_result = self.forecast_service.generate(series)
        insight_models = self.insight_builder.build(series=series, analytics=analytics, forecast=forecast_result)
        forecast_models = [
            Forecast(
                mes_referencia=item.mes_referencia,
                predicted_kwh=item.predicted_kwh,
                lower_bound_kwh=item.lower_bound_kwh,
                upper_bound_kwh=item.upper_bound_kwh,
                model_used=forecast_result.model_used,
            )
            for item in forecast_result.forecasts
        ]

        self.forecast_repository.replace_for_bill(bill_id=bill.id, forecasts=forecast_models)
        self.insight_repository.replace_for_bill(bill_id=bill.id, insights=insight_models)
        self.session.commit()

        persisted_forecasts = self.forecast_repository.list_by_bill_id(bill.id)
        persisted_insights = self.insight_repository.list_by_bill_id(bill.id)
        return persisted_forecasts, persisted_insights, forecast_result.explanation

    def _load_confirmed_bill(self, *, bill_id: UUID, current_user_id: UUID):
        bill = self.bill_repository.get_by_id_for_user(bill_id, current_user_id)
        if bill is None:
            raise AppError("Bill not found.", code="bill_not_found", status_code=status.HTTP_404_NOT_FOUND)
        if bill.extraction_status != BillExtractionStatus.CONFIRMED:
            raise AppError(
                "Bill must be confirmed before analytics or forecasting can be generated.",
                code="bill_not_confirmed",
                status_code=status.HTTP_409_CONFLICT,
            )
        return bill

    def _resolve_series(self, bill):
        confirmed_bills = self.bill_repository.list_confirmed_by_user_id(bill.user_id)
        return self.series_resolver.resolve(target_bill=bill, confirmed_bills=confirmed_bills)

    def _resolve_reference_tariff_brl_per_kwh(self, *, target_bill, confirmed_bills) -> Decimal | None:
        target_rate = self._extract_tariff(target_bill)
        if target_rate is not None:
            return target_rate

        historical_rates = [rate for rate in (self._extract_tariff(item) for item in confirmed_bills) if rate is not None]
        if not historical_rates:
            return None

        average_rate = sum(historical_rates, Decimal("0")) / Decimal(len(historical_rates))
        return average_rate.quantize(Decimal("0.0001"))

    def _extract_tariff(self, bill) -> Decimal | None:
        if not bill.valor_total or not bill.consumo_kwh or bill.consumo_kwh <= 0:
            return None
        return (bill.valor_total / bill.consumo_kwh).quantize(Decimal("0.0001"))

    def _estimate_value(self, consumption_kwh: Decimal, tariff_brl_per_kwh: Decimal | None) -> Decimal | None:
        if tariff_brl_per_kwh is None:
            return None
        return (consumption_kwh * tariff_brl_per_kwh).quantize(Decimal("0.01"))
