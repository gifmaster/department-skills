# DPIA template (GDPR Art. 35)
Use: read when screening whether a DPIA is needed or when writing a DPIA (konsekvensanalyse), to follow the Art. 35(7) structure, rate risks on a fixed scale, record measures and sign-off, and check whether prior consultation under Art. 36 is needed.

Legal information and drafting support, not legal advice. Assess risks to individuals (data subjects), not only to the organisation. Replace all [placeholders].

## 0. Screening: is a DPIA required?

A DPIA is required where processing is likely to result in a high risk to the rights and freedoms of individuals (Art. 35(1)). It is always required for (Art. 35(3)):
- [ ] (a) systematic and extensive evaluation of personal aspects based on automated processing, including profiling, with legal or similarly significant effects
- [ ] (b) large-scale processing of special categories (Art. 9(1)) or criminal convictions data (Art. 10)
- [ ] (c) systematic monitoring of a publicly accessible area on a large scale

Also check Datatilsynet's list of processing that requires a DPIA (Art. 35(4)) on datatilsynet.dk (verify current list).

Indicators from the EDPB-endorsed guidelines on DPIA (WP248 rev.01). Two or more ticked usually means a DPIA is needed:
- [ ] Evaluation or scoring, including profiling and predicting
- [ ] Automated decision-making with legal or similarly significant effect
- [ ] Systematic monitoring (including of employees)
- [ ] Sensitive data or data of a highly personal nature (including CPR numbers in Denmark)
- [ ] Data processed on a large scale
- [ ] Matching or combining datasets
- [ ] Data concerning vulnerable data subjects (employees, children, patients)
- [ ] Innovative use or new technology (for example AI systems)
- [ ] Processing that prevents individuals from exercising a right or using a service

AI Act link: where a high-risk AI system is deployed, the deployer uses the provider's information (Art. 13 AI Act) to carry out its DPIA (AI Act Art. 26(9)). Some deployers must also carry out a fundamental rights impact assessment (AI Act Art. 27). High-risk deployer duties for Annex III systems apply from 2 Dec 2027 (facts file).

Screening result:

| Question | Answer |
|---|---|
| DPIA required? | [Yes / No / Voluntary] |
| Reasons (criteria ticked) | [ ] |
| Screened by / date | [ ] |
| If no DPIA: reasons recorded and reviewed by DPO | [ ] |

## 1. Systematic description of the processing (Art. 35(7)(a))

| Item | Description |
|---|---|
| Name of processing / project | [ ] |
| Controller and contact | [ ] |
| DPO (if any) | [ ] |
| Purposes | [ ] |
| Legitimate interests pursued (if Art. 6(1)(f)) | [ ] |
| Nature of processing: collection, use, storage, sharing, deletion | [ ] |
| Data subjects and approximate number | [ ] |
| Categories of personal data | [ ] |
| Special categories, criminal data, CPR numbers | [ ] |
| Sources of data | [ ] |
| Systems, assets and vendors (processors, sub-processors) | [ ] |
| Recipients | [ ] |
| Transfers outside the EU/EEA and safeguards | [ ] |
| Retention periods | [ ] |
| Data flow diagram | [attach or link] |
| AI component: model, provider, inputs, outputs, human oversight | [ ] |

## 2. Necessity and proportionality (Art. 35(7)(b))

| Question | Assessment |
|---|---|
| Legal basis under Art. 6 (and Art. 9 condition where relevant; databeskyttelsesloven § 11 for CPR) | [ ] |
| Is each purpose specified, explicit and legitimate? | [ ] |
| Is the processing necessary for the purpose? Could less intrusive means achieve it? | [ ] |
| Data minimisation: is every data field needed? | [ ] |
| Accuracy: how is data kept accurate? | [ ] |
| Storage limitation: are retention periods justified and enforced? | [ ] |
| Transparency: how are individuals informed (Art. 13 and 14)? | [ ] |
| Rights: how are access, rectification, erasure, objection and Art. 22 rights handled? | [ ] |
| Processors: Art. 28 agreements in place? | [ ] |
| International transfers: Chapter V mechanism and transfer impact assessment? | [ ] |
| Views of data subjects or their representatives sought (Art. 35(9)); in Denmark consider employee representatives or the cooperation committee (samarbejdsudvalg) for employee processing | [ ] |

## 3. Risk scale

Likelihood (that harm to individuals occurs):

| Score | Level | Meaning |
|---|---|---|
| 1 | Remote | Unlikely to happen; would need several failures or unusual circumstances |
| 2 | Possible | Could happen; has happened elsewhere |
| 3 | Likely | Expected to happen at some point under current controls |
| 4 | Almost certain | Will happen or is happening |

Severity (impact on the individual):

| Score | Level | Meaning |
|---|---|---|
| 1 | Minimal | Minor inconvenience, easily overcome |
| 2 | Significant | Inconvenience or distress that can be overcome with some difficulty |
| 3 | Serious | Significant consequences, e.g. financial loss, discrimination, loss of job opportunities, damage to reputation |
| 4 | Severe | Irreversible or very serious consequences, e.g. identity theft with lasting harm, threat to health or safety, loss of employment |

Risk level = likelihood x severity:

| Score | Risk |
|---|---|
| 1 to 3 | Low |
| 4 to 7 | Medium |
| 8 to 16 | High |

Any risk rated 4 on severity should be treated as high unless likelihood is 1 and documented.

## 4. Risk register (Art. 35(7)(c))

Describe each risk from the individual's perspective (what could happen to them), not the organisation's.

| ID | Risk to individuals | Source / cause | Rights and freedoms affected | Likelihood (1-4) | Severity (1-4) | Inherent risk |
|---|---|---|---|---|---|---|
| R1 | [e.g. Employees feel monitored and self-censor in meetings] | [AI note-taker records all meetings] | [Privacy, freedom of expression] | [ ] | [ ] | [ ] |
| R2 | [e.g. Health data mentioned in meetings is stored and searchable] | [Transcripts kept indefinitely] | [Privacy; Art. 9 data] | [ ] | [ ] | [ ] |
| R3 | [e.g. Inaccurate AI summary used in a performance decision] | [Model errors, no human review] | [Fair treatment; Art. 22] | [ ] | [ ] | [ ] |
| R4 | [e.g. Unauthorised access to transcripts] | [Weak access control at vendor] | [Confidentiality] | [ ] | [ ] | [ ] |
| R5 | [e.g. Transfer to third country without adequate protection] | [Vendor support outside EU/EEA] | [Privacy; Chapter V] | [ ] | [ ] | [ ] |
| R6 | [e.g. Individuals unable to exercise access or erasure rights] | [No process to locate data] | [Data subject rights] | [ ] | [ ] | [ ] |

## 5. Measures and residual risk (Art. 35(7)(d))

| Risk ID | Measure (safeguard, security measure or mechanism) | Type (legal / organisational / technical) | Owner | Deadline | Status | Residual likelihood | Residual severity | Residual risk |
|---|---|---|---|---|---|---|---|---|
| R1 | [e.g. Opt-in per meeting; visible indicator; excluded meeting types (HR, health, union)] | Organisational | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| R2 | [e.g. 30-day retention; keyword alerts; no transcripts for excluded meetings] | Technical | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| R3 | [e.g. Ban on use for performance evaluation; human review] | Policy | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| R4 | [e.g. MFA, role-based access, logging, Art. 28 DPA with audit rights] | Technical / legal | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| R5 | [e.g. EU data residency; SCCs and transfer impact assessment] | Legal | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| R6 | [e.g. Search procedure in DSAR process] | Organisational | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

## 6. Prior consultation check (Art. 36)

- [ ] Is any residual risk still high after measures?
- [ ] If yes: can further measures reduce it? Record why not.
- [ ] If residual high risk remains, the controller must consult Datatilsynet before processing starts (Art. 36(1)).
- [ ] Information to provide includes: responsibilities of controller, joint controllers and processors; purposes and means; measures and safeguards; DPO contact details; the DPIA; any other information requested (Art. 36(3)).
- [ ] Datatilsynet gives written advice within up to 8 weeks of receiving the request, extendable by 6 weeks for complex processing (Art. 36(2)).

Result: [Prior consultation not required / Required: submitted on [date]]

## 7. Conclusion and sign-off

| Item | Entry |
|---|---|
| Overall conclusion | [Proceed / Proceed with measures / Do not proceed / Consult Datatilsynet] |
| Conditions for proceeding | [ ] |
| DPO advice (Art. 35(2)) and whether followed; reasons if not | [ ] |
| Views of data subjects or representatives and response | [ ] |
| Approved by (name, role, date) | [ ] |
| Measures owner | [ ] |
| Review date (Art. 35(11): review when risk changes) | [e.g. 12 months, or on change of vendor, model or purpose] |

## 8. Review log

| Date | Change | Reviewer | Outcome |
|---|---|---|---|
| [ ] | [ ] | [ ] | [ ] |
