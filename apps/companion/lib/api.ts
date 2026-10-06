export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api/v1/' + path, {method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? {} : {'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID()}, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new ApiError(data.error?.message || data.detail?.[0]?.msg || 'Something went wrong. Please review your input and retry.', response.status);
  return data;
}
export async function upload(file: File) {
  const form = new FormData(); form.append('file', file);
  const response = await fetch('/api/v1/documents', {method:'POST', headers:{'Idempotency-Key':crypto.randomUUID()}, body: form});
  const data = await response.json();
  if (!response.ok) throw new ApiError(data.error?.message || 'Upload failed', response.status);
  return data;
}
export const money = (n: number | null | undefined) => n == null ? 'Not available' : new Intl.NumberFormat('en-MY', {style:'currency',currency:'MYR',maximumFractionDigits:2}).format(n / 100);
export const sen = (value: FormDataEntryValue | null) => {
  const text = String(value ?? '').trim();
  if (!/^\d+(\.\d{1,2})?$/.test(text)) throw new Error('Enter an amount with at most two decimal places.');
  const [whole, fraction = ''] = text.split('.');
  const result = Number(whole) * 100 + Number(fraction.padEnd(2,'0'));
  if (!Number.isSafeInteger(result) || result > 9000000000000) throw new Error('Amount is too large.');
  return result;
};
export const words = (s: string) => s.replaceAll('_', ' ');
export const dateLabel = (s: string) => new Date(s + (s.length === 10 ? 'T12:00:00' : '')).toLocaleDateString('en-MY', {day:'numeric', month:'short'});
export type Party = {id:string; name:string; kind:string; language:string; version:number};
export type Deal = {id:string; title:string; counterparty_id:string; total_minor:number; deposit_minor:number; due_date:string|null; delivery_date:string|null; status:string; version:number; confirmation_level:string; evidence_ids:string[]; terms:{items:{product:string; quantity:string; unit:string; unit_price_minor:number}[]; charges:string}};
export type Invoice = {id:string; number:string; counterparty_id:string; total_minor:number; outstanding_minor:number; status:string; direction:string; due_date:string; issued_on:string; version:number; payment_state:string; days_overdue:number; deal_id:string|null; disputed:boolean};
export type Receipt = {id:string; amount_minor:number; unapplied_minor:number; version:number; source:string; reference:string; booked_on:string; direction:string; category:string; status:string; account:string};
export type Case = {id:string; title:string; rule:string; record_id:string; amount_minor:number|null; explanation:string; status:string; version:number; reason:string};
export type Action = {id:string; kind:string; message:string; language:string; recipient_id:string; status:string; version:number; payload_digest:string; expires_at:string; outcome:string};
export type Evidence = {id:string; kind:string; text:string; filename:string|null; status:string; source:string; created_at:string; extraction:{candidate?:{quantity?:string; unit?:string; unit_price_minor?:number}; transcript?:string; translations?:Record<string,string>; warning?:string; questions?:string[]}};
export type Forecast = {buffer_minor?:number;daily:{date:string; inflow_minor:number; outflow_minor:number; closing_minor:number|null; movements:{label:string; basis:string; amount_minor:number}[]}[]; trough_minor:number|null; trough_date:string|null; buffer_breach_dates:string[]; coverage_warnings:string[]; beyond_horizon:{label:string; date:string; amount_minor:number}[]; baseline_revision:number};
export type Business = {id:string; name:string; mode:string; language:string; paused:boolean; opening_minor:number|null; opening_date:string|null; buffer_minor:number; revision:number};
export type Dashboard = {business:Business; today:string; actual_cash_minor:number|null; outstanding_minor:number; payable_minor:number; invoices:Invoice[]; receipts:Receipt[]; parties:Party[]; deals:Deal[]; cases:Case[]; actions:Action[]; evidence:Evidence[]; forecast:Forecast; source_label:string; as_of:string};
export type Me = {user:{id:string;name:string}; business:Business; role:string; action_mode:string};

