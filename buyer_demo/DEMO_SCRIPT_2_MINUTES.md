# Two-Minute Demo Script

## 0:00-0:20 - The Problem

"Omics pipelines can produce stable-looking components that are actually batch,
donor, metadata, or multiple-testing artifacts. OmicsTrust audits the evidence
before a team spends months validating the wrong result."

## 0:20-0:55 - The Audit

Open **Audit**. Point to local-path and upload workflows, metadata selectors,
trust verdict, main failure, claim matrix, and evidence ledger.

"The key behavior is conservative: missing metadata becomes unknown risk, never
low risk. Mathematical stability is reported separately from biological safety."

## 0:55-1:25 - GPT-5.6 Evidence Copilot

Open **Evidence Copilot** and submit:

```text
Audit this single-cell dataset for structural signal, batch confounding,
stability, and biological interpretability. Keep all claims RUO.
```

"GPT-5.6 interprets intent and explains the result. It cannot override an
explicit workflow, see raw expression matrices, or change a deterministic
statistic. The engine remains authoritative."

## 1:25-1:55 - PC11 Proof

Open **PC11 Evidence**.

"In VANISH, OmicsTrust recovered PC11 as the top treatment-response interaction:
OR 0.1688 per SD, Wald p 0.00377, LRT p 0.001258, FDR 0.03145, permutation p
0.003996, and 99.9% bootstrap direction stability. The product also refuses the
clinical leap: this is a retrospective internal signal requiring locked external
validation."

## 1:55-2:00 - Close

"OmicsTrust does not manufacture confidence. It makes evidence auditable."
