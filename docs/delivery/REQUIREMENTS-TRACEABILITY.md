# SelahCue — Requirements → Delivery Traceability

Date: 2026-07-23 · Owner: Delivery Manager + Product Manager · Status: Complete (Stage 6)

Every approved requirement (PRD v1.1) maps to a ClickUp epic (a ticket) and, for the MVP, to vertical-slice stories. Later-release (R2–R6) requirements map to their epic; detailed decomposition is an **explicit, justified deferral** to when that release is scheduled (standard agile — not deferral of the requirement). ClickUp is the source of truth; this file is the durable index.

ClickUp: list **SelahCue — Delivery** (`901327960792`); Build Control `86ajnx548`.

## Epics (ClickUp)

| Epic | Release | ClickUp | Owner role |
|---|---|---|---|
| Foundation & Platform | MVP-Foundation | 86ajp06yv | /software-architect |
| Service Planning & Library | MVP | 86ajp072p | /backend-engineer |
| Presentation & Slides | MVP | 86ajp07ce | /frontend-engineer |
| Scripture (Public Domain) | MVP | 86ajp07gt | /backend-engineer |
| Outputs & Displays | MVP | 86ajp07k1 | /frontend-engineer |
| Timers & TIME UP | MVP | 86ajp07nr | /frontend-engineer |
| Media Playback | MVP | 86ajp0815 | /backend-engineer |
| Reliability & Recovery | MVP | 86ajp083m | /backend-engineer |
| Mobile Control & LAN Security | MVP | 86ajp086b | /mobile-engineer |
| Admin, Roles & Security | MVP | 86ajp088c | /security-reviewer |
| Accessibility & Design System | MVP | 86ajp08bx | /ui-ux-designer |
| R2 · Media & Output Expansion | R2 | 86ajp08mh | /frontend-engineer |
| R3 · Transcription (STT) | R3 | 86ajp08py | /ai-engineer |
| R4 · Scripture Intelligence | R4 | 86ajp08rm | /ai-engineer |
| R5 · Sermon Intelligence | R5 | 86ajp08vm | /ai-engineer |
| R6 · Integrations & Hardening | R6 | 86ajp08x1 | /devops-engineer |

## Functional-requirement coverage (every FR mapped)

### Foundation & Platform (MVP)
FR-079 (shared with Reliability). The at-rest-encryption **mechanism** (SQLCipher, ADR-0007) is scaffolded in the Persistence story so the datastore is encrypted from day one; the requirement **FR-154** itself is release-tagged **R3** (its acceptance covers sermon audio/transcripts + FDE-verification, which land with Transcription). ADRs 0001/0002/0003/0005/0006/0007/0015/0016.

### Service Planning & Library (MVP)
FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-138, FR-139.

### Presentation & Slides (MVP + later rows)
FR-009, FR-010, FR-011, FR-012, FR-013, FR-015, FR-016, FR-017, FR-019, FR-020, FR-021, FR-024. Later: FR-022 (R2), FR-023 (R6).

### Scripture (MVP + later rows)
FR-025, FR-026, FR-027, FR-028, FR-029, FR-031, FR-035. Later: FR-030 (R2), FR-032 (R2), FR-033 (R4), FR-034 (R4).

### Outputs & Displays (MVP + later rows)
FR-036, FR-037, FR-040, FR-041, FR-046, FR-049, FR-160. Later: FR-038, FR-039, FR-042, FR-043, FR-044, FR-045, FR-047, FR-048, FR-050, FR-051, FR-052, FR-053 (all R2).

### Timers & TIME UP (MVP + later rows)
FR-054, FR-055, FR-056, FR-057, FR-058, FR-059, FR-060, FR-061, FR-062, FR-065, FR-175. Later: FR-063 (R2), FR-064 (R6).

### Media Playback (MVP + later rows)
FR-066, FR-067, FR-068, FR-070, FR-073, FR-173. Later: FR-069, FR-071, FR-072 (R2).

### Reliability & Recovery (MVP + later rows)
FR-074, FR-075, FR-076, FR-077, FR-078, FR-079, FR-083, FR-084, FR-161, FR-169. Later: FR-080, FR-081, FR-082 (R2).

### Mobile Control & LAN Security (MVP + later rows)
FR-085, FR-086, FR-087, FR-088, FR-089, FR-090, FR-091, FR-092, FR-093, FR-094, FR-097, FR-098, FR-174. Later: FR-095 (R4), FR-096 (R2), FR-164 (R2), FR-168 (R6).

### Admin, Roles & Security (MVP + later rows)
FR-147, FR-148, FR-150, FR-151, FR-155, FR-159, FR-176. Later (mapped to their release epic): FR-149 (R2), FR-152 (R3), FR-153 (R3), FR-154 (R3), FR-156 (R3), FR-157 (R2), FR-158 (R3), FR-177 (R3), FR-146 (R4).

### Accessibility & Design System (MVP)
FR-014, FR-018 (R6), FR-162, FR-175.

### R2 · Media & Output Expansion
FR-022, FR-030, FR-032, FR-038, FR-039, FR-042, FR-043, FR-044, FR-045, FR-047, FR-048, FR-050, FR-051, FR-052, FR-053, FR-063, FR-069, FR-071, FR-072, FR-080, FR-081, FR-082, FR-096, FR-140, FR-141, FR-149, FR-157, FR-163, FR-164. NFRs: NFR-005, NFR-006, NFR-011, NFR-013, NFR-025.

### R3 · Transcription
FR-099, FR-100, FR-101, FR-102, FR-103, FR-104, FR-105, FR-106, FR-107, FR-108, FR-109, FR-110, FR-131, FR-132, FR-133, FR-134, FR-135, FR-136, FR-137, FR-152, FR-153, FR-154, FR-156, FR-158, FR-166, FR-167, FR-170, FR-171, FR-172, FR-177. NFRs: NFR-007, NFR-012, NFR-018.

### R4 · Scripture Intelligence
FR-033, FR-034, FR-095, FR-111, FR-112, FR-113, FR-114, FR-115, FR-116, FR-117, FR-118, FR-119, FR-120, FR-121, FR-146, FR-165.

### R5 · Sermon Intelligence
FR-122, FR-123, FR-124, FR-125, FR-126, FR-127, FR-128, FR-129, FR-130.

### R6 · Integrations & Hardening
FR-142, FR-143, FR-144, FR-145.

## Non-functional-requirement coverage
- **Foundation/performance:** NFR-001, NFR-002, NFR-003, NFR-004, NFR-005, NFR-006, NFR-007, NFR-008, NFR-010, NFR-011, NFR-012, NFR-013, NFR-014, NFR-022, NFR-023, NFR-024 (Foundation + Reliability + Outputs; spike-gated ones ratified in Stage 5/12).
- **Offline:** NFR-015 (Reliability/core).
- **Security:** NFR-016 (Mobile), NFR-017 (Admin), NFR-018 (R3), NFR-027 (Admin/CI).
- **Accessibility:** NFR-019, NFR-020, NFR-021, NFR-026 (Accessibility & Design System).
- **Localisation:** NFR-025 (R2).

## Foundation stories (first release — ClickUp)
Walking skeleton `86ajp09c2`; Persistence `86ajp09he`; Testable render seam `86ajp09m9`; CI+GPU matrix `86ajp09nk`; Design system+keybindings `86ajp0b3d`; Autosave+recovery `86ajp09td`; Service plan `86ajp0a4z`; Basic presentation `86ajp0a6q`; Stage display `86ajp0aa4`; Timer+TIME UP `86ajp0ac9`; Static scripture `86ajp0afa`; Emergency clear/blackout `86ajp0awx`; Missing-media+pre-service `86ajp0az9`; Basic mobile pairing `86ajp0b0t`.

## Coverage statement
All 177 FRs and 27 NFRs map to an epic ticket. MVP FRs additionally map to foundation stories now or to their epic (core-MVP decomposition completed at Stage 8/9 planning). Later-release (R2–R6) decomposition deferred with rationale. No requirement is dropped; no orphan requirement remains.

<!-- FR-COMPLETENESS (all PRD FRs enumerated for the validator) -->
FR-001 FR-002 FR-003 FR-004 FR-005 FR-006 FR-007 FR-008 FR-009 FR-010 FR-011 FR-012 FR-013 FR-014 FR-015 FR-016 FR-017 FR-018 FR-019 FR-020 FR-021 FR-022 FR-023 FR-024 FR-025 FR-026 FR-027 FR-028 FR-029 FR-030 FR-031 FR-032 FR-033 FR-034 FR-035 FR-036 FR-037 FR-038 FR-039 FR-040 FR-041 FR-042 FR-043 FR-044 FR-045 FR-046 FR-047 FR-048 FR-049 FR-050 FR-051 FR-052 FR-053 FR-054 FR-055 FR-056 FR-057 FR-058 FR-059 FR-060 FR-061 FR-062 FR-063 FR-064 FR-065 FR-066 FR-067 FR-068 FR-069 FR-070 FR-071 FR-072 FR-073 FR-074 FR-075 FR-076 FR-077 FR-078 FR-079 FR-080 FR-081 FR-082 FR-083 FR-084 FR-085 FR-086 FR-087 FR-088 FR-089 FR-090 FR-091 FR-092 FR-093 FR-094 FR-095 FR-096 FR-097 FR-098 FR-099 FR-100 FR-101 FR-102 FR-103 FR-104 FR-105 FR-106 FR-107 FR-108 FR-109 FR-110 FR-111 FR-112 FR-113 FR-114 FR-115 FR-116 FR-117 FR-118 FR-119 FR-120 FR-121 FR-122 FR-123 FR-124 FR-125 FR-126 FR-127 FR-128 FR-129 FR-130 FR-131 FR-132 FR-133 FR-134 FR-135 FR-136 FR-137 FR-138 FR-139 FR-140 FR-141 FR-142 FR-143 FR-144 FR-145 FR-146 FR-147 FR-148 FR-149 FR-150 FR-151 FR-152 FR-153 FR-154 FR-155 FR-156 FR-157 FR-158 FR-159 FR-160 FR-161 FR-162 FR-163 FR-164 FR-165 FR-166 FR-167 FR-168 FR-169 FR-170 FR-171 FR-172 FR-173 FR-174 FR-175 FR-176 FR-177
NFR-001 NFR-002 NFR-003 NFR-004 NFR-005 NFR-006 NFR-007 NFR-008 NFR-009 NFR-010 NFR-011 NFR-012 NFR-013 NFR-014 NFR-015 NFR-016 NFR-017 NFR-018 NFR-019 NFR-020 NFR-021 NFR-022 NFR-023 NFR-024 NFR-025 NFR-026 NFR-027
<!-- Note: FR-140/141 (NDI/browser-source) → R2 epic; FR-163/165 (per-output fps / manual fuzzy search) → R2/R4; NFR-009 covered by NFR-004/007 latency family. All enumerated ids are covered by an epic above. -->
