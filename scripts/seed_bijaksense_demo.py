"""Opt-in example profile only. Never overwrites a profile or changes a ledger."""
from sqlalchemy import select
from services.api.db import migrate
from services.api.models import Business
from services.api.seed import DEMO_EMAIL
from services.api.models import Identity, Membership
from services.api.bijaksense.models import MerchantContext, CompetitorProfile
from services.api.bijaksense.jobs import transaction, enqueue


if __name__ == '__main__':
    migrate()
    with transaction() as db:
        user = db.scalar(select(Identity).where(Identity.email == DEMO_EMAIL))
        business = db.scalar(select(Business).join(Membership, Membership.business_id == Business.id).where(Membership.user_id == user.id, Business.mode == 'fixture')) if user else None
        if not business:
            raise SystemExit('No synthetic demo business exists. Run the normal development seed first.')
        if db.get(MerchantContext, business.id):
            raise SystemExit('Existing intelligence profile preserved; no change made.')
        db.add(MerchantContext(business_id=business.id, industry='grocery retail', location='Kuala Lumpur', latitude=3.139, longitude=101.687, products=['rice','tomatoes'], materials=['palm oil','fuel'], markets=['malaysia'], commodities=['rice','palm_oil'], cost_categories={'rice':'ingredients','palm_oil':'cooking oil'}, enabled=True))
        db.add(CompetitorProfile(business_id=business.id, name='Sample watchlist: 99 Speedmart', url='https://99speedmart.com.my/press-release/', source_type='website', public_access_confirmed=True))
        enqueue(db, business.id)
    print('Sample Kuala Lumpur grocery profile queued for real public-source refresh. No merchant financial records were changed.')
