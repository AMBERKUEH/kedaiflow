"""Generate reproducible API and initial PostgreSQL migration from typed source."""
import json
from pathlib import Path
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from services.api.main import app
from services.api.models import Base

root = Path(__file__).resolve().parents[1]
target = root / 'packages' / 'contracts'
target.mkdir(parents=True, exist_ok=True)
(target / 'openapi.json').write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False), encoding='utf-8')
ddl = ['-- KedaiFlow 0001: initial schema. Generated from services/api/models.py.', 'BEGIN;']
for table in Base.metadata.sorted_tables:
    ddl.append(str(CreateTable(table).compile(dialect=postgresql.dialect())) + ';')
    for index in sorted(table.indexes, key=lambda i: i.name):
        ddl.append(str(CreateIndex(index).compile(dialect=postgresql.dialect())) + ';')
ddl += ['CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());', "INSERT INTO schema_migrations(version) VALUES ('0001');", 'COMMIT;']
(root / 'database' / 'migrations' / '0001_initial.sql').write_text('\n\n'.join(ddl), encoding='utf-8')
# Supabase public clients have no direct write path to domain tables. Authenticated
# reads are scoped by membership; roles also restrict financial table access.
rls = ['-- Optional Supabase deployment hardening. Apply after 0001 using migration owner.', '-- API/worker connections stay server-only. Never expose their database credentials.', 'BEGIN;', '''CREATE OR REPLACE FUNCTION public.kf_finance_member(bid text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT EXISTS (SELECT 1 FROM memberships WHERE business_id=bid AND user_id=auth.uid()::text AND active AND role IN ('owner','bookkeeper','accountant')) $$;
REVOKE ALL ON FUNCTION public.kf_finance_member(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.kf_finance_member(text) TO authenticated;''']
private = {'identities','sessions','memberships','operations','telegram_inbox','bind_codes','bindings','callbacks','recipient_invites','jobs','evidence','supplements'}
for table in Base.metadata.sorted_tables:
    name = table.name
    rls += [f'ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY;', f'REVOKE ALL ON public.{name} FROM anon, authenticated;']
    if name not in private and ('business_id' in table.c or name=='businesses'):
        key = 'id' if name=='businesses' else 'business_id'
        rls += [f'GRANT SELECT ON public.{name} TO authenticated;', f'CREATE POLICY {name}_finance_read ON public.{name} FOR SELECT TO authenticated USING (public.kf_finance_member({key}));']
rls += ['COMMIT;']
(root / 'database' / 'migrations' / '0002_supabase_rls.sql').write_text('\n\n'.join(rls), encoding='utf-8')
print('Generated OpenAPI and PostgreSQL/Supabase migrations.')
