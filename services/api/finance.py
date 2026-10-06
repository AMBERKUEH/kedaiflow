from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP


def total_items(items):
    result = sum(int((Decimal(i['quantity']) * i['unit_price_minor']).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) for i in items)
    if not 0 < result <= 9000000000000:
        from .security import fail
        fail('TOTAL_OUT_OF_RANGE', 'Deal total exceeds supported monetary limits.', 422)
    return result


def forecast(opening, start, horizon, movements, buffer):
    """Integer sen; a missing baseline propagates as unknown, never zero."""
    daily = []
    balance = opening
    for n in range(horizon):
        day = start + timedelta(days=n)
        entries = [m for m in movements if m['date'] == day.isoformat()]
        inflow = sum(m['amount_minor'] for m in entries if m['amount_minor'] > 0)
        outflow = -sum(m['amount_minor'] for m in entries if m['amount_minor'] < 0)
        balance = None if balance is None else balance + inflow - outflow
        daily.append({'date': day.isoformat(), 'inflow_minor': inflow, 'outflow_minor': outflow, 'closing_minor': balance, 'movements': entries})
    known = [d for d in daily if d['closing_minor'] is not None]
    trough = min(known, key=lambda d: d['closing_minor']) if known else None
    end = (start + timedelta(days=horizon - 1)).isoformat()
    return {'daily': daily, 'trough_minor': trough['closing_minor'] if trough else None, 'trough_date': trough['date'] if trough else None, 'buffer_breach_dates': [d['date'] for d in known if d['closing_minor'] < buffer], 'beyond_horizon': [m for m in movements if m['date'] > end], 'calculation_version': 'daily_cash_v1', 'label': 'Forecast — assumptions, not available cash'}


def batch_cost(data):
    produced, sold, wasted = data['produced'], data['sold'], data['wasted']
    if sold + wasted > produced:
        raise ValueError('Sold plus wasted cannot exceed produced quantity')
    total = data['ingredient_minor'] + data['packaging_minor']
    unit = Decimal(total) / produced
    sold_cost = int((unit * sold).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    waste_cost = int((unit * wasted).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return {'total_cost_minor': total, 'unit_cost_minor_decimal': str(unit), 'revenue_minor': sold * data['price_minor'], 'sold_cost_minor': sold_cost, 'waste_cost_minor': waste_cost, 'inventory_minor': total - sold_cost - waste_cost, 'gross_margin_minor': sold * data['price_minor'] - sold_cost, 'contribution_minor': sold * data['price_minor'] - sold_cost - waste_cost, 'warning': 'Contribution before excluded overhead, tax and owner drawings. Not take-home profit.'}
