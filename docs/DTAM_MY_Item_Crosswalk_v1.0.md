# DTAM-MY Item Crosswalk — Online vs Paper (OMR)

**Version:** 1.0 · **Status:** pending PI / psychometric review · **Machine-readable copy:** `docs/dtam_item_crosswalk_v1.0.json`

## Decision

The PI decided (5 November 2026) to **keep both instrument versions** for the pilot (resolves F-02/F-07 in the architecture spec). Responses are tagged with their capture **mode** (`digital`, `paper`, `verbal`), and pooled analyses use **only the items the two versions share**, with mode as a covariate.

## Rules

| Level | Meaning | How to analyse |
|---|---|---|
| **same** | Same published item, or near-verbatim wording | May be pooled at **item level**; include `mode` as a covariate; test measurement invariance across modes before pooling (multi-group CFA, or MICOM for PLS-SEM) |
| **construct** | Same construct, different wording | Compare at **construct-score level only**; do not pool items |
| **none** | No counterpart in the other version | Analyse within mode only |

Where the data live:
- **Online:** `mode` is on every questionnaire record (`dtam_my_responses`) and in the dashboard/admin survey CSVs.
- **Paper:** `mode: "paper"` is in OMR JSON exports and in both OMR CSVs.
- **Verbal:** `mode: "verbal"` is in verbal-interview exports.

## Summary

| Instrument | Same | Construct only | No counterpart | Notes |
|---|---|---|---|---|
| SUS | 10 | 0 | 0 | Standard instrument, identical positions |
| ZBI | 22 | 0 | 0 | Standard instrument; minor phrasing differences on paper ("Your relative asks…" vs "Do you feel that your relative asks…") |
| WHOQOL-BREF | 26 | 0 | 0 | Standard instrument, identical positions |
| TAM | 4 | 3 | 0 | Two of the four shared items sit under UTAUT2 (EE_2, BI_1) on the paper sheet |
| UTAUT2 | 4 | 2 | 4 | Paper omits Performance Expectancy and Price Value, so PE/PV can be analysed online only |
| TUQ | 2 | 8 | 0 | Online and paper TUQ use different item wordings; compare at mean-score level |
| MAST | 2 | 8 | 2 | Online 12-item short form vs paper 28-item, 7-domain form |

## Non-standard instruments (item level)

### TAM
| Online code | Online item | Paper code | Paper item | Level | Note |
|---|---|---|---|---|---|
| `tam4` | Learning to use telerehabilitation technology would be easy for me. | `PEOU_1` | Learning to use telerehabilitation technology would be easy for me | **same** | Near-verbatim |
| `tam5` | I would find telerehabilitation technology easy to use. | `PEOU_2` | I find telerehabilitation technology easy to use | **same** | Near-verbatim (tense) |
| `tam1` | Using telerehabilitation technology would improve my performance/quality of care. | `PU_1` | Using telerehabilitation would improve quality of rehabilitation services | **construct** | Perceived usefulness; wording differs |
| `tam2` | Using telerehabilitation technology would make it easier to deliver/receive rehabilitation. | `PU_2` | Using telerehabilitation would make it easier to access rehabilitation | **construct** | Perceived usefulness; wording differs |
| `tam3` | Using telerehabilitation technology would be beneficial overall. | `PU_5` | Overall, I find telerehabilitation to be advantageous | **construct** | Overall usefulness; wording differs |
| `tam6` | My interaction with telerehabilitation technology would be clear and understandable. | `EE_2` | My interaction with telerehabilitation is clear and understandable | **same** | Same wording, but the paper sheet files it under UTAUT2 Effort Expectancy |
| `tam7` | I intend to use telerehabilitation technology in the future (if available). | `BI_1` | I intend to use telerehabilitation in the future | **same** | Behavioural intention; paper sheet files it under UTAUT2 BI |

### UTAUT2
| Online code | Online item | Paper code | Paper item | Level | Note |
|---|---|---|---|---|---|
| `u3` | Learning to operate telerehabilitation technology is easy for me. | `EE_1` | Learning how to use telerehabilitation technology is easy for me | **same** | Near-verbatim |
| `u4` | I can easily become skillful at using telerehabilitation technology. | `EE_3` | It is easy for me to become skillful at using telerehabilitation technology | **same** | Near-verbatim |
| `u5` | People who are important to me think I should use telerehabilitation. | `SI_1` | People who are important to me think I should use telerehabilitation | **same** | Verbatim |
| `u6` | I have the knowledge and ability to use telerehabilitation technology. | `FC_2` | I have the knowledge necessary to use telerehabilitation | **construct** | Digital adds "and ability" |
| `u7` | Using telerehabilitation technology is fun and enjoyable. | `HM_1` | Using telerehabilitation is fun | **construct** | Digital item is double-barrelled (fun and enjoyable); paper splits HM_1/HM_2 |
| `u9` | Using telerehabilitation technology has become a habit in my daily routine. | `HB_1` | The use of telerehabilitation has become a habit for me | **same** | Near-verbatim |
| `u1` | Using telerehabilitation technology helps me accomplish my tasks more quickly. | — | — | **none** | Performance Expectancy: no paper counterpart |
| `u2` | Using telerehabilitation technology increases my productivity. | — | — | **none** | Performance Expectancy: no paper counterpart |
| `u8` | The value of telerehabilitation technology justifies any cost or effort. | — | — | **none** | Price Value: no paper counterpart |
| `u10` | I am confident in my ability to use telerehabilitation technology effectively. | — | — | **none** | Self-efficacy item scored as FC in the app; no paper counterpart |

### TUQ
| Online code | Online item | Paper code | Paper item | Level | Note |
|---|---|---|---|---|---|
| `tuq1` | The telerehabilitation system is easy to use. | `TUQ_1` | The telerehabilitation system was easy to use | **same** | Near-verbatim (tense) |
| `tuq10` | I would recommend telerehabilitation services to others. | `TUQ_10` | I would recommend telerehabilitation to others | **same** | Near-verbatim |
| `tuq2` | The telerehabilitation system is reliable and stable. | `TUQ_5` | The telerehabilitation system performed reliably | **construct** | Reliability; wording differs |

The remaining online TUQ items (`tuq3`–`tuq9`) have no item-level counterpart; compare TUQ only at mean-score level (threshold ≥ 3.5).

### MAST
| Online code | Online item | Paper code | Paper item | Level | Note |
|---|---|---|---|---|---|
| `mast3` | The patient experience during telerehabilitation is satisfactory. | `MAST_D4_2` | The patient experience is satisfactory | **same** | Near-verbatim |
| `mast5` | Telerehabilitation is well integrated into existing healthcare workflows. | `MAST_D6_1` | Telerehabilitation can be integrated into existing workflows | **same** | Near-verbatim |
| `mast7` | The economic cost-effectiveness of telerehabilitation is favourable. | `MAST_D5_2` | The cost-effectiveness is acceptable | **construct** | Cost-effectiveness; wording differs |
| `mast1` | The clinical effectiveness of telerehabilitation for post-stroke patients is adequate. | `MAST_D3_1` | Telerehabilitation is clinically effective | **construct** | Clinical effectiveness |
| `mast2` | Telerehabilitation provides patient safety standards equivalent to in-person care. | `MAST_D2_1` | Telerehabilitation appears to be safe for patients | **construct** | Safety |
| `mast4` | Telerehabilitation respects patient dignity and privacy. | `MAST_D4_4` | Patient privacy is respected during telerehabilitation | **construct** | Privacy |
| `mast6` | Healthcare professionals are adequately trained for telerehabilitation delivery. | `MAST_D6_2` | Staff training requirements are manageable | **construct** | Staff training |
| `mast9` | The telerehabilitation system meets data security and privacy requirements. | `MAST_D2_2` | Patient data security is adequately protected | **construct** | Data security |
| `mast10` | Telerehabilitation aligns with Malaysian healthcare policy and regulatory requirements. | `MAST_D7_2` | Legal and regulatory requirements are met (PDPA 2010) | **construct** | Legal/regulatory |
| `mast12` | Ethical standards for informed consent are maintained in telerehabilitation. | `MAST_D7_1` | Telerehabilitation raises no major ethical concerns | **construct** | Ethics |
| `mast8` | Implementation of telerehabilitation is technically feasible in our context. | — | — | **none** | Technical feasibility: no direct paper item |
| `mast11` | Telerehabilitation supports equitable access to rehabilitation services across Malaysia. | — | — | **none** | Equitable access: no direct paper item |

## Caveats

1. The mappings are an analyst's judgement from item wording. **The PI or a psychometrician must review them before analysis.**
2. Items marked "same" still need a measurement-invariance check across modes before item-level pooling.
3. The paper sheets' translated wordings (BM/ZH/TA) were not compared; this crosswalk is based on the English source text in the apps.
