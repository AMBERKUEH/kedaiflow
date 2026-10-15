"""Safe diagnostics; an explicit --audio argument performs one real provider request."""
import argparse
import json
import mimetypes
from pathlib import Path
from services.api.config import settings, PROJECT_ROOT
from services.api.speech import selected_provider, transcribe_audio, SpeechError


def main():
    parser=argparse.ArgumentParser(description='Check speech settings without displaying credentials. --audio makes one potentially billable transcription request.')
    parser.add_argument('--audio',type=Path)
    args=parser.parse_args()
    print(json.dumps({'provider':selected_provider(),'key_configured':bool(settings.elevenlabs_key),'processing_approved':settings.speech_approved,'model':settings.speech_model,'language':settings.speech_language or 'automatic'},indent=2))
    if not args.audio:
        return
    media_type=mimetypes.guess_type(str(args.audio))[0]
    if args.audio.suffix.lower()=='.webm':
        media_type='audio/webm'
    if args.audio.suffix.lower()=='.m4a':
        media_type='audio/mp4'
    if args.audio.stat().st_size > 8*1024*1024:
        raise SystemExit('Audio must be at most 8 MB.')
    try:
        result=transcribe_audio(args.audio.read_bytes(),media_type or '', 'manual-connection-test')
    except SpeechError as exc:
        raise SystemExit(exc.code + ': ' + str(exc)) from None
    destination=PROJECT_ROOT/'.local'/'speech-check.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('One live transcription succeeded. Private result saved in .local/speech-check.json. Review it before using any facts.')


if __name__=='__main__':
    main()
