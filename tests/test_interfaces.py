import inspect

from backend.analyzers.base import (
    AudioAnalyzer,
    CarouselAnalyzer,
    ImageAnalyzer,
    TextAnalyzer,
    VideoAnalyzer,
)
from backend.connectors.base import BaseConnector
from backend.generators.base import CopyGenerator, ImageGenerator, VideoGenerator
from backend.jobs.base import InlineJobExecutor, Job, JobExecutor, JobStatus
from backend.rules_engine.engine import RulesEngine


def test_base_interfaces_import_as_abstract_contracts() -> None:
    interfaces = (
        BaseConnector,
        VideoAnalyzer,
        ImageAnalyzer,
        AudioAnalyzer,
        TextAnalyzer,
        CarouselAnalyzer,
        ImageGenerator,
        VideoGenerator,
        CopyGenerator,
        JobExecutor,
    )

    assert all(inspect.isabstract(interface) for interface in interfaces)
    assert isinstance(RulesEngine(), RulesEngine)


def test_inline_job_executor_uses_queue_neutral_states() -> None:
    job = Job(name="multiply", payload={"value": 4})
    completed = InlineJobExecutor().submit(
        job,
        lambda payload: payload["value"] * 2,
    )

    assert completed.status is JobStatus.COMPLETED
    assert completed.result == 8
    assert completed.started_at is not None
    assert completed.finished_at is not None
