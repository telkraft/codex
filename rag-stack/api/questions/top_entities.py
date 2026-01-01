"""
Top Entities Question
=====================

"En çok gelen ..." tipi sorular için soru handler'ı.

Bu katman:
- intent_router.parse_top_entities_question → TopEntitiesQuestion üretir
- mvp_orchestrator → bu handler'ı çağırır
- LRSQueryService → gerçek sayım ve örnek kayıtları üretir
"""

from __future__ import annotations

from typing import Any, Dict, List

from models import TopEntitiesQuestion
from services.lrs_service import LRSQueryService


class TopEntitiesQuestionHandler:
    """
    Tek bir TopEntitiesQuestion örneğini uçtan uca çalıştırır:

    - LRSQueryService.answer_top_entities_question(question)
    - LRSQueryService.get_examples_for_top_entities(question, rows, limit)

    Sonuç olarak:
      {
        "result": {...},    # LRS'in top_entities_overall çıktısı (rows + meta)
        "examples": [...],  # İlgili xAPI örnek kayıtları
      }
    döner.
    """

    def __init__(self, question: TopEntitiesQuestion) -> None:
        self.question = question

    def run(
        self,
        lrs: LRSQueryService,
        example_limit: int = 5,
        with_examples: bool = True,
    ) -> Dict[str, Any]:
        # 1) Asıl istatistik
        result = lrs.answer_top_entities_question(self.question)

        # 2) Gerekirse örnek xAPI kayıtları
        examples: List[Dict[str, Any]] = []
        if with_examples:
            rows = result.get("rows", []) or []
            examples = lrs.get_examples_for_top_entities(
                question=self.question,
                rows=rows,
                limit=example_limit,
            )

        return {
            "result": result,
            "examples": examples,
        }


def answer_top_entities_question(
    lrs: LRSQueryService,
    question: TopEntitiesQuestion,
    example_limit: int = 5,
    with_examples: bool = True,
) -> Dict[str, Any]:
    """
    Fonksiyonel API tercih eden kodlar için kısayol.

    Örneğin mvp_orchestrator içinde:

        teq = parse_top_entities_question(user_query)
        if teq is not None:
            out = answer_top_entities_question(lrs_service, teq, example_limit=5)
            result = out["result"]
            examples = out["examples"]
            rows = result.get("rows", [])
            ...

    şeklinde kullanılabilir.
    """
    handler = TopEntitiesQuestionHandler(question)
    return handler.run(
        lrs=lrs,
        example_limit=example_limit,
        with_examples=with_examples,
    )
