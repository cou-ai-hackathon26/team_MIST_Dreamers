# Demo phrases (print this page)

**Bold** questions are in the answer cache (`python -m scripts.prewarm --voice`), so they answer in about
1 s. Type or say them **exactly** as written, including "৬৭" as a number. The other questions are not cached
and take 10 to 30 s, and they were not tested in this run; use them only if the judges ask for "another question".

## App (type, or tap the mic in Chrome)

| Service | Main question (cached) | Other questions |
|---|---|---|
| বয়স্ক ভাতা | **আমার বয়স ৬৭। আমি কি বয়স্ক ভাতা পাবো? কী কী লাগবে?** | মহিলাদের বয়স্ক ভাতার বয়সসীমা কত? |
| বিধবা ভাতা | **বিধবা ভাতার জন্য কী লাগে?** | স্বামী মারা যাওয়ার পর বিধবা ভাতার আবেদন কোথায় করব? |
| প্রতিবন্ধী ভাতা | **প্রতিবন্ধী ভাতা পেতে কী কী কাগজ লাগে?** | প্রতিবন্ধী কার্ড থাকলে ভাতার জন্য আবেদন করব কোথায়? |
| জন্ম নিবন্ধন | **জন্ম নিবন্ধন করতে কী কী কাগজ লাগে?** | জন্ম নিবন্ধন সনদের নকল কপি নিতে কত টাকা? |
| এনআইডি সংশোধন | **NID-te namer banan bhul, ki korbo?** (Banglish) | জাতীয় পরিচয়পত্র সংশোধনের ফি কত টাকা? |
| ই-পাসপোর্ট | **ই-পাসপোর্ট করতে কত টাকা লাগে?** | ১৫ বছরের ছেলের পাসপোর্টে কি জন্ম নিবন্ধন দিলে হবে? |
| নামজারি | **জমির নামজারি করতে কী কী লাগে?** | নামজারির আবেদন ফি কত টাকা? |
| ট্রেড লাইসেন্স | **ট্রেড লাইসেন্স করতে কী কী কাগজ লাগে?** | ট্রেড লাইসেন্স নবায়নের ফি কত? |
| Not our service (S7) | **প্রতিবেশীর সাথে জমি নিয়ে ঝামেলা, কী করবো?** gives the safe "call 333" answer | পল্লী বিদ্যুতের নতুন মিটার নিতে কী লাগে? |

Short follow-ups that stay on the same service: "আর কোথায় জমা দেবো?", "ফি কত?", "কত দিন লাগে?"

## Phone call (tap "আমাকে কল করুন", answer, wait for the greeting)

1. After the trial notice, press any key if asked, then wait for the greeting.
2. Say: **"আমার বয়স ৬৭। আমি কি বয়স্ক ভাতা পাবো? কী কী লাগবে?"** Speak slowly, phone close to the mouth.
   The answer ends with "আপনার মোবাইলে এসএমএস পাঠানো হয়েছে।" and the SMS arrives (S1, S3).
3. Follow-up: **"আর কোথায় জমা দেবো?"** (same service, no second SMS).
4. If the agent asks a yes/no question, answer **"হ্যাঁ"** or **"না"** (S2: this does not end the call).
5. End: **"না, ধন্যবাদ"**, and the agent says goodbye and hangs up.
6. Silence test (S8): say nothing twice. First a reminder, then goodbye.

## Before the demo (checklist)

- [ ] BanglaBERT model folder on the demo laptop (`backend/data/models/router/`)
- [ ] `python -m scripts.ingest`, then `python -m scripts.prewarm --voice`: every bold question says "stored" or "cache hit"
- [ ] ngrok running, `PUBLIC_URL` = the ngrok URL, Twilio number webhook = `PUBLIC_URL/voice/incoming`
- [ ] `VALIDATE_TWILIO_SIGNATURE=true`, `MISSED_CALL_MODE=false`, `SMS_BACKEND=textbee`
- [ ] Gateway phone: textbee app running, Messages is the default SMS app, SMS pack or balance
- [ ] Demo phone is a Twilio verified number
