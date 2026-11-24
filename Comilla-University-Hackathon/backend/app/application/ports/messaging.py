"""Ports: SMS, outbound calls and text-to-speech (FR-SMS, FR-CALL-07, FR-APP-04)."""

from typing import Protocol, runtime_checkable

from app.domain.value_objects import PhoneNumber


@runtime_checkable
class SmsSender(Protocol):
    def send(self, phone: PhoneNumber, text: str) -> bool:
        """True if accepted by the gateway. Never raises: failures are logged and return False."""
        ...


@runtime_checkable
class CallPlacer(Protocol):
    def call(self, phone: PhoneNumber) -> str:
        """Starts an outbound call and returns its call SID."""
        ...


@runtime_checkable
class TextToSpeech(Protocol):
    def synthesize(self, text: str) -> bytes:
        """Bangla speech as MP3 bytes."""
        ...
