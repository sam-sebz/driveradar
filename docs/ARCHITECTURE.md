# DriveRadar architecture

## Layers

```
backend/app/
  api/routes/     HTTP only: validate input, call a service, shape the response
  services/       business logic and transactions (auth, drives, profile, analytics)
  repositories/   SQL queries (SQLAlchemy 2)
  models/         tables
  domain/         pure Python, no database and no HTTP: parsing, extraction, eligibility,
                  skills, role categories, LLM clients
  core/           config, logging, errors, security, rate limiting
```

Routes never contain business rules. The `domain` package can be unit-tested in
milliseconds and has its own coverage gate (≥70%; currently 98%).

## Data model

```mermaid
erDiagram
    users ||--o{ drives : "uploads"
    users ||--o{ user_drives : "tracks"
    drives ||--o{ user_drives : "tracked in"
    users ||--o{ refresh_tokens : "has"

    users {
        uuid id PK
        varchar email UK "stored lower-case"
        varchar password_hash "bcrypt"
        varchar role "student | coordinator"
        varchar name
        varchar branch
        int batch
        float cgpa "0-10"
        float pct_10
        float pct_12
        int backlogs
        text_arr skills "normalised"
        timestamptz created_at
    }
    drives {
        uuid id PK
        uuid uploaded_by FK
        varchar company
        varchar role
        varchar role_category
        varchar location
        float ctc_lpa_min
        float ctc_lpa_max
        int stipend_per_month
        timestamptz deadline "stored UTC, shown IST"
        date joining_date
        float bond_years
        bigint bond_penalty_inr
        float min_cgpa
        float min_ug_percent
        float min_percent_10th
        float min_percent_12th
        int max_active_backlogs
        text_arr eligible_branches
        int_arr eligible_batch
        text_arr required_skills
        text_arr selection_process
        text notes
        text raw_text
        varchar source_filename
        varchar stored_path
        varchar content_hash "sha256 of normalised role text"
        varchar extraction_provider
        jsonb extracted_original "extractor output before edits"
        timestamptz created_at
    }
    user_drives {
        uuid user_id PK
        uuid drive_id PK
        varchar eligibility "eligible | not_eligible | unknown"
        jsonb eligibility_reasons
        float match_score "null if notice lists no skills"
        text_arr matched_skills
        text_arr missing_skills
        varchar status
        timestamptz updated_at
    }
    refresh_tokens {
        uuid id PK
        uuid user_id FK
        varchar token_hash UK "sha256"
        timestamptz expires_at
        timestamptz revoked_at
        timestamptz created_at
    }
```

Indexes: `users(email)` unique, `drives(uploaded_by)`, `drives(deadline)`,
`drives(content_hash)`, `user_drives(user_id, status)`, `refresh_tokens(user_id)`.
Foreign keys cascade on delete. CHECK constraints guard `role`, `eligibility`, `status`
and the CGPA range.

**Why `user_drives` is separate from `drives`.** A drive is a fact about a notice. The
eligibility result, match score and status are facts about one student and that notice.
Keeping them apart means a profile change only recomputes `user_drives` rows, and it
leaves room to share one drive between students later.

## Request flow: upload

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant R as routes/drives.py
    participant S as DriveService
    participant P as domain.parsing
    participant X as Extractor (mock or LLM)
    participant E as eligibility + skills
    participant DB as PostgreSQL
    participant FS as uploads volume

    B->>R: POST /drives/upload (file or text, Bearer JWT)
    R->>R: authenticate, require student role
    R->>S: upload_file(user, name, bytes <= 10 MB + 1)
    S->>P: parse_bytes: magic bytes + extension check
    P-->>S: role_blocks (1, or N for a multi-role XLSX)
    S->>FS: save original under a random name
    loop each role block
        S->>X: run(text)
        X-->>S: DriveInfo + provider used
        S->>S: normalise skills and branches, categorise role
        S->>DB: INSERT drives
        S->>E: evaluate(profile, requirements), match_skills
        S->>DB: INSERT user_drives
    end
    S->>DB: COMMIT
    S-->>R: drives
    R-->>B: 201 {"drives": [...]}
```

Failure paths:
- **Wrong type:** 415 `UNSUPPORTED_FILE`.
- **Too big:** 413 `FILE_TOO_LARGE`.
- **No text found:** 422 `EMPTY_DOCUMENT`.
- **Corrupt file:** 422 `UNREADABLE_FILE`.
- **Error after the file is saved:** the stored file is deleted and the transaction rolls
  back.

## Request flow: LLM extraction with fallback

```mermaid
flowchart TD
    A["role text"] --> L{"text > 60,000 chars?"}
    L -- yes --> F["RuleBasedExtractor (provider = mock_fallback)"]
    L -- no --> C1["LLM call 1: JSON schema output"]
    C1 -- provider error --> F
    C1 --> V1{"valid DriveInfo?"}
    V1 -- yes --> OK["use LLM result"]
    V1 -- no --> C2["LLM call 2 with the validation error message"]
    C2 -- provider error --> F
    C2 --> V2{"valid?"}
    V2 -- yes --> OK
    V2 -- no --> F
```

Every result records which provider produced it (`drives.extraction_provider`).

## Request flow: auth

- **Signup / login:** bcrypt check, then a 15-minute HS256 access JWT
  (`sub`, `role`, `type=access`) plus an opaque refresh token. Only the token's SHA-256
  is stored. Login is rate limited per IP + email, and an unknown email still runs a bcrypt
  check so response time does not reveal which emails exist.
- **Refresh:** look up the hash, then:
  - if it was already revoked: revoke every token for that user (theft detection) → 401
  - if it has expired → 401
  - otherwise: revoke it and issue a new pair (rotation)
- **Every request:** the bearer JWT is verified, then the user is loaded, so a deleted
  user's token stops working at once.

## Observability

- Every log line is JSON with `request_id`. The ID is taken from an incoming
  `X-Request-ID` header or generated, and echoed back in the response header.
- Each request logs method, path, status and `duration_ms`. Extraction logs which provider
  ran and LLM latency. Uploaded text and file names are not logged.
- `GET /health` does a real `SELECT 1`. Docker healthchecks use it, and the frontend
  waits for a healthy backend.
