import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Always read the project's private environment file, regardless of launcher cwd.
load_dotenv(PROJECT_ROOT / '.env')


class Settings:
    def __init__(self):
        self.env = os.getenv('APP_ENV', 'development')
        self.data_mode = os.getenv('DATA_MODE', 'fixture')
        self.action_mode = os.getenv('ACTION_MODE', 'simulation')
        self.database_url = os.getenv('DATABASE_URL', 'sqlite:///./kedaiflow.db')
        self.web_origin = os.getenv('WEB_ORIGIN', 'http://localhost:3000')
        self.media = Path(os.getenv('PRIVATE_MEDIA_DIR', './private_media')).resolve()
        self.auth_mode = os.getenv('AUTH_MODE', 'local')
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_id = os.getenv('TELEGRAM_BOT_ID', '')
        self.webhook_secret = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
        self.telegram_mode = os.getenv('TELEGRAM_MODE', 'polling')
        self.llm_provider = os.getenv('LLM_PROVIDER', 'groq').strip().lower()
        self.groq_key = os.getenv('GROQ_API_KEY', '').strip()
        self.groq_model = os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b').strip()
        self.groq_vision_model = os.getenv('GROQ_VISION_MODEL', '').strip()
        self.model_approved = os.getenv('MODEL_PROCESSING_APPROVED', 'false') == 'true'
        self.elevenlabs_key = os.getenv('ELEVENLABS_API_KEY', '')
        self.speech_provider = os.getenv('SPEECH_PROVIDER', 'auto')
        self.speech_approved = os.getenv('SPEECH_PROCESSING_APPROVED', 'false') == 'true'
        self.speech_model = os.getenv('ELEVENLABS_STT_MODEL', 'scribe_v2')
        self.speech_language = os.getenv('ELEVENLABS_LANGUAGE_CODE', '').strip() or None
        self.speech_timeout = 90
        if self.llm_provider not in ('groq', 'manual'):
            raise RuntimeError('LLM_PROVIDER must be groq or manual')
        if self.llm_provider == 'groq' and not self.groq_model:
            raise RuntimeError('GROQ_MODEL must name the selected Groq text model')
        if self.speech_provider not in ('auto', 'manual', 'elevenlabs'):
            raise RuntimeError('SPEECH_PROVIDER must be auto, manual or elevenlabs. Groq is the language model; ElevenLabs handles audio.')
        if self.action_mode not in ('draft', 'simulation', 'connected'):
            raise RuntimeError('ACTION_MODE must be draft, simulation or connected')
        if self.auth_mode not in ('local', 'supabase') or self.telegram_mode not in ('polling', 'webhook'):
            raise RuntimeError('Unsupported identity or Telegram delivery mode')
        if self.data_mode not in ('fixture', 'imported', 'connected'):
            raise RuntimeError('DATA_MODE must be fixture, imported or connected')
        if self.env == 'production':
            if self.auth_mode != 'supabase' or not self.database_url.startswith('postgresql'):
                raise RuntimeError('Production requires Supabase auth and PostgreSQL')
            if self.data_mode == 'fixture' or self.action_mode == 'simulation':
                raise RuntimeError('Fixture/simulation modes are forbidden in production')


settings = Settings()
