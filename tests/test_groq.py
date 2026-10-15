import json
from datetime import date
import httpx
import pytest
from dotenv import dotenv_values
from sqlalchemy import select
from services.api import ai, worker, speech
from services.api.config import Settings
from services.api.models import Evidence, Job
from scripts.configure_groq import configure, DEFAULT_MODEL
from test_workflows import register, post


@pytest.fixture
def groq(monkeypatch):
    monkeypatch.setattr(ai.settings,'llm_provider','groq')
    monkeypatch.setattr(ai.settings,'groq_key','synthetic-test-key')
    monkeypatch.setattr(ai.settings,'groq_model','openai/gpt-oss-20b')
    monkeypatch.setattr(ai.settings,'groq_vision_model','')
    monkeypatch.setattr(ai.settings,'model_approved',True)
    return monkeypatch


def extraction():
    return {'transcript':'Model should not rewrite original text','translation_en':'20 crates, balance next month','translation_ms':'20 kotak, baki bulan depan','translation_zh':'20箱，下个月付余款','candidate':{'product':'tomatoes','quantity':'20','unit':'crate','unit_price_minor':6000,'due_date':None,'delivery_date':None},'questions':['What is the exact balance due date?']}


def response(data=None,**choice):
    return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(data if data is not None else extraction())},**choice}]}


def test_groq_strict_request_and_translation(groq):
    def receive(request):
        assert str(request.url)==ai.GROQ_ENDPOINT
        assert request.headers['authorization']=='Bearer synthetic-test-key'
        payload=json.loads(request.content)
        assert payload['model']=='openai/gpt-oss-20b'
        assert payload['response_format']['json_schema']['strict']
        assert payload['messages'][1]['content']=='20 crates RM60 per crate; next month.'
        assert 'synthetic-test-key' not in request.content.decode()
        assert 'tools' not in payload
        schema=payload['response_format']['json_schema']['schema']
        assert schema['required']==list(schema['properties'])
        candidate=schema['$defs']['Candidate']
        assert candidate['required']==list(candidate['properties'])
        assert candidate['additionalProperties'] is False
        return httpx.Response(200,json=response())
    result=ai.model_extract('20 crates RM60 per crate; next month.','ev1',transport=httpx.MockTransport(receive))
    assert result['provider']=='groq'
    assert result['model_version']=='openai/gpt-oss-20b'
    assert result['candidate']['unit_price_minor']==6000
    assert result['candidate']['due_date'] is None
    assert result['translations']['zh']=='20箱，下个月付余款'
    assert result['transcript']=='20 crates RM60 per crate; next month.'


def test_other_groq_text_model_uses_validated_json_mode(groq):
    groq.setattr(ai.settings,'groq_model','llama-3.3-70b-versatile')
    def receive(request):
        assert json.loads(request.content)['response_format']=={'type':'json_object'}
        return httpx.Response(200,json=response())
    assert ai.model_extract('20 crates','ev',transport=httpx.MockTransport(receive))['provider']=='groq'


@pytest.mark.parametrize('mode',['manual','no_key','no_consent'])
def test_no_cloud_fallback_when_unavailable(groq,mode):
    if mode=='manual':groq.setattr(ai.settings,'llm_provider','manual')
    if mode=='no_key':groq.setattr(ai.settings,'groq_key','')
    if mode=='no_consent':groq.setattr(ai.settings,'model_approved',False)
    result=ai.model_extract('20 crates RM60 per crate','ev',transport=httpx.MockTransport(lambda _:pytest.fail('Must not contact a provider')))
    assert result['provider']=='deterministic_review'


@pytest.mark.parametrize('status,code',[(401,'GROQ_AUTH_FAILED'),(403,'GROQ_AUTH_FAILED'),(429,'GROQ_RATE_LIMITED'),(400,'GROQ_REQUEST_FAILED'),(503,'GROQ_REQUEST_FAILED')])
def test_provider_errors_never_expose_credentials(groq,status,code):
    transport=httpx.MockTransport(lambda _:httpx.Response(status,json={'error':'synthetic-test-key and private provider response'}))
    with pytest.raises(ai.LLMError) as error:
        ai.model_extract('20 crates','ev',transport=transport)
    assert error.value.code==code
    assert 'synthetic-test-key' not in str(error.value)
    assert 'private provider response' not in str(error.value)


@pytest.mark.parametrize('problem',['float_money','bad_date','bad_quantity','extra_policy','truncated','tool_call','refusal','bad_json'])
def test_model_output_needs_business_schema_validation(groq,problem):
    value=extraction()
    if problem=='float_money':value['candidate']['unit_price_minor']=60.5
    if problem=='bad_date':value['candidate']['due_date']='next month'
    if problem=='bad_quantity':value['candidate']['quantity']='NaN'
    if problem=='extra_policy':value['bank_account_override']='attacker'
    result=response(value)
    if problem=='truncated':result['choices'][0]['finish_reason']='length'
    if problem=='tool_call':result['choices'][0]['message']['tool_calls']=[{'name':'transfer_money'}]
    if problem=='refusal':result['choices'][0]['message']['refusal']='No'
    if problem=='bad_json':result['choices'][0]['message']['content']='not valid JSON'
    with pytest.raises(ai.LLMError) as error:
        ai.model_extract('Untrusted document','ev',transport=httpx.MockTransport(lambda _:httpx.Response(200,json=result)))
    assert error.value.code=='GROQ_RESPONSE_INVALID'


def test_pdf_text_is_sent_without_original_bytes(groq):
    def receive(request):
        assert 'private-pdf-binary' not in request.content.decode()
        assert json.loads(request.content)['messages'][1]['content']=='Reviewed PDF text'
        return httpx.Response(200,json=response())
    assert ai.model_extract('Reviewed PDF text','ev',b'private-pdf-binary','application/pdf',transport=httpx.MockTransport(receive))['provider']=='groq'


def test_scanned_pdf_and_unconfigured_vision_are_manual(groq):
    transport=httpx.MockTransport(lambda _:pytest.fail('Do not invent OCR or call a text-only model with images'))
    for media_type in ('application/pdf','image/png'):
        result=ai.model_extract('','ev',b'private-bytes',media_type,transport=transport)
        assert result['transcript']==''
        assert result['provider']=='deterministic_review'


def test_configured_vision_uses_bounded_inline_image(groq):
    groq.setattr(ai.settings,'groq_vision_model','selected/vision-model')
    def receive(request):
        data=json.loads(request.content)
        assert data['model']=='selected/vision-model'
        assert data['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
        return httpx.Response(200,json=response())
    assert ai.model_extract('','ev',b'private-image','image/png',transport=httpx.MockTransport(receive))['model_version']=='selected/vision-model'


def test_groq_never_receives_raw_audio_and_does_not_become_speech_fallback(groq):
    groq.setattr(speech.settings,'speech_provider','auto')
    groq.setattr(speech.settings,'elevenlabs_key','')
    assert speech.selected_provider()=='manual'
    with pytest.raises(ai.LLMError) as error:
        ai.model_extract('','ev',b'private-raw-audio','audio/wav')
    assert error.value.code=='AUDIO_TRANSCRIPTION_REQUIRED'


def test_transport_failure_is_safe(groq):
    def receive(request):raise httpx.ReadTimeout('synthetic-test-key')
    with pytest.raises(ai.LLMError) as error:
        ai.model_extract('Source','ev',transport=httpx.MockTransport(receive))
    assert error.value.code=='GROQ_UNAVAILABLE'
    assert 'synthetic-test-key' not in str(error.value)


def test_groq_worker_failure_surfaces_actionable_status(env,groq):
    c,factory,tx=env
    register(c)
    ev=post(c,'evidence',{'text':'20 crates tomato'})
    def failed(*args,**kwargs):raise ai.LLMError('GROQ_AUTH_FAILED','Check your Groq key locally.')
    groq.setattr(ai,'model_extract',failed)
    worker.tick()
    with factory() as db:
        assert db.get(Evidence,ev['id']).status=='extraction_failed'
        job=db.scalar(select(Job).where(Job.record_id==ev['id']))
        assert job.status=='needs_review'
        assert 'GROQ_AUTH_FAILED' in job.error


def test_groq_configuration_migration_preserves_speech_and_hides_key(tmp_path):
    (tmp_path/'.env.example').write_text('GROQ_API_KEY=synthetic-groq-key\nGROQ_MODEL='+DEFAULT_MODEL+'\n',encoding='utf-8')
    (tmp_path/'.env').write_text('ELEVENLABS_API_KEY=synthetic-speech-key\nSPEECH_PROVIDER=elevenlabs\n',encoding='utf-8')
    result=configure(tmp_path)
    values=dotenv_values(tmp_path/'.env')
    assert values['GROQ_API_KEY']=='synthetic-groq-key'
    assert values['ELEVENLABS_API_KEY']=='synthetic-speech-key'
    assert result['speech_provider']=='elevenlabs'
    assert 'synthetic-groq-key' not in (tmp_path/'.env.example').read_text()
    assert configure(tmp_path)['key_configured']


def test_groq_configuration_preserves_selected_model(tmp_path):
    (tmp_path/'.env.example').write_text('GROQ_API_KEY=\n',encoding='utf-8')
    (tmp_path/'.env').write_text('GROQ_MODEL=llama-3.3-70b-versatile\nSPEECH_PROVIDER=gemini\n',encoding='utf-8')
    result=configure(tmp_path)
    assert result['model']=='llama-3.3-70b-versatile'
    assert result['speech_provider']=='auto'
    assert not result['key_configured']


def test_unknown_llm_provider_fails_configuration(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','unapproved-provider')
    with pytest.raises(RuntimeError):Settings()


def test_connection_status_names_groq_and_never_contains_key(env,groq):
    c=env[0]
    register(c)
    result=c.get('/v1/connectors')
    assert any(i['name']=='Groq extraction and translation' for i in result.json()['items'])
    assert 'synthetic-test-key' not in result.text
    assert 'Gemini' not in result.text
