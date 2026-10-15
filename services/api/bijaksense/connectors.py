"""Bounded public data readers. External content is evidence, never instructions."""
import calendar
import csv
import html
import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlencode
from urllib.robotparser import RobotFileParser
from defusedxml import ElementTree
from pydantic import Field
from .schemas import Model
from .config import COMMODITIES, DOSM_URL, WORLD_BANK_URL, option

UTC = timezone.utc
AGENT = 'BijakSense/1.0 (+public-market-research; respects robots.txt)'


class Unavailable(Exception):
    """Safe operator-facing failure. Never include request headers or credentials."""


def public_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443) or p.fragment:
        raise Unavailable('Use a canonical public HTTPS URL without credentials, fragments or custom ports.')
    if len(url) > 2000:
        raise Unavailable('Source URL is too long.')
    return p


class PublicHTTPS(http.client.HTTPSConnection):
    def connect(self):
        # Pin the vetted resolved address for this connection. Validating DNS and
        # subsequently letting a different client resolve again permits rebinding.
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise Unavailable('Private or non-public network destinations are not allowed.')
        raw = socket.create_connection((addresses[0][4][0], 443), timeout=self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def fetch(url, limit=2_000_000):
    p = public_url(url)
    conn = PublicHTTPS(p.hostname, timeout=20, context=ssl.create_default_context())
    try:
        conn.request('GET', (p.path or '/') + ('?' + p.query if p.query else ''), headers={'User-Agent': AGENT, 'Accept-Encoding': 'identity'})
        response = conn.getresponse()
        if response.status == 404:
            raise Unavailable('Source not found (404).')
        if response.status != 200:
            raise Unavailable(f'Source unavailable (HTTP {response.status}); redirects and access controls are not bypassed.')
        content = response.read(limit + 1)
        if len(content) > limit:
            raise Unavailable('Source exceeds the permitted download size.')
        return content
    except (OSError, http.client.HTTPException) as exc:
        raise Unavailable('Source connection failed or timed out.') from exc
    finally:
        conn.close()


def date_time(value):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        try:
            d = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


def clean(value, length=1500):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', str(value)))).strip()[:length]


class EvidenceItem(Model):
    category: str
    title: str = Field(max_length=500)
    text: str = Field(max_length=6000)
    url: str
    provider: str
    reliability: str
    basis: str
    published_at: datetime | None = None
    geography: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    ttl_hours: int = 168


def weather(context):
    if context.latitude is None or context.longitude is None:
        raise Unavailable('Add your merchant coordinates to retrieve a local forecast.')
    key = option('OPEN_METEO_API_KEY')
    host = 'customer-api.open-meteo.com' if key else 'api.open-meteo.com'
    params = dict(latitude=context.latitude, longitude=context.longitude, daily='temperature_2m_max,precipitation_sum,precipitation_probability_max,wind_speed_10m_max', timezone='Asia/Kuala_Lumpur', forecast_days=7)
    citation = 'https://' + host + '/v1/forecast?' + urlencode(params)
    if key:
        params['apikey'] = key
    body = json.loads(fetch('https://' + host + '/v1/forecast?' + urlencode(params)))
    daily, units = body['daily'], body['daily_units']
    if units.get('precipitation_sum') != 'mm' or units.get('temperature_2m_max') != '°C' or units.get('wind_speed_10m_max') != 'km/h':
        raise Unavailable('Weather units changed; forecast requires review.')
    result = []
    for i, day in enumerate(daily['time']):
        values = {key: daily[key][i] for key in ('temperature_2m_max', 'precipitation_sum', 'precipitation_probability_max', 'wind_speed_10m_max')}
        if any(v is None for v in values.values()):
            continue
        risks = []
        if values['precipitation_sum'] >= 20 or values['precipitation_probability_max'] >= 80:
            risks.append('rain')
        if values['temperature_2m_max'] >= 35:
            risks.append('heat')
        if values['wind_speed_10m_max'] >= 40:
            risks.append('wind')
        result.append(EvidenceItem(category='weather', title=f'{context.location}: forecast for {day}', text=f"Forecast: {values['precipitation_sum']} mm rain, {values['precipitation_probability_max']}% rain probability, maximum {values['temperature_2m_max']} °C, wind {values['wind_speed_10m_max']} km/h. This is a forecast, not a confirmed disruption.", url=citation, provider='Open-Meteo', reliability='forecast_model', basis='forecast', geography=[context.location], data={**values, 'date': day, 'risks': risks, 'latitude': context.latitude, 'longitude': context.longitude, 'units': units}, ttl_hours=12))
    return result


def rss_items(content):
    root = ElementTree.fromstring(content)
    items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
    result = []
    for node in items[:40]:
        def value(tag):
            el = node.find(tag)
            if el is None:
                el = node.find('{http://www.w3.org/2005/Atom}' + tag)
            return (el.text or el.attrib.get('href', '')) if el is not None else ''
        url = value('link')
        try:
            public_url(url)
        except (Unavailable, ValueError):
            continue
        result.append({'title': clean(value('title'), 500), 'url': url, 'published_at': date_time(value('pubDate') or value('published') or value('updated'))})
    return result


def news(context):
    # Feed contains headlines and original publisher attribution, no article-body
    # scraping, paywall bypass or fabricated summary. Headline is a reported signal.
    terms = 'Malaysia (supply chain OR logistics OR shortage OR port OR tariff OR export ban) when:7d'
    url = option('NEWS_RSS_URL') or 'https://news.google.com/rss/search?' + urlencode({'q': terms, 'hl': 'en-MY', 'gl': 'MY', 'ceid': 'MY:en'})
    result = []
    for item in rss_items(fetch(url)):
        if item['published_at'] and item['published_at'] > datetime.now(UTC) + timedelta(hours=2):
            continue
        geography = ['Global'] if re.search(r'\bglobal\b', item['title'], re.I) else [country for country in ('Malaysia','Singapore','Thailand','Indonesia','India','China','Russia','Australia','Vietnam') if re.search(r'\b' + country + r'\b', item['title'], re.I)]
        result.append(EvidenceItem(category='supply_chain', **item, text=item['title'], provider='Public news RSS', reliability='reported_unverified', basis='qualitative_news', geography=geography, tags=['logistics', 'trade'], data={'discovery_feed': url, 'search_scope': 'Malaysia', 'geographic_basis': 'headline_mentions_only' if geography else 'not_established', 'conflict_policy': 'Reports are separate claims. Verify with supplier; no consensus is inferred.'}))
    return result


def normalize_price(value, unit):
    price = Decimal(str(value))
    if not price.is_finite() or price <= 0:
        raise ValueError('Price must be positive and finite')
    units = {'($/mt)': ('USD', 'kg', Decimal('0.001')), '($/kg)': ('USD', 'kg', Decimal(1)), '($/bbl)': ('USD', 'barrel', Decimal(1)), '(cents/kg)': ('USD', 'kg', Decimal('0.01'))}
    if unit not in units:
        raise ValueError('Unknown commodity unit; no conversion performed')
    currency, normalized_unit, factor = units[unit]
    return price * factor, currency, normalized_unit


def commodities(context):
    from openpyxl import load_workbook
    import zipfile
    if not context.commodities:
        raise Unavailable('Choose commodity benchmarks in the merchant profile. Unselected local products have no proxy price.')
    url = option('WORLD_BANK_URL', WORLD_BANK_URL)
    raw = fetch(url, 8_000_000)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 80_000_000:
            raise Unavailable('Commodity workbook is unexpectedly large.')
    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    try:
        rows = list(workbook['Monthly Prices'].values)
    finally:
        workbook.close()
    header_index = next(i for i, row in enumerate(rows[:15]) if 'Crude oil, Brent' in row)
    headers = tuple(str(v).strip().removesuffix(' **').strip() if v else '' for v in rows[header_index])
    units = rows[header_index + 1]
    published = None
    for row in rows[:header_index]:
        for cell in row:
            match = re.search(r'Updated on (.+)', str(cell))
            if match:
                for fmt in ('%B %d, %Y', '%b %d, %Y'):
                    try:
                        published = datetime.strptime(match[1].strip(), fmt).replace(tzinfo=UTC)
                    except ValueError:
                        pass
    result = []
    for key in context.commodities:
        label = COMMODITIES[key][0]
        if label not in headers:
            continue
        col = headers.index(label)
        observations = []
        for row in rows[header_index + 2:]:
            if not isinstance(row[0], str) or not re.fullmatch(r'\d{4}M\d{2}', row[0]) or row[col] in (None, '..', '…'):
                continue
            year, month = int(row[0][:4]), int(row[0][-2:])
            observed = datetime(year, month, calendar.monthrange(year, month)[1], tzinfo=UTC)
            if observed > datetime.now(UTC):
                continue
            try:
                Decimal(str(row[col]))
            except Exception:
                continue  # Historical missing-value markers are not zero prices.
            value, currency, unit = normalize_price(row[col], units[col])
            observations.append({'value': str(value), 'currency': currency, 'unit': unit, 'original_value': str(row[col]), 'original_unit': units[col], 'observed_at': observed.isoformat(), 'location': 'International benchmark'})
        observations = observations[-25:]
        if observations:
            latest = observations[-1]
            result.append(EvidenceItem(category='commodities', title=f'{label}: monthly benchmark', text=f"{label}: {latest['value']} {latest['currency']}/{latest['unit']} for month ending {latest['observed_at'][:10]}. International proxy; not a Malaysian supplier quote or today's spot price.", url=url, provider='World Bank Pink Sheet', reliability='official_statistics', basis='monthly_benchmark', published_at=published, geography=['Global'], tags=COMMODITIES[key][2], data={'commodity': key, 'observations': observations, 'cost_category': context.cost_categories.get(key, COMMODITIES[key][1]), 'is_proxy': True}, ttl_hours=24*45))
    return result


def trends(context):
    if not any(t in context.industry.lower() for t in ('retail', 'wholesale', 'trade', 'grocery', 'kedai')):
        # Do not stretch a retail statistic to an unrelated industry. Public
        # industry reporting remains qualitative; internal measurements are separate.
        terms = ' '.join(re.findall(r'[\w]+', context.industry + ' ' + ' '.join(context.products[:3])))
        url = 'https://news.google.com/rss/search?' + urlencode({'q': f'Malaysia {terms} (consumer OR demand OR seasonal OR Ramadan) when:30d', 'hl': 'en-MY', 'gl': 'MY', 'ceid': 'MY:en'})
        return [EvidenceItem(category='trends', **row, text=row['title'], provider='Public industry news RSS', reliability='reported_unverified', basis='qualitative_news', geography=['Malaysia'], tags=context.products, data={'discovery_feed': url, 'limitation': 'Qualitative industry reporting, not measured demand.'}, ttl_hours=24*30) for row in rss_items(fetch(url))]
    rows = list(csv.DictReader(io.StringIO(fetch(DOSM_URL).decode('utf-8-sig'))))
    rows = sorted((r for r in rows if r['series'] == 'abs' and r['date'] <= datetime.now(UTC).strftime('%Y-%m-%d')), key=lambda r: r['date'])
    if len(rows) < 13:
        raise Unavailable('Insufficient DOSM history for a comparable change.')
    latest, prior, annual = rows[-1], rows[-2], rows[-13]
    # Value and volume are different measures. Neither is a merchant demand claim.
    data = {'date': latest['date'], 'sales_myr_million': str(Decimal(latest['sales'])), 'sales_mom_pct': percentage(latest['sales'], prior['sales']), 'sales_yoy_pct': percentage(latest['sales'], annual['sales']), 'volume_yoy_pct': percentage(latest['volume'], annual['volume']), 'scope': 'Malaysia wholesale and retail trade aggregate', 'seasonality': 'Year-on-year comparison; not a forecast or causal attribution'}
    return [EvidenceItem(category='trends', title='Malaysia distributive trade: measured sector signal', text=f"DOSM wholesale/retail trade sales value changed {data['sales_yoy_pct']}% year-on-year for {latest['date'][:7]}; volume index changed {data['volume_yoy_pct']}%. National sector proxy, not proof that demand for your products increased.", url='https://open.dosm.gov.my/data-catalogue/iowrt', provider='DOSM (CC BY 4.0)', reliability='official_statistics', basis='measured_sector_proxy', geography=['Malaysia'], tags=['retail', 'wholesale', 'trade'], data={**data, 'download_url': DOSM_URL}, ttl_hours=24*100)]


def percentage(current, previous):
    a, b = Decimal(str(current)), Decimal(str(previous))
    if not a.is_finite() or not b.is_finite() or b <= 0:
        return None
    return str(((a-b)/b*100).quantize(Decimal('0.01')))


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.title_mode = False
        self.title = ''
        self.parts = []
        self.json_mode = False
        self.json_parts = []
        self.documents = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'footer'):
            self.hidden += 1
        if tag == 'title':
            self.title_mode = True
        if tag == 'script' and dict(attrs).get('type') == 'application/ld+json':
            self.json_mode, self.json_parts = True, []

    def handle_endtag(self, tag):
        if tag == 'script' and self.json_mode:
            try:
                self.documents.append(json.loads(''.join(self.json_parts)))
            except ValueError:
                pass
            self.json_mode = False
        if tag in ('script', 'style', 'nav', 'footer'):
            self.hidden = max(0, self.hidden - 1)
        if tag == 'title':
            self.title_mode = False

    def handle_data(self, text):
        if self.json_mode:
            self.json_parts.append(text)
        if self.title_mode:
            self.title += text
        if not self.hidden:
            self.parts.append(text)


def advertised_offers(documents):
    offers = []
    def walk(node, product='', depth=0):
        if depth > 15 or len(offers) >= 20:
            return
        if isinstance(node, list):
            for item in node[:100]:
                walk(item, product, depth+1)
        elif isinstance(node, dict):
            product = str(node.get('name', product))[:200]
            if node.get('@type') == 'Offer' and 'price' in node and re.fullmatch('[A-Z]{3}', str(node.get('priceCurrency', ''))):
                try:
                    price = Decimal(str(node['price']))
                    if price.is_finite() and price >= 0:
                        offers.append({'product': product, 'price': str(price), 'currency': node['priceCurrency'], 'basis': 'publicly_advertised_not_checkout_verified'})
                except Exception:
                    pass
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value, product, depth+1)
    walk(documents)
    return offers


def competitor(profile):
    if not profile.public_access_confirmed:
        raise Unavailable('Public-source authorization has not been confirmed.')
    p = public_url(profile.url)
    robot_url = f'https://{p.hostname}/robots.txt'
    try:
        robots = fetch(robot_url, 500_000).decode('utf-8', errors='replace')
    except Unavailable as exc:
        if '404' not in str(exc):
            raise Unavailable('Could not verify robots.txt permission; source was not fetched.') from exc
        robots = ''
    parser = RobotFileParser()
    parser.parse(robots.splitlines())
    if not parser.can_fetch('BijakSense', profile.url):
        raise Unavailable('robots.txt disallows access to this source.')
    raw = fetch(profile.url)
    if profile.source_type == 'rss':
        return [EvidenceItem(category='competitors', **item, text=item['title'], provider=profile.name, reliability='competitor_self_report', basis='public_announcement', data={'competitor_id': profile.id, 'kind': mention_kind(item['title']), 'advertised_prices': []}) for item in rss_items(raw)]
    page = PageParser()
    page.feed(raw.decode('utf-8', errors='replace'))
    snippet = clean(' '.join(page.parts), 2500)
    if not snippet:
        raise Unavailable('No public text available; JavaScript rendering, sign-in and access controls are not bypassed.')
    prices = advertised_offers(page.documents)
    kind = 'advertised_price' if prices else mention_kind(snippet)
    return [EvidenceItem(category='competitors', title=clean(page.title or profile.name, 500), text=snippet, url=profile.url, provider=profile.name, reliability='competitor_self_report', basis='public_page_observation', data={'competitor_id': profile.id, 'kind': kind, 'advertised_prices': prices, 'note': 'Observed page content; a first observation is not evidence of a new launch or price change.'})]


def mention_kind(text):
    if re.search(r'\b(launch(?:es|ed)?|new product|introducing)\b', text, re.I):
        return 'product_launch_mention'
    if re.search(r'\b(promotion|discount|buy one|buy 1|sale|promosi)\b', text, re.I):
        return 'promotion_mention'
    return 'public_announcement'
