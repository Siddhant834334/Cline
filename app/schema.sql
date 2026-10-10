CREATE TABLE IF NOT EXISTS segment(
  segment_id TEXT PRIMARY KEY, u INTEGER, v INTEGER, edge_key INTEGER,
  parent_way_id TEXT, length_m REAL, walk_time_s REAL,
  pedestrian_access TEXT, geometry_wkt TEXT, crs TEXT);
CREATE TABLE IF NOT EXISTS observation(
  obs_id INTEGER PRIMARY KEY AUTOINCREMENT,
  segment_id TEXT, field TEXT, value REAL,
  hour_of_day INTEGER,
  source TEXT,
  observed_at TEXT, valid_until TEXT,
  review_status TEXT,
  scenario_version TEXT);
CREATE INDEX IF NOT EXISTS idx_obs_seg ON observation(segment_id, field, hour_of_day);
CREATE TABLE IF NOT EXISTS collection_catalog(
  field TEXT, proposed_method TEXT,
  kind TEXT,
  permission_class TEXT,
  validation_needed TEXT, dependency_status TEXT,
  PRIMARY KEY(field, proposed_method));
CREATE TABLE IF NOT EXISTS condition_event(
  event_id TEXT PRIMARY KEY, segment_ids TEXT, field TEXT, new_value REAL,
  event_type TEXT,
  starts_at TEXT, ends_at TEXT, source TEXT, created_by TEXT,
  supersedes TEXT, rolled_back INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS report(
  report_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE,
  segment_id TEXT, original_text TEXT, photo_path TEXT,
  extracted_json TEXT, extraction_confidence REAL, extraction_mode TEXT,
  state TEXT,
  submitted_at TEXT, reviewed_by TEXT, reviewed_at TEXT, linked_event_id TEXT);
