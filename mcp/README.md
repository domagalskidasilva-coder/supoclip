# SupoClip MCP Server

A Model Context Protocol server for a local SupoClip backend.

The local app has no login or API-key layer, so the MCP server calls the backend directly. By default it uses `http://localhost:8000`; set `SUPOCLIP_API_URL` if your backend runs somewhere else.

## Tools

| Tool | Description |
|------|-------------|
| `supoclip_health` | API status and MCP configuration |
| `supoclip_list_caption_templates` | Available caption styles |
| `supoclip_list_transitions` | Available transition effects |
| `supoclip_broll_status` | B-roll provider status |
| `supoclip_list_fonts` | Available subtitle fonts |
| `supoclip_billing_summary` | Local compatibility response; monetization is disabled |
| `supoclip_create_clip_task` | Start clipping a video and return a `task_id` |
| `supoclip_list_tasks` | List local tasks |
| `supoclip_get_task` | Task status, progress and clips |
| `supoclip_wait_for_task` | Poll until a task finishes |
| `supoclip_list_clips` | List generated clips |
| `supoclip_download_clip` | Save a clip MP4 to disk |
| `supoclip_export_clip` | Re-encode and save with a platform preset |
| `supoclip_cancel_task`, `supoclip_resume_task`, `supoclip_delete_task` | Manage tasks |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPOCLIP_API_URL` | `http://localhost:8000` | Backend base URL |
| `SUPOCLIP_DOWNLOAD_DIR` | `./supoclip-downloads` | Where downloaded/exported clips are written |
| `SUPOCLIP_TIMEOUT` | `60` | HTTP timeout in seconds |
| `SUPOCLIP_MCP_TRANSPORT` | `stdio` | `stdio`, `sse`, or `streamable-http` |
| `SUPOCLIP_MCP_HOST` | `127.0.0.1` | Host for HTTP/SSE transports |
| `SUPOCLIP_MCP_PORT` | `9100` | Port for HTTP/SSE transports |

## Run

```bash
cd mcp
uv run supoclip-mcp
```

Example Claude Desktop config:

```json
{
  "mcpServers": {
    "supoclip": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/supoclip/mcp", "run", "supoclip-mcp"],
      "env": {
        "SUPOCLIP_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Example Prompts

- "Use SupoClip to make clips from this YouTube URL with the hormozi caption template."
- "List recent SupoClip tasks and show the virality scores from the latest task."
- "Export this clip as a TikTok preset and download it."
