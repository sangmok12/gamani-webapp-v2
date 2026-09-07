-- 가마니연구소 V2 PostgreSQL 초안
-- 조사 기준: 2026-09-07
-- 외부 API 값은 변할 수 있으므로 enum보다 text + 카탈로그를 우선한다.

CREATE TABLE crawl_runs (
  id                    bigserial PRIMARY KEY,
  job_type              text NOT NULL,
  shard_key             text,
  status                text NOT NULL,
  expected_count        integer,
  collected_count       integer NOT NULL DEFAULT 0,
  unique_listing_count  integer NOT NULL DEFAULT 0,
  request_count         integer NOT NULL DEFAULT 0,
  success_count         integer NOT NULL DEFAULT 0,
  failure_count         integer NOT NULL DEFAULT 0,
  started_at            timestamptz NOT NULL DEFAULT now(),
  finished_at           timestamptz,
  failure_code          text,
  failure_message       text,
  CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'ABORTED'))
);

CREATE TABLE crawl_requests (
  id                  bigserial PRIMARY KEY,
  run_id              bigint NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
  endpoint_type       text NOT NULL,
  source_entity_id    text,
  page_offset         integer,
  requested_size      integer,
  http_status         integer,
  attempt_count       smallint NOT NULL DEFAULT 1,
  elapsed_ms          integer,
  response_hash       text,
  result_status       text NOT NULL,
  error_code          text,
  error_message       text,
  requested_at        timestamptz NOT NULL DEFAULT now(),
  next_retry_at       timestamptz,
  CHECK (result_status IN ('SUCCEEDED', 'NOT_AVAILABLE', 'RETRY', 'FAILED'))
);

CREATE INDEX crawl_requests_run_idx
  ON crawl_requests (run_id, result_status);

CREATE INDEX crawl_requests_retry_idx
  ON crawl_requests (next_retry_at)
  WHERE result_status = 'RETRY';

CREATE TABLE vehicles (
  id                         bigserial PRIMARY KEY,
  canonical_source_id        text NOT NULL UNIQUE,
  vehicle_type               text,
  manufacturer_code          text,
  manufacturer_name          text,
  manufacturer_english_name  text,
  model_group_code           text,
  model_group_name           text,
  model_code                 text,
  model_name                 text,
  grade_code                 text,
  grade_name                 text,
  grade_detail_code          text,
  grade_detail_name          text,
  year_month                 varchar(6),
  form_year                  smallint,
  domestic                   boolean,
  import_type                text,
  origin_price_manwon        integer,
  mileage_km                 integer,
  displacement_cc            integer,
  transmission_code         text,
  transmission_name         text,
  fuel_code                  text,
  fuel_name                  text,
  color_name                 text,
  seat_count                 smallint,
  body_name                  text,
  trade_type                 text,
  first_registration_date    date,
  source_modified_at         timestamptz,
  first_seen_at              timestamptz NOT NULL DEFAULT now(),
  last_seen_at               timestamptz NOT NULL DEFAULT now(),
  created_at                 timestamptz NOT NULL DEFAULT now(),
  updated_at                 timestamptz NOT NULL DEFAULT now(),
  CHECK (year_month IS NULL OR year_month ~ '^[0-9]{6}$')
);

CREATE INDEX vehicles_category_idx
  ON vehicles (manufacturer_code, model_group_code, model_code, grade_code);

CREATE INDEX vehicles_basic_filter_idx
  ON vehicles (form_year, mileage_km);

-- VIN/차량번호가 꼭 필요할 때만 사용한다.
-- 원문은 두지 않고 서버 비밀키를 사용한 HMAC만 저장한다.
CREATE TABLE vehicle_private_identifiers (
  vehicle_id       bigint PRIMARY KEY REFERENCES vehicles(id) ON DELETE CASCADE,
  vin_hmac         text UNIQUE,
  vehicle_no_hmac  text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vehicle_listings (
  source_listing_id       text PRIMARY KEY,
  vehicle_id              bigint REFERENCES vehicles(id),
  resolution_status       text NOT NULL DEFAULT 'UNRESOLVED',
  service_copy_car        text,
  advertisement_status    text,
  sell_type               text,
  price_manwon            integer,
  mileage_km              integer,
  office_city_state       text,
  condition_codes         jsonb NOT NULL DEFAULT '[]'::jsonb,
  service_marks           jsonb NOT NULL DEFAULT '[]'::jsonb,
  trust_codes             jsonb NOT NULL DEFAULT '[]'::jsonb,
  ad_types                jsonb NOT NULL DEFAULT '[]'::jsonb,
  buy_types               jsonb NOT NULL DEFAULT '[]'::jsonb,
  representative_photo    text,
  list_fingerprint        text NOT NULL,
  first_advertised_at     timestamptz,
  source_registered_at    timestamptz,
  source_modified_at      timestamptz,
  first_seen_at           timestamptz NOT NULL DEFAULT now(),
  last_seen_at            timestamptz NOT NULL DEFAULT now(),
  missing_streak          integer NOT NULL DEFAULT 0,
  inactive_at             timestamptz,
  next_detail_refresh_at  timestamptz,
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),
  CHECK (resolution_status IN ('UNRESOLVED', 'RESOLVED', 'NOT_FOUND', 'RETRY')),
  CHECK (missing_streak >= 0)
);

CREATE INDEX vehicle_listings_active_search_idx
  ON vehicle_listings (price_manwon, mileage_km, vehicle_id)
  WHERE inactive_at IS NULL;

CREATE INDEX vehicle_listings_vehicle_idx
  ON vehicle_listings (vehicle_id, inactive_at);

CREATE INDEX vehicle_listings_refresh_idx
  ON vehicle_listings (next_detail_refresh_at)
  WHERE inactive_at IS NULL;

CREATE TABLE vehicle_price_history (
  listing_id    text NOT NULL REFERENCES vehicle_listings(source_listing_id) ON DELETE CASCADE,
  observed_at   timestamptz NOT NULL,
  price_manwon  integer NOT NULL,
  run_id        bigint REFERENCES crawl_runs(id),
  PRIMARY KEY (listing_id, observed_at)
);

CREATE TABLE option_catalog (
  source_code    text PRIMARY KEY,
  name           text NOT NULL,
  category_code  text,
  category_name  text,
  display_order  numeric,
  active         boolean NOT NULL DEFAULT true,
  first_seen_at  timestamptz NOT NULL DEFAULT now(),
  last_seen_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vehicle_options (
  vehicle_id     bigint NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  source_code    text NOT NULL REFERENCES option_catalog(source_code),
  source_group   text NOT NULL,
  active         boolean NOT NULL DEFAULT true,
  first_seen_at  timestamptz NOT NULL DEFAULT now(),
  last_seen_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (vehicle_id, source_code, source_group),
  CHECK (source_group IN ('standard', 'choice', 'tuning', 'etc'))
);

CREATE INDEX vehicle_options_search_idx
  ON vehicle_options (source_code, vehicle_id)
  WHERE active;

CREATE TABLE vehicle_photos (
  vehicle_id          bigint NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  source_code         text NOT NULL,
  photo_type          text,
  path                text NOT NULL,
  description         text,
  source_updated_at   timestamptz,
  display_order       integer,
  active              boolean NOT NULL DEFAULT true,
  first_seen_at       timestamptz NOT NULL DEFAULT now(),
  last_seen_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (vehicle_id, source_code, path)
);

CREATE TABLE insurance_records (
  id                         bigserial PRIMARY KEY,
  vehicle_id                 bigint NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  content_hash               text NOT NULL,
  open_data                  boolean,
  registered_at              date,
  first_registered_at        date,
  usage_name                 text,
  owner_change_count         integer,
  vehicle_no_change_count    integer,
  government_use_count       integer,
  business_use_count         integer,
  loan_use_count             integer,
  my_accident_count          integer,
  my_accident_cost_won       bigint,
  other_accident_count       integer,
  other_accident_cost_won    bigint,
  robbery_count              integer,
  total_loss_count           integer,
  flood_total_loss_count     integer,
  flood_partial_loss_count   integer,
  non_subscription_periods   jsonb NOT NULL DEFAULT '[]'::jsonb,
  source_observed_at         timestamptz NOT NULL DEFAULT now(),
  is_current                 boolean NOT NULL DEFAULT true,
  UNIQUE (vehicle_id, content_hash)
);

CREATE UNIQUE INDEX insurance_records_current_idx
  ON insurance_records (vehicle_id)
  WHERE is_current;

CREATE TABLE insurance_accidents (
  insurance_record_id   bigint NOT NULL REFERENCES insurance_records(id) ON DELETE CASCADE,
  sequence_no           integer NOT NULL,
  accident_type         text,
  accident_date         date,
  insurance_benefit_won bigint,
  parts_cost_won        bigint,
  labor_cost_won        bigint,
  painting_cost_won     bigint,
  PRIMARY KEY (insurance_record_id, sequence_no)
);

CREATE TABLE inspections (
  id                       bigserial PRIMARY KEY,
  vehicle_id               bigint NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  content_hash             text NOT NULL,
  record_no                text,
  inspection_source        text,
  registration_date        date,
  first_registration_date  date,
  mileage_km               integer,
  accident                 boolean,
  simple_repair            boolean,
  tuning                   boolean,
  water_damage             boolean,
  recall                   boolean,
  recall_fulfilled         boolean,
  formats                  jsonb NOT NULL DEFAULT '[]'::jsonb,
  source_observed_at       timestamptz NOT NULL DEFAULT now(),
  is_current               boolean NOT NULL DEFAULT true,
  UNIQUE (vehicle_id, content_hash)
);

CREATE UNIQUE INDEX inspections_current_idx
  ON inspections (vehicle_id)
  WHERE is_current;

CREATE TABLE inspection_items (
  inspection_id       bigint NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
  item_path           text NOT NULL,
  item_code           text,
  item_name           text,
  status_code         text,
  status_name         text,
  description         text,
  attributes          jsonb NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY (inspection_id, item_path)
);

CREATE TABLE inspection_body_panels (
  inspection_id       bigint NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
  panel_code          text NOT NULL,
  panel_name          text,
  status_code         text,
  status_name         text,
  attributes          jsonb NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY (inspection_id, panel_code)
);

CREATE TABLE diagnoses (
  id                    bigserial PRIMARY KEY,
  vehicle_id            bigint NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  content_hash          text NOT NULL,
  diagnosis_no          text,
  diagnosis_date        date,
  real_diagnosis_date   date,
  center_code           text,
  center_name           text,
  source_observed_at    timestamptz NOT NULL DEFAULT now(),
  is_current            boolean NOT NULL DEFAULT true,
  UNIQUE (vehicle_id, content_hash)
);

CREATE UNIQUE INDEX diagnoses_current_idx
  ON diagnoses (vehicle_id)
  WHERE is_current;

CREATE TABLE diagnosis_items (
  diagnosis_id  bigint NOT NULL REFERENCES diagnoses(id) ON DELETE CASCADE,
  sequence_no   integer NOT NULL,
  item_code     text,
  item_name     text,
  result_code   text,
  result_name   text,
  PRIMARY KEY (diagnosis_id, sequence_no)
);

-- 서비스용 DB에는 반드시 개인정보를 제거한 payload만 저장한다.
CREATE TABLE raw_snapshots (
  id                  bigserial PRIMARY KEY,
  vehicle_id          bigint REFERENCES vehicles(id) ON DELETE CASCADE,
  listing_id          text REFERENCES vehicle_listings(source_listing_id) ON DELETE CASCADE,
  endpoint_type       text NOT NULL,
  source_entity_id    text NOT NULL,
  content_hash        text NOT NULL,
  schema_fingerprint  text NOT NULL,
  payload_redacted    jsonb NOT NULL,
  observed_at         timestamptz NOT NULL DEFAULT now(),
  run_id              bigint REFERENCES crawl_runs(id),
  UNIQUE (endpoint_type, source_entity_id, content_hash)
);

CREATE INDEX raw_snapshots_vehicle_idx
  ON raw_snapshots (vehicle_id, endpoint_type, observed_at DESC);

-- 검색 읽기 모델의 예시. 실제 구현에서는 materialized view 또는 별도 테이블로 관리한다.
CREATE TABLE vehicle_search_documents (
  vehicle_id          bigint PRIMARY KEY REFERENCES vehicles(id) ON DELETE CASCADE,
  listing_id          text NOT NULL REFERENCES vehicle_listings(source_listing_id) ON DELETE CASCADE,
  manufacturer_code   text,
  model_group_code    text,
  model_code          text,
  grade_code          text,
  form_year           smallint,
  mileage_km          integer,
  price_manwon        integer,
  fuel_code           text,
  option_codes        text[] NOT NULL DEFAULT '{}',
  accident_summary    jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX vehicle_search_category_price_idx
  ON vehicle_search_documents
  (manufacturer_code, model_group_code, model_code, price_manwon);

CREATE INDEX vehicle_search_year_mileage_idx
  ON vehicle_search_documents (form_year, mileage_km);

CREATE INDEX vehicle_search_options_gin_idx
  ON vehicle_search_documents USING gin (option_codes);
