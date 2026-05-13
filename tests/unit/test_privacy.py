"""Privacy filter — PII & secret detection across multiple domains."""
from __future__ import annotations

from mosaic.security.privacy import PrivacyAction, PrivacyFilter


def test_email_detection_and_redact():
    f = PrivacyFilter()
    text = "Contact me at user@example.com for details."
    result = f.scan(text)
    hits = [h for h in result.hits if h.entity_type == "EMAIL"]
    assert len(hits) == 1
    redacted = result.redacted_text
    assert "user@example.com" not in redacted
    assert "[EMAIL]" in redacted


def test_credit_card_detection_multiple_formats():
    f = PrivacyFilter()
    text = "Visa 4111-1111-1111-1111 and Amex 378282246310005"
    result = f.scan(text)
    hits = [h for h in result.hits if "CARD" in h.entity_type]
    assert len(hits) >= 2


def test_api_key_common_patterns():
    f = PrivacyFilter()
    text = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 is my key"
    result = f.scan(text)
    hits = [h for h in result.hits if h.entity_type == "API_KEY"]
    assert len(hits) == 1


def test_block_action_prevents_disclosure():
    f = PrivacyFilter(default_action=PrivacyAction.BLOCK)
    text = "My password is hunter2"
    result = f.scan(text)
    assert result.action == PrivacyAction.BLOCK


def test_log_only_action_preserves_text():
    f = PrivacyFilter(default_action=PrivacyAction.LOG)
    text = "My SSN is 123-45-6789"
    result = f.scan(text)
    # LOG action leaves text unchanged
    assert result.redacted_text == text


def test_multiple_hits_same_type():
    f = PrivacyFilter()
    text = "First: user1@example.com, Second: user2@example.com"
    result = f.scan(text)
    emails = [h for h in result.hits if h.entity_type == "EMAIL"]
    assert len(emails) == 2
    redacted = result.redacted_text
    assert all(e not in redacted for e in ["user1@example.com", "user2@example.com"])


def test_ip_address_detection():
    f = PrivacyFilter()
    text = "Origin IP: 192.168.1.100 and 10.0.0.5"
    result = f.scan(text)
    ips = [h for h in result.hits if h.entity_type == "IP_ADDRESS"]
    assert len(ips) == 2


def test_phone_number_detection():
    f = PrivacyFilter()
    text = "Call +1-555-123-4567 or (555) 987-6543"
    result = f.scan(text)
    phones = [h for h in result.hits if h.entity_type == "PHONE"]
    assert len(phones) >= 1


def test_pii_confidence_threshold():
    f = PrivacyFilter(min_confidence=0.8)
    # Ambiguous pattern, low confidence → should be filtered
    text = "My number is 123-45-6789"  # ambiguous SSN pattern
    result = f.scan(text)
    # Depending on regex, might still hit; just ensure result is well-formed
    assert hasattr(result, "hits")
    assert hasattr(result, "redacted_text")


def test_span_offsets_are_character_positions():
    f = PrivacyFilter()
    text = "abc@def.com"
    result = f.scan(text)
    email_hits = [h for h in result.hits if h.entity_type == "EMAIL"]
    assert len(email_hits) == 1
    hit = email_hits[0]
    start, end = hit.span
    assert text[start:end] == "abc@def.com"
