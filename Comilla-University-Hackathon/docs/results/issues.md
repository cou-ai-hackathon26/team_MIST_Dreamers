# Issues found in testing

Owner: Ragib. Each issue names the person who can fix it. Newest run first.

## App flow test, 22 Nov 2026 (D1-R6: S1, S2, S4, S5, S7)

Setup: backend on one laptop through `POST /api/v1/chat`, the same call the app makes, then checked
in the app. Test number 01700000067. `LLM_BACKEND=gemini` (gemini-3.5-flash-lite), `ROUTER_BACKEND=banglabert`
but **no BanglaBERT model on this laptop, so the router was TF-IDF**. After `scripts.ingest` (188 passages).

| Scenario | Result | Time | Notes |
|---|---|---|---|
| S1 old age, "আমার বয়স ৬৭ …" | pass, with issue 2 | 11.5 s | `old_age_allowance` (TF-IDF 0.99). Age rules right (men 65, women 62), income limit, NID, selection committee. Checklist and 2 sources. |
| S2 widow, "বিধবা ভাতার জন্য কী লাগে?" | pass, with issues 1 and 2 | **29.0 s** | `widow_allowance`, but only after the LLM classified it (TF-IDF unsure). No follow-up question was asked (the SRS says "may ask", so allowed). |
| S4 Banglish NID, "NID-te namer banan bhul, ki korbo?" | pass, with issue 3 | 16.0 s | `nid_correction` (LLM router). Checklist card and 1 source link. |
| S5 history for the test number | pass | | All 3 checklists listed (old age, widow, NID), newest first. |
| S7 land dispute, "প্রতিবেশীর সাথে জমি নিয়ে ঝামেলা …" | pass | 1.5 s | Exact FALLBACK text, no sources, logged as `fallback` in the admin list. |

### Open issues

1. **The demo laptop needs the BanglaBERT model (Tamim).** Without `backend/data/models/router/`, TF-IDF is unsure
   about S2 and S4, so each one costs one extra Gemini call and **is never cached** (FR-AGT-15 caches only sure
   routes). S2 took 29 s. Copy the model folder to the laptop that runs the demo, then run
   `python -m scripts.prewarm --voice` again and check that every demo question says "stored".
   **Done on Ragib's laptop (22 Nov):** model folder copied, `pip install git+https://github.com/csebuetnlp/normalizer`
   (needed, see `docs/SETUP.md`), all 8 demo questions "sure" (0.83 to 0.94, about 45 ms each) and cached
   for app and voice. S7 stays unsure (0.65), so it goes to the LLM and gets the fallback, as intended.
2. **"Fee" is "তথ্য পাওয়া যায়নি" for old age and widow allowance (Tamim).** The SRS S1 expects "free". The
   documents in `data/raw_docs/old_age_allowance/` never say the application is free, so the answer
   cannot say it. Either add an official source that says so, or change the S1 expectation in the SRS.
3. **NID correction fee missing although the document has it (Tamim).** `data/raw_docs/nid_correction/fees.md`
   says the first correction costs 200 Tk + 30 Tk VAT, but the S4 answer gave "তথ্য পাওয়া যায়নি" for the
   fee. The fee table was probably not in the top passages for a "name spelling" question.
4. **Small wording issues (Tamim, prompts).**
   - Widow "where": "ইউনিয়ন সমাজকর্মীর ডিভাইস" reads oddly for citizens.
   - NID "decision" repeats the general note ("চূড়ান্ত সিদ্ধান্ত সংশ্লিষ্ট অফিস নেবে।") instead of naming who decides.
   - The S1 spoken answer is 5 sentences; on a phone call that is long (NFR voice style).
5. **Phone speech is sometimes misheard (Ragib, known).** Two voice questions in the fallback list were
   misheard: "এলাকাবাস কিভাবে" and "নতুন বাসায় কি কি হবে". Speech hints help (D1-A5); in the demo, speak the
   demo phrases slowly and close to the phone.
6. **Slow answers when Gemini is busy (all).** Prewarm on 22 Nov had several `ServerError` (503) from Gemini,
   and uncached answers take 10 to 30 s. Prewarm right before the demo; keep a second API key ready.

### Fixed during voice testing (21 to 22 Nov)

- A phone answer that took more than about 5 s ended the call with a Twilio error. Fixed in D2-A2: the call says
  a short wait message and fetches the answer through `/voice/result` (wait 4 s, SRS FR-CALL-10 updated).
- Questions were cut off at the first pause. Fixed with `speechTimeout=2` and speech hints (D1-A5).
- The SMS line was spoken twice, or spoken although no SMS was sent. Fixed: `AskResult.sms_scheduled` (Ariful)
  and the LLM no longer writes it (Tamim, TEAM_UPDATES 14).
- An SMS through textbee failed with "Android needs a default SMS app". Fix on the gateway phone: set
  Messages as the default SMS app.
- A missed call on the trial account is answered (trial notice) before our Reject. Expected on a trial; in the
  demo use "Call me".
