# Groq language-model setup

KedaiFlow uses Groq for candidate trade extraction and English/Malay/Chinese translation. ElevenLabs remains the speech-to-text provider. Financial arithmetic and approval authority stay in deterministic server code.

## Settings

The private project `.env` is configured with:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
GROQ_VISION_MODEL=
MODEL_PROCESSING_APPROVED=true
```

Enter the real key only in `.env`. `.env.example` contains placeholders and keeps processing opt-in by default. The saved Groq key was verified with live synthetic extraction on 16 October 2026; the ElevenLabs-to-Groq handoff also passed.

The default model supports strict structured output according to [Groq's structured-output documentation](https://console.groq.com/docs/structured-outputs). The adapter calls the fixed server-only [OpenAI-compatible endpoint](https://console.groq.com/docs/openai). Other selected text models use JSON object mode plus the same local schema validation. Confirm model availability and account permissions in [Groq's model list](https://console.groq.com/docs/models) before changing the model ID.

Optional `GROQ_VISION_MODEL` must name an image-capable model available in your Groq account. It is blank by default: images remain reviewable with manual entry. Readable PDFs are parsed locally and only their text is sent to the text model. A scanned PDF with no extractable text requests manual entry. Audio is first transcribed by ElevenLabs; Groq receives only the transcript.

## Apply and verify

From the project directory:

```powershell
.\.venv\Scripts\python.exe -m scripts.configure_groq
.\.venv\Scripts\python.exe -m scripts.check_llm
```

The configuration helper selects Groq, preserves your chosen model and ElevenLabs settings, and moves a Groq key saved in `.env.example` into ignored `.env`. It does not print keys or reuse a Gemini key as a Groq credential. Legacy Gemini secrets may remain privately stored for your own recovery, but runtime code does not read them.

`check_llm` prints safe configuration status without a network call. For one small synthetic extraction request, which may use account credits:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_llm --live
```

Restart after saving credentials or model changes:

```powershell
.\Stop-KedaiFlow.ps1
.\Start-KedaiFlow.ps1 -SkipBuild
```

Docker Compose forwards these same provider settings to both API and worker; keep your private `.env` alongside `compose.yml`. No Groq secret goes into the frontend or Docker image.

## Failures and manual operation

Use `LLM_PROVIDER=manual` to keep extraction local. Missing keys or disabled model processing return explicitly labeled deterministic candidates. Authentication, quota, invalid JSON, relative dates, invalid quantities, noninteger money, truncated responses and model-requested tools are rejected or retained for review. Failures show safe Groq-specific guidance in the evidence processing view. There is no automatic fallback to another cloud vendor.

Speech transcripts are retained when Groq extraction fails; reviewed extraction retries reuse them. Every candidate still needs merchant confirmation before it becomes a financial/commercial record.
