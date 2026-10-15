import io
import wave
from datetime import timedelta
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select
from services.api import speech, worker
from services.api.models import Evidence, Job, now
from test_workflows import register, post


def wav_bytes():
    result = io.BytesIO()
    with wave.open(result, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b'\0\0' * 4000)
    return result.getvalue()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(speech.settings, 'elevenlabs_key', 'fake-test-key-never-live')
    monkeypatch.setattr(speech.settings, 'speech_approved', True)
    monkeypatch.setattr(speech.settings, 'speech_provider', 'elevenlabs')
    monkeypatch.setattr(speech.settings, 'speech_model', 'scribe_v2')
    monkeypatch.setattr(speech.settings, 'speech_language', None)
    monkeypatch.setattr(speech.settings, 'groq_key', '')
    return monkeypatch


def provider_response():
    return {'language_code':'msa','text':'50 crates tomato RM160 per crate, baki next month.', 'words':[{'text':'50','type':'word','start':0.0,'end':0.5,'speaker_id':'speaker_0'},{'text':'crates','type':'word','start':0.5,'end':1.0,'speaker_id':'speaker_0'}]}


def test_elevenlabs_multipart_and_grounding(configured):
    def receive(request):
        assert str(request.url) == speech.ENDPOINT
        assert request.headers['xi-api-key'] == 'fake-test-key-never-live'
        body = request.read()
        assert b'scribe_v2' in body and b'RIFF' in body
        assert b'language_code' not in body  # mixed-language auto detection
        assert b'fake-test-key' not in body
        return httpx.Response(200, json=provider_response())
    result = speech.transcribe_audio(wav_bytes(),'audio/wav','ev-test',transport=httpx.MockTransport(receive))
    assert result['provider']=='elevenlabs'
    assert result['segments'][0]['end_ms']==500
    assert result['segments'][0]['evidence_id']=='ev-test'
    assert result['review_status']=='unconfirmed'


@pytest.mark.parametrize('status,code',[(401,'SPEECH_AUTH_FAILED'),(403,'SPEECH_AUTH_FAILED'),(429,'SPEECH_RATE_LIMITED'),(422,'SPEECH_REJECTED'),(500,'SPEECH_OUTCOME_UNKNOWN')])
def test_redacted_provider_errors(configured,status,code):
    def receive(request):
        return httpx.Response(status,json={'detail':'private provider text fake-test-key-never-live'})
    with pytest.raises(speech.SpeechError) as error:
        speech.transcribe_audio(wav_bytes(),'audio/wav','ev',transport=httpx.MockTransport(receive))
    assert error.value.code==code
    assert 'fake-test-key' not in str(error.value)
    assert 'private provider text' not in str(error.value)


def test_timeout_never_retries_automatically(configured):
    calls=[]
    def receive(request):
        calls.append(request)
        raise httpx.ReadTimeout('secret-key-in-provider-exception')
    with pytest.raises(speech.SpeechError) as error:
        speech.transcribe_audio(wav_bytes(),'audio/wav','ev',transport=httpx.MockTransport(receive))
    assert len(calls)==1 and error.value.uncertain
    assert 'secret-key' not in str(error.value)


@pytest.mark.parametrize('data',[{'text':''},{'text':'Hello','words':[{'text':'Hello','start':2,'end':1}]},{'text':'x'*30001}])
def test_malformed_transcript_does_not_create_facts(configured,data):
    with pytest.raises(speech.SpeechError) as error:
        speech.transcribe_audio(wav_bytes(),'audio/wav','ev',transport=httpx.MockTransport(lambda _:httpx.Response(200,json=data)))
    assert error.value.code=='SPEECH_RESPONSE_INVALID'


def test_consent_blocks_network(configured):
    configured.setattr(speech.settings,'speech_approved',False)
    with pytest.raises(speech.SpeechError) as error:
        speech.transcribe_audio(wav_bytes(),'audio/wav','ev',transport=httpx.MockTransport(lambda _:pytest.fail('Must not call provider')))
    assert error.value.code=='SPEECH_CONSENT_REQUIRED'


def upload_audio(c):
    register(c)
    r=c.post('/v1/documents',files={'file':('note.wav',wav_bytes(),'audio/wav')},headers={'Idempotency-Key':str(uuid4())})
    assert r.status_code==202,r.text
    return r.json()['id']


def test_audio_upload_to_reviewable_terms(env,configured):
    c,factory,tx=env
    eid=upload_audio(c)
    def fake(*args,**kwargs):
        return {'provider':'elevenlabs','model':'scribe_v2','text':provider_response()['text'],'language_code':'msa','segments':[{'evidence_id':eid,'start_ms':0,'end_ms':500,'text':'50'}]}
    configured.setattr(speech,'transcribe_audio',fake)
    worker.tick()
    with factory() as db:
        ev=db.get(Evidence,eid)
        assert ev.status=='needs_review'
        assert ev.extraction['candidate']['quantity']=='50'
        assert ev.extraction['candidate']['due_date'] is None
        assert ev.extraction['transcription']['provider']=='elevenlabs'
        assert ev.extraction['audio_evidence'][0]['evidence_id']==eid


def test_transcript_is_reused_after_downstream_failure(env,configured):
    from services.api import ai
    c,factory,tx=env
    eid=upload_audio(c)
    calls=[]
    def fake(*args,**kwargs):
        calls.append(1)
        return {'provider':'elevenlabs','model':'scribe_v2','text':'20 crates','language_code':'eng','segments':[]}
    configured.setattr(speech,'transcribe_audio',fake)
    original=ai.model_extract
    configured.setattr(ai,'model_extract',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('model unavailable')))
    worker.tick()
    with tx() as db:
        job=db.scalar(select(Job).where(Job.record_id==eid))
        assert db.get(Evidence,eid).extraction['transcription']['text']=='20 crates'
        job.available_at=now()-timedelta(seconds=1)
    configured.setattr(ai,'model_extract',original)
    worker.tick()
    assert len(calls)==1
    with factory() as db:
        assert db.get(Evidence,eid).status=='needs_review'


def test_unknown_speech_outcome_needs_explicit_retry_acknowledgment(env,configured):
    c,factory,tx=env
    eid=upload_audio(c)
    def unknown(*a,**kw):
        raise speech.SpeechError('SPEECH_OUTCOME_UNKNOWN','Request interrupted; check provider usage.',uncertain=True)
    configured.setattr(speech,'transcribe_audio',unknown)
    worker.tick()
    with factory() as db:
        job=db.scalar(select(Job).where(Job.record_id==eid))
        assert job.status=='outcome_unknown'
        assert db.get(Evidence,eid).status=='transcription_uncertain'
        jid=job.id
    assert worker.claim_job() is None
    post(c,f'jobs/{jid}/retry',{'reason':'Reviewed failure'},expected=409)
    post(c,f'jobs/{jid}/retry',{'reason':'Reviewed provider usage and accept possible duplicate charge','accept_possible_duplicate_charge':True})


def test_crash_during_speech_is_not_replayed(env,configured):
    c,factory,tx=env
    eid=upload_audio(c)
    with tx() as db:
        ev=db.get(Evidence,eid)
        ev.extraction={'speech_request':'in_flight'}
        job=db.scalar(select(Job).where(Job.record_id==eid))
        job.status='processing'
        job.lease_until=now()-timedelta(seconds=1)
    assert worker.claim_job() is None
    with factory() as db:
        assert db.get(Evidence,eid).status=='transcription_uncertain'


def test_manual_speech_mode_never_sends_audio(env,configured):
    from services.api import ai
    c,factory,tx=env
    eid=upload_audio(c)
    configured.setattr(speech.settings,'speech_provider','manual')
    configured.setattr(ai,'model_extract',lambda *a,**kw:pytest.fail('Manual speech must never call a provider'))
    worker.tick()
    with factory() as db:
        assert db.get(Evidence,eid).status=='manual_entry_required'


def test_reviewed_transcript_preserves_provider_original_and_history(env,configured):
    c,factory,tx=env
    eid=upload_audio(c)
    configured.setattr(speech,'transcribe_audio',lambda *a,**kw:{'provider':'elevenlabs','text':'15 crates','segments':[]})
    worker.tick()
    result=post(c,f'evidence/{eid}/transcript-review',{'expected_version':1,'text':'50 crates tomato','reason':'Corrected quantity after replaying original recording'})
    assert result['version']==2
    with factory() as db:
        ev=db.get(Evidence,eid)
        assert ev.extraction['transcription']['text']=='15 crates'
        assert ev.extraction['transcript']=='50 crates tomato'
        assert ev.extraction['candidate']['quantity']=='50'
        assert len(ev.extraction['transcript_reviews'])==1
    post(c,f'evidence/{eid}/transcript-review',{'expected_version':1,'text':'99 crates','reason':'Stale correction must fail'},expected=409)


def test_original_audio_and_processing_are_tenant_scoped(env,configured):
    c=env[0]
    eid=upload_audio(c)
    response=c.get(f'/v1/evidence/{eid}/audio')
    assert response.status_code==200
    assert response.headers['content-type'].startswith('audio/wav')
    assert response.content==wav_bytes()
    assert c.get(f'/v1/evidence/{eid}/processing').json()['job_status']=='queued'
    post(c,'auth/logout')
    register(c,'other-audio-user@example.test')
    assert c.get(f'/v1/evidence/{eid}/audio').status_code==404
    assert c.get(f'/v1/evidence/{eid}/processing').status_code==404
    post(c,f'evidence/{eid}/retry',{'reason':'Attempt across business boundary'},expected=404)
