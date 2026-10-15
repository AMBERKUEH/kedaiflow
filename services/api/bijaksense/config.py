import os
from ..config import settings


def option(name, default=''):
    return os.getenv('BIJAKSENSE_' + name, default).strip()


def llm_key():
    return option('QWEN_API_KEY') or settings.groq_key


EMBEDDING_MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
CATEGORIES = ('supply_chain', 'commodities', 'weather', 'trends', 'competitors')
# No currency conversion without a dated FX observation. International benchmarks
# are explicitly proxies, never presented as Malaysian supplier quotations.
COMMODITIES = {
    'palm_oil': ('Palm oil', 'ingredients', ['palm oil', 'cooking oil', 'oil', 'minyak']),
    'rice': ('Rice, Thai 5%', 'ingredients', ['rice', 'beras']),
    'wheat': ('Wheat, US HRW', 'ingredients', ['wheat', 'flour', 'bread', 'tepung']),
    'sugar': ('Sugar, world', 'ingredients', ['sugar', 'gula', 'bakery']),
    'coffee': ('Coffee, Robusta', 'ingredients', ['coffee', 'kopi', 'cafe']),
    'cocoa': ('Cocoa', 'ingredients', ['cocoa', 'chocolate']),
    'rubber': ('Rubber, TSR20', 'materials', ['rubber', 'tyre', 'getah']),
    'aluminium': ('Aluminum', 'materials', ['aluminium', 'aluminum', 'metal']),
    'copper': ('Copper', 'materials', ['copper', 'wiring', 'electrical']),
    'crude_oil': ('Crude oil, Brent', 'transport', ['fuel', 'diesel', 'delivery', 'logistics']),
}
WORLD_BANK_URL = 'https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx'
DOSM_URL = 'https://storage.dosm.gov.my/iowrt/iowrt.csv'
