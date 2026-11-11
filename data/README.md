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

## Employee & leave database
_TODO: synthetic seed (see `src/hr_assistant/db.py`)._

## Eval datasets — `evals/datasets/`
_TODO: per-component counts, label distribution, dev/test split._
