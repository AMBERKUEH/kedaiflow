"""FLOW evaluations: deterministic fixtures; no external services or secrets."""
from datetime import timedelta, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from sqlalchemy import select, func
from services.api.models import now, Business, Invoice, Counterparty, Membership
from services.api.bijaksense import connectors as c, engine as e, jobs, retrieval
from services.api.bijaksense.models import *
from services.api.bijaksense.schemas import ContextInput, RecommendationOutput
from tests.test_workflows import register


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('BIJAKSENSE_EMBEDDINGS_ENABLED', 'false')
    monkeypatch.setenv('BIJAKSENSE_QWEN_API_KEY', '')
    monkeypatch.setattr(e, 'llm_key', lambda: '')


def context(bid='merchant', **kwargs):
    return MerchantContext(business_id=bid, industry='grocery retail', location='Kuala Lumpur', latitude=3.139, longitude=101.687, products=['rice', 'tomatoes'], materials=['palm oil'], markets=['malaysia'], commodities=['rice'], cost_categories={'rice': 'food ingredients'}, enabled=True, **kwargs)


def profile(client):
    register(client)
    bid = client.get('/v1/me').json()['business']['id']
    response = client.post('/api/bijaksense/context', json={'industry':'grocery retail','location':'Kuala Lumpur','latitude':3.139,'longitude':101.687,'products':['rice','tomatoes'],'materials':['palm oil'],'commodities':['rice'],'cost_categories':{'rice':'ingredients'}})
    assert response.status_code == 200, response.text
    return bid


def item(category='supply_chain', **kw):
    values = dict(category=category, title='Malaysia rice supply disruption reported', text='Rice supplier shortage in Malaysia', url='https://example.com/news', provider='Fixture source', reliability='reported_unverified', basis='qualitative_news', published_at=now(), geography=['Malaysia'])
    values.update(kw)
    return c.EvidenceItem(**values)


def test_api_auth_and_context_validation(client):
    for path in ('overview','signals','commodities','weather','trends','competitors','insights'):
        assert client.get('/api/bijaksense/'+path).status_code == 401
    profile(client)
    assert len(client.get('/api/bijaksense/overview').json()['categories']) == 5
    invalid = dict(industry='grocery', location='KL', latitude=100, longitude=101, commodities=['imaginary'])
    assert client.post('/api/bijaksense/context',json=invalid).status_code == 422


@pytest.mark.parametrize('industry,products,title,expected',[
    ('grocery retail',['rice'],'Malaysia rice shortage',True),
    ('fashion retail',['shirts'],'Malaysia rice shortage',False),
    ('construction',['copper'],'Malaysia copper shortage',True),
    ('software services',[],'Malaysia freight disruption',False),
    ('bakery',['bread'],'Malaysia port logistics delays',True),
    ('grocery retail',['rice'],'Malaysia export technology report',False),
])
def test_industry_relevance(industry, products, title, expected):
    ctx=context(); ctx.industry,ctx.products,ctx.materials=industry,products,[]
    s=MarketSignal(category='supply_chain', title=title,text=title, geography=['Malaysia'],basis='qualitative_news',data={},expires_at=now()+timedelta(days=1))
    assert bool(retrieval.relevance(s,ctx)) == expected


def test_stale_geography_and_forecast_filtering():
    ctx=context()
    s=MarketSignal(category='supply_chain',title='rice shortage',text='rice',geography=['Canada'],basis='qualitative_news',data={},expires_at=now()+timedelta(days=1))
    assert retrieval.relevance(s,ctx) is None
    s.geography=['Malaysia']; s.expires_at=now()-timedelta(seconds=1)
    assert retrieval.relevance(s,ctx) is None
    s.category='weather';s.expires_at=now()+timedelta(hours=1);s.data={'latitude':0,'longitude':0,'date':'2099-01-01'}
    assert retrieval.relevance(s,ctx) is None


def test_currency_unit_normalization_and_rejection():
    assert c.normalize_price('1000','($/mt)') == (Decimal('1'), 'USD','kg')
    assert c.normalize_price('250','(cents/kg)') == (Decimal('2.5'),'USD','kg')
    for value,unit in [('12','MYR/bag'),('NaN','($/kg)'),('-1','($/kg)')]:
        with pytest.raises(ValueError):c.normalize_price(value,unit)
    assert c.percentage('110','100') == '10.00'
    assert c.percentage('10','0') is None


def test_price_windows_exclude_currency_unit_location_mismatch(env):
    client,factory,tx=env; bid=profile(client)
    with tx() as db:
        s=e.persist(db,bid,item('commodities',basis='monthly_benchmark',data={'commodity':'rice','observations':[{'value':'1','currency':'USD','unit':'kg','original_value':'1000','original_unit':'($/mt)','observed_at':'2026-08-31T00:00:00+00:00','location':'International benchmark'},{'value':'1.1','currency':'USD','unit':'kg','original_value':'1100','original_unit':'($/mt)','observed_at':'2026-09-30T00:00:00+00:00','location':'International benchmark'}]}))
        db.add(CommodityPriceObservation(business_id=bid,signal_id=s.id,commodity='rice',value=500,currency='MYR',unit='bag',original_value='500',original_unit='MYR/bag',location='KL',observed_at=datetime(2026,8,31,tzinfo=timezone.utc)))
    with factory() as db:
        series=e.price_series(db,bid,'rice')
        assert series['movements_pct']['1m']=='10.00'
        assert series['movements_pct']['3m'] is None
        assert series['incompatible_observations_excluded']==1


def test_missing_data_jobs_and_refresh_abuse(env,monkeypatch):
    client,factory,tx=env;profile(client)
    for name in ('news','commodities','weather','trends'):
        monkeypatch.setattr(c,name,Mock(side_effect=c.Unavailable('External data unavailable')))
    first=client.post('/api/bijaksense/refresh').json()['job']
    second=client.post('/api/bijaksense/refresh').json()['job']
    assert first['id']==second['id']
    assert jobs.tick()
    result=client.get('/api/bijaksense/jobs/'+first['id']).json()
    assert result['status']=='completed'
    assert result['result']['categories']['weather']['status']=='unavailable'
    assert result['result']['categories']['competitors']['status']=='not_configured'
    assert client.post('/api/bijaksense/refresh').status_code==429
    assert client.get('/api/bijaksense/insights').json()['items']==[]


def test_tenant_isolation_feedback_and_role(env):
    client,factory,tx=env;bid=profile(client)
    with tx() as db:
        s=e.persist(db,bid,item());sid=s.id
        ctx=db.get(MerchantContext,bid);items,mode=e.candidates(db,ctx)
        iid=e.save_insights(db,bid,items,'deterministic',mode)[0]
    assert client.post(f'/api/bijaksense/insights/{iid}/feedback',json={'status':'dismissed'}).status_code==200
    client.post('/v1/auth/logout')
    register(client,'other@example.test')
    assert client.get(f'/api/bijaksense/signals/{sid}').status_code==404
    assert client.post(f'/api/bijaksense/insights/{iid}/feedback',json={'status':'useful'}).status_code==404
    assert client.get('/api/bijaksense/signals').json()['items']==[]
    uid=client.get('/v1/me').json()['user']['id']
    with tx() as db:
        db.scalar(select(Membership).where(Membership.user_id==uid)).role='sales'
    assert client.get('/api/bijaksense/overview').status_code==403
    assert client.post('/api/bijaksense/refresh').status_code==403


def test_dedup_and_conflicting_reports_preserve_dismissal(env):
    client,factory,tx=env;bid=profile(client)
    a=item(title='Malaysia rice port closed after storm',text='Malaysia rice port closed after storm')
    b=item(title='Malaysia rice port reopened after storm',text='Malaysia rice port reopened after storm',url='https://example.com/second')
    with tx() as db:
        first=e.persist(db,bid,a);e.persist(db,bid,a);e.persist(db,bid,b)
        assert db.scalar(select(func.count()).select_from(MarketSignal))==2
        options,mode=e.candidates(db,db.get(MerchantContext,bid))
        assert any(len(i['evidence_ids'])==2 for i in options)
        ids=e.save_insights(db,bid,options,'deterministic',mode)
        db.flush(); db.get(MarketInsight,ids[0]).status='dismissed'
        e.save_insights(db,bid,options,'deterministic',mode)
        db.flush()
        assert db.get(MarketInsight,ids[0]).status=='dismissed'
        assert db.scalar(select(func.count()).select_from(MarketInsight))==1


@pytest.mark.parametrize('payload',[
    {'choices':[{'candidate_id':'invented-source','action_codes':['review_costs']}]},
    {'choices':[{'candidate_id':'real','action_codes':['buy_100_tonnes_now']}]},
    {'choices':[{'candidate_id':'real','action_codes':['review_costs'],'price':123}]},
    {'choices':[], 'explanation':'Demand has risen 50% without evidence'},
])
def test_llm_hallucination_rejected(env,monkeypatch,payload):
    import json
    monkeypatch.setattr(e,'llm_key',lambda:'synthetic-test-key'); monkeypatch.setattr(e.settings,'model_approved',True)
    response=Mock(status_code=200);response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload)}}]}
    fake=Mock();fake.__enter__=Mock(return_value=fake);fake.__exit__=Mock(return_value=False);fake.post.return_value=response
    monkeypatch.setattr(e.httpx,'Client',lambda **kw:fake)
    options=[{'candidate_id':'real','category':'commodities','allowed_action_codes':['review_costs'],'action_codes':['review_costs']}]
    selected,mode=e.recommend(options,context(),{})
    assert selected==options and mode=='deterministic_fallback_qwen_validation_failed'


def test_qwen_validated_selection(env,monkeypatch):
    import json
    monkeypatch.setattr(e,'llm_key',lambda:'synthetic-test-key');monkeypatch.setattr(e.settings,'model_approved',True)
    response=Mock(status_code=200);response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'choices':[{'candidate_id':'real','action_codes':['review_costs']}]})}}]}
    fake=Mock();fake.__enter__=Mock(return_value=fake);fake.__exit__=Mock(return_value=False);fake.post.return_value=response
    monkeypatch.setattr(e.httpx,'Client',lambda **kw:fake)
    _,mode=e.recommend([{'candidate_id':'real','category':'commodities','allowed_action_codes':['review_costs']}],context(),{})
    assert mode.startswith('qwen:')


def test_ssrf_private_dns_credentials_and_redirects(monkeypatch):
    for url in ('http://example.com','https://user:pass@example.com','https://example.com:8443','https://example.com/#fragment'):
        with pytest.raises(c.Unavailable):c.public_url(url)
    monkeypatch.setattr(c.socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(c.Unavailable):c.fetch('https://rebound.example/test')


def test_competitor_robots_and_ads(monkeypatch):
    p=SimpleNamespace(id='comp',name='Test store',url='https://example.com/products',public_access_confirmed=True,source_type='website')
    mock=Mock(return_value=b'User-agent: *\nDisallow: /products');monkeypatch.setattr(c,'fetch',mock)
    with pytest.raises(c.Unavailable,match='disallows'):c.competitor(p)
    assert mock.call_count==1
    page=b'<html><title>Product listing</title><script type="application/ld+json">{"@type":"Product","name":"Rice 5 kg","offers":{"@type":"Offer","price":"25.90","priceCurrency":"MYR"}}</script><p>Public promotion, terms apply.</p></html>'
    monkeypatch.setattr(c,'fetch',lambda url,*a:b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else page)
    result=c.competitor(p)[0]
    assert result.data['advertised_prices'][0]['price']=='25.90'
    assert result.published_at is None and result.basis=='public_page_observation'
    assert 'first observation' in result.data['note']


def test_weather_units_forecast_risk(monkeypatch):
    import json
    raw={'daily_units':{'temperature_2m_max':'°C','precipitation_sum':'mm','wind_speed_10m_max':'km/h'},'daily':{'time':['2026-10-16'],'temperature_2m_max':[36],'precipitation_sum':[30],'precipitation_probability_max':[90],'wind_speed_10m_max':[45]}}
    monkeypatch.setattr(c,'fetch',lambda *a:json.dumps(raw).encode())
    signal=c.weather(context())[0]
    assert signal.basis=='forecast' and set(signal.data['risks'])=={'rain','heat','wind'}
    raw['daily_units']['precipitation_sum']='inch'
    with pytest.raises(c.Unavailable):c.weather(context())


def test_dosm_measured_not_demand_and_nonretail_qualitative(monkeypatch):
    raw='series,date,sales,volume,volume_sa\n'+''.join(f'abs,{2025+(i//12)}-{i%12+1:02}-01,{100+i},100,100\n' for i in range(13))
    monkeypatch.setattr(c,'fetch',lambda *a:raw.encode())
    result=c.trends(context())[0]
    assert result.data['sales_yoy_pct']=='12.00' and result.data['volume_yoy_pct']=='0.00'
    assert 'not proof' in result.text
    ctx=context();ctx.industry='software services'
    monkeypatch.setattr(c,'fetch',lambda *a:b'<rss><channel><item><title>Malaysia software seasonal interest report</title><link>https://example.com/report</link></item></channel></rss>')
    assert c.trends(ctx)[0].basis == 'qualitative_news'


def test_all_five_module_vertical_slice(env,monkeypatch):
    client,factory,tx=env;bid=profile(client)
    comp=client.post('/api/bijaksense/competitors',json={'name':'Public test competitor','url':'https://example.com','public_access_confirmed':True}).json()
    fixtures={
        'news':[item()],
        'commodities':[item('commodities',basis='monthly_benchmark',data={'commodity':'rice','observations':[{'value':'1.1','currency':'USD','unit':'kg','original_value':'1100','original_unit':'($/mt)','observed_at':now().isoformat(),'location':'International benchmark'}]})],
        'weather':[item('weather',basis='forecast',data={'date':(now()+timedelta(days=1)).date().isoformat(),'latitude':3.139,'longitude':101.687,'risks':['rain']})],
        'trends':[item('trends',basis='measured_sector_proxy',data={'date':now().date().isoformat()})],
        'competitor':[item('competitors',basis='public_page_observation',data={'competitor_id':comp['id'],'kind':'public_page_observation','advertised_prices':[]})]
    }
    for name,items in fixtures.items():monkeypatch.setattr(c,name,lambda ctx,items=items:items)
    job=client.post('/api/bijaksense/refresh').json()['job'];assert jobs.tick()
    result=client.get('/api/bijaksense/jobs/'+job['id']).json()
    assert result['status']=='completed',result
    rows=client.get('/api/bijaksense/insights').json()['items']
    assert {r['category'] for r in rows}=={'supply_chain','commodities','weather','trends','competitors'}
    assert all(r['evidence'] and r['actions'] and r['business_id']==bid for r in rows)


def test_stale_publication_not_refreshed_into_fresh_evidence(env):
    client,factory,tx=env;bid=profile(client)
    with tx() as db:
        old=item(published_at=now()-timedelta(days=60))
        s=e.persist(db,bid,old);e.persist(db,bid,old)
        assert s.expires_at < now()
        assert retrieval.relevance(s,db.get(MerchantContext,bid)) is None


def test_recorded_sales_are_measured_with_sample_and_coverage_labels(env):
    client,factory,tx=env;bid=profile(client)
    with tx() as db:
        db.get(Business,bid).mode='fixture'
        party=Counterparty(business_id=bid,name='Synthetic buyer');db.add(party);db.flush()
        for n,days,amount,status,currency in [('old',40,10000,'issued','MYR'),('recent',7,12000,'issued','MYR'),('draft',8,999999,'draft','MYR'),('foreign',9,999999,'issued','USD')]:
            db.add(Invoice(business_id=bid,number=n,counterparty_id=party.id,total_minor=amount,status=status,currency=currency,issued_on=now().date()-timedelta(days=days),due_date=now().date()))
        db.flush()
        signal=e.internal_trend(db,bid)
        assert signal.data['change_pct']=='20.00'
        assert signal.data['current_count']==1 and signal.data['sample']
        assert signal.title.startswith('SAMPLE:') and 'not consumer demand' in signal.text


def test_forecast_supersession_keeps_history_but_not_old_alerts(env):
    client,factory,tx=env;bid=profile(client)
    with tx() as db:
        s=e.persist(db,bid,item('weather',basis='forecast',data={'date':'2026-10-17','latitude':3.139,'longitude':101.687,'risks':['rain']}))
        second=e.persist(db,bid,item('weather',basis='forecast',text='Updated dry forecast',data={'date':'2026-10-17','latitude':3.139,'longitude':101.687,'risks':[]}))
        assert s.expires_at<=now() and second.expires_at>now()


def test_disabled_context_not_scheduled_and_interrupted_job_recovered(env,monkeypatch):
    client,factory,tx=env;bid=profile(client)
    with tx() as db:
        db.get(MerchantContext,bid).enabled=False
        db.add(IngestionJob(business_id=bid,kind='refresh',bucket='old',status='running',started_at=now()-timedelta(minutes=30)))
    jobs.schedule(); assert jobs.claim() is None
    with factory() as db:
        row=db.scalar(select(IngestionJob))
        assert row.status=='failed' and 'No automatic paid retry' in row.result['error']


def test_unknown_commodity_header_never_becomes_fake_zero(monkeypatch):
    import io
    from openpyxl import Workbook
    workbook=Workbook();sheet=workbook.active;sheet.title='Monthly Prices'
    sheet.append(['Updated on October 02, 2026']);sheet.append([None,'Crude oil, Brent','Rice, Thai 5% ']);sheet.append([None,'($/bbl)','($/mt)']);sheet.append(['2026M08',80,'�']);sheet.append(['2026M09',90,1000])
    buffer=io.BytesIO();workbook.save(buffer)
    monkeypatch.setattr(c,'fetch',lambda *a:buffer.getvalue())
    rows=c.commodities(context())[0].data['observations']
    assert len(rows)==1 and Decimal(rows[0]['value'])==Decimal(1)


def test_news_metadata_normalization_does_not_duplicate_alert_evidence(env):
    client,factory,tx=env;bid=profile(client)
    with tx() as db:
        original=e.persist(db,bid,item(geography=['Malaysia']))
        normalized=e.persist(db,bid,item(geography=['Global'],data={'geographic_basis':'headline_mentions_only'}))
        assert original.id==normalized.id and normalized.geography==['Global']
        assert db.scalar(select(func.count()).select_from(MarketSignal))==1
