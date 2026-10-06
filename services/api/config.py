import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


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
        self.gemini_key = os.getenv('GEMINI_API_KEY', '')
        self.gemini_model = os.getenv('GEMINI_MODEL', '')
        self.model_approved = os.getenv('MODEL_PROCESSING_APPROVED', 'false') == 'true'
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
