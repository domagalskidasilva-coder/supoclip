"""
Clip repository - handles all database operations for generated clips.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

# Viral scorecard columns (0-10 subscores + 0-100 overall) added in
# migration 20260703_0002_viral_scorecard.sql.
SCORECARD_INT_COLUMNS = (
    "retention_score",
    "emotion_score",
    "clarity_score",
    "pacing_score",
    "payoff_score",
    "loop_score",
    "standalone_context_score",
    "overall_score",
)


def _parse_hashtags(raw: Any) -> List[str]:
    """Decode the suggested_hashtags TEXT column back into a list."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return [item.strip() for item in str(raw).split(",") if item.strip()]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return []


def _scorecard_row_fields(row: Any) -> Dict[str, Any]:
    """Extract scorecard columns from a row, tolerating older schemas."""
    fields: Dict[str, Any] = {}
    for column in SCORECARD_INT_COLUMNS:
        fields[column] = getattr(row, column, 0) or 0
    fields["suggested_title"] = getattr(row, "suggested_title", None) or ""
    fields["suggested_description"] = getattr(row, "suggested_description", None) or ""
    fields["hashtags"] = _parse_hashtags(getattr(row, "suggested_hashtags", None))
    return fields


class ClipRepository:
    """Repository for clip-related database operations."""

    @staticmethod
    async def create_clip(
        db: AsyncSession,
        task_id: str,
        filename: str,
        file_path: str,
        start_time: str,
        end_time: str,
        duration: float,
        text: str,
        relevance_score: float,
        reasoning: str,
        clip_order: int,
        virality_score: int = 0,
        hook_score: int = 0,
        engagement_score: int = 0,
        value_score: int = 0,
        shareability_score: int = 0,
        hook_type: Optional[str] = None,
        scorecard: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new clip record and return its ID.

        ``scorecard`` may carry the viral scorecard fields (retention_score,
        emotion_score, clarity_score, pacing_score, payoff_score, loop_score,
        standalone_context_score, overall_score) plus post metadata
        (suggested_title, suggested_description, hashtags list).
        """
        scorecard = scorecard or {}
        scorecard_params: Dict[str, Any] = {
            column: int(scorecard.get(column) or 0) for column in SCORECARD_INT_COLUMNS
        }
        scorecard_params["suggested_title"] = (
            str(scorecard.get("suggested_title") or "")[:300] or None
        )
        scorecard_params["suggested_description"] = (
            str(scorecard.get("suggested_description") or "") or None
        )
        hashtags = scorecard.get("hashtags") or []
        scorecard_params["suggested_hashtags"] = (
            json.dumps(list(hashtags), ensure_ascii=False) if hashtags else None
        )
        try:
            result = await db.execute(
                sa_text("""
                    INSERT INTO generated_clips
                    (task_id, filename, file_path, start_time, end_time, duration,
                     text, relevance_score, reasoning, clip_order,
                     virality_score, hook_score, engagement_score, value_score, shareability_score, hook_type,
                     retention_score, emotion_score, clarity_score, pacing_score,
                     payoff_score, loop_score, standalone_context_score, overall_score,
                     suggested_title, suggested_description, suggested_hashtags,
                     created_at)
                    VALUES
                    (:task_id, :filename, :file_path, :start_time, :end_time, :duration,
                     :text, :relevance_score, :reasoning, :clip_order,
                     :virality_score, :hook_score, :engagement_score, :value_score, :shareability_score, :hook_type,
                     :retention_score, :emotion_score, :clarity_score, :pacing_score,
                     :payoff_score, :loop_score, :standalone_context_score, :overall_score,
                     :suggested_title, :suggested_description, :suggested_hashtags,
                     NOW())
                    RETURNING id
                """),
                {
                    "task_id": task_id,
                    "filename": filename,
                    "file_path": file_path,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "text": text,
                    "relevance_score": relevance_score,
                    "reasoning": reasoning,
                    "clip_order": clip_order,
                    "virality_score": virality_score,
                    "hook_score": hook_score,
                    "engagement_score": engagement_score,
                    "value_score": value_score,
                    "shareability_score": shareability_score,
                    "hook_type": hook_type,
                    **scorecard_params,
                },
            )
        except Exception:
            await db.rollback()
            result = await db.execute(
                sa_text("""
                    INSERT INTO generated_clips
                    (task_id, filename, file_path, start_time, end_time, duration,
                     text, relevance_score, reasoning, clip_order, created_at)
                    VALUES
                    (:task_id, :filename, :file_path, :start_time, :end_time, :duration,
                     :text, :relevance_score, :reasoning, :clip_order, NOW())
                    RETURNING id
                """),
                {
                    "task_id": task_id,
                    "filename": filename,
                    "file_path": file_path,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "text": text,
                    "relevance_score": relevance_score,
                    "reasoning": reasoning,
                    "clip_order": clip_order,
                },
            )
        clip_id = result.scalar()
        if not clip_id:
            raise RuntimeError("Failed to create clip: no ID returned")
        logger.debug(f"Created clip {clip_id} for task {task_id}")
        return str(clip_id)

    @staticmethod
    async def get_clips_by_task(db: AsyncSession, task_id: str) -> List[Dict[str, Any]]:
        """Get all clips for a specific task, ordered by clip_order."""
        try:
            result = await db.execute(
                sa_text("""
                    SELECT id, filename, file_path, start_time, end_time, duration,
                           text, relevance_score, reasoning, clip_order, created_at,
                           virality_score, hook_score, engagement_score, value_score, shareability_score, hook_type,
                           retention_score, emotion_score, clarity_score, pacing_score,
                           payoff_score, loop_score, standalone_context_score, overall_score,
                           suggested_title, suggested_description, suggested_hashtags
                    FROM generated_clips
                    WHERE task_id = :task_id
                    ORDER BY clip_order ASC
                """),
                {"task_id": task_id},
            )
        except Exception:
            await db.rollback()
            result = await db.execute(
                sa_text("""
                    SELECT id, filename, file_path, start_time, end_time, duration,
                           text, relevance_score, reasoning, clip_order, created_at
                    FROM generated_clips
                    WHERE task_id = :task_id
                    ORDER BY clip_order ASC
                """),
                {"task_id": task_id},
            )

        clips = []
        for row in result.fetchall():
            clips.append(
                {
                    "id": row.id,
                    "filename": row.filename,
                    "file_path": row.file_path,
                    "start_time": row.start_time,
                    "end_time": row.end_time,
                    "duration": row.duration,
                    "text": row.text,
                    "relevance_score": row.relevance_score,
                    "reasoning": row.reasoning,
                    "clip_order": row.clip_order,
                    "created_at": row.created_at.isoformat(),
                    "video_url": f"/tasks/{task_id}/clips/{row.id}/file",
                    "virality_score": getattr(row, "virality_score", 0) or 0,
                    "hook_score": getattr(row, "hook_score", 0) or 0,
                    "engagement_score": getattr(row, "engagement_score", 0) or 0,
                    "value_score": getattr(row, "value_score", 0) or 0,
                    "shareability_score": getattr(row, "shareability_score", 0) or 0,
                    "hook_type": getattr(row, "hook_type", None),
                    **_scorecard_row_fields(row),
                }
            )

        return clips

    @staticmethod
    async def get_clips_count(db: AsyncSession, task_id: str) -> int:
        """Get the count of clips for a task."""
        result = await db.execute(
            sa_text(
                "SELECT COUNT(*) as count FROM generated_clips WHERE task_id = :task_id"
            ),
            {"task_id": task_id},
        )
        return result.scalar()

    @staticmethod
    async def delete_clips_by_task(db: AsyncSession, task_id: str) -> int:
        """Delete all clips for a task. Returns count of deleted clips."""
        result = await db.execute(
            sa_text("DELETE FROM generated_clips WHERE task_id = :task_id"),
            {"task_id": task_id},
        )
        await db.commit()
        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} clips for task {task_id}")
        return deleted_count

    @staticmethod
    async def delete_clip(db: AsyncSession, clip_id: str) -> None:
        """Delete a single clip by ID."""
        await db.execute(
            sa_text("DELETE FROM generated_clips WHERE id = :clip_id"),
            {"clip_id": clip_id},
        )
        await db.commit()
        logger.info(f"Deleted clip {clip_id}")

    @staticmethod
    async def get_clip_by_id(
        db: AsyncSession, clip_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get one clip by ID."""
        try:
            result = await db.execute(
                sa_text(
                    """
                    SELECT id, task_id, filename, file_path, start_time, end_time, duration,
                           text, relevance_score, reasoning, clip_order,
                           virality_score, hook_score, engagement_score, value_score, shareability_score, hook_type,
                           retention_score, emotion_score, clarity_score, pacing_score,
                           payoff_score, loop_score, standalone_context_score, overall_score,
                           suggested_title, suggested_description, suggested_hashtags,
                           created_at
                    FROM generated_clips
                    WHERE id = :clip_id
                    """
                ),
                {"clip_id": clip_id},
            )
        except Exception:
            await db.rollback()
            result = await db.execute(
                sa_text(
                    """
                    SELECT id, task_id, filename, file_path, start_time, end_time, duration,
                           text, relevance_score, reasoning, clip_order, created_at
                    FROM generated_clips
                    WHERE id = :clip_id
                    """
                ),
                {"clip_id": clip_id},
            )
        row = result.fetchone()
        if not row:
            return None

        return {
            "id": row.id,
            "task_id": row.task_id,
            "filename": row.filename,
            "file_path": row.file_path,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "duration": row.duration,
            "text": row.text,
            "relevance_score": row.relevance_score,
            "reasoning": row.reasoning,
            "clip_order": row.clip_order,
            "virality_score": getattr(row, "virality_score", 0) or 0,
            "hook_score": getattr(row, "hook_score", 0) or 0,
            "engagement_score": getattr(row, "engagement_score", 0) or 0,
            "value_score": getattr(row, "value_score", 0) or 0,
            "shareability_score": getattr(row, "shareability_score", 0) or 0,
            "hook_type": getattr(row, "hook_type", None),
            **_scorecard_row_fields(row),
            "created_at": row.created_at.isoformat(),
            "video_url": f"/tasks/{row.task_id}/clips/{row.id}/file",
        }

    @staticmethod
    async def update_clip(
        db: AsyncSession,
        clip_id: str,
        filename: str,
        file_path: str,
        start_time: str,
        end_time: str,
        duration: float,
        text: str,
    ) -> None:
        """Update core clip metadata and file path."""
        await db.execute(
            sa_text(
                """
                UPDATE generated_clips
                SET filename = :filename,
                    file_path = :file_path,
                    start_time = :start_time,
                    end_time = :end_time,
                    duration = :duration,
                    text = :text,
                    updated_at = NOW()
                WHERE id = :clip_id
                """
            ),
            {
                "clip_id": clip_id,
                "filename": filename,
                "file_path": file_path,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "text": text,
            },
        )
        await db.commit()

    @staticmethod
    async def reorder_task_clips(db: AsyncSession, task_id: str) -> None:
        """Normalize clip_order sequence after edits."""
        result = await db.execute(
            sa_text(
                "SELECT id FROM generated_clips WHERE task_id = :task_id ORDER BY clip_order ASC, created_at ASC"
            ),
            {"task_id": task_id},
        )
        clip_ids = [row.id for row in result.fetchall()]
        for idx, cid in enumerate(clip_ids, start=1):
            await db.execute(
                sa_text(
                    "UPDATE generated_clips SET clip_order = :clip_order, updated_at = NOW() WHERE id = :clip_id"
                ),
                {"clip_order": idx, "clip_id": cid},
            )
        await db.commit()
