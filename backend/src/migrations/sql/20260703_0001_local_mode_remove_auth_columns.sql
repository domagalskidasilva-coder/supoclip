ALTER TABLE tasks
DROP CONSTRAINT IF EXISTS tasks_user_id_fkey;

DROP INDEX IF EXISTS idx_tasks_user_id;

ALTER TABLE tasks
DROP COLUMN IF EXISTS user_id;

ALTER TABLE app_settings
DROP CONSTRAINT IF EXISTS app_settings_updated_by_fkey;

DROP INDEX IF EXISTS idx_app_settings_updated_by;

ALTER TABLE app_settings
DROP COLUMN IF EXISTS updated_by;
