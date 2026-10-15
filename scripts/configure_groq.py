"""Select Groq and migrate saved keys into private .env without printing them."""
import re
from pathlib import Path
from dotenv import dotenv_values, set_key
from .configure_speech import real_key

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = 'openai/gpt-oss-20b'


def configure(root=ROOT):
    template,private=root/'.env.example',root/'.env'
    public=dotenv_values(template)
    local=dotenv_values(private) if private.exists() else {}
    source=template.read_text(encoding='utf-8-sig')
    for name in ('GROQ_API_KEY','ELEVENLABS_API_KEY','GEMINI_API_KEY'):
        if real_key(public.get(name)) and real_key(local.get(name)) and public[name]!=local[name]:
            raise RuntimeError(f'Different {name} values exist in the public and private files. Keep the intended key in .env before continuing.')
    if not private.exists():
        private.write_text(source,encoding='utf-8')
    for name in ('GROQ_API_KEY','ELEVENLABS_API_KEY','GEMINI_API_KEY'):
        if real_key(public.get(name)):
            set_key(str(private),name,public[name],quote_mode='always')
        source=re.sub(r'(?m)^\s*(?:export\s+)?'+name+r'\s*=.*$',name+'=',source)
    template.write_text(source,encoding='utf-8')
    set_key(str(private),'LLM_PROVIDER','groq',quote_mode='never')
    set_key(str(private),'GROQ_MODEL',local.get('GROQ_MODEL') or public.get('GROQ_MODEL') or DEFAULT_MODEL,quote_mode='never')
    if not local.get('GROQ_VISION_MODEL'):
        set_key(str(private),'GROQ_VISION_MODEL',public.get('GROQ_VISION_MODEL') or '',quote_mode='never')
    # The user explicitly selected Groq; consent applies when a key is saved.
    set_key(str(private),'MODEL_PROCESSING_APPROVED','true',quote_mode='never')
    if local.get('SPEECH_PROVIDER')=='gemini':
        set_key(str(private),'SPEECH_PROVIDER','auto',quote_mode='never')
    result=dotenv_values(private)
    return {'provider':result['LLM_PROVIDER'],'model':result['GROQ_MODEL'],'key_configured':real_key(result.get('GROQ_API_KEY')),'speech_provider':result.get('SPEECH_PROVIDER','auto'),'elevenlabs_key_preserved':real_key(result.get('ELEVENLABS_API_KEY'))}


if __name__=='__main__':
    import json
    print(json.dumps(configure(),indent=2))
