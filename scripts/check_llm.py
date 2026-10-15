"""Safe model settings check. --live makes one small synthetic Groq request."""
import argparse
import json
from services.api.config import settings
from services.api.ai import model_extract, LLMError


def main():
    parser=argparse.ArgumentParser(description='Groq diagnostics without displaying keys. --live may use account credits.')
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    print(json.dumps({'provider':settings.llm_provider,'model':settings.groq_model,'key_configured':bool(settings.groq_key),'processing_approved':settings.model_approved,'vision_model':settings.groq_vision_model or 'manual image review'},indent=2))
    if not args.live:
        return
    if not settings.groq_key or not settings.model_approved or settings.llm_provider!='groq':
        raise SystemExit('Set GROQ_API_KEY and enable MODEL_PROCESSING_APPROVED in private .env first.')
    try:
        result=model_extract('Synthetic test: 20 crates tomato at RM60 per crate. The balance is due next month; ask for the exact date.','synthetic-groq-connection-check')
    except LLMError as exc:
        raise SystemExit(exc.code+': '+str(exc)) from None
    print(json.dumps({'live_provider':result['provider'],'model':result['model_version'],'schema_validated':True,'requires_merchant_review':True},indent=2))


if __name__=='__main__':
    main()
