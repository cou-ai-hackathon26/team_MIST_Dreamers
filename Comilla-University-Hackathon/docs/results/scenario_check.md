# Sprint scenario checks (S10 to S16, SPRINT_PLAN Section 6.3)

Run on 24 Nov 2026 against the local backend (`POST /api/v1/chat`, app channel, `LLM_BACKEND=gemini`,
`ROUTER_BACKEND=banglabert` v1, `SITUATION_MODE=true`, TF-IDF v2 hint router). S12 was also checked in the
app at 360 px. S11 and S13 by phone (V2) are still to be done on a real call.

| # | Question | Result | Pass | Note |
|---|---|---|---|---|
| S10 | আমার স্বামী গত বছর মারা গেছেন, দুটো বাচ্চা নিয়ে খুব কষ্টে আছি। সরকার থেকে কোনো সাহায্য পাওয়া যায়? | `widow_allowance`, router `banglabert`, checklist + 2 sources | yes | Confident router and hint agree, so no `understand` call and no situation chip (the plan allows `banglabert`) |
| S11 | বাবা মারা যাওয়ার পর জমিটা এখনো বাবার নামেই আছে, আমাদের নামে করবো কীভাবে? | not run yet | | Phone check (V2) |
| S12 | আমি বিধবা, বয়স ৬৬। বয়স্ক ভাতা আর বিধবা ভাতা দুটোই কি একসাথে পাবো? | `mode=multi`, 2 cards, age conflict (১৮+ vs ৬২+) with both sources, combine rule quoted from the documents, 60 words | yes (2 of 3 runs) | Each rule cites its own service. 1 of 3 runs fell back; see below |
| S13 | আমার বাবার বয়স সত্তর, আবার চোখেও দেখেন না। কোন ভাতার জন্য আবেদন করবো? | `mode=multi`: old age + disability, 29 words | yes (app) | Before the hint router (T6) it was old age only; phone check (V2) still to do |
| S14 | ধান ক্ষেতে পোকা লেগেছে, কী ওষুধ দেবো? | exact FALLBACK | yes | |
| S15 | S1, S4, S7 from the SRS | S1 `old_age_allowance`; S4 `nid_correction` (now via `understand`); S7 exact FALLBACK | yes | No regression |
| S16 | সরকারি কোনো ভাতা কি পাবো? | one follow-up question, then after "আমার বয়স ৭০ বছর, আমি পুরুষ।" a correct `old_age_allowance` answer | yes | Before T6 the router guessed disability allowance |
| S17 | Appendix C, 18 rows (classify path, `situation_eval.md`) | C1 to C16 all routed to the right service (16 of 16, target at least 14); C17 refused; C18 one follow-up question, no guess (3 of 3 runs) | yes (routing) | C18 first failed; fixed with the "hint router unsure" rule (`situation_tuning.md`). Full answers per row in the app are still to be run |

## Fixes made during the checks

- S12 first ended in FALLBACK: the verifier judged that a two-service answer did not answer "can I get both?",
  because it did not see the fixed `COMBINE_UNKNOWN` sentence. Verify now sees the fixed notes (test added).
- S12 once reported a "conflict" whose two sides said the same rule (already getting another regular government
  allowance makes you ineligible). `grounding_guard` now drops such agreement, and the prompt files it as the
  documents' combine rule, which the answer then quotes with its source.
- Spoken lines were cut mid-phrase ("আয় অনূর্ধ্ব পঁয়তাল্লিশ।"); lines are now kept whole or cut at a sentence or
  comma, with the 60-word cap kept.
- S13 / S16: BanglaBERT v1 is over-confident on situations (2nd label at most 0.16), so `MULTI_SERVICE_MIN_PROB`
  alone could not catch them. The TF-IDF v2 hint router sends them to `understand` (tuned on `val_v2.csv` and
  the plan's mixed seed examples only).
