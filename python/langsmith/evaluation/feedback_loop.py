"""Feedback loop utilities for LangSmith evaluation.

This module provides the FeedbackLoop context manager, which wraps a LangSmith
evaluator run and enables automated tagging of low-scoring runs and firing
user-supplied callbacks without requiring manual UI inspection.

Motivation
----------
After running ``evaluate()`` or a custom evaluator on a dataset, the typical
workflow requires a human to:

1. Open the LangSmith UI.
2. Filter runs by score.
3. Manually apply tags or labels.
4. Kick off a corrective action (prompt update, re-run, alert, etc.).

``FeedbackLoop`` closes this gap programmatically so that the trace →
eval-score → corrective-action cycle can be automated in CI or nightly
pipelines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Union

from langsmith.evaluation.evaluator import EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class FeedbackLoopConfig:
    """Configuration for a FeedbackLoop.

    Parameters
    ----------
    threshold:
        Runs whose score is *strictly below* this value are considered
        low-quality and will trigger the ``on_failure`` callback and/or
        be tagged with ``failure_tag``.  Defaults to ``0.5``.
    failure_tag:
        Label applied to runs that fall below ``threshold`` via
        ``client.create_feedback``.  Set to ``None`` to skip tagging.
        Defaults to ``"needs-review"``.
    on_failure:
        Optional callable invoked for each low-scoring
        ``EvaluationResult``.  Receives the result as its only argument.
        Useful for sending alerts, logging to external systems, or
        triggering prompt-update pipelines.
    on_success:
        Optional callable invoked for each high-scoring
        ``EvaluationResult`` (i.e., score >= threshold).  Receives the
        result as its only argument.
    webhook_url:
        If provided, a lightweight HTTP POST is fired to this URL for
        every low-scoring result.  The payload is a JSON-serialisable
        dict with keys ``run_id``, ``key``, ``score``, and ``comment``.
        Requires ``httpx`` (already a dependency of langsmith).
    """

    threshold: float = 0.5
    failure_tag: Optional[str] = "needs-review"
    on_failure: Optional[Callable[[EvaluationResult], None]] = None
    on_success: Optional[Callable[[EvaluationResult], None]] = None
    webhook_url: Optional[str] = None


@dataclass
class FeedbackLoopSummary:
    """Summary returned by :class:`FeedbackLoop` after processing results.

    Attributes
    ----------
    total:
        Total number of ``EvaluationResult`` objects processed.
    failures:
        Number of results whose score fell below the configured threshold.
    successes:
        Number of results whose score met or exceeded the threshold.
    skipped:
        Number of results that were skipped because their score was
        ``None`` (non-numeric feedback).
    tagged_run_ids:
        Set of run IDs that received the failure tag.
    """

    total: int = 0
    failures: int = 0
    successes: int = 0
    skipped: int = 0
    tagged_run_ids: set = field(default_factory=set)


class FeedbackLoop:
    """Programmatically close the eval → feedback → action loop.

    ``FeedbackLoop`` wraps a sequence of :class:`EvaluationResult` objects
    returned by ``evaluate()`` (or any custom evaluator) and:

    * applies a ``failure_tag`` to runs whose score is below ``threshold``
      via ``client.create_feedback``,
    * fires an optional ``on_failure`` callback per low-scoring result,
    * fires an optional ``on_success`` callback per high-scoring result,
    * optionally POSTs a JSON payload to a ``webhook_url`` for each failure.

    Usage
    -----
    .. code-block:: python

        import langsmith
        from langsmith.evaluation import evaluate
        from langsmith.evaluation.feedback_loop import FeedbackLoop, FeedbackLoopConfig

        client = langsmith.Client()

        results = evaluate(
            my_pipeline,
            data="my-dataset",
            evaluators=[correctness_evaluator],
        )

        def handle_failure(result):
            print(f"Low score on run {result.source_run_id}: {result.score}")

        loop = FeedbackLoop(
            client=client,
            config=FeedbackLoopConfig(
                threshold=0.7,
                failure_tag="needs-review",
                on_failure=handle_failure,
            ),
        )
        summary = loop.process(results.results)
        print(summary)

    Parameters
    ----------
    client:
        An initialised :class:`langsmith.Client` instance.  The client is
        used to persist feedback tags to LangSmith.
    config:
        A :class:`FeedbackLoopConfig` instance.  If omitted, defaults are
        used (threshold=0.5, failure_tag="needs-review").
    """

    def __init__(
        self,
        client: object,
        config: Optional[FeedbackLoopConfig] = None,
    ) -> None:
        self._client = client
        self._config = config or FeedbackLoopConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        results: Sequence[EvaluationResult],
    ) -> FeedbackLoopSummary:
        """Process a sequence of evaluation results.

        For each result:

        * If ``score`` is ``None``, the result is skipped (non-numeric
          feedback cannot be compared to a numeric threshold).
        * If ``score < threshold``, the failure path is triggered.
        * Otherwise, the success path is triggered.

        Parameters
        ----------
        results:
            An iterable of :class:`EvaluationResult` objects, typically
            obtained from ``ExperimentResults.results`` after calling
            ``evaluate()``.

        Returns
        -------
        FeedbackLoopSummary
            A dataclass summarising how many results were processed,
            how many triggered failures, and which run IDs were tagged.
        """
        summary = FeedbackLoopSummary()

        for result in results:
            summary.total += 1

            if result.score is None:
                logger.debug(
                    "Skipping result for key '%s' (score is None).", result.key
                )
                summary.skipped += 1
                continue

            if result.score < self._config.threshold:
                self._handle_failure(result, summary)
            else:
                self._handle_success(result, summary)

        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_failure(
        self,
        result: EvaluationResult,
        summary: FeedbackLoopSummary,
    ) -> None:
        summary.failures += 1

        # 1. Apply the failure tag via create_feedback
        if self._config.failure_tag and result.source_run_id is not None:
            try:
                self._client.create_feedback(  # type: ignore[union-attr]
                    run_id=result.source_run_id,
                    key=self._config.failure_tag,
                    score=0,
                    comment=(
                        f"Auto-tagged by FeedbackLoop: score {result.score:.4f} "
                        f"below threshold {self._config.threshold}."
                    ),
                )
                summary.tagged_run_ids.add(result.source_run_id)
                logger.info(
                    "Tagged run %s with '%s' (score=%.4f).",
                    result.source_run_id,
                    self._config.failure_tag,
                    result.score,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to tag run %s: %s", result.source_run_id, exc
                )

        # 2. Fire on_failure callback
        if self._config.on_failure is not None:
            try:
                self._config.on_failure(result)
            except Exception as exc:  # noqa: BLE001
                logger.warning("on_failure callback raised: %s", exc)

        # 3. Fire webhook
        if self._config.webhook_url is not None:
            self._post_webhook(result)

    def _handle_success(
        self,
        result: EvaluationResult,
        summary: FeedbackLoopSummary,
    ) -> None:
        summary.successes += 1

        if self._config.on_success is not None:
            try:
                self._config.on_success(result)
            except Exception as exc:  # noqa: BLE001
                logger.warning("on_success callback raised: %s", exc)

    def _post_webhook(self, result: EvaluationResult) -> None:
        """Fire a lightweight HTTP POST to the configured webhook URL."""
        try:
            import httpx  # httpx is already a dependency of langsmith

            payload = {
                "run_id": str(result.source_run_id),
                "key": result.key,
                "score": result.score,
                "comment": result.comment,
            }
            response = httpx.post(self._config.webhook_url, json=payload, timeout=5.0)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Webhook POST to %s failed: %s", self._config.webhook_url, exc)


__all__ = [
    "FeedbackLoop",
    "FeedbackLoopConfig",
    "FeedbackLoopSummary",
]
