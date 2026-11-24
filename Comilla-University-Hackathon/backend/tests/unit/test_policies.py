from app.domain import policies


def test_policy_defaults_match_the_srs() -> None:
    assert policies.ROUTER_CONFIDENCE_THRESHOLD == 0.7  # FR-AGT-03
    assert policies.TOP_K == 5  # FR-AGT-05
    assert policies.MIN_FILTERED_RESULTS == 2  # FR-AGT-05
    assert policies.MAX_RETRIEVAL_RETRIES == 2  # FR-AGT-07
    assert policies.MAX_SPEECH_WORDS == 45  # FR-AGT-08
    assert policies.MAX_SMS_CHARS == 300  # SRS 3.2
    assert policies.MAX_TURNS_PER_CALL == 6  # FR-CALL-06
    assert policies.MAX_SILENT_REPROMPTS == 1  # FR-CALL-04
    assert policies.VOICE_BUDGET_SECONDS == 8  # FR-CALL-10
    assert policies.CALLBACK_COOLDOWN_SECONDS == 60  # FR-CALL-07
    assert policies.CACHE_TTL_HOURS == 24  # FR-AGT-15


def test_thresholds_are_valid_probabilities() -> None:
    assert 0 < policies.ROUTER_CONFIDENCE_THRESHOLD < 1
    assert 0 < policies.RETRIEVAL_MIN_SCORE < 1
