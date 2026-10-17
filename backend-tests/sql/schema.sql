-- =====================================================================
-- The Stolen Hours of the Monkey King - database schema (MySQL HeatWave)
-- Translated from design doc section 8 (written for Oracle Autonomous DB).
--
-- Oracle -> MySQL translation:
--   VARCHAR2(n) -> VARCHAR(n)      CLOB -> TEXT
--   NUMBER(1)   -> TINYINT         SYSTIMESTAMP -> CURRENT_TIMESTAMP(6)
--   "REFERENCES realms" -> "REFERENCES realms(realm_id)" (MySQL needs the column)
--
-- Additions to the doc schema (each marked "ADDED" below):
--   variants.culprit_words, realms.display_order, pearls.title, pearls.visual,
--   duel_rounds.proof_mode + reason columns, sessions.legend_step + pearl_salt,
--   unlocks.actions_before + opened_at, duel_answers.proof (up to 2 pearls) + reason,
--   surrogate ids / timestamps on log tables, verdicts.try_no, session_id indexes,
--   and two new tables for the before/after questions (assessment_items, assessment_answers).
--
-- Safe to run more than once (CREATE ... IF NOT EXISTS). CREATE ... IF NOT
-- EXISTS never changes a table that is already there, so do NOT run this file
-- by hand to upgrade: run python scripts/setup_db.py, which upgrades older
-- databases first (app/migrations.py) and records the version below.
-- =====================================================================

CREATE TABLE IF NOT EXISTS schema_version (       -- ADDED: which upgrade this database is on
  version      SMALLINT     NOT NULL PRIMARY KEY,
  applied_at   TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------- STORY TABLES (load once) -------------------

CREATE TABLE IF NOT EXISTS variants (
  variant_id   VARCHAR(4)  NOT NULL PRIMARY KEY,   -- 'V1','V2','V3'
  culprit      VARCHAR(40) NOT NULL,               -- HIDDEN: never sent to AI or browser
  culprit_words VARCHAR(200) NOT NULL DEFAULT '',  -- ADDED: words the Scroll's reply must not contain
  ending_text  TEXT        NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS realms (
  realm_id      VARCHAR(10)  NOT NULL PRIMARY KEY, -- 'bamboo','sea','moon'
  name          VARCHAR(40),
  display_order TINYINT      NOT NULL DEFAULT 0,   -- ADDED: map order, so new myths need no code
  image_url     VARCHAR(400),
  look_text     VARCHAR(400),
  listen_text   VARCHAR(400)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS pearls (
  pearl_id     VARCHAR(4)   NOT NULL PRIMARY KEY,  -- 'P1'..'P6'
  realm_id     VARCHAR(10)  NOT NULL,
  true_order   TINYINT      NOT NULL,              -- HIDDEN: 1..6
  time_label   VARCHAR(20),                        -- HIDDEN (would give away the timeline)
  title        VARCHAR(60)  NOT NULL,              -- ADDED: name shown to the child
  visual       VARCHAR(200),                       -- ADDED: JSON for the clue picture (sun / tide / moon)
  shared_text  VARCHAR(600) NOT NULL,
  predict_q    VARCHAR(200),
  predict_ok   VARCHAR(100),
  predict_no1  VARCHAR(100),
  predict_no2  VARCHAR(100),
  CONSTRAINT fk_pearls_realm FOREIGN KEY (realm_id) REFERENCES realms(realm_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS pearl_signs (           -- variant signs for P2 and P5
  pearl_id     VARCHAR(4)   NOT NULL,
  variant_id   VARCHAR(4)   NOT NULL,
  sign_text    VARCHAR(300),
  PRIMARY KEY (pearl_id, variant_id),
  CONSTRAINT fk_signs_pearl   FOREIGN KEY (pearl_id)   REFERENCES pearls(pearl_id),
  CONSTRAINT fk_signs_variant FOREIGN KEY (variant_id) REFERENCES variants(variant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS duel_rounds (
  round_no     TINYINT      NOT NULL,
  variant_id   VARCHAR(4)   NOT NULL,              -- 'ALL' for shared rounds
  form_name    VARCHAR(40),
  claim_text   VARCHAR(400),
  is_lie       TINYINT      NOT NULL,              -- HIDDEN
  proof_pearls VARCHAR(20)  NOT NULL,              -- HIDDEN, e.g. 'P4,P5'
  proof_mode   VARCHAR(4)   NOT NULL DEFAULT 'any',-- ADDED: 'any' = pick 1 of these, 'all' = pick all of these
  reason_ok    VARCHAR(120) NOT NULL,              -- ADDED: HIDDEN which reason is right
  reason_no1   VARCHAR(120) NOT NULL,              -- ADDED
  reason_no2   VARCHAR(120) NOT NULL,              -- ADDED
  PRIMARY KEY (round_no, variant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS assessment_items (     -- ADDED: before/after questions
  item_id      VARCHAR(10)  NOT NULL PRIMARY KEY,  -- 'PRE1','PRE2','POST1','POST2'
  phase        VARCHAR(4)   NOT NULL,              -- 'pre' or 'post'
  skill        VARCHAR(30)  NOT NULL,
  question     VARCHAR(400) NOT NULL,
  choice_ok    VARCHAR(120) NOT NULL,              -- HIDDEN
  choice_no1   VARCHAR(120) NOT NULL,
  choice_no2   VARCHAR(120) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hints (
  puzzle_key   VARCHAR(20)  NOT NULL,              -- 'P1'..'P6','TIMELINE','R1'..'R3','VERDICT'
  level_no     TINYINT      NOT NULL,
  hint_text    VARCHAR(300),
  PRIMARY KEY (puzzle_key, level_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------- PLAY TABLES (fill during play) -------------

CREATE TABLE IF NOT EXISTS sessions (
  session_id   VARCHAR(36)  NOT NULL PRIMARY KEY,  -- UUID
  nickname     VARCHAR(30)  NOT NULL,
  variant_id   VARCHAR(4)   NOT NULL,              -- random at start, HIDDEN
  hairs_left   TINYINT      NOT NULL DEFAULT 3,
  stage        VARCHAR(20)  NOT NULL DEFAULT 'prologue',
  legend_step  TINYINT      NOT NULL DEFAULT 0,    -- ADDED: how many legend questions were asked
  pearl_salt   VARCHAR(32)  NOT NULL,              -- ADDED: secret per game; makes the pearl codes the browser sees
  started_at   TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_sessions_variant FOREIGN KEY (variant_id) REFERENCES variants(variant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS actions_log (
  id           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,  -- ADDED
  session_id   VARCHAR(36)  NOT NULL,
  realm_id     VARCHAR(10),
  action       VARCHAR(10)  NOT NULL,              -- 'look','listen','ask'
  at_time      TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  INDEX idx_actions_session (session_id),
  CONSTRAINT fk_actions_session FOREIGN KEY (session_id) REFERENCES sessions(session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS unlocks (
  session_id     VARCHAR(36) NOT NULL,
  pearl_id       VARCHAR(4)  NOT NULL,
  predicted_ok   TINYINT     NOT NULL,
  actions_before SMALLINT    NOT NULL DEFAULT 0,  -- ADDED: observation metric
  opened_at      TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),  -- ADDED
  PRIMARY KEY (session_id, pearl_id),
  CONSTRAINT fk_unlocks_session FOREIGN KEY (session_id) REFERENCES sessions(session_id),
  CONSTRAINT fk_unlocks_pearl   FOREIGN KEY (pearl_id)   REFERENCES pearls(pearl_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS timeline_tries (
  session_id   VARCHAR(36)  NOT NULL,
  try_no       SMALLINT     NOT NULL,
  order_given  VARCHAR(30)  NOT NULL,              -- 'P1,P2,P3,P4,P5,P6'
  is_correct   TINYINT      NOT NULL,
  at_time      TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),  -- ADDED
  PRIMARY KEY (session_id, try_no),
  CONSTRAINT fk_timeline_session FOREIGN KEY (session_id) REFERENCES sessions(session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS duel_answers (
  session_id   VARCHAR(36)  NOT NULL,
  round_no     TINYINT      NOT NULL,
  try_no       SMALLINT     NOT NULL,
  said_lie     TINYINT      NOT NULL,
  proof        VARCHAR(20)  NOT NULL,              -- ADDED (was proof_pearl): 1 or 2 pearls, e.g. 'P2,P3'
  reason       VARCHAR(120) NOT NULL,              -- ADDED: the reason the child picked
  is_correct   TINYINT      NOT NULL,
  at_time      TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),  -- ADDED
  PRIMARY KEY (session_id, round_no, try_no),
  CONSTRAINT fk_duel_session FOREIGN KEY (session_id) REFERENCES sessions(session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hint_uses (
  id           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,  -- ADDED
  session_id   VARCHAR(36)  NOT NULL,
  puzzle_key   VARCHAR(20)  NOT NULL,
  level_no     TINYINT      NOT NULL,
  at_time      TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),  -- ADDED
  INDEX idx_hints_session (session_id),
  CONSTRAINT fk_hintuse_session FOREIGN KEY (session_id) REFERENCES sessions(session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS verdicts (
  session_id   VARCHAR(36)  NOT NULL,
  try_no       SMALLINT     NOT NULL,              -- ADDED: one row per try
  named        VARCHAR(40)  NOT NULL,
  proof        VARCHAR(20)  NOT NULL,
  is_correct   TINYINT      NOT NULL,
  legend_text  TEXT,
  at_time      TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),  -- ADDED
  PRIMARY KEY (session_id, try_no),
  CONSTRAINT fk_verdict_session FOREIGN KEY (session_id) REFERENCES sessions(session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS assessment_answers (   -- ADDED: before/after answers
  session_id   VARCHAR(36)  NOT NULL,
  item_id      VARCHAR(10)  NOT NULL,
  choice       VARCHAR(120) NOT NULL,
  is_correct   TINYINT      NOT NULL,
  at_time      TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (session_id, item_id),
  CONSTRAINT fk_assess_session FOREIGN KEY (session_id) REFERENCES sessions(session_id),
  CONSTRAINT fk_assess_item    FOREIGN KEY (item_id)    REFERENCES assessment_items(item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
