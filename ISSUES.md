# WikiSeed Documentation Review - GitHub Issues

Generated from comprehensive review of claude.md on 2025-12-02

Total Issues: 49
- Critical: 8
- Moderate: 12
- Minor: 10
- Questions/Clarifications: 19

---

## 🔴 CRITICAL PRIORITY ISSUES

### Issue #1: Controller Container Missing from Architecture Diagram

**Priority:** Critical
**Labels:** documentation, architecture, bug
**File:** claude.md:18-28

**Description:**
The container architecture diagram is missing the Controller container, even though it's listed in the container responsibilities section (line 31).

**Current State:**
```
┌─────────────────────────────────────┐
│ WikiSeed Ecosystem                  │
├─────────────┬──────────┬────────────┤
│   Scraper   │Downloader│  Creator   │
├─────────────┼──────────┼────────────┤
│   Seeder    │ Sharing  │   Web UI   │
├─────────────┴──────────┴────────────┤
│         PostgreSQL Database         │
└─────────────────────────────────────┘
```

**Expected:**
Add Controller to the diagram as an orchestration layer above or alongside other containers.

**Impact:**
- Architectural understanding is unclear
- New contributors won't understand Controller's role in the system
- Diagram doesn't match implementation plan

---

### Issue #2: Shared Directory Distribution Strategy Undefined

**Priority:** Critical
**Labels:** architecture, documentation, needs-decision
**File:** claude.md:226-251

**Description:**
The project structure shows a `shared/` directory containing common code (database.py, models.py, utils.py), but there's no explanation of how this code is distributed to the individual Docker containers.

**Questions:**
- Is shared code copied into each Docker image at build time?
- Is it mounted as a volume at runtime?
- Is it published as an internal Python package?
- How do changes to shared code get deployed?

**Impact:**
- Cannot design Docker build process without this information
- Hot-reload strategy unclear for development
- Deployment strategy is ambiguous
- Container interdependencies not defined

**Recommendation:**
Document the complete strategy for shared code distribution, including:
1. Build-time vs runtime distribution
2. Version synchronization across containers
3. Update/deployment process
4. Development hot-reload implications

---

### Issue #3: Database Schema Not Defined

**Priority:** Critical
**Labels:** database, documentation, blocker
**File:** claude.md (Controller + Database Foundation section)

**Description:**
No database schema is defined in the documentation. Tables, columns, types, constraints, and relationships are not specified.

**Missing Information:**
- Table definitions (jobs, dumps, torrents, metrics, etc.)
- Column names and types
- Primary keys and foreign keys
- Indexes (critical for performance)
- Constraints (unique, not null, check constraints)
- Relationships between tables

**Impact:**
- Cannot begin implementation without schema
- Database migration strategy cannot be planned
- Query optimization cannot be designed
- ORM models cannot be created

**Recommendation:**
Add a complete database schema section including:
1. ERD (Entity Relationship Diagram)
2. CREATE TABLE statements or equivalent
3. Index definitions for high-traffic queries
4. Sample data for testing

---

### Issue #4: No Database Backup Strategy Defined

**Priority:** Critical
**Labels:** database, operations, disaster-recovery
**File:** claude.md (missing section)

**Description:**
The system will store critical preservation data, torrent metadata, job state, and metrics in PostgreSQL, but there's no backup or disaster recovery strategy defined.

**Missing Information:**
- Backup frequency (hourly, daily, weekly?)
- Backup retention policy
- Backup storage location
- Point-in-time recovery capability
- Restore testing procedures
- Hot backup vs cold backup strategy

**Impact:**
- Risk of catastrophic data loss
- No recovery plan if database corrupted
- Production deployment would be risky
- Cannot calculate storage requirements for backups

**Recommendation:**
Add database backup section covering:
1. Automated backup schedule
2. Retention policy (e.g., 7 daily, 4 weekly, 12 monthly)
3. Backup verification process
4. Documented restore procedure
5. Disaster recovery RTO/RPO targets

---

### Issue #5: Database Polling Efficiency Not Addressed

**Priority:** Critical
**Labels:** performance, architecture, needs-decision
**File:** claude.md:329-333

**Description:**
The inter-container communication strategy relies on database polling, but critical efficiency details are missing.

**Current Specification:**
```
- Each container polls the `jobs` table for work
```

**Missing Information:**
- Polling interval (every second? 5 seconds? minute?)
- Jitter/randomization to avoid thundering herd
- How to handle high-frequency job creation
- Database load under polling

**Impact:**
- Could cause high database load at scale
- All containers polling simultaneously causes spikes
- Inefficient use of resources
- Potential race conditions

**Recommendations:**
Either:
1. Specify polling intervals with jitter (e.g., "every 5-10 seconds with random offset")
2. Switch to PostgreSQL LISTEN/NOTIFY for event-driven architecture
3. Implement hybrid: polling with backoff when idle, NOTIFY for high-priority jobs

---

### Issue #6: Database Indexes Not Specified

**Priority:** Critical
**Labels:** database, performance, blocker
**File:** claude.md (missing from schema section)

**Description:**
Job assignment queries will run frequently, but no indexes are defined. Without proper indexes, job polling will become slow as the job table grows.

**Critical Queries Needing Indexes:**
- Finding pending jobs by type: `WHERE job_type = ? AND status = 'pending'`
- Finding assigned jobs by container: `WHERE assigned_to = ? AND status = 'assigned'`
- Finding jobs by dump/torrent: `WHERE dump_id = ?`
- Sorting jobs by creation time: `ORDER BY created_at`

**Impact:**
- Slow job assignment as table grows
- High database CPU usage
- Query timeouts at scale
- Poor system performance

**Recommendation:**
Define indexes for all high-traffic queries:
```sql
CREATE INDEX idx_jobs_type_status ON jobs(job_type, status);
CREATE INDEX idx_jobs_assigned_to ON jobs(assigned_to, status);
CREATE INDEX idx_jobs_dump_id ON jobs(dump_id);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
```

---

### Issue #7: Version Requirements Not Specified

**Priority:** Critical
**Labels:** documentation, dependencies, blocker
**File:** claude.md:195-214

**Description:**
The technical stack is defined, but no version requirements are specified for any component.

**Missing Version Requirements:**
- Python (3.9+? 3.10+? 3.11+? 3.12+?)
- PostgreSQL (13+? 14+? 15+? 16+?)
- Node.js (for React build)
- Docker
- docker-compose
- Flask
- SQLAlchemy
- Alembic
- React
- Chart.js

**Impact:**
- Environment setup unclear
- Compatibility issues likely
- Dependency conflicts
- Cannot create Dockerfile without knowing base image version
- Cannot test in CI without knowing what to install

**Recommendation:**
Add a "Version Requirements" section specifying:
```yaml
Python: ">=3.11"
PostgreSQL: ">=15"
Node.js: ">=18"
Docker: ">=24.0"
docker-compose: ">=2.20"
```

---

### Issue #8: Secrets Management Strategy Not Defined

**Priority:** Critical
**Labels:** security, configuration, blocker
**File:** claude.md:169-183

**Description:**
The system will need API keys and credentials (Internet Archive, torrent sites), but there's no secrets management strategy defined.

**Missing Information:**
- How are secrets stored?
- Are they in YAML config files? (security risk!)
- Environment variables?
- Secrets vault (HashiCorp Vault, Docker secrets)?
- How are secrets rotated?
- How are secrets backed up?

**Security Concerns:**
- Secrets in YAML files could be committed to git
- Secrets in config files visible in container filesystem
- No rotation mechanism
- No audit trail of secret access

**Impact:**
- Major security vulnerability
- Cannot deploy to production safely
- Risk of credential leaks
- Compliance issues

**Recommendation:**
Add secrets management section covering:
1. Use Docker secrets or environment variables
2. Never store secrets in YAML files
3. Document secret rotation procedures
4. Implement secret scanning in CI/CD
5. Use separate secrets for dev/staging/prod

---

## 🟡 MODERATE PRIORITY ISSUES

### Issue #9: Job Quarantine Max Retries Not Defined

**Priority:** Moderate
**Labels:** documentation, job-queue
**File:** claude.md:324

**Description:**
The documentation mentions quarantining jobs after "maximum retry attempts" but doesn't specify what the maximum is.

**Current Text:**
```
- Quarantine jobs after maximum retry attempts
```

**Context:**
- Chunk retries are specified as "max 3 attempts per chunk" (line 71)
- Job-level retries are mentioned but not quantified

**Impact:**
- Implementation ambiguity
- Cannot estimate failure handling behavior
- Testing strategy unclear

**Recommendation:**
Specify job-level retry count, e.g.:
```
- Quarantine jobs after 5 failed attempts with exponential backoff
```

---

### Issue #10: Configuration Backup/Rollback Mechanism Missing

**Priority:** Moderate
**Labels:** configuration, operations, enhancement
**File:** claude.md:169-183

**Description:**
Configuration changes are validated and applied gracefully, but there's no backup, versioning, or rollback capability defined.

**Missing Features:**
- Configuration versioning
- Configuration backup before changes
- Rollback to previous configuration
- Configuration change history/audit log

**Risk:**
- Bad configuration change could break system
- No way to undo changes
- No history of what changed when

**Recommendation:**
Add configuration management features:
1. Auto-backup config before applying changes
2. Keep last N configuration versions
3. Web UI "Rollback" button
4. Configuration change audit log

---

### Issue #11: No CI/CD Pipeline Defined

**Priority:** Moderate
**Labels:** devops, documentation, enhancement
**File:** claude.md:215-274

**Description:**
Development workflow is documented, but there's no CI/CD pipeline specification.

**Missing Information:**
- GitHub Actions workflows?
- Automated testing on PR?
- Automated builds?
- Container image publishing?
- Deployment automation?

**Impact:**
- Manual testing burden
- No automated quality checks
- Risk of breaking changes
- Slow development feedback loop

**Recommendation:**
Add CI/CD section covering:
1. GitHub Actions for automated testing
2. Lint and type checking on every PR
3. Automated Docker image builds
4. Integration test suite
5. Deployment automation

---

### Issue #12: Test Coverage Requirements Missing

**Priority:** Moderate
**Labels:** testing, documentation, quality
**File:** claude.md:260-274

**Description:**
Testing strategy mentions unit and integration tests, but no coverage requirements or quality gates defined.

**Missing Information:**
- Minimum code coverage target (80%? 90%?)
- Coverage measurement tools (coverage.py?)
- PR merge requirements
- Coverage reporting

**Impact:**
- No quality baseline
- Cannot enforce testing standards
- Technical debt may accumulate

**Recommendation:**
Specify test coverage requirements:
```
- Minimum 80% line coverage for all containers
- 100% coverage for shared utilities
- Coverage reports in CI/CD
- Block PR merge if coverage decreases
```

---

### Issue #13: Code Quality Tools Not Specified

**Priority:** Moderate
**Labels:** devops, documentation, quality
**File:** claude.md:215-274

**Description:**
Python backend is defined but no code quality tools specified (linters, formatters, type checkers).

**Missing Tools:**
- Code formatter (black, autopep8?)
- Linter (pylint, flake8, ruff?)
- Type checker (mypy?)
- Import sorter (isort?)
- Pre-commit hooks?

**Impact:**
- Inconsistent code style
- No static analysis
- Type errors not caught
- Code review friction

**Recommendation:**
Add code quality tools section:
```yaml
Formatter: black
Linter: ruff
Type Checker: mypy
Import Sorter: isort
Pre-commit: yes
```

---

### Issue #14: RSS Feed Format Not Specified

**Priority:** Moderate
**Labels:** documentation, distribution
**File:** claude.md:135-150

**Description:**
RSS feeds are listed as a distribution method, but no format or structure is specified.

**Missing Information:**
- RSS feed URL structure
- Feed update frequency
- What information is included in feed items?
- RSS vs Atom format?
- Feed discovery mechanism

**Impact:**
- Cannot implement RSS without spec
- Users won't know how to subscribe
- Feed format unclear

**Recommendation:**
Add RSS feed specification:
```xml
Example feed structure:
- Title: WikiSeed - New Wikimedia Torrents
- Update frequency: Daily
- Item format: Torrent name, size, date, magnet link
```

---

### Issue #15: Log Retention After 90 Days Unclear

**Priority:** Moderate
**Labels:** documentation, operations, monitoring
**File:** claude.md:162

**Description:**
Logs have 90-day retention, but what happens after 90 days is not specified.

**Current Text:**
```
- **Operation logs**: Structured logging with 90-day retention
```

**Missing Information:**
- Archive to cold storage?
- Compress and keep?
- Delete permanently?
- Different retention for different log levels?

**Impact:**
- Storage planning unclear
- Compliance requirements unknown
- Cannot estimate storage needs

**Recommendation:**
Specify complete log lifecycle:
```
- 90-day retention in hot storage
- Compress and archive to cold storage for 1 year
- Delete after 1 year total retention
- Critical errors retained indefinitely
```

---

### Issue #16: Storage Threshold Logic Unclear

**Priority:** Moderate
**Labels:** documentation, storage, clarification-needed
**File:** claude.md:44-47

**Description:**
Storage thresholds seem backwards: cleanup triggers at 85% but pause at 90%.

**Current Text:**
```
- Queue pause: 90% (finish active downloads, stop new downloads)
- Cleanup trigger: 85% (start cleanup process)
```

**Question:**
Why trigger cleanup at a lower threshold than pause? Typically cleanup would trigger first, then pause if cleanup can't free enough space.

**Recommendation:**
Clarify the intended workflow:
- Option A: Cleanup at 85%, if it fails and reaches 90%, then pause
- Option B: Actually meant to be cleanup at 90%, pause at 95%
- Document the complete threshold logic flow

---

### Issue #17: Job Assignment Race Condition Prevention Not Documented

**Priority:** Moderate
**Labels:** database, architecture, concurrency
**File:** claude.md:276-356

**Description:**
Multiple containers poll for jobs, but race condition prevention is not documented.

**Problem:**
Two containers could simultaneously:
1. SELECT same pending job
2. Both UPDATE it to assigned
3. Both start working on it

**Missing Information:**
- Pessimistic locking (SELECT FOR UPDATE)?
- Optimistic locking (version number)?
- Unique constraints?
- Transaction isolation level?

**Impact:**
- Duplicate work
- Wasted resources
- Data corruption risk

**Recommendation:**
Document race condition prevention:
```sql
-- Use SELECT FOR UPDATE SKIP LOCKED
SELECT * FROM jobs
WHERE status = 'pending' AND job_type = ?
ORDER BY created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

---

### Issue #18: Frontend Build Process Not Defined

**Priority:** Moderate
**Labels:** documentation, frontend
**File:** claude.md:195-214

**Description:**
React frontend is mentioned, but build process and tooling are not specified.

**Missing Information:**
- Build tool (webpack, vite, esbuild, create-react-app?)
- Development server
- Production build process
- Asset optimization
- Bundle size targets

**Impact:**
- Cannot set up frontend development
- Build process unclear
- Optimization strategy unknown

**Recommendation:**
Add frontend build section:
```
Build Tool: Vite
Dev Server: Vite dev server with HMR
Build: Static assets bundled in Web UI container
Bundle Size Target: <500KB gzipped
```

---

### Issue #19: Fragile External Dependency on WikiStats URL

**Priority:** Moderate
**Labels:** reliability, architecture, risk
**File:** claude.md:187

**Description:**
Auto-discovery relies on a specific WikiStats URL that could change.

**Current Text:**
```
Weekly scans of https://wikistats.wmcloud.org/wikimedias_wiki.php
```

**Risks:**
- URL could change
- Service could be discontinued
- Format could change
- Network issues

**Impact:**
- Discovery could break
- No fallback mechanism
- Manual intervention required

**Recommendation:**
Add fallback discovery methods:
1. Primary: WikiStats API
2. Secondary: Wikimedia site matrix API
3. Tertiary: Manual project addition via Web UI
4. Cache last successful discovery result

---

### Issue #20: Job Progress Tracking Not Defined

**Priority:** Moderate
**Labels:** enhancement, job-queue, ux
**File:** claude.md:276-356

**Description:**
Job system tracks state (pending, assigned, in_progress, completed), but no progress tracking within jobs.

**Missing Feature:**
Cannot show:
- "Download 45% complete"
- "Processed 1000 of 5000 files"
- "ETA: 2 hours remaining"

**Impact:**
- Poor user experience
- Cannot estimate completion time
- Cannot prioritize based on progress

**Recommendation:**
Add job progress fields:
```python
progress_current: int  # e.g., bytes downloaded
progress_total: int    # e.g., total bytes
progress_percent: float  # calculated
eta_seconds: int       # estimated time remaining
```

---

## 🟢 MINOR PRIORITY ISSUES

### Issue #21: Typo - "orgnization" → "organization"

**Priority:** Minor
**Labels:** documentation, typo
**File:** claude.md:48

**Description:**
Typo in file organization description.

**Current Text:**
```
- **File organization**: Same as torrent file orgnization
```

**Fix:**
```
- **File organization**: Same as torrent file organization
```

---

### Issue #22: Typo - "Languauge" → "Language"

**Priority:** Minor
**Labels:** documentation, typo
**File:** claude.md:125

**Description:**
Typo in sources.txt format example.

**Current Text:**
```
Languauge: en
```

**Fix:**
```
Language: en
```

---

### Issue #23: Typo - "Stauts" → "Status"

**Priority:** Minor
**Labels:** documentation, typo
**File:** claude.md:132

**Description:**
Typo in sources.txt format example.

**Current Text:**
```
Archived Stauts JSON: https://archive.ph/def456
```

**Fix:**
```
Archived Status JSON: https://archive.ph/def456
```

---

### Issue #24: Tree Structure Formatting Error

**Priority:** Minor
**Labels:** documentation, formatting
**File:** claude.md:98

**Description:**
Broken tree structure in torrent content example.

**Current Text:**
```
├── wikipedia/                  #project
│   ├── en                      #language
│    ── ├── [dump_files]
```

**Fix:**
```
├── wikipedia/                  #project
│   └── en/                     #language
│       └── [dump_files]
```

---

### Issue #25: Inconsistent Naming - WikiSeed vs wikiseed

**Priority:** Minor
**Labels:** documentation, consistency
**File:** claude.md:227

**Description:**
Repository is called WikiSeed but directory structure shows wikiseed/ (lowercase).

**Current:**
```
wikiseed/
├── docker-compose.dev.yml
```

**Recommendation:**
Use consistent naming throughout. Recommend lowercase for directories:
- Repository: WikiSeed
- Directory: wikiseed/
- Docker images: wikiseed/controller, wikiseed/scraper, etc.

---

### Issue #26: Date Format Inconsistency

**Priority:** Minor
**Labels:** documentation, consistency
**File:** claude.md:90-106

**Description:**
Date format specified as template but example shows different format.

**Template (line 90):**
```
"Wikimedia Complete - [Month Year]"
```

**Example (line 106):**
```
# WikiSeed Torrent Dump Checksums - June 2025
```

**Recommendation:**
Specify exact format standard:
- Prefer: "June 2025" (human-readable)
- Or: "2025-06" (ISO 8601)
- Document the chosen standard

---

### Issue #27: Web UI vs wikiseed.app Naming Confusion

**Priority:** Minor
**Labels:** documentation, clarification-needed
**File:** claude.md:37

**Description:**
Container list shows both "Web UI" and "wikiseed.app" but it's unclear if these are the same thing or different.

**Current Text:**
```
- **wikiseed.app**: Public status page; will be hosted in cloud
```

Earlier mention:
```
│   Seeder    │ Sharing  │   Web UI   │
```

**Question:**
Are these the same or different components?
- Web UI = internal admin interface
- wikiseed.app = public status page

**Recommendation:**
Clarify the distinction or consolidate naming.

---

### Issue #28: Exponential Backoff Parameters Missing

**Priority:** Minor
**Labels:** documentation, error-handling
**File:** claude.md:75

**Description:**
Exponential backoff mentioned but parameters not specified.

**Current Text:**
```
- **Automatic retry**: Re-upload failed uploads with exponential backoff
```

**Missing:**
- Initial delay (1 second? 5 seconds?)
- Multiplier (2x? 3x?)
- Max delay (1 hour? 24 hours?)
- Max attempts (3? 5? 10?)

**Recommendation:**
Specify backoff parameters:
```
Exponential backoff: 30s, 60s, 120s, 240s (max 4 attempts)
```

---

### Issue #29: Chunk Retry Delay Not Specified

**Priority:** Minor
**Labels:** documentation, error-handling
**File:** claude.md:71

**Description:**
Chunk retry max attempts specified, but delay between retries is not.

**Current Text:**
```
- **Automatic retry**: Re-download failed chunks (max 3 attempts per chunk)
```

**Missing:**
- Delay between retries
- Backoff strategy

**Recommendation:**
Add retry delay:
```
Re-download failed chunks (max 3 attempts with 5s, 15s, 30s delays)
```

---

### Issue #30: Job State Machine Diagram Clarity

**Priority:** Minor
**Labels:** documentation, visualization
**File:** claude.md:313-317

**Description:**
State machine diagram arrow directions are unclear.

**Current:**
```
pending → assigned → in_progress → completed
    ↓         ↓           ↓
  failed ← failed ← failed (with retry logic)
```

**Issue:**
The bottom arrows pointing left are confusing. Does each state transition to failed, or does failed loop back?

**Recommendation:**
Improve diagram:
```
           ┌─────────┐
           │ pending │
           └────┬────┘
                │
           ┌────▼────┐
        ┌──│assigned │──┐
        │  └─────────┘  │
        │               │
        ▼               ▼
  ┌──────────┐    ┌────────┐
  │in_progress│    │ failed │◄─┐
  └─────┬────┘    └────┬───┘  │
        │              │       │
        ▼              └───────┘
   ┌─────────┐         (retry)
   │completed│
   └─────────┘
```

---

## ❓ QUESTIONS & CLARIFICATIONS NEEDED

### Issue #31: How Are Dumps Spanning Multiple Months Categorized?

**Priority:** Question
**Labels:** question, torrents, clarification-needed
**File:** claude.md:89-91

**Question:**
If a dump is published on June 30 but downloaded/processed on July 2, which monthly torrent does it go in?
- June (dump date)
- July (processing date)
- Both (hard links)

**Impact:**
- Torrent organization logic
- File categorization rules

**Needs:**
Decision on categorization logic

---

### Issue #32: What If Internet Archive Upload Fails?

**Priority:** Question
**Labels:** question, distribution, error-handling
**File:** claude.md:135-150

**Question:**
Archive process step 3 is "Upload torrent archive to Internet Archive", step 4 is "Create torrent with IA as web seed".

What happens if step 3 fails?
- Can torrent still be created without webseed?
- Does process halt?
- Retry later?

**Impact:**
- Error recovery flow
- Torrent distribution strategy

**Needs:**
Decision on failure handling

---

### Issue #33: How Are Hard Links Maintained Across Torrent Groupings?

**Priority:** Question
**Labels:** question, torrents, storage
**File:** claude.md:87-88

**Question:**
Multiple torrent groupings use hard links to avoid file duplication. What happens if:
- One torrent is deleted by user?
- One torrent is moved?
- Hard link count goes to zero?

**Impact:**
- Data integrity
- Storage management
- Cleanup logic

**Needs:**
Hard link management strategy

---

### Issue #34: What Happens to Dumps Larger Than Total Available Storage?

**Priority:** Question
**Labels:** question, storage, edge-case
**File:** claude.md:40-64

**Question:**
If a single dump file is larger than available storage (e.g., 20TB dump but only 18TB storage):
- Skip it?
- Download partial?
- Alert user?
- Queue for manual handling?

**Impact:**
- Storage planning
- Edge case handling
- User experience

**Needs:**
Policy decision

---

### Issue #35: Are Yearly History Dumps Separate Files?

**Priority:** Question
**Labels:** question, torrents, storage
**File:** claude.md:91

**Question:**
`"Wikimedia Complete with History - [Year]"` - are these:
- A. Separate full history dumps (completely different files)
- B. Hard links to monthly dumps (same files, different torrent)
- C. Incremental history on top of monthly dumps

**Impact:**
- Storage requirements (significantly different for A vs B)
- Download strategy
- Torrent creation logic

**Needs:**
Clarification on history dump strategy

---

### Issue #36: How Are Partial Downloads Handled During Cleanup?

**Priority:** Question
**Labels:** question, storage, downloads
**File:** claude.md:40-64

**Question:**
Storage cleanup is triggered, but there are in-progress downloads. What happens to partial files?
- Protected from cleanup?
- Deleted and restarted later?
- Completed before cleanup?

**Impact:**
- Download efficiency
- Storage calculation
- Cleanup logic

**Needs:**
Policy decision

---

### Issue #37: How Are In-Progress Downloads Protected During Cleanup?

**Priority:** Question
**Labels:** question, storage, concurrency
**File:** claude.md:40-64

**Question:**
Related to #36 but broader: Are active downloads protected from cleanup process?
- Lock files?
- Database flag?
- Separate directory?

**Impact:**
- Data integrity
- Concurrency control
- Cleanup safety

**Needs:**
Protection mechanism specification

---

### Issue #38: What If dumpstatus.json Is Unavailable?

**Priority:** Question
**Labels:** question, downloads, error-handling
**File:** claude.md:56

**Question:**
"Parse dumpstatus.json for accurate file sizes" - what if:
- File doesn't exist?
- File is corrupted?
- File is incomplete?

**Impact:**
- Pre-download space checks
- Download reliability
- Fallback strategy

**Needs:**
Fallback mechanism specification

---

### Issue #39: What Happens to Quarantined Files?

**Priority:** Question
**Labels:** question, error-handling, operations
**File:** claude.md:76

**Question:**
"Per-file quarantine: Skip problematic files, retry next cycle"

Follow-up questions:
- Where are quarantined files tracked?
- How long until retry?
- Are there alerts/notifications?
- Manual review process?
- Automatic unquarantine conditions?

**Impact:**
- Operations procedures
- Monitoring requirements
- Recovery workflow

**Needs:**
Complete quarantine workflow specification

---

### Issue #40: How Are Discontinued Wikimedia Projects Handled?

**Priority:** Question
**Labels:** question, future-proofing, preservation
**File:** claude.md:184-194

**Question:**
If Wikimedia discontinues a project:
- Keep seeding forever?
- Special "archived projects" category?
- Different preservation rules?
- Still included in new torrents?

**Impact:**
- Long-term preservation strategy
- Storage allocation
- Torrent organization

**Needs:**
Archival policy for discontinued projects

---

### Issue #41: What Happens If WikiStats Becomes Unavailable?

**Priority:** Question
**Labels:** question, reliability, auto-discovery
**File:** claude.md:187

**Question:**
Auto-discovery relies on WikiStats. If it becomes unavailable:
- Use cached list?
- Fall back to manual?
- Use alternative API?
- How long to retry?

**Impact:**
- Discovery reliability
- System autonomy
- Operational burden

**Needs:**
Fallback discovery strategy

---

### Issue #42: What Are Specific Targets for Success Metrics?

**Priority:** Question
**Labels:** question, metrics, goals
**File:** claude.md:389-401

**Question:**
"Completeness: At least one copy of every Wikimedia project+language"

What are the specific targets?
- 95% coverage acceptable or must be 100%?
- How many seeders per torrent?
- What upload ratio target?
- What storage utilization target?

**Impact:**
- Success definition
- Resource planning
- Monitoring alerts

**Needs:**
Specific numerical targets

---

### Issue #43: What Is Baseline for "High Torrent Health"?

**Priority:** Question
**Labels:** question, metrics, torrents
**File:** claude.md:391

**Question:**
"Availability: High torrent health across all shared torrents"

What defines "high torrent health"?
- Minimum seeders (5? 10? 50?)
- Minimum seed ratio (1.0? 2.0?)
- DHT availability percentage?
- Response time thresholds?

**Impact:**
- Monitoring thresholds
- Alert definitions
- Success measurement

**Needs:**
Specific health metric definitions

---

### Issue #44: What Is Metrics Retention Policy?

**Priority:** Question
**Labels:** question, metrics, storage
**File:** claude.md:151-168

**Question:**
Logs have 90-day retention. What about metrics?
- Same 90 days?
- Different retention?
- Aggregated over time (hourly → daily → monthly)?
- Forever?

**Impact:**
- Storage planning
- Historical analysis capability
- Database size

**Needs:**
Metrics retention policy

---

### Issue #45: How Are Changes to Shared Code Deployed?

**Priority:** Question
**Labels:** question, devops, architecture
**File:** claude.md:226-251

**Question:**
If `shared/database.py` is updated:
- Rebuild all containers?
- Hot reload?
- Graceful restart of all containers?
- Rolling update?

**Impact:**
- Deployment process
- Downtime
- Development workflow

**Needs:**
Deployment procedure for shared code changes

---

### Issue #46: What Is the Branching Strategy?

**Priority:** Question
**Labels:** question, devops, git
**File:** claude.md:215-274

**Question:**
No git workflow defined:
- Git-flow (develop, feature, release branches)?
- Trunk-based (direct to main)?
- GitHub flow (feature branches to main)?
- Release branches?

**Impact:**
- Collaboration workflow
- Release management
- Code review process

**Needs:**
Git branching strategy decision

---

### Issue #47: Where Are Docker Images Published?

**Priority:** Question
**Labels:** question, devops, docker
**File:** claude.md:195-214

**Question:**
No container registry specified:
- Docker Hub?
- GitHub Container Registry (ghcr.io)?
- Self-hosted registry?
- Public or private?

**Impact:**
- Deployment process
- Image distribution
- Version management

**Needs:**
Container registry decision

---

### Issue #48: What Frontend State Management?

**Priority:** Question
**Labels:** question, frontend, architecture
**File:** claude.md:195-214

**Question:**
React frontend specified, but state management unclear:
- Redux (complex, powerful)?
- Context API (simple, built-in)?
- Zustand (lightweight)?
- MobX?
- None (local state only)?

**Impact:**
- Frontend architecture
- Development complexity
- State synchronization

**Needs:**
State management decision

---

### Issue #49: What Is Database Migration Testing Strategy?

**Priority:** Question
**Labels:** question, database, testing
**File:** claude.md:192-193

**Question:**
"Automatic migration: Database schema updates handled during WikiSeed updates"

How are migrations tested?
- Staging environment?
- Migration rollback capability?
- Data validation after migration?
- Test migrations on copy of production data?

**Impact:**
- Upgrade safety
- Data integrity
- Downtime during upgrades

**Needs:**
Migration testing procedure

---

## Summary Statistics

**By Priority:**
- 🔴 Critical: 8 issues
- 🟡 Moderate: 12 issues
- 🟢 Minor: 10 issues
- ❓ Questions: 19 issues
- **Total: 49 issues**

**By Category:**
- Documentation: 20
- Architecture: 8
- Database: 7
- Operations: 5
- Testing: 3
- Security: 2
- Frontend: 2
- DevOps: 2

**Estimated Effort to Resolve All Issues:**
- Critical issues: ~40 hours (blockers, must resolve before coding)
- Moderate issues: ~30 hours (important for production readiness)
- Minor issues: ~5 hours (quick fixes)
- Questions: ~15 hours (research and decision making)
- **Total: ~90 hours of work**

**Recommended Approach:**
1. Start with all Critical issues (especially #3 database schema)
2. Make decisions on high-impact Questions (#31-#35)
3. Address Moderate issues before Phase 2
4. Fix Minor issues during implementation
5. Resolve remaining Questions as they become relevant

---

*Generated by Claude Code Documentation Review*
*Date: 2025-12-02*
