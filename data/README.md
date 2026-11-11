# Data card

## Policy corpus — `data/policies/`
| Property | Value |
|---|---|
| Origin | Synthetic, written for this project for the fictional company *Lumora Tech* (no real company or person) |
| Structural reference | [opengovfoundation/hr-manual](https://github.com/opengovfoundation/hr-manual) (CC0-1.0) |
| Documents | 9 (leave, sick leave, remote work, onboarding, benefits, expense reimbursement, equipment, code of conduct, internal requests) |
| Citable sections | 98 (`### N.M` headings → ID `<doc_id> §N.M`) |
| Size | ~4,000 words |
| Language | English |

**Design features used by the evals:** conditional rules (employment type: full-time / part-time / contractor; probation passed or not; office: Lviv / Kyiv / remote); cross-references between documents; 4 tables; an outdated-version note (leave carry-over); sections that explicitly route to HR.

**Topics deliberately NOT covered** (should be routed to HR): salary levels and reviews, promotions, relocation, stock options, layoffs, individual disputes, maternity details, stays abroad over 30 days.

## External question source
| Source | Use | License |
|---|---|---|
| [syncora/hr-policies-qa-dataset](https://huggingface.co/datasets/syncora/hr-policies-qa-dataset) | Realistic employee phrasing for router and HR-referral probes. Only the questions are used, relabelled by hand. | MIT |

## Employee & leave database — `src/hr_assistant/db.py`
| Property | Value |
|---|---|
| Engine | SQLite (`data/hr.db`, git-ignored, recreated from the seed with `db.reset_db`) |
| Tables | `employees`, `leave_requests` (status: approved / declined / pending_hr / cancelled), `hr_tickets` |
| Employees | 30 fictional people in 7 teams (People/HR, Platform, Mobile, Data, Design, Sales, QA); 22 full-time (incl. 2 HR users with role `hr`), 4 part-time, 4 contractors; offices Lviv / Kyiv / remote; 3 first-year joiners |
| Leave history | 14 seeded requests, chosen to trigger each rule: team overlap (Mobile, 28–30 Dec), low balance (E021: 2 days), zero balance (E013), carry-over (E003 → 5 days into 2027), sick yearly cap (E010: 8 days), pending unpaid (E004), cancellable future leave (E017), a declined request (E022) |
| Business date | fixed via `HR_TODAY` (default for evals: 2026-11-12) so that decisions are reproducible |
| Assumption | leave history starts in 2026, so nothing is carried over into 2026 |

## Eval datasets — `evals/datasets/`
_TODO: per-component counts, label distribution, dev/test split._
