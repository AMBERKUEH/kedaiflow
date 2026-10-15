"""Move a saved ElevenLabs key into private .env without printing its value."""
import re
from pathlib import Path
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def real_key(value):
    return bool(value and value.strip() and not value.strip().lower().startswith(('<','replace','your_','example','placeholder')))


def configure(root=ROOT):
    example, private = root/'.env.example', root/'.env'
    public_values = dotenv_values(example)
    private_values = dotenv_values(private) if private.exists() else {}
    public_key, local_key = public_values.get('ELEVENLABS_API_KEY'), private_values.get('ELEVENLABS_API_KEY')
    if real_key(public_key) and real_key(local_key) and public_key != local_key:
        raise RuntimeError('Different ElevenLabs keys exist in .env and .env.example. Keep the intended key in .env before continuing.')
    if not private.exists():
        private.write_text(example.read_text(encoding='utf-8-sig'),encoding='utf-8')
    key = public_key if real_key(public_key) else local_key
    if real_key(key):
        set_key(str(private),'ELEVENLABS_API_KEY',key,quote_mode='always')
        set_key(str(private),'SPEECH_PROVIDER','elevenlabs',quote_mode='never')
        set_key(str(private),'SPEECH_PROCESSING_APPROVED','true',quote_mode='never')
    # Sanitize every occurrence of this variable in the public template.
    source=example.read_text(encoding='utf-8-sig')
    source=re.sub(r'(?m)^\s*(?:export\s+)?ELEVENLABS_API_KEY\s*=.*$', 'ELEVENLABS_API_KEY=', source)
    example.write_text(source,encoding='utf-8')
    return {'private_env_exists':private.exists(),'key_configured':real_key(key),'template_has_no_key':not real_key(dotenv_values(example).get('ELEVENLABS_API_KEY'))}


if __name__=='__main__':
    status=configure()
    if status['key_configured']:
        print('ElevenLabs key is in private .env; template restored. Speech processing enabled. Restart API and worker.')
    else:
        print('Private .env prepared. No saved ElevenLabs key was found. Set ELEVENLABS_API_KEY in .env, save it, then run this command again.')
