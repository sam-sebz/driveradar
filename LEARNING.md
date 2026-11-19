# LEARNING: how DriveRadar works and why

This file explains every major decision in simple English, then gives 20 likely interview
questions with model answers. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) alongside it.

---

## Part 1: Design decisions

### 1. Layered backend: routes → services → repositories → models, plus a pure `domain`

- **What:** HTTP code (routes) only validates input and calls a service. Services hold the
  business steps. Repositories hold SQL. The `domain` package (parsing, extraction,
  eligibility, skills) imports nothing from the database or the web framework.
- **Why:** The most important logic, "is this student eligible?", can be tested with
  plain function calls in milliseconds. Each layer can also change without breaking the
  others: switching Postgres for another database touches repositories only.
- **Alternatives:** Put everything in route functions (fast to write, hard to test). Or a
  full "clean architecture" with interfaces for every repository (more ceremony than a
  project this size needs).
- **Trade-off:** More files and a little indirection, in exchange for testability and clear
  places to look.

### 2. The eligibility engine is pure Python rules, not an LLM

- **What:** `domain/eligibility/engine.py` checks CGPA, UG %, Class X/XII %, backlogs,
  branch and batch. Each rule returns `pass`, `fail`, `unknown` or `not_specified`, with
  a sentence explaining why.
- **Why:** Eligibility is a yes/no decision that affects someone's career. It has to be
  deterministic, explainable and testable, and an LLM is none of those reliably. The LLM
  (when enabled) only *reads* the notice; the rules *decide*.
- **The four statuses:**
  - `not_specified`: the notice has no rule, so it does not restrict anyone.
  - `unknown`: the notice has a rule but the profile lacks the value.
  - Overall result: any `fail` → not eligible; else any `unknown` → "check manually";
    else eligible.
  - A notice with *no* rules at all is also "check manually", because extraction may have
    missed them and we never guess.
- **Alternative:** Ask the LLM "is this student eligible?". Rejected: it is
  non-deterministic and cannot be unit-tested.

### 3. Extraction sits behind one interface with an offline default

- **What:**
  - `Extractor.run(text) -> ExtractionResult(info, provider)`.
  - `RuleBasedExtractor` (regex + keywords) is the default `mock` provider.
  - `LLMExtractor` wraps any `LLMClient` (Anthropic via the official SDK; OpenAI and Gemini
    via REST). It asks for JSON matching a strict schema, validates with Pydantic, retries
    once with the validation error, and falls back to the rules.
- **Why:** The app must run with no API key, in tests and in CI. Switching provider is a
  config change (`LLM_PROVIDER`), not a code change. The fallback means an LLM outage
  makes extraction worse, never broken.
- **Trade-off:** The rule extractor is brittle. The held-out notice shows it missing
  labels it was not written for (84.2% field accuracy on that one notice).

### 4. "Never guess" is enforced by design

- Every `DriveInfo` field is optional, and null means "not stated".
- The rules only fill a field when a clear pattern matches.
- A joining date given only as "July 2027" stays null, because we do not invent a day.
- The eval counts a null label as correct **only** if the extractor also returned null,
  so guessing is penalised.

### 5. PostgreSQL with arrays and JSONB

- **What:**
  - Skills, branches and batch years are `text[]` / `int[]`.
  - Eligibility reasons and the original extraction are `jsonb`.
  - Deadlines are `timestamptz` stored in UTC and shown in IST.
- **Why:** The data is relational: users, drives, and the link between them. Arrays keep
  small lists in the row they belong to, without extra join tables. JSONB stores the
  reasons exactly as the engine produced them.
- **Alternative:** MongoDB. Rejected: we need foreign keys, cascades, uniqueness
  (one email per account) and transactions.
- **Testing trick:** a custom column type falls back to JSON on SQLite. Tests run instantly
  in memory locally, and CI runs the same tests on real Postgres with the real migration.

### 6. `drives` vs `user_drives`

A drive is a fact about the notice. Eligibility, match % and application status are facts
about *one student and that notice*. So when a student changes their CGPA, only their
`user_drives` rows are recomputed. Duplicate uploads are detected with `content_hash`, so
analytics count each notice once.

### 7. Auth: short access JWT + rotating, hashed refresh tokens

- **What:**
  - The access token is a 15-minute HS256 JWT.
  - The refresh token is a random 32-byte string; the database stores only its SHA-256.
  - Each refresh revokes the old token and issues a new one (rotation).
  - Using an already-revoked token revokes *all* of that user's tokens (theft detection).
  - Passwords are hashed with bcrypt (cost 12).
- **Why:**
  - A stolen access token is useful for at most 15 minutes.
  - A database leak does not expose usable refresh tokens.
  - Rotation detects replay of a stolen refresh token.
- **Other security details:**
  - Login is rate limited (5 per minute per IP + email).
  - An unknown email still runs a bcrypt check, so response timing does not reveal which
    emails are registered.
  - Wrong password and unknown email return identical errors.
  - You cannot sign up as a coordinator.
- **Trade-off:** The frontend keeps tokens in `sessionStorage`. That is simpler than
  httpOnly cookies but readable by injected scripts. In production I would put the refresh
  token in an httpOnly, SameSite cookie.

### 8. Upload safety

- **Size:** we read at most `MAX_UPLOAD_MB + 1` bytes, so oversized files are rejected
  without buffering more.
- **Type:** checked by **magic bytes**, not only the extension. A renamed `.exe` is a 415,
  and a DOCX must actually contain `word/document.xml`.
- **Storage:** files are saved under random UUID names, never the user's filename, so path
  traversal is impossible. The delete helper double-checks the path stays inside the
  upload folder.
- **Errors:** a corrupt file becomes a 422, never a 500.
- **Limits:** XLSX reading is capped at 1,000 rows per sheet; PDFs at 50 pages.

### 9. Consistent errors and structured logs

- **Errors:** every error is `{"error": {"code", "message"}}` with the right status code:
  401, 403, 404, 409, 413, 415, 422, 429 and 503. The frontend reads `message` directly.
- **Logs:** every log line is JSON with a `request_id`, which is echoed back in the
  `X-Request-ID` header. A user can report one ID, and every log line for that request can
  be found.

### 10. Frontend: TanStack Query + zod

- **Server state:** TanStack Query caches it (drives, profile, analytics) and refetches
  after mutations. For example, saving the profile invalidates the drives, because
  eligibility changed on the server.
- **Runtime checks:** zod parses every API response, so a backend change fails loudly
  instead of rendering `undefined`.
- **Expired tokens:** the fetch wrapper refreshes once on a 401 and then retries the
  original request.

### 11. Evaluation and honesty

- **How it works:** `eval/run_eval.py` compares extractor output with hand-written labels,
  field by field. Skills and branches are compared as sets after normalisation; dates as
  instants.
- **The 100% is in-sample:** I wrote both the sample notices and the rules, so 100% on them
  is not a real accuracy claim. That is why there is a **held-out** synthetic notice the
  rules were never tuned on. Its score (84.2% fields, 0/1 exact) is the more honest number.
- **Real-world accuracy is TBD.** The next step is labelling real, anonymised notices.

### 12. One-command start

- **Order of startup:** `docker compose up` waits for Postgres to pass `pg_isready`, then
  the backend runs `alembic upgrade head`, seeds demo data (idempotent), and starts
  uvicorn. The frontend (nginx) starts only once the backend's `/health` passes.
- **Verification:** CI repeats exactly this on a fresh runner, then runs the smoke test.

---

## Part 2: 20 interview questions with model answers

**1. Walk me through what happens when a student uploads a notice.**
- The route checks the JWT and the student role, then reads at most 10 MB + 1 byte.
- The service checks the file type by magic bytes, parses it to text, and splits an XLSX
  role table into one text block per role. It saves the original under a random name.
- For each role it runs the extractor, normalises skills and branches, inserts a `drives`
  row, runs the eligibility engine and skill matcher, and inserts a `user_drives` row.
- It commits everything in one transaction and returns the list of drives.

**2. Why didn't you let the LLM decide eligibility?**
Eligibility must be deterministic, explainable and testable. The same input must always
give the same answer with a reason, and I have 40+ test cases for it. The LLM only turns
messy text into structured fields; pure rules make the decision. If extraction is wrong,
the student can fix the field, and the rules re-run.

**3. How does the LLM part work, and what if the LLM returns garbage?**
- I send the notice text with a strict JSON schema: every field present and nullable, no
  extra keys. On Claude this uses structured output via `output_config.format`.
- I validate the answer with Pydantic: ranges such as CGPA 0–10 and min CTC ≤ max CTC.
- If validation fails, I retry once and include the validation error in the prompt. If it
  fails again, or the provider is down or refuses, I fall back to the rule-based extractor.
- Each drive records which provider produced it.

**4. What does "mock" mean here? Isn't that cheating?**
It is the offline default: a real regex and keyword extractor, not fake data. It lets the
app, tests and CI run with no API key and no network. Its accuracy is measured honestly:
100% on in-sample synthetic notices, 84.2% field accuracy on a held-out synthetic notice.
I am explicit that real-world accuracy is not yet measured.

**5. How do you handle CGPA vs percentage?**
Notices state either a CGPA cut-off or a UG percentage. They go in different fields
(`min_cgpa`, `min_ug_percent`). For a percentage rule, the engine converts the student's
CGPA with a configurable factor (default ×10; some universities use 9.5) and shows the
maths in the reason: "CGPA 6.5 x 10 = 65% >= required 60%".

**6. How do branch synonyms work?**
A JSON catalogue maps names like "Computer Science and Engineering", "CSE" and "B.Tech
CSE" to a code. Groups like "Computer Science or equivalent" and "circuit branches" list
their member codes. Specialisations like CSE-IT count as their parent (CSE). That is a
documented assumption, because colleges differ. If the student's branch is not
recognised, the result is "unknown", not a guess.

**7. Why PostgreSQL and not MongoDB?**
The data is relational: users, drives and the link between them. I need foreign keys with
cascades, a unique email, and transactions so an upload of three roles is all-or-nothing.
Postgres also has `text[]` and `jsonb`, which give me document-style flexibility exactly
where I need it.

**8. How do refresh tokens work, and how do you detect token theft?**
- The refresh token is random; I store only its SHA-256 hash.
- On refresh I revoke it and issue a new pair (rotation).
- If anyone presents a token that was already rotated, someone has a copy, so I revoke
  every token for that user and force a fresh login.

**9. What security measures did you take?**
- bcrypt password hashing, short-lived JWTs, and hashed rotating refresh tokens.
- A login rate limit, identical errors and timing for a wrong password vs an unknown
  email, and no self-registration as coordinator.
- CORS limited to the frontend origin.
- File size and magic-byte checks, and random storage names.
- Parameterised queries via the ORM.
- 404 instead of 403 for other users' drives, so IDs are not leaked.
- Config only from env vars, and no secrets in git.

**10. How would you scale this to 100 colleges?**
- Run several API replicas behind a load balancer, which works because the API is
  stateless apart from two things:
  - move uploads to S3-compatible storage
  - move the rate limiter to Redis
- Run migrations as a separate deploy step, not on container start.
- Push extraction to a background queue (Celery or RQ) so LLM latency does not block
  requests.
- Add a `college_id` for tenancy, and index `user_drives` by user.

**11. What happens if two students upload the same notice?**
Each gets their own drive rows, so either can edit their copy safely. Analytics
de-duplicate by a SHA-256 of the normalised role text, so the notice counts once. A future
improvement is to share one drive row and store edits as per-user overrides.

**12. How do you test this without a real database or API key?**
- The domain layer is pure functions, so unit tests need nothing.
- API tests use FastAPI's TestClient on in-memory SQLite through a column type that maps
  Postgres arrays and JSONB to JSON.
- CI runs the same tests on real PostgreSQL with the Alembic migration, plus `alembic check`.
- LLM clients are tested against mocked HTTP: success, refusal, cut-off output, bad JSON,
  network errors.
- The frontend is tested with Vitest and a fake `fetch`.

**13. What was the hardest bug?**
- An XLSX with three roles shares one stored file, so deleting one role must not delete
  the file the other two still use. I count references before deleting.
- The SQLite tests also hid a cascade bug: SQLite ignores `ON DELETE CASCADE` unless
  `PRAGMA foreign_keys=ON` is set.
- Manual UI testing caught a regex looking for "eligible" that missed lines starting with
  "Eligibility:". I fixed it and added a regression test.

**14. What does your coverage number really mean?**
It is line coverage: 98% on the core `domain` package, 97% on the backend overall, 95% on
the frontend. It shows which lines ran during tests, not that the logic is correct. That
is why the eligibility engine has explicit edge-case tests: exact cut-off, float noise,
missing data, specialisations and unknown branches.

**15. How do you handle time zones?**
Notices are written in IST. A deadline without a time zone is treated as IST, and one
without a time closes at 23:59 IST. The database stores UTC (`timestamptz`), the API
returns IST (`+05:30`), and the frontend formats with `Asia/Kolkata`. The "closes in
< 24h" badge is computed on the server.

**16. Why TanStack Query instead of Redux?**
Almost all state here is server state: drives, profile, analytics. TanStack Query
already handles caching, loading and error states, and invalidation after mutations.
Redux would mean writing that by hand. The only client state is the auth token.

**17. What are the main failure cases, and how does the app behave?**
| Failure | Behaviour |
|---|---|
| Scanned PDF | 422 with a clear message (no OCR yet) |
| Corrupt file | 422 |
| Wrong type | 415 |
| Too big | 413 |
| LLM down | falls back to rules (`mock_fallback`) |
| DB down | `/health` returns 503 and Docker marks the backend unhealthy |
| Expired access token | the frontend refreshes once, then logs out |

**18. How did you make sure the README numbers are honest?**
- Every number comes from a script whose raw output is committed:
  - accuracy: `eval/results.md`
  - coverage: `benchmarks/`
- Synthetic data is labelled "synthetic", and I separate in-sample from held-out results.
- Anything not measured, like real-world accuracy, LLM accuracy and user count, is
  written as TBD.

**19. Why is `extracted_original` stored?**
It keeps the extractor's output next to what the student corrected via "edit if wrong".
That gives free labelled data: I can measure how often each field gets corrected, and use
those corrections to improve the rules or evaluate prompts.

**20. What would you do differently?**
- Collect and label real (consented, anonymised) notices first, so I measure on what users
  actually upload.
- Use httpOnly cookies for refresh tokens.
- Make extraction asynchronous from the start.
- Add OCR.
- Consider sharing drive rows between students, with per-user overrides, instead of
  copying them.
