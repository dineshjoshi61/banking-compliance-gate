# Sanctions Screening — Insertion Point & Design

## 1. Pipeline Position

Current pipeline: `kyc_check → aml_analysis → [NEW: sanctions_screening] → approval`

The sanctions-screening step is inserted between AML analysis and final approval. This ensures that suspicious counterparties are evaluated before a transaction is approved, while still preserving the existing AML review flow. The screening is an explicit gate to identify sanctions matches before approval is issued.

## 2. Data Inputs Required

| Field | Type | Source | Notes |
|---|---|---|---|
| `customer_id` | string | customer record / transaction metadata | Used for audit logging and result correlation |
| `counterparty_details` | object | transaction payload | Includes at least `name`, and may include `country` or other metadata |
| `transaction_amount` | float | transaction payload | Used for context and risk evaluation |

The required fields for this step are `customer_id`, `counterparty_details`, and `transaction_amount`, matching the design contract established for the sanctions check.

## 3. Output Schema

```json
{
  "screened": true,
  "match_list": [],
  "confidence": 0.0
}
```

- `screened` (bool) — whether the screening step executed successfully.
- `match_list` (list) — zero or more OFAC/UN matches, each containing `list_source`, `matched_name`, and `score`.
- `confidence` (float, 0–1) — maximum confidence score from any sanctions match; `0.0` when no matches are found.

## 4. Integration Contract with the AML Module

- **Input from AML module:** `aml_result` and transaction context pass through unchanged; sanctions screening is a separate but adjacent gate in the compliance pipeline.
- **Output to Approval step:** any non-empty `match_list` with `confidence >= 0.75` should trigger manual compliance review and block automatic approval.
- **Failure mode:** if the sanctions API is unavailable or validation fails, `screened` becomes `false` and the transaction is routed to manual review rather than silently passing.

## 5. Open Questions / Risks

- False-positive matching can occur when a counterparty name is similar to a sanctioned entity.
- Name normalization should be applied for case-insensitive matching and whitespace trimming.
- This stub intentionally uses deterministic mock data for OFAC and UN lists to keep the lab safe and testable.
