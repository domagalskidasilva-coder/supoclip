import hashlib
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.ai import TRANSCRIPT_ANALYSIS_CACHE_VERSION
from src.config import Config
from src.services.task_service import TaskService


@pytest.mark.asyncio
async def test_create_task_with_source_creates_queued_task(monkeypatch):
    service = TaskService(db=AsyncMock())
    service.source_repo.create_source = AsyncMock(return_value="source-1")
    service.task_repo.create_task = AsyncMock(return_value="task-1")
    monkeypatch.setattr(
        service.video_service,
        "determine_source_type",
        lambda _url: "youtube",
    )
    service.video_service.get_video_title = AsyncMock(return_value="Seeded title")

    task_id = await service.create_task_with_source(
        url="https://www.youtube.com/watch?v=demo",
    )

    assert task_id == "task-1"
    service.source_repo.create_source.assert_awaited_once_with(
        service.db,
        source_type="youtube",
        title="Seeded title",
        url="https://www.youtube.com/watch?v=demo",
    )
    service.task_repo.create_task.assert_awaited_once()


def build_clip_result() -> dict:
    return {
        "filename": "clip-1.mp4",
        "path": "/tmp/clip-1.mp4",
        "start_time": "00:00",
        "end_time": "00:10",
        "duration": 10.0,
        "text": "Hook text",
        "relevance_score": 0.95,
        "reasoning": "Strong hook",
    }


def build_task_service() -> TaskService:
    config = Config()
    config.app_base_url = "http://localhost:3107"
    service = TaskService(db=AsyncMock(), config=config)
    service.cache_repo.get_cache = AsyncMock(return_value=None)
    service.cache_repo.upsert_cache = AsyncMock()
    service.task_repo.update_task_runtime_metadata = AsyncMock()
    service.task_repo.update_task_status = AsyncMock()
    service.task_repo.update_task_clips = AsyncMock()
    service.clip_repo.create_clip = AsyncMock(return_value="clip-1")
    service.video_service.create_single_clip = AsyncMock(return_value=build_clip_result())
    service.video_service.process_video_complete = AsyncMock(
        return_value={
            "clips": [build_clip_result()],
            "segments_to_render": [{"start": 0, "end": 10}],
            "video_path": "/tmp/source.mp4",
            "segments": [],
            "summary": None,
            "key_topics": [],
            "transcript": "Transcript",
            "analysis_json": "{}",
        }
    )
    return service


def build_queued_task(task_id: str = "task-1") -> dict:
    stale_time = datetime.utcnow() - timedelta(seconds=300)
    return {
        "id": task_id,
        "status": "queued",
        "created_at": stale_time,
        "updated_at": stale_time,
        "source_id": "source-1",
    }


class _PendingJobRedis:
    def __init__(self, *_args, **_kwargs):
        pass

    async def zrange(self, _key, _start, _end):
        return [b"job-1"]

    async def get(self, _key):
        return b"\x80\x04process_video_task task-1"

    async def close(self):
        pass


class _EmptyQueueRedis:
    def __init__(self, *_args, **_kwargs):
        pass

    async def zrange(self, _key, _start, _end):
        return []

    async def close(self):
        pass


def test_cache_key_includes_analysis_prompt_version():
    url = "https://www.youtube.com/watch?v=demo"
    cache_key = TaskService._build_cache_key(
        url,
        "youtube",
        "fast",
    )
    expected = hashlib.sha256(
        f"youtube|fast|{TRANSCRIPT_ANALYSIS_CACHE_VERSION}|{url}".encode("utf-8")
    ).hexdigest()

    assert cache_key == expected


def test_cache_key_includes_requested_clip_duration():
    url = "https://www.youtube.com/watch?v=demo"
    cache_key = TaskService._build_cache_key(
        url,
        "youtube",
        "fast",
        clip_duration=45,
    )
    expected = hashlib.sha256(
        f"youtube|fast|{TRANSCRIPT_ANALYSIS_CACHE_VERSION}|duration=45|{url}".encode("utf-8")
    ).hexdigest()

    assert cache_key == expected


@pytest.mark.asyncio
async def test_get_task_keeps_stale_queued_task_when_job_is_still_pending(monkeypatch):
    service = build_task_service()
    service.config.queued_task_timeout_seconds = 180
    queued_task = build_queued_task()
    refreshed_task = {
        **queued_task,
        "progress_message": "Aguardando worker disponível.",
    }
    service.task_repo.get_task_by_id = AsyncMock(
        side_effect=[queued_task, refreshed_task]
    )
    service.clip_repo.get_clips_by_task = AsyncMock(return_value=[])
    service._load_task_source_settings = AsyncMock(return_value={})
    monkeypatch.setattr("src.services.task_service.redis.Redis", _PendingJobRedis)

    task = await service.get_task_with_clips("task-1")

    assert task["status"] == "queued"
    service.task_repo.update_task_status.assert_awaited_once()
    assert service.task_repo.update_task_status.await_args.args[2] == "queued"
    assert "Aguardando worker" in service.task_repo.update_task_status.await_args.kwargs[
        "progress_message"
    ]


@pytest.mark.asyncio
async def test_get_task_marks_stale_queued_task_error_when_job_is_missing(monkeypatch):
    service = build_task_service()
    service.config.queued_task_timeout_seconds = 180
    queued_task = build_queued_task()
    errored_task = {
        **queued_task,
        "status": "error",
        "progress_message": "A geração expirou esperando na fila.",
    }
    service.task_repo.get_task_by_id = AsyncMock(side_effect=[queued_task, errored_task])
    service.clip_repo.get_clips_by_task = AsyncMock(return_value=[])
    service._load_task_source_settings = AsyncMock(return_value={})
    monkeypatch.setattr("src.services.task_service.redis.Redis", _EmptyQueueRedis)

    task = await service.get_task_with_clips("task-1")

    assert task["status"] == "error"
    service.task_repo.update_task_status.assert_awaited_once()
    assert service.task_repo.update_task_status.await_args.args[2] == "error"


@pytest.mark.asyncio
async def test_process_task_renders_fallback_when_no_clip_segments_are_selected(monkeypatch):
    service = build_task_service()
    service.config.clip_duration = 30
    monkeypatch.setattr(service.video_service, "_get_file_duration", lambda _path: 42.0)
    service.video_service.process_video_complete = AsyncMock(
        return_value={
            "clips": [],
            "segments_to_render": [],
            "video_path": "/tmp/source.mp4",
            "segments": [],
            "summary": None,
            "key_topics": [],
            "transcript": "Transcript",
            "analysis_json": '{"most_relevant_segments":[]}',
        }
    )

    result = await service.process_task(
        task_id="task-1",
        url="https://www.youtube.com/watch?v=demo",
        source_type="youtube",
    )

    assert result["clips_count"] == 1
    fallback_segment = service.video_service.create_single_clip.await_args.args[1]
    assert fallback_segment["start_time"] == "00:00"
    assert fallback_segment["end_time"] == "00:30"
    assert fallback_segment["hook_type"] == "fallback"
    service.cache_repo.upsert_cache.assert_awaited_once()
    cached_analysis = json.loads(
        service.cache_repo.upsert_cache.await_args.kwargs["analysis_json"]
    )
    assert cached_analysis["most_relevant_segments"][0]["hook_type"] == "fallback"


@pytest.mark.asyncio
async def test_process_task_renders_fallback_when_selected_segments_fail(monkeypatch):
    service = build_task_service()
    service.config.clip_duration = 30
    monkeypatch.setattr(service.video_service, "_get_file_duration", lambda _path: 42.0)
    service.video_service.create_single_clip = AsyncMock(
        side_effect=[
            None,
            {
                **build_clip_result(),
                "filename": "fallback.mp4",
                "path": "/tmp/fallback.mp4",
            },
        ]
    )

    result = await service.process_task(
        task_id="task-1",
        url="https://www.youtube.com/watch?v=demo",
        source_type="youtube",
    )

    assert result["clips_count"] == 1
    assert result["segments"][0]["hook_type"] == "fallback"
    fallback_call = service.video_service.create_single_clip.await_args_list[1]
    assert fallback_call.args[1]["hook_type"] == "fallback"
    assert fallback_call.args[10]["cut_long_pauses"] is False
    assert service.clip_repo.create_clip.await_args.kwargs["filename"] == "fallback.mp4"


@pytest.mark.asyncio
async def test_process_task_keeps_generated_clips_standalone():
    service = build_task_service()
    service.video_service.create_single_clip = AsyncMock(
        side_effect=[
            {
                **build_clip_result(),
                "filename": "clip-1.mp4",
                "path": "/tmp/clip-1.mp4",
                "duration": 10.0,
            },
            {
                **build_clip_result(),
                "filename": "clip-2.mp4",
                "path": "/tmp/clip-2.mp4",
                "start_time": "00:10",
                "end_time": "00:20",
                "duration": 10.0,
            },
        ]
    )
    service.video_service.process_video_complete = AsyncMock(
        return_value={
            "clips": [build_clip_result(), build_clip_result()],
            "segments_to_render": [
                {"start_time": "00:00", "end_time": "00:10"},
                {"start_time": "00:10", "end_time": "00:20"},
            ],
            "video_path": "/tmp/source.mp4",
            "segments": [],
            "summary": None,
            "key_topics": [],
            "transcript": "Transcript",
            "analysis_json": "{}",
        }
    )

    result = await service.process_task(
        task_id="task-1",
        url="https://www.youtube.com/watch?v=demo",
        source_type="youtube",
        clip_duration=45,
    )

    assert service.video_service.process_video_complete.await_args.kwargs[
        "clip_duration"
    ] == 45
    assert result["clips_count"] == 2
    saved_paths = [
        call.kwargs["file_path"]
        for call in service.clip_repo.create_clip.await_args_list
    ]
    assert saved_paths == ["/tmp/clip-1.mp4", "/tmp/clip-2.mp4"]


@pytest.mark.asyncio
async def test_completion_notifications_are_disabled_for_local_mode():
    service = build_task_service()
    service.task_repo.get_task_notification_context = AsyncMock()
    service.task_repo.mark_completion_notification_sent = AsyncMock()

    await service._send_completion_notification_if_needed(
        task_id="task-1",
        clips_count=1,
    )

    service.task_repo.get_task_notification_context.assert_not_called()
    service.task_repo.mark_completion_notification_sent.assert_not_called()
