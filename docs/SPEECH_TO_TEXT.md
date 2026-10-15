# ElevenLabs speech to text

Implemented 16 October 2026 using the [official batch speech endpoint](https://elevenlabs.io/docs/api-reference/speech-to-text/convert). The adapter uses the already-locked HTTP client; no extra SDK or global CLI is required.

## Connect your key

Use the project directory containing this README and run:

```powershell
.\.venv\Scripts\python.exe -m scripts.configure_speech
```

This moves a saved `ELEVENLABS_API_KEY` from `.env.example` into the ignored `.env`, restores the example placeholder, and enables ElevenLabs speech processing when a key is present. It never prints the key. If your editor changes are unsaved, save them first. You can also place the key directly in `.env`:

```dotenv
ELEVENLABS_API_KEY=YOUR_KEY_HERE
SPEECH_PROVIDER=elevenlabs
ELEVENLABS_STT_MODEL=scribe_v2
ELEVENLABS_LANGUAGE_CODE=
SPEECH_PROCESSING_APPROVED=true
```

Leaving the language blank enables provider language detection for Malay/English/Chinese and mixed-language notes. A configured model does not establish transcription accuracy for your merchant dataset. Do not put a real key in the frontend, screenshots, Git or chat.

The approval setting enables sending uploaded audio to ElevenLabs. Provider account processing and retention terms apply. This implementation does not claim zero retention; ElevenLabs documents that as an account-dependent enterprise option.

Restart the API and worker after changing `.env`:

```powershell
.\Stop-KedaiFlow.ps1
.\Start-KedaiFlow.ps1 -SkipBuild
```

For a configuration-only check, which makes **no provider call**:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_speech
```

For one explicit real transcription request (may use account credits):

```powershell
.\.venv\Scripts\python.exe -m scripts.check_speech --audio C:\path\to\a-short-test.wav
```

The real result is saved privately under `.local/speech-check.json`; raw provider errors and credentials are not printed.

## Use it in KedaiFlow

1. Choose **Capture something** and upload an OGG, MP3, WAV, M4A or WebM recording up to 8 MB.
2. The durable worker transcribes it, saves the original text, detected language, word timestamps and speaker labels, then extracts candidate trade fields.
3. Open the evidence under Deals. Replay the original recording and inspect the transcript/source metadata. Edit the proposed deal fields before confirming exact dates and terms.
4. Groq remains optional for deeper extraction/translation. An ElevenLabs key alone enables transcription and the existing conservative rules; it does not provide translation, OCR or financial authority.
5. Existing Telegram voice intake uses this same worker, so it does not need a separate transcription implementation.

## Failure and retry behavior

Authentication, quota, unsupported input and invalid provider responses produce safe review messages. Audio remains private and no invoice/payment is created from a failed transcript. Network timeout/server ambiguity or a worker crash during paid speech processing stops automatic replay. The owner must review provider usage and explicitly accept a possible duplicate charge before retrying an uncertain request.

A successful transcript is persisted before downstream extraction. Retrying a language-model failure reuses that transcript without paying for speech again. From the evidence dialog, open **Retry transcription or extraction** after correcting connection settings. Manual mode never sends audio to either speech or Groq providers.

## Validation boundary

Mocked multipart, authentication, timestamps, review state, failure redaction, recovery, transcript reuse and tenant/file permissions are tested. A real key and a successful provider response are required before calling the connection live. Do not infer live connection from `configured_unverified` in Connections.
