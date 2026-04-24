from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pandas as pd

from app.core.enums import BillExtractionStatus
from app.models.utility_bill import UtilityBill
from app.utils.months import month_to_timestamp, timestamp_to_reference_month


@dataclass(slots=True)
class SeriesPointCandidate:
    mes_referencia: str
    consumo_kwh: Decimal
    dias_faturados: int | None
    source: str
    confirmed_source: bool
    precedence: int


class ConsumptionSeriesResolver:
    def resolve(self, *, target_bill: UtilityBill, confirmed_bills: list[UtilityBill]) -> pd.DataFrame:
        candidates_by_month: dict[str, SeriesPointCandidate] = {}

        def add_candidate(candidate: SeriesPointCandidate) -> None:
            current = candidates_by_month.get(candidate.mes_referencia)
            if current is None or candidate.precedence < current.precedence:
                candidates_by_month[candidate.mes_referencia] = candidate

        self._add_bill_main(candidate_consumer=add_candidate, bill=target_bill, source="target_bill", precedence=0)
        self._add_bill_history(candidate_consumer=add_candidate, bill=target_bill, source="target_bill_history", precedence=1)

        for bill in confirmed_bills:
            if bill.id == target_bill.id:
                continue
            self._add_bill_main(candidate_consumer=add_candidate, bill=bill, source="confirmed_bill", precedence=2)
            self._add_bill_history(candidate_consumer=add_candidate, bill=bill, source="confirmed_bill_history", precedence=3)

        records: list[dict[str, Any]] = []
        for candidate in sorted(candidates_by_month.values(), key=lambda item: item.mes_referencia):
            avg_daily = None
            if candidate.dias_faturados and candidate.dias_faturados > 0:
                avg_daily = float(candidate.consumo_kwh / candidate.dias_faturados)
            records.append(
                {
                    "mes_referencia": candidate.mes_referencia,
                    "ds": month_to_timestamp(candidate.mes_referencia),
                    "y": float(candidate.consumo_kwh),
                    "consumo_kwh": candidate.consumo_kwh,
                    "dias_faturados": candidate.dias_faturados,
                    "avg_daily_kwh": avg_daily,
                    "source": candidate.source,
                    "confirmed_source": candidate.confirmed_source,
                }
            )

        if not records:
            return pd.DataFrame(
                columns=[
                    "mes_referencia",
                    "ds",
                    "y",
                    "consumo_kwh",
                    "dias_faturados",
                    "avg_daily_kwh",
                    "source",
                    "confirmed_source",
                ]
            )

        dataframe = pd.DataFrame(records).sort_values("ds").reset_index(drop=True)
        dataframe["mes_referencia"] = dataframe["ds"].apply(timestamp_to_reference_month)
        return dataframe

    def _add_bill_main(self, *, candidate_consumer, bill: UtilityBill, source: str, precedence: int) -> None:
        if bill.mes_referencia and bill.consumo_kwh and bill.consumo_kwh > 0:
            candidate_consumer(
                SeriesPointCandidate(
                    mes_referencia=bill.mes_referencia,
                    consumo_kwh=bill.consumo_kwh,
                    dias_faturados=bill.dias_faturados,
                    source=source,
                    confirmed_source=bill.extraction_status == BillExtractionStatus.CONFIRMED,
                    precedence=precedence,
                )
            )

    def _add_bill_history(self, *, candidate_consumer, bill: UtilityBill, source: str, precedence: int) -> None:
        for entry in bill.consumption_history:
            if entry.mes_referencia and entry.consumo_kwh and entry.consumo_kwh > 0:
                candidate_consumer(
                    SeriesPointCandidate(
                        mes_referencia=entry.mes_referencia,
                        consumo_kwh=entry.consumo_kwh,
                        dias_faturados=entry.dias_faturados,
                        source=source,
                        confirmed_source=bill.extraction_status == BillExtractionStatus.CONFIRMED,
                        precedence=precedence,
                    )
                )

