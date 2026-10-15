from pathlib import Path
from dotenv import dotenv_values
from scripts.configure_speech import configure
from services.api.config import Settings


def test_saved_key_moved_without_public_template_leak(tmp_path):
    secret='synthetic-only-test-value'
    (tmp_path/'.env.example').write_text('APP_ENV=development\nELEVENLABS_API_KEY='+secret+'\nSPEECH_PROVIDER=auto\n',encoding='utf-8')
    result=configure(tmp_path)
    assert result['key_configured']
    assert dotenv_values(tmp_path/'.env')['ELEVENLABS_API_KEY']==secret
    assert secret not in (tmp_path/'.env.example').read_text()
    assert dotenv_values(tmp_path/'.env')['SPEECH_PROCESSING_APPROVED']=='true'
    assert configure(tmp_path)['key_configured']


def test_empty_configuration_does_not_claim_live_connection(tmp_path):
    (tmp_path/'.env.example').write_text('ELEVENLABS_API_KEY=\n',encoding='utf-8')
    assert not configure(tmp_path)['key_configured']


def test_provider_settings_reject_unknown_mode(monkeypatch):
    import pytest
    monkeypatch.setenv('SPEECH_PROVIDER','untrusted-custom-url')
    with pytest.raises(RuntimeError):
        Settings()
