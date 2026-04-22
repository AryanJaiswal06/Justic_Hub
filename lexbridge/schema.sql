

CREATE DATABASE IF NOT EXISTS lexbridge CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lexbridge;

-- ── Users ──────────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    uuid            CHAR(36)        NOT NULL UNIQUE DEFAULT (UUID()),
    full_name       VARCHAR(120)    NOT NULL,
    email           VARCHAR(180)    NOT NULL UNIQUE,
    phone           VARCHAR(20)     NULL,
    password_hash   VARCHAR(255)    NOT NULL,
    role            ENUM('client','lawyer','admin') NOT NULL DEFAULT 'client',
    avatar_url      VARCHAR(500)    NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN         NOT NULL DEFAULT FALSE,
    email_verified  BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login      DATETIME        NULL,
    INDEX idx_email  (email),
    INDEX idx_role   (role)
) ENGINE=InnoDB;

-- ── Lawyer Profiles ────────────────────────────────────────────────────────────
CREATE TABLE lawyer_profiles (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id             INT UNSIGNED NOT NULL UNIQUE,
    bar_council_no      VARCHAR(50)  NOT NULL,
    specializations     JSON         NULL,
    experience_years    TINYINT UNSIGNED NOT NULL DEFAULT 0,
    court_levels        JSON         NULL,
    languages           JSON         NULL,
    bio                 TEXT         NULL,
    consultation_fee    DECIMAL(10,2) NULL,
    availability_status ENUM('available','busy','offline') NOT NULL DEFAULT 'available',
    avg_rating          DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    total_ratings       INT UNSIGNED NOT NULL DEFAULT 0,
    total_cases         INT UNSIGNED NOT NULL DEFAULT 0,
    verified_at         DATETIME     NULL,
    verified_by         INT UNSIGNED NULL,
    CONSTRAINT fk_lp_user    FOREIGN KEY (user_id)    REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_admin   FOREIGN KEY (verified_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ── Cases ──────────────────────────────────────────────────────────────────────
CREATE TABLE cases (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_number     VARCHAR(30)     NOT NULL UNIQUE,
    client_id       INT UNSIGNED    NOT NULL,
    lawyer_id       INT UNSIGNED    NULL,
    case_type       VARCHAR(80)     NOT NULL,
    title           VARCHAR(255)    NOT NULL,
    description     TEXT            NULL,
    priority        ENUM('low','medium','high','urgent') NOT NULL DEFAULT 'medium',
    status          ENUM('pending','active','in_progress','closed','dismissed') NOT NULL DEFAULT 'pending',
    stage           VARCHAR(80)     NULL,
    next_hearing    DATE            NULL,
    opened_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at       DATETIME        NULL,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_client  (client_id),
    INDEX idx_lawyer  (lawyer_id),
    INDEX idx_status  (status),
    CONSTRAINT fk_case_client FOREIGN KEY (client_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_case_lawyer FOREIGN KEY (lawyer_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ── Case Updates / Timeline ────────────────────────────────────────────────────
CREATE TABLE case_updates (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_id     INT UNSIGNED NOT NULL,
    author_id   INT UNSIGNED NOT NULL,
    update_type ENUM('status_change','note','hearing_scheduled','document_added','lawyer_assigned') NOT NULL,
    content     TEXT         NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cu_case   FOREIGN KEY (case_id)   REFERENCES cases (id) ON DELETE CASCADE,
    CONSTRAINT fk_cu_author FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── Documents ─────────────────────────────────────────────────────────────────
CREATE TABLE documents (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_id         INT UNSIGNED    NULL,
    uploaded_by     INT UNSIGNED    NOT NULL,
    file_name       VARCHAR(255)    NOT NULL,
    original_name   VARCHAR(255)    NOT NULL,
    mime_type       VARCHAR(100)    NOT NULL,
    file_size_bytes INT UNSIGNED    NOT NULL,
    storage_path    VARCHAR(500)    NOT NULL,
    doc_type        ENUM('evidence','contract','petition','judgment','identity','other') NOT NULL DEFAULT 'other',
    status          ENUM('pending','under_review','verified','rejected') NOT NULL DEFAULT 'pending',
    reviewed_by     INT UNSIGNED    NULL,
    reviewed_at     DATETIME        NULL,
    uploaded_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_case      (case_id),
    INDEX idx_uploader  (uploaded_by),
    INDEX idx_status    (status),
    CONSTRAINT fk_doc_case      FOREIGN KEY (case_id)     REFERENCES cases (id) ON DELETE SET NULL,
    CONSTRAINT fk_doc_uploader  FOREIGN KEY (uploaded_by) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_doc_reviewer  FOREIGN KEY (reviewed_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ── Conversations ─────────────────────────────────────────────────────────────
CREATE TABLE conversations (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_id         INT UNSIGNED    NULL,
    participant_a   INT UNSIGNED    NOT NULL,
    participant_b   INT UNSIGNED    NOT NULL,
    last_message_at DATETIME        NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_case  (case_id),
    -- FIX (high): removed the UNIQUE KEY with nullable case_id.
    -- MySQL treats NULL != NULL in unique indexes, so two rows with case_id=NULL
    -- for the same pair would be allowed, creating duplicate conversations.
    -- Deduplication is now enforced in get_or_create_conversation() in application code.
    CONSTRAINT fk_conv_case  FOREIGN KEY (case_id)       REFERENCES cases (id) ON DELETE SET NULL,
    CONSTRAINT fk_conv_a     FOREIGN KEY (participant_a) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_conv_b     FOREIGN KEY (participant_b) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── Messages ──────────────────────────────────────────────────────────────────
CREATE TABLE messages (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT UNSIGNED    NOT NULL,
    sender_id       INT UNSIGNED    NOT NULL,
    content         TEXT            NOT NULL,
    is_read         BOOLEAN         NOT NULL DEFAULT FALSE,
    sent_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- FIX (medium): composite index on (conversation_id, id DESC) for efficient
    -- cursor-based pagination used by get_messages()
    INDEX idx_conv_id (conversation_id, id),
    INDEX idx_sent    (sent_at),
    CONSTRAINT fk_msg_conv   FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE,
    CONSTRAINT fk_msg_sender FOREIGN KEY (sender_id)       REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── Ratings & Reviews ─────────────────────────────────────────────────────────
CREATE TABLE ratings (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_id     INT UNSIGNED NOT NULL,
    reviewer_id INT UNSIGNED NOT NULL,
    lawyer_id   INT UNSIGNED NOT NULL,
    score       TINYINT UNSIGNED NOT NULL CHECK (score BETWEEN 1 AND 5),
    review      TEXT         NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_rating (case_id, reviewer_id),
    CONSTRAINT fk_rat_case     FOREIGN KEY (case_id)     REFERENCES cases (id) ON DELETE CASCADE,
    CONSTRAINT fk_rat_reviewer FOREIGN KEY (reviewer_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_rat_lawyer   FOREIGN KEY (lawyer_id)   REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── Billing / Payments ────────────────────────────────────────────────────────
CREATE TABLE payments (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    case_id         INT UNSIGNED    NOT NULL,
    client_id       INT UNSIGNED    NOT NULL,
    lawyer_id       INT UNSIGNED    NOT NULL,
    amount          DECIMAL(12,2)   NOT NULL,
    currency        CHAR(3)         NOT NULL DEFAULT 'INR',
    gateway_txn_id  VARCHAR(120)    NULL UNIQUE,
    payment_type    ENUM('consultation','retainer','milestone','final') NOT NULL,
    status          ENUM('pending','completed','failed','refunded') NOT NULL DEFAULT 'pending',
    paid_at         DATETIME        NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_case    (case_id),
    INDEX idx_client  (client_id),
    CONSTRAINT fk_pay_case   FOREIGN KEY (case_id)   REFERENCES cases (id) ON DELETE RESTRICT,
    CONSTRAINT fk_pay_client FOREIGN KEY (client_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_pay_lawyer FOREIGN KEY (lawyer_id) REFERENCES users (id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ── Disputes ──────────────────────────────────────────────────────────────────
CREATE TABLE disputes (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    filed_by    INT UNSIGNED NOT NULL,
    against     INT UNSIGNED NOT NULL,
    case_id     INT UNSIGNED NULL,
    subject     VARCHAR(255) NOT NULL,
    description TEXT         NULL,
    severity    ENUM('low','medium','high') NOT NULL DEFAULT 'medium',
    status      ENUM('open','investigating','resolved','dismissed') NOT NULL DEFAULT 'open',
    resolved_by INT UNSIGNED NULL,
    resolved_at DATETIME     NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dis_filer    FOREIGN KEY (filed_by)    REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_dis_against  FOREIGN KEY (against)     REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_dis_case     FOREIGN KEY (case_id)     REFERENCES cases (id) ON DELETE SET NULL,
    CONSTRAINT fk_dis_resolver FOREIGN KEY (resolved_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ── Notifications ─────────────────────────────────────────────────────────────
CREATE TABLE notifications (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     INT UNSIGNED NOT NULL,
    type        VARCHAR(60)  NOT NULL,
    title       VARCHAR(200) NOT NULL,
    body        TEXT         NULL,
    link        VARCHAR(300) NULL,
    is_read     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user     (user_id),
    INDEX idx_is_read  (is_read),
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── OTP / Tokens ──────────────────────────────────────────────────────────────
CREATE TABLE auth_tokens (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     INT UNSIGNED NOT NULL,
    token       VARCHAR(120) NOT NULL UNIQUE,
    token_type  ENUM('email_verify','password_reset','otp') NOT NULL,
    expires_at  DATETIME     NOT NULL,
    used_at     DATETIME     NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tok_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── FIX (critical): Seed admin via a safe script, not a hardcoded placeholder hash.
-- The INSERT below is intentionally removed. Create the admin account by running:
--
--   python manage.py create_admin
--
-- Or manually generate a real bcrypt hash and insert:
--   python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('YourStrongPassword123!'))"
-- Then run:
--   INSERT INTO users (full_name, email, role, password_hash, is_active, is_verified, email_verified)
--   VALUES ('Platform Admin', 'admin@lexbridge.in', 'admin', '<paste_hash_here>', TRUE, TRUE, TRUE);
