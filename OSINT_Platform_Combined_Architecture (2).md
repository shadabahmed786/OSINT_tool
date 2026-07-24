# OSINT Investigation Platform — Architecture Design

**Scope:** Single-user, local-first prototype/MVP, not a national-scale or full commercial-parity system

---

## 1. Purpose

A platform that starts from a single selector (email, username, phone, name, or image), pivots through live platform checks, correlates the results with confidence scoring, and produces both an investigator-facing evidence log and a plain-language summary report.

**Core constraint: zero paid APIs, zero SaaS subscriptions.** Every component is either self-coded or built on free, open-source tooling. AI inference runs locally on-device rather than through any cloud model provider. Where a task would normally lean on a paid API (breach lookups, facial recognition, reverse image search), the design below either substitutes a free equivalent or explicitly excludes that capability rather than pretending it's covered.

---

## 2. Hardware Ceiling Specification

| Component | Spec | Role |
|---|---|---|
| CPU | Core Ultra 9 285H | Orchestration, Playwright browser automation, async API calls, OCR fallback |
| GPU | RTX 5080, 16GB VRAM, **150W (laptop variant)** | Local LLM/VLM inference for OCR, summarization, entity extraction |
| RAM | 32GB @ 8000MT/s (multi-channel) | KV cache, headless browser fleet, image pipeline |
| Storage | 200GB | Model weights, evidence archive, vector DB, screenshots |

**Note on power draw:** most published local-LLM throughput numbers assume a 175W desktop 5080. At 150W, expect tok/s roughly 10-15% lower than typical benchmarks. Plan model choice around the smaller end of what fits, not the largest that theoretically fits.

---

## 3. Core Input Types (Selectors)

- Email address
- Username / alias
- Phone number
- Full name
- Image (reverse image / hash lookup)
- IP address (later-stage, advanced use only)

Every newly discovered selector during an investigation gets added back into the search bar to continue the pivot chain.

---

## 4. System Architecture

```
                    Target Input (selector)
                              │
                              ▼
              ┌───────────────────────────────┐
              │   Investigation Manager        │  (Query Planner)
              │   decides which modules apply  │
              └───────────────┬────────────────┘
                              ▼
   ┌──────────────────────────────────────────────────┐
   │  STEP 1: ENUMERATION LAYER                        │
   │  Sherlock/Maigret (usernames) · Holehe (email)    │
   │  PhoneInfoga (phone) · theHarvester (domain/email) │
   │  Playwright-driven per-source adapter modules      │
   └───────────────────────┬────────────────────────────┘
                            ▼
   ┌──────────────────────────────────────────────────┐
   │  STEP 2: CAPTURE + EXTRACTION LAYER                │
   │  Full-page screenshot + raw HTML/JSON per hit      │
   │  Tesseract OCR (cheap/fast) → fallback to local VLM │
   │  for messy screenshots or non-Latin text            │
   └───────────────────────┬────────────────────────────┘
                            ▼
   ┌──────────────────────────────────────────────────┐
   │  STEP 3: FREE BREACH SIGNAL (OPTIONAL, LIMITED)    │
   │  HIBP Pwned Passwords k-anonymity API (free,        │
   │  keyless, password-hash checks only)                 │
   │  No paid breach-database lookups in this design      │
   └───────────────────────┬────────────────────────────┘
                            ▼
   ┌──────────────────────────────────────────────────┐
   │  STEP 4: CORRELATION / TALLY ENGINE                │
   │  Text similarity (bio, name, location) via local    │
   │  sentence-embedding model                            │
   │  Image-hash matching for reused profile pictures     │
   │  (no heavy face model needed for this)                │
   │  Weighted confidence score per candidate match         │
   └───────────────────────┬────────────────────────────┘
                            ▼
   ┌──────────────────────────────────────────────────┐
   │  STEP 5: CASE ASSEMBLY                              │
   │  Node graph (selector-centered) · Timeline ·         │
   │  Evidence log (auto-timestamped, append-only)         │
   └───────────────────────┬────────────────────────────┘
                            ▼
   ┌──────────────────────────────────────────────────┐
   │  STEP 6: REPORT GENERATION                          │
   │  Local LLM drafts executive summary + confidence      │
   │  rationale → Markdown → HTML/PDF export                │
   └──────────────────────────────────────────────────┘
```

This keeps a clear separation of concerns between stages, but replaces "many always-on agents" with a **sequential, one-model-loaded-at-a-time** pipeline, which is what actually fits in 16GB VRAM at 150W.

---

## 5. Data Structure Per Finding ("Hit")

| Field | Description |
|---|---|
| Platform | Source site/app (e.g. GitHub, Twitter, Gravatar) |
| Matched selector | Which input triggered this hit |
| Profile picture | Pulled image, flagged if it reappears elsewhere in the case (via hash match) |
| Display name / bio | Raw account text |
| Region / locale | Inferred from account metadata |
| Last active date | If available |
| Account status | Live / dead / archived |
| Linked platforms | Other accounts referencing this one |
| Source | Which free tool or live-check surfaced it |
| Screenshot + timestamp | Stored alongside every field, so findings are auditable, not just asserted |
| Confidence score | See Section 6 |

---

## 6. Confidence Scoring

Every result gets a probability, never a flat found/not-found boolean. Common names, stock photos, and reused usernames cause false positives.

**Tiers:**
- **High** — multiple corroborating signals (same alias + matching region + matching interest area)
- **Medium** — one strong signal, no corroboration yet
- **Low** — name/alias overlap only

**Weighting factors:**
- Platform rarity (obscure platforms carry more signal than major networks)
- Cross-platform overlap count
- Geographic consistency across accounts
- Temporal consistency (activity dates lining up with known timeline)
- Image-hash match against other findings in the same case

Score first with simple weighted rules; only move to a model-driven score once the rule-based version is stable and you can compare outputs against it.

---

## 7. Local AI Models (sized for 150W, 16GB VRAM)

**Principle: load one model at a time, unload between pipeline stages.** Don't run a text LLM and a VLM concurrently, budget assumes sequential use.

| Stage | Model | Quant | VRAM | Notes |
|---|---|---|---|---|
| Text (summarization, entity extraction, report writing) | Llama 3.1 8B | Q4_K_M | ~5-6GB | Safe default, most tested with Ollama |
| Vision (screenshot OCR, layout understanding) | Qwen2.5-VL 7B | Q4 | ~5-6GB | Load only during Step 2, unload after |
| Text similarity | A small sentence-transformers/bge/e5 model | — | ~1GB | Can stay resident, small footprint |
| Image matching | `imagehash` (Python library) | — | ~0GB (CPU) | No GPU model needed, this alone replaces a heavy face-embedding model |

Skip full-precision or 24B-class models at 150W: the desktop-benchmarked numbers for those don't hold, and the marginal quality gain isn't worth the VRAM headroom lost for swapping between stages.

---

## 8. Case Structure

1. **Node graph view** — selector at the center, platforms branching outward, discovered selectors branching further (link-analysis style, native to the platform rather than exported to Maltego)
2. **Timeline view** — account creation/last-active dates plotted chronologically
3. **Evidence log** — append-only, auto-timestamped record of every search and result, so nothing needs manual screenshotting after the fact

---

## 9. Tooling

**Enumeration (free, open-source, self-hosted, no subscription):**
- Sherlock / Maigret — username across 400+ platforms
- Holehe — email-to-account mapping
- PhoneInfoga — carrier/line-type/VOIP check
- theHarvester — email/DNS/subdomain harvesting

All four are open-source CLI tools you run yourself, no API key or paid tier required. This is also the enumeration layer covered directly in the NCCIA OSINT coursework, so it slots in as reusable knowledge, not a new stack to learn.

**Breach data:** the only free, keyless option is HIBP's Pwned Passwords API (k-anonymity model, checks a password hash against known-breached passwords, no account/email lookup). Full email-to-breach lookups on HIBP, DeHashed, and IntelX all require a paid subscription now, so this design excludes that capability rather than faking coverage. If broader breach correlation is needed later, that's a deliberate future add-on requiring a paid key, not part of the free baseline build.

**Local stack:**
- Browser automation: Playwright (headless Chromium), per-source adapter pattern so adding a source means adding one adapter, not touching core logic
- OCR: Tesseract first, VLM fallback for messy/non-Latin screenshots
- Model serving: Ollama or llama.cpp
- Text similarity: sentence-transformers (small `bge`/`e5` variant)
- Image matching: `imagehash`
- Storage: SQLite or DuckDB for structured findings, folder structure keyed by investigation ID for raw evidence
- Vector store (optional, once stable): Chroma or FAISS for bio/alias similarity search
- Frontend: Streamlit for a fast MVP, React + `react-force-graph`/`vis.js` later for the graph view
- Backend: FastAPI (Python)
- Report export: Jinja2 templates → Markdown → HTML/PDF

---

## 10. Reporting Output

Two modes:

1. **Executive summary** — one page, plain language: who the target is, key findings, what's actionable. For non-technical stakeholders.
2. **Full evidence appendix** — every source, screenshot, timestamp, and confidence rating, for anyone verifying the findings.

**Template:**
```markdown
# OSINT Investigation Report
**Target:** {selector}
**Date:** {timestamp}
**Overall Confidence:** {HIGH/MEDIUM/LOW}

## Discovered Accounts
| Platform | URL | Profile Pic | Found Data | Confidence |
|---|---|---|---|---|

## Password Exposure Check (free, k-anonymity, optional)
| Password Hash Checked | Exposed? | Times Seen |
|---|---|---|

## Correlation Summary
- Linked identities:
- Risk score:
- Recommendation:
```

---

## 11. What's Realistically Buildable Solo (and What Isn't)

**Realistic on this hardware:**
- Local LLM/VLM inference for OCR, summarization, entity extraction, confidence rationale
- Local text-similarity and image-hash correlation
- A working single-selector-type MVP (start with email or username) that pivots through 3-5 sources

**Not realistic without paid access, and excluded from this design:**
- Full email/username breach lookups (HIBP, DeHashed, IntelX all gate this behind paid subscriptions now) — only the free password-hash check is included
- Live scraping of every social platform at scale (rate limits, CAPTCHAs, ToS violations, IP bans, and none of the free enumeration tools bypass these)
- 24/7 dark web monitoring or real-time alerting infrastructure
- Facial recognition against third-party databases (PimEyes/FaceCheck.ID-style, both paid and legally sensitive) — image-hash matching covers the "reused profile picture" use case for free, without needing this
- Broad multi-category coverage (crypto de-anonymization, disinformation tracking, CIB detection, deepfake detection, etc.) as a single project — each of those is its own tool; pick one investigative thread and build it well rather than sketching fifty

The platform is a **workflow/aggregation layer over free, self-coded tools**, with local AI doing the scoring, clustering, and report writing on top. Nothing in the design depends on a paid subscription; where a capability genuinely requires one, it's marked as excluded rather than half-implemented.

---

## 12. Build Order (MVP → Fuller System)

1. Single selector type (email or username) + one free enumeration tool (Holehe or Sherlock) + flat result-card output, no graph yet
2. Add OCR + basic structured extraction from screenshots
3. Add the free HIBP Pwned Passwords check (optional module, password-hash only)
4. Add local LLM for a simple auto-summary of results
5. Add rule-based confidence scoring (weighted, not AI-driven yet)
6. Add the evidence log (append-only search/result table)
7. Add image-hash correlation across profile pictures
8. Add the node-graph view once the data model is stable
9. Add more selector types and free enumeration sources incrementally

Something demoable exists after step 4-5, well before the full system is built out.

---

## 13. Legal and Ethical Scope (define before building)

- Restrict use to identifiers you're authorized to investigate: consented background checks, your own digital footprint, confirmed fraud/impersonation cases, or work done under institutional oversight (e.g. NCCIA internship scope)
- Respect each source's Terms of Service; because this design uses free enumeration tools instead of official paid APIs, most checks are effectively lightweight automated lookups rather than licensed access, so rate-limit conservatively and expect some platforms to block or CAPTCHA the requests
- Be mindful of data-protection law regarding storage of personal data gathered this way, including retention limits and secure deletion
- Everything stays local by default, since there's no cloud API in the loop to route data through in the first place
- Hard line: nothing built here is for unauthorized surveillance, stalking, or harassment, regardless of technical feasibility

---

## 14. Bottom Line

The hardware comfortably runs every AI component of this locally at the 7-9B quantized scale, sequentially staged rather than run concurrently, and every non-AI component is a free, open-source tool run under your own control. The actual limiting factor isn't the machine or the budget, it's coverage: without paid breach APIs, breach correlation is limited to the free password-hash check, and enumeration is limited to what Sherlock/Maigret/Holehe/theHarvester can reach before a platform starts blocking automated requests. A tight single-selector MVP that does one thing well within that free scope is more valuable, and more finishable, than a sprawling multi-category framework that quietly assumes paid access it doesn't have.
