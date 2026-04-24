from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.bill import ReferenceMonth
from app.schemas.forecast import ForecastRead
from app.schemas.insight import InsightRead


class ConsumptionSeriesPoint(BaseModel):
    mes_referencia: ReferenceMonth
    consumo_kwh: Decimal
    dias_faturados: int | None = None
    avg_daily_kwh: float | None = None
    source: str
    confirmed_source: bool


class MonthVariation(BaseModel):
    current_month: ReferenceMonth
    previous_month: ReferenceMonth
    variation_pct: float


class ConsumptionExtreme(BaseModel):
    mes_referencia: ReferenceMonth
    consumo_kwh: Decimal


class ConsumptionAnomaly(BaseModel):
    mes_referencia: ReferenceMonth
    consumo_kwh: Decimal
    deviation_pct: float
    reason: str


class BillAnalyticsResponse(BaseModel):
    bill_id: UUID
    reference_month: ReferenceMonth | None = None
    history_points_used: int
    average_daily_kwh: float | None = None
    average_monthly_kwh: float | None = None
    latest_month_over_month_variation_pct: float | None = None
    month_over_month_variations: list[MonthVariation] = Field(default_factory=list)
    highest_consumption: ConsumptionExtreme | None = None
    lowest_consumption: ConsumptionExtreme | None = None
    trend_direction: Literal["up", "down", "stable", "insufficient_data"]
    trend_summary: str
    seasonality_detected: bool
    seasonality_summary: str
    anomalies: list[ConsumptionAnomaly] = Field(default_factory=list)
    insights: list[InsightRead] = Field(default_factory=list)
    series: list[ConsumptionSeriesPoint] = Field(default_factory=list)


class BillForecastResponse(BaseModel):
    bill_id: UUID
    reference_month: ReferenceMonth | None = None
    model_used: str
    horizon_months: int
    history_points_used: int
    explanation: str
    reference_tariff_brl_per_kwh: Decimal | None = None
    generated_forecasts: list[ForecastRead] = Field(default_factory=list)
    insights: list[InsightRead] = Field(default_factory=list)
