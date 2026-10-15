"""Bounded server-only transcription; results remain unconfirmed source evidence."""
from typing import Literal
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from .config import settings

ENDPOINT = 'https://api.elevenlabs.io/v1/speech-to-text'
MAX_BYTES = 8 * 1024 * 1024
MAX_TEXT = 30000


class SpeechError(RuntimeError):
    def __init__(self, code, message, retryable=False, uncertain=False):
        self.code, self.retryable, self.uncertain = code, retryable, uncertain
        super().__init__(message)


class Word(BaseModel):
    model_config = ConfigDict(extra='ignore', allow_inf_nan=False)
    text: str = Field(max_length=2000)
    type: str = Field(default='word', max_length=50)
    start: float | None = Field(default=None, ge=0, le=86400)
    end: float | None = Field(default=None, ge=0, le=86400)
    speaker_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode='after')
    def ordered(self):
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError('Invalid word timing')
        return self


class Transcription(BaseModel):
    model_config = ConfigDict(extra='ignore')
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    language_code: str = Field(default='und', max_length=20)
    words: list[Word] = Field(default_factory=list, max_length=15000)


def selected_provider():
    if settings.speech_provider != 'auto':
        return settings.speech_provider
    if settings.elevenlabs_key:
        return 'elevenlabs'
    return 'manual'


def transcribe_audio(content, media_type, evidence_id, transport=None):
    if not settings.speech_approved:
        raise SpeechError('SPEECH_CONSENT_REQUIRED', 'Enable SPEECH_PROCESSING_APPROVED in the private .env after reviewing ElevenLabs processing terms.')
    if not settings.elevenlabs_key:
        raise SpeechError('SPEECH_NOT_CONFIGURED', 'Set ELEVENLABS_API_KEY in the private project .env.')
    if not content or len(content) > MAX_BYTES or not media_type.startswith('audio/'):
        raise SpeechError('AUDIO_INVALID', 'Use a nonempty audio file no larger than 8 MB.')
    if settings.speech_model not in ('scribe_v2', 'scribe_v1'):
        raise SpeechError('SPEECH_MODEL_INVALID', 'Choose scribe_v2 or scribe_v1 for trade transcription.')
    extensions = {'audio/ogg':'ogg','audio/mpeg':'mp3','audio/wav':'wav','audio/mp4':'m4a','audio/webm':'webm'}
    if media_type not in extensions:
        raise SpeechError('AUDIO_TYPE_UNSUPPORTED', 'Use OGG, MP3, WAV, M4A or WebM audio.')
    form = {'model_id': settings.speech_model, 'diarize': 'true', 'tag_audio_events': 'true', 'timestamps_granularity': 'word'}
    if settings.speech_language:
        form['language_code'] = settings.speech_language
    try:
        with httpx.Client(timeout=httpx.Timeout(settings.speech_timeout, connect=10), transport=transport, follow_redirects=False, trust_env=False) as client:
            # Bytes only. No arbitrary source URLs, caller tools, financial state or keys in prompts.
            response = client.post(ENDPOINT, headers={'xi-api-key': settings.elevenlabs_key}, data=form, files={'file':('recording.' + extensions[media_type], content, media_type)})
    except httpx.TransportError:
        raise SpeechError('SPEECH_OUTCOME_UNKNOWN', 'The transcription request was interrupted. Audio is saved; check provider usage before manually retrying.', uncertain=True) from None
    if response.status_code in (401, 403):
        raise SpeechError('SPEECH_AUTH_FAILED', 'ElevenLabs rejected the configured key or speech-to-text permission. Check it locally.')
    if response.status_code == 429:
        raise SpeechError('SPEECH_RATE_LIMITED', 'ElevenLabs rate limit or quota reached. Audio is saved; retry later.')
    if response.status_code >= 500:
        raise SpeechError('SPEECH_OUTCOME_UNKNOWN', 'ElevenLabs returned a server error. Check provider usage before retrying.', uncertain=True)
    if not 200 <= response.status_code < 300:
        raise SpeechError('SPEECH_REJECTED', 'ElevenLabs could not process this audio. Check format and account permissions, or enter the transcript manually.')
    try:
        if len(response.content) > 2 * 1024 * 1024:
            raise ValueError()
        result = Transcription.model_validate(response.json())
        if not result.text.strip():
            raise ValueError()
    except (ValueError, ValidationError):
        raise SpeechError('SPEECH_RESPONSE_INVALID', 'The provider returned no usable transcript. Audio is saved for manual review.') from None
    spans = [{'evidence_id': evidence_id, 'text': word.text, 'start_ms': round(word.start * 1000) if word.start is not None else None, 'end_ms': round(word.end * 1000) if word.end is not None else None, 'speaker_id': word.speaker_id, 'type': word.type} for word in result.words]
    return {'provider': 'elevenlabs', 'model': settings.speech_model, 'schema_version': 'speech_v1', 'text': result.text, 'language_code': result.language_code, 'segments': spans, 'review_status': 'unconfirmed', 'retention': 'Provider account processing/retention terms apply; zero retention has not been configured.'}
