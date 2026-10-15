"""Merchant-scoped BM25 + FAISS reciprocal rank fusion over text only."""
import math
import re
from collections import Counter
from functools import lru_cache
from ..models import now
from ..security import aware
from .config import EMBEDDING_MODEL, option


def tokens(text):
    return re.findall(r'\w+', text.lower())


@lru_cache(maxsize=1)
def encoder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL, device='cpu', local_files_only=True, trust_remote_code=False)


def relevance(signal, context):
    if aware(signal.expires_at) <= now():
        return None
    if signal.category == 'weather':
        if signal.data.get('latitude') != context.latitude or signal.data.get('longitude') != context.longitude or signal.data.get('date', '') < now().astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kuala_Lumpur')).date().isoformat():
            return None
        return {'matched': [context.location], 'reason': 'Forecast for merchant coordinates'}
    if signal.category == 'commodities':
        key = signal.data.get('commodity')
        return {'matched': [key], 'reason': 'Merchant-selected input benchmark'} if key in context.commodities else None
    if signal.category == 'competitors':
        return {'matched': ['merchant-selected competitor'], 'reason': 'Public source chosen by merchant'}
    if signal.basis == 'measured_merchant_sales':
        return {'matched': ['recorded invoices'], 'reason': 'Merchant-specific financial records'}
    text = (signal.title + ' ' + signal.text).lower()
    terms = context.products + context.materials + [context.industry]
    aliases = {'fuel': ['diesel', 'petrol', 'crude oil'], 'tomatoes': ['tomato'], 'flour': ['wheat'], 'cooking oil': ['palm oil'], 'aluminium': ['aluminum']}
    matched = [term for term in terms if term and any(re.search(r'(?<!\w)' + re.escape(word.lower()) + r'(?!\w)', text) for word in [term] + aliases.get(term.lower(), []))]
    geo = [g.lower() for g in signal.geography]
    markets = [m.lower() for m in context.markets] + ['malaysia', context.location.lower()]
    if geo and 'global' not in geo and not any(g in markets for g in geo):
        return None
    if signal.basis == 'measured_sector_proxy':
        if not any(t in context.industry.lower() for t in ('retail', 'wholesale', 'trade', 'grocery', 'kedai')):
            return None
        matched.append('Malaysia wholesale/retail sector')
    if signal.category == 'supply_chain' and context.products and re.search(r'\b(logistics|ports?|shipping|freight|supply chain|tariffs?)\b', text):
        matched.append('physical-goods supply chain (indirect exposure)')
    return {'matched': matched, 'reason': 'Profile terms and geographic coverage matched; exposure requires merchant verification'} if matched else None


def hybrid(signals, context, limit=40):
    rows = [(s, relevance(s, context)) for s in signals]
    rows = [(s, r) for s, r in rows if r]
    if not rows:
        return [], 'no_relevant_evidence'
    query = ' '.join([context.industry, context.location] + context.products + context.materials + context.commodities)
    query_terms = set(tokens(query))
    docs = [Counter(tokens(s.title + ' ' + s.text)) for s, _ in rows]
    avg = sum(sum(d.values()) for d in docs) / len(docs) or 1
    df = Counter(t for d in docs for t in d)
    scores = []
    for i, doc in enumerate(docs):
        length = sum(doc.values())
        score = sum(math.log(1 + (len(docs)-df[t]+.5)/(df[t]+.5)) * (doc[t]*2.2)/(doc[t]+1.2*(.25+.75*length/avg)) for t in query_terms if doc[t])
        scores.append((i, score))
    lexical = sorted(scores, key=lambda pair: pair[1], reverse=True)
    fused = {i: 1/(60+rank) for rank, (i, _) in enumerate(lexical, 1)}
    mode = 'bm25_only_embeddings_unavailable'
    if option('EMBEDDINGS_ENABLED', 'true') == 'true':
        try:
            import faiss
            import numpy as np
            model = encoder()
            pending = [(i, s) for i, (s, _) in enumerate(rows) if not s.embedding or s.embedding_model != EMBEDDING_MODEL]
            if pending:
                vectors = model.encode([s.title + '\n' + s.text for _, s in pending], normalize_embeddings=True, show_progress_bar=False)
                for (_, s), vector in zip(pending, vectors):
                    s.embedding, s.embedding_model = vector.tolist(), EMBEDDING_MODEL
            vectors = np.asarray([s.embedding for s, _ in rows], dtype='float32')
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            _, ids = index.search(model.encode([query], normalize_embeddings=True, show_progress_bar=False), len(rows))
            for rank, i in enumerate(ids[0], 1):
                fused[int(i)] += 1/(60+rank)
            mode = 'bm25_sentence_transformers_faiss_rrf'
        except (ImportError, OSError, ValueError, RuntimeError):
            pass
    ranked = sorted(range(len(rows)), key=lambda i: fused[i], reverse=True)
    # Guarantee available categories receive representation before top-k truncation.
    chosen, seen = [], set()
    for i in ranked:
        category = rows[i][0].category
        if category not in seen:
            chosen.append(i)
            seen.add(category)
    chosen += [i for i in ranked if i not in chosen]
    return [(rows[i][0], {**rows[i][1], 'retrieval_score': round(fused[i], 5)}) for i in chosen[:limit]], mode
