#!/usr/bin/env python3
"""
MCP server for SupoClip — an AI tool that turns long-form videos into short,
vertical, subtitled viral clips.

The server talks to the local SupoClip REST API. Set ``SUPOCLIP_API_URL`` when
the backend is not running at ``http://localhost:8000``.

Typical workflow:
    1. ``supoclip_create_clip_task`` with a YouTube URL  -> returns a task_id
    2. ``supoclip_wait_for_task`` (or poll ``supoclip_get_task``) until done
    3. ``supoclip_list_clips`` / ``supoclip_download_clip`` to retrieve results
"""

from __future__ import annotations

import asyncio
import functools
import json
import os
import re
import time
from typing import Annotated, Awaitable, Callable, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

try:  # Python 3.10 lacks typing.Literal niceties only in edge cases; import is fine.
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal  # type: ignore

from .client import SupoClipClient, SupoClipError
from .config import load_settings

SETTINGS = load_settings()
CLIENT = SupoClipClient(SETTINGS)


def _build_mcp() -> FastMCP:
    return FastMCP(
        "supoclip_mcp",
        host=SETTINGS.mcp_host,
        port=SETTINGS.mcp_port,
    )


mcp = _build_mcp()

ProcessingMode = Literal["fast", "balanced", "quality"]
OutputFormat = Literal["vertical", "vertical_pan", "vertical_split", "original"]
ExportPreset = Literal["tiktok", "reels", "shorts"]
TERMINAL_STATES = {"completed", "error", "cancelled"}
VALID_OUTPUT_FORMATS = {"vertical", "vertical_pan", "vertical_split", "original"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _json(data: object) -> str:
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def _client() -> SupoClipClient:
    return CLIENT


def tool_errors(func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    """Wrap a tool so backend errors come back as readable text, not stack traces."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> str:
        try:
            return await func(*args, **kwargs)
        except SupoClipError as exc:
            return f"Error: {exc}"
        except Exception as exc:  # pragma: no cover - defensive
            return f"Error: unexpected {type(exc).__name__}: {exc}"

    return wrapper


def _safe_filename(name: str, default: str) -> str:
    """Reduce an arbitrary string to a safe ``.mp4`` basename (no path traversal)."""
    base = os.path.basename((name or "").strip()) or default
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    if not base.lower().endswith(".mp4"):
        base = f"{base}.mp4"
    return base


# --------------------------------------------------------------------------- #
# Public tools
# --------------------------------------------------------------------------- #
@mcp.tool(
    name="supoclip_health",
    annotations={
        "title": "SupoClip Health & Config",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_health() -> str:
    """Report SupoClip API status and how this MCP server is configured.

    Use this first to confirm connectivity.

    Returns:
        str: JSON with the configured API URL, download directory, MCP transport,
        and the backend's reported status.
    """
    root = await _client().request("GET", "/", authenticated=False)
    health = await _client().request("GET", "/health", authenticated=False)
    return _json(
        {
            "configured": {
                "api_url": SETTINGS.api_url,
                "authentication": "disabled",
                "download_dir": SETTINGS.download_dir,
                "mcp_transport": SETTINGS.mcp_transport,
            },
            "backend": root,
            "health": health,
        }
    )


@mcp.tool(
    name="supoclip_list_caption_templates",
    annotations={
        "title": "List Caption Templates",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_list_caption_templates() -> str:
    """List the caption/subtitle templates available for clip generation.

    Each template id (e.g. ``default``, ``hormozi``, ``mrbeast``) can be passed
    as ``caption_template`` to ``supoclip_create_clip_task``.

    Returns:
        str: JSON ``{"templates": [{"id", "name", "description", "animation",
        "font_family", "font_size", "font_color", ...}]}``.
    """
    data = await _client().request("GET", "/caption-templates", authenticated=False)
    return _json(data)


@mcp.tool(
    name="supoclip_list_transitions",
    annotations={
        "title": "List Transition Effects",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_list_transitions() -> str:
    """List available video transition effects.

    Returns:
        str: JSON ``{"transitions": [{"name", "display_name", "file_path"}]}``.
    """
    data = await _client().request("GET", "/transitions", authenticated=False)
    return _json(data)


@mcp.tool(
    name="supoclip_broll_status",
    annotations={
        "title": "B-roll Availability",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_broll_status() -> str:
    """Report whether automatic B-roll overlays are configured on the backend.

    If ``configured`` is false, passing ``include_broll=true`` when creating a
    task has no effect.

    Returns:
        str: JSON ``{"configured": bool, "provider": str | null}``.
    """
    data = await _client().request("GET", "/broll/status", authenticated=False)
    return _json(data)


# --------------------------------------------------------------------------- #
# Local tools — discovery
# --------------------------------------------------------------------------- #
@mcp.tool(
    name="supoclip_list_fonts",
    annotations={
        "title": "List Fonts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_list_fonts() -> str:
    """List subtitle fonts available to the local instance.

    Any returned ``name`` can be used as ``font_family`` in
    ``supoclip_create_clip_task``.

    Returns:
        str: JSON ``{"fonts": [{"name", "display_name", ...}]}``.
    """
    data = await _client().request("GET", "/fonts")
    return _json(data)


@mcp.tool(
    name="supoclip_billing_summary",
    annotations={
        "title": "Billing & Usage Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_billing_summary() -> str:
    """Get the local billing compatibility response.

    Local mode disables monetization, so task creation is always allowed.

    Returns:
        str: JSON with ``plan``, ``subscription_status``, ``usage_count``,
        ``usage_limit``, ``remaining``, ``upgrade_required`` and
        ``monetization_enabled``.
    """
    data = await _client().request("GET", "/tasks/billing/summary")
    return _json(data)


# --------------------------------------------------------------------------- #
# Local tools — task lifecycle
# --------------------------------------------------------------------------- #
@mcp.tool(
    name="supoclip_create_clip_task",
    annotations={
        "title": "Create Clipping Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_create_clip_task(
    url: str = "",
    title: str = "",
    processing_mode: str = "fast",
    output_format: str = "vertical",
    add_subtitles: bool = True,
    caption_template: str = "default",
    include_broll: bool = False,
    font_family: str = "",
    font_size: int = 0,
    font_color: str = "",
    cut_long_pauses: bool = False,
    remove_filler_words: bool = False,
) -> str:
    """Create a SupoClip task that downloads a video and generates viral short clips.

    Processing is asynchronous: this returns immediately with a ``task_id``.
    Track progress with ``supoclip_wait_for_task`` or ``supoclip_get_task``, then
    fetch results with ``supoclip_list_clips`` / ``supoclip_download_clip``.

    Args:
        url: YouTube or direct video URL to clip.
        title: Optional task title.
        processing_mode: 'fast' | 'balanced' | 'quality'.
        output_format: 'vertical' | 'vertical_pan' | 'vertical_split' | 'original'.
        add_subtitles: Whether to burn in subtitles.
        caption_template: Caption template id.
        include_broll: Whether to add B-roll overlays.
        font_family / font_size / font_color: Optional subtitle styling overrides.
        cut_long_pauses / remove_filler_words: Optional cleanup toggles.

    Returns:
        str: JSON ``{"task_id": str, "job_id": str, "message": str}`` on success.
    """
    cleaned_url = (url or "").strip()
    if len(cleaned_url) < 4:
        raise SupoClipError("url is required. Pass a YouTube URL or direct video URL.")

    normalized_mode = processing_mode if processing_mode in {"fast", "balanced", "quality"} else "fast"
    normalized_format = output_format if output_format in VALID_OUTPUT_FORMATS else "vertical"

    source: dict = {"url": cleaned_url[:2000]}
    cleaned_title = title.strip()
    if cleaned_title:
        source["title"] = cleaned_title[:300]

    body: dict = {
        "source": source,
        "processing_mode": normalized_mode,
        "output_format": normalized_format,
        "add_subtitles": add_subtitles,
        "caption_template": (caption_template or "default").strip()[:50] or "default",
        "include_broll": include_broll,
    }

    font_options: dict = {}
    cleaned_font_family = font_family.strip()
    if cleaned_font_family:
        font_options["font_family"] = cleaned_font_family[:100]
    if font_size:
        font_options["font_size"] = max(12, min(72, int(font_size)))
    cleaned_font_color = font_color.strip()
    if re.match(r"^#[0-9A-Fa-f]{6}$", cleaned_font_color):
        font_options["font_color"] = cleaned_font_color
    if font_options:
        body["font_options"] = font_options

    if cut_long_pauses:
        body["cut_long_pauses"] = cut_long_pauses
    if remove_filler_words:
        body["remove_filler_words"] = remove_filler_words

    data = await _client().request("POST", "/tasks/", json_body=body)
    return _json(data)


@mcp.tool(
    name="supoclip_create_clip",
    annotations={
        "title": "Create Clip",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_create_clip(url: str = "") -> str:
    """Create a SupoClip task from a YouTube or direct video URL.

    This is a compatibility alias for clients that fail to pass arguments to
    the richer ``supoclip_create_clip_task`` tool. Pass the video URL in the
    ``url`` argument.
    """
    return await supoclip_create_clip_task(url=url)


@mcp.tool(
    name="supoclip_list_tasks",
    annotations={
        "title": "List Tasks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_list_tasks(
    limit: Annotated[
        int,
        Field(default=50, description="Maximum number of tasks to return.", ge=1, le=200),
    ] = 50,
) -> str:
    """List local clipping tasks, newest first.

    Args:
        limit: Maximum tasks to return (1-200, default 50).

    Returns:
        str: JSON ``{"tasks": [{"id", "status", "progress", "title", ...}], "total": int}``.
    """
    data = await _client().request("GET", "/tasks/", params={"limit": limit})
    return _json(data)


@mcp.tool(
    name="supoclip_get_task",
    annotations={
        "title": "Get Task",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_get_task(
    task_id: Annotated[str, Field(description="The task id returned by create_clip_task.", min_length=1)],
) -> str:
    """Get a task's status, progress and generated clips.

    Args:
        task_id: The task id.

    Returns:
        str: JSON of the task including ``status`` (queued/processing/completed/
        error/cancelled), ``progress`` (0-100), ``progress_message`` and a
        ``clips`` array (each with ``id``, ``filename``, timing and scores).
    """
    data = await _client().request("GET", f"/tasks/{task_id}")
    return _json(data)


@mcp.tool(
    name="supoclip_wait_for_task",
    annotations={
        "title": "Wait For Task",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_wait_for_task(
    task_id: Annotated[str, Field(description="The task id to wait on.", min_length=1)],
    timeout_seconds: Annotated[
        int,
        Field(default=600, description="Give up after this many seconds.", ge=5, le=3600),
    ] = 600,
    poll_interval_seconds: Annotated[
        int,
        Field(default=5, description="Seconds between status checks.", ge=2, le=60),
    ] = 5,
    ctx: Optional[Context] = None,
) -> str:
    """Poll a task until it finishes (completed/error/cancelled) or times out.

    Convenience wrapper around ``supoclip_get_task`` for the asynchronous
    pipeline. Reports progress while waiting.

    Args:
        task_id: The task id to wait on.
        timeout_seconds: Max seconds to wait (5-3600, default 600).
        poll_interval_seconds: Seconds between polls (2-60, default 5).

    Returns:
        str: JSON ``{"status", "progress", "timed_out": bool, "task": {...}}``.
        When ``status`` is ``completed`` the ``task.clips`` array holds results.
    """
    deadline = time.monotonic() + timeout_seconds
    last: dict = {}
    while True:
        last = await _client().request("GET", f"/tasks/{task_id}")
        status = str(last.get("status", "unknown"))
        progress = last.get("progress", 0)

        if ctx is not None:
            try:
                await ctx.report_progress(
                    progress=float(progress or 0) / 100.0,
                    message=f"{status}: {last.get('progress_message', '')}",
                )
            except Exception:
                pass

        if status in TERMINAL_STATES:
            return _json(
                {"status": status, "progress": progress, "timed_out": False, "task": last}
            )

        if time.monotonic() >= deadline:
            return _json(
                {
                    "status": status,
                    "progress": progress,
                    "timed_out": True,
                    "message": f"Still '{status}' after {timeout_seconds}s; poll again later.",
                    "task": last,
                }
            )

        await asyncio.sleep(poll_interval_seconds)


@mcp.tool(
    name="supoclip_list_clips",
    annotations={
        "title": "List Clips",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_list_clips(
    task_id: Annotated[str, Field(description="The task id whose clips to list.", min_length=1)],
) -> str:
    """List the generated clips for a task.

    Args:
        task_id: The task id.

    Returns:
        str: JSON ``{"task_id", "clips": [{"id", "filename", "start_time",
        "end_time", "virality_score", ...}], "total_clips": int}``.
    """
    data = await _client().request("GET", f"/tasks/{task_id}/clips")
    return _json(data)


# --------------------------------------------------------------------------- #
# Local tools — retrieval (download to disk)
# --------------------------------------------------------------------------- #
@mcp.tool(
    name="supoclip_download_clip",
    annotations={
        "title": "Download Clip",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_download_clip(
    task_id: Annotated[str, Field(description="The task id that owns the clip.", min_length=1)],
    clip_id: Annotated[str, Field(description="The clip id (from supoclip_list_clips).", min_length=1)],
    filename: Annotated[
        Optional[str],
        Field(default=None, description="Optional output filename; '.mp4' is enforced.", max_length=200),
    ] = None,
) -> str:
    """Download a generated clip's MP4 to the local download directory.

    The file is saved under ``SUPOCLIP_DOWNLOAD_DIR`` (default
    ``./supoclip-downloads``).

    Args:
        task_id: The owning task id.
        clip_id: The clip id to download.
        filename: Optional output filename.

    Returns:
        str: JSON ``{"path": str, "filename": str, "bytes": int}`` — the absolute
        local path of the saved MP4.
    """
    out_name = _safe_filename(filename or "", default=f"clip_{clip_id}.mp4")
    result = await _client().download(
        f"/tasks/{task_id}/clips/{clip_id}/file", SETTINGS.download_dir, out_name
    )
    return _json(result)


@mcp.tool(
    name="supoclip_export_clip",
    annotations={
        "title": "Export Clip (Platform Preset)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_export_clip(
    task_id: Annotated[str, Field(description="The task id that owns the clip.", min_length=1)],
    clip_id: Annotated[str, Field(description="The clip id to export.", min_length=1)],
    preset: Annotated[
        ExportPreset,
        Field(default="tiktok", description="Export preset: 'tiktok', 'reels' or 'shorts'."),
    ] = "tiktok",
    filename: Annotated[
        Optional[str],
        Field(default=None, description="Optional output filename; '.mp4' is enforced.", max_length=200),
    ] = None,
) -> str:
    """Export a clip re-encoded for a social platform and save the MP4 locally.

    Presets (tiktok/reels/shorts) produce 1080x1920 H.264 with platform-tuned
    bitrates. Saved under ``SUPOCLIP_DOWNLOAD_DIR``.

    Args:
        task_id: The owning task id.
        clip_id: The clip id to export.
        preset: 'tiktok' | 'reels' | 'shorts'.
        filename: Optional output filename.

    Returns:
        str: JSON ``{"path": str, "filename": str, "bytes": int}``.
    """
    out_name = _safe_filename(filename or "", default=f"clip_{clip_id}_{preset}.mp4")
    result = await _client().download(
        f"/tasks/{task_id}/clips/{clip_id}/export",
        SETTINGS.download_dir,
        out_name,
        params={"preset": preset},
    )
    return _json(result)


# --------------------------------------------------------------------------- #
# Local tools — management
# --------------------------------------------------------------------------- #
@mcp.tool(
    name="supoclip_cancel_task",
    annotations={
        "title": "Cancel Task",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_cancel_task(
    task_id: Annotated[str, Field(description="The task id to cancel.", min_length=1)],
) -> str:
    """Cancel a queued or processing task.

    Args:
        task_id: The task id to cancel.

    Returns:
        str: JSON ``{"message": str}``.
    """
    data = await _client().request("POST", f"/tasks/{task_id}/cancel")
    return _json(data)


@mcp.tool(
    name="supoclip_resume_task",
    annotations={
        "title": "Resume Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_resume_task(
    task_id: Annotated[str, Field(description="The task id to resume.", min_length=1)],
) -> str:
    """Re-queue a cancelled or errored task for processing.

    Args:
        task_id: The task id to resume.

    Returns:
        str: JSON ``{"message": str, "job_id": str}``.
    """
    data = await _client().request("POST", f"/tasks/{task_id}/resume")
    return _json(data)


@mcp.tool(
    name="supoclip_delete_task",
    annotations={
        "title": "Delete Task",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@tool_errors
async def supoclip_delete_task(
    task_id: Annotated[str, Field(description="The task id to delete.", min_length=1)],
) -> str:
    """Permanently delete a task and all of its generated clips.

    This cannot be undone.

    Args:
        task_id: The task id to delete.

    Returns:
        str: JSON ``{"message": str}``.
    """
    data = await _client().request("DELETE", f"/tasks/{task_id}")
    return _json(data)


def main() -> None:
    """Console-script entry point."""
    mcp.run(transport=SETTINGS.mcp_transport, mount_path=SETTINGS.mcp_mount_path)


if __name__ == "__main__":
    main()
