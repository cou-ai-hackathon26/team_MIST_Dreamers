"""Fixed Bangla texts the user hears or reads (SRS Appendix A).

These never come from the LLM. Change wording here and in docs/SRS.md together;
tests/unit/test_messages_bn.py checks that both match.
"""

from typing import Final

GREETING: Final = "আসসালামু আলাইকুম। আমি এক কল, একটি এআই সহকারী। সরকারি সেবা নিয়ে কী জানতে চান, বলুন।"
CONTINUE: Final = "আর কিছু জানতে চাইলে বলুন।"
REPROMPT: Final = "দুঃখিত, আমি শুনতে পাইনি। আবার বলবেন?"
WAIT_FILLER: Final = "একটু অপেক্ষা করুন, আমি দেখে বলছি।"
FALLBACK: Final = (
    "দুঃখিত, এই বিষয়ে সরকারি কাগজে আমি নিশ্চিত তথ্য পাইনি। দয়া করে ৩৩৩ নম্বরে ফোন করুন অথবা উপজেলা অফিসে যোগাযোগ করুন।"
)
ERROR: Final = "দুঃখিত, এখন একটু সমস্যা হচ্ছে। একটু পরে আবার চেষ্টা করুন অথবা ৩৩৩ নম্বরে ফোন করুন।"
SMS_SENT: Final = "আপনার মোবাইলে এসএমএস পাঠানো হয়েছে।"
GOODBYE: Final = "ধন্যবাদ। ভালো থাকবেন।"
DECISION_NOTE: Final = "চূড়ান্ত সিদ্ধান্ত সংশ্লিষ্ট অফিস নেবে।"
RATE_LIMITED: Final = "একটু আগেই আপনাকে কল করা হয়েছে। এক মিনিট পরে আবার চেষ্টা করুন।"
INVALID_PHONE: Final = "মোবাইল নম্বরটি সঠিক নয়। ০১ দিয়ে শুরু ১১ অঙ্কের নম্বর দিন।"
NOT_FOUND: Final = "কোনো তথ্য পাওয়া যায়নি।"
BAD_REQUEST: Final = "অনুরোধটি সঠিক নয়। তথ্যগুলো দেখে আবার চেষ্টা করুন।"
MULTI_INTRO: Final = "আপনার কথায় দুটি সেবার কথা আসছে: {a} আর {b}।"
CONFLICT_NOTE: Final = "এই দুই সেবার নিয়ম আলাদা। আপনার ক্ষেত্রে কোনটি প্রযোজ্য, তা উপজেলা অফিস ঠিক করবে।"
COMBINE_UNKNOWN: Final = "দুটি সুবিধা একসাথে পাওয়া যায় কিনা, সরকারি কাগজে আমি নিশ্চিত তথ্য পাইনি।"
TWO_SMS: Final = "দুটি সেবার জন্য আলাদা দুটি এসএমএস পাঠানো হয়েছে।"
SITUATION_HEARD: Final = "আমি যা বুঝেছি: {summary}"

ALL_MESSAGES: Final[dict[str, str]] = {
    "GREETING": GREETING,
    "CONTINUE": CONTINUE,
    "REPROMPT": REPROMPT,
    "WAIT_FILLER": WAIT_FILLER,
    "FALLBACK": FALLBACK,
    "ERROR": ERROR,
    "SMS_SENT": SMS_SENT,
    "GOODBYE": GOODBYE,
    "DECISION_NOTE": DECISION_NOTE,
    "RATE_LIMITED": RATE_LIMITED,
    "INVALID_PHONE": INVALID_PHONE,
    "NOT_FOUND": NOT_FOUND,
    "BAD_REQUEST": BAD_REQUEST,
    "MULTI_INTRO": MULTI_INTRO,
    "CONFLICT_NOTE": CONFLICT_NOTE,
    "COMBINE_UNKNOWN": COMBINE_UNKNOWN,
    "TWO_SMS": TWO_SMS,
    "SITUATION_HEARD": SITUATION_HEARD,
}
