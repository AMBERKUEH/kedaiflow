"""Opt-in live, synthetic-profile evaluation. Never reads merchant ledger records.

python -m scripts.check_bijaksense --live
Uses public sources + one Qwen selection per synthetic merchant; saves private
evaluation DB/report under .local. Does not contact competitors or write websites.
"""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from services.api import db as database
from services.api.models import Base, Business, now
from services.api.bijaksense.models import MerchantContext, CompetitorProfile, IngestionJob, MarketSignal, MarketInsight
from services.api.bijaksense import jobs, connectors


def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    if not args.live:
        print('No external requests made. Pass --live to test public sources, local FAISS and Qwen with synthetic profiles.')
        return
    folder=Path('.local/flow-evaluation');folder.mkdir(parents=True,exist_ok=True)
    engine=database.make_engine('sqlite:///'+str((folder/(str(uuid4())+'.db')).resolve()))
    Base.metadata.create_all(engine)
    database.Session=sessionmaker(engine,expire_on_commit=False)
    # Within-run cache avoids downloading the same public workbook/feed for each
    # profile. This cache is not used for credentialed requests or across runs.
    original=connectors.fetch; cache={}
    def cached(url,limit=2_000_000):
        if 'apikey=' in url:return original(url,limit)
        if url not in cache:cache[url]=original(url,limit)
        return cache[url]
    connectors.fetch=cached
    profiles=[
      ('grocery retail','Kuala Lumpur',3.139,101.687,['rice','tomatoes'],['palm oil','fuel'],['rice','palm_oil'], 'https://99speedmart.com.my/press-release/'),
      ('construction','Klang',3.0449,101.4456,['copper','aluminium'],['copper','fuel'],['copper','aluminium'], 'https://www.mrdiy.com/zh/promotion?mode=ongoing'),
    ]
    report={'checked_at':now().isoformat(),'purpose':'Synthetic merchant profiles, real retrieved public evidence; no actual competitor relationship asserted','profiles':[]}
    for industry,location,lat,lon,products,materials,commodities,url in profiles:
        with jobs.transaction() as db:
            business=Business(name='FLOW evaluation: '+industry,mode='fixture');db.add(business);db.flush()
            bid=business.id
            db.add(MerchantContext(business_id=bid,industry=industry,location=location,latitude=lat,longitude=lon,products=products,materials=materials,markets=['malaysia'],commodities=commodities,cost_categories={},enabled=True))
            db.add(CompetitorProfile(business_id=bid,name='Public source evaluation (not a claimed competitor)',url=url,source_type='website',public_access_confirmed=True))
            job,_=jobs.enqueue(db,bid);jid=job.id
        jobs.tick()
        with database.Session() as db:
            job=db.get(IngestionJob,jid)
            insights=list(db.scalars(select(MarketInsight).where(MarketInsight.business_id==bid)))
            result={'industry':industry,'location':location,'status':job.status,'result':job.result,'insight_categories':sorted({i.category for i in insights}),'embedding_count':sum(bool(s.embedding) for s in db.scalars(select(MarketSignal).where(MarketSignal.business_id==bid)))}
            report['profiles'].append(result)
            print(json.dumps(result,ensure_ascii=True),flush=True)
    (folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Private evaluation report: .local/flow-evaluation/report.json')


if __name__=='__main__':run()
