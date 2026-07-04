CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE "sources" (
    "id" VARCHAR(36) NOT NULL DEFAULT uuid_generate_v4()::text,
    "type" VARCHAR(20) NOT NULL,
    "title" VARCHAR(500) NOT NULL,
    "url" VARCHAR(1000),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "sources_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "tasks" (
    "id" VARCHAR(36) NOT NULL DEFAULT uuid_generate_v4()::text,
    "source_id" VARCHAR(36),
    "generated_clips_ids" VARCHAR(36)[],
    "status" VARCHAR(20) NOT NULL DEFAULT 'pending',
    "progress" INTEGER DEFAULT 0,
    "progress_message" TEXT,
    "completion_notification_sent_at" TIMESTAMPTZ,
    "font_family" VARCHAR(100) DEFAULT 'TikTokSans-Regular',
    "font_size" INTEGER DEFAULT 24,
    "font_color" VARCHAR(7) DEFAULT '#FFFFFF',
    "caption_template" VARCHAR(50) DEFAULT 'default',
    "include_broll" BOOLEAN DEFAULT false,
    "processing_mode" VARCHAR(20) NOT NULL DEFAULT 'fast',
    "started_at" TIMESTAMPTZ,
    "completed_at" TIMESTAMPTZ,
    "cache_hit" BOOLEAN NOT NULL DEFAULT false,
    "error_code" VARCHAR(80),
    "stage_timings_json" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "tasks_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "generated_clips" (
    "id" VARCHAR(36) NOT NULL DEFAULT uuid_generate_v4()::text,
    "task_id" VARCHAR(36) NOT NULL,
    "filename" VARCHAR(255) NOT NULL,
    "file_path" VARCHAR(500) NOT NULL,
    "start_time" VARCHAR(20) NOT NULL,
    "end_time" VARCHAR(20) NOT NULL,
    "duration" DOUBLE PRECISION NOT NULL,
    "text" TEXT,
    "relevance_score" DOUBLE PRECISION NOT NULL,
    "reasoning" TEXT,
    "clip_order" INTEGER NOT NULL,
    "virality_score" INTEGER DEFAULT 0,
    "hook_score" INTEGER DEFAULT 0,
    "engagement_score" INTEGER DEFAULT 0,
    "value_score" INTEGER DEFAULT 0,
    "shareability_score" INTEGER DEFAULT 0,
    "hook_type" VARCHAR(50),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "generated_clips_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "processing_cache" (
    "cache_key" VARCHAR(255) NOT NULL,
    "source_url" TEXT NOT NULL,
    "source_type" VARCHAR(20) NOT NULL,
    "video_path" TEXT,
    "transcript_text" TEXT,
    "analysis_json" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "processing_cache_pkey" PRIMARY KEY ("cache_key")
);

CREATE TABLE "app_settings" (
    "setting_key" VARCHAR(100) NOT NULL,
    "encrypted_value" TEXT NOT NULL,
    "prefer_admin_value" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "app_settings_pkey" PRIMARY KEY ("setting_key")
);

ALTER TABLE "tasks"
ADD CONSTRAINT "tasks_source_id_fkey"
FOREIGN KEY ("source_id") REFERENCES "sources"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "generated_clips"
ADD CONSTRAINT "generated_clips_task_id_fkey"
FOREIGN KEY ("task_id") REFERENCES "tasks"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE INDEX "sources_created_at_idx" ON "sources"("created_at");
CREATE INDEX "tasks_source_id_idx" ON "tasks"("source_id");
CREATE INDEX "tasks_created_at_idx" ON "tasks"("created_at");
CREATE INDEX "tasks_status_idx" ON "tasks"("status");
CREATE INDEX "tasks_processing_mode_idx" ON "tasks"("processing_mode");
CREATE INDEX "generated_clips_task_id_idx" ON "generated_clips"("task_id");
CREATE INDEX "generated_clips_clip_order_idx" ON "generated_clips"("clip_order");
CREATE INDEX "generated_clips_created_at_idx" ON "generated_clips"("created_at");
CREATE INDEX "processing_cache_source_url_idx" ON "processing_cache"("source_url");
