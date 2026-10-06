-- Optional Supabase deployment hardening. Apply after 0001 using migration owner.

-- API/worker connections stay server-only. Never expose their database credentials.

BEGIN;

CREATE OR REPLACE FUNCTION public.kf_finance_member(bid text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT EXISTS (SELECT 1 FROM memberships WHERE business_id=bid AND user_id=auth.uid()::text AND active AND role IN ('owner','bookkeeper','accountant')) $$;
REVOKE ALL ON FUNCTION public.kf_finance_member(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.kf_finance_member(text) TO authenticated;

ALTER TABLE public.actions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.actions FROM anon, authenticated;

GRANT SELECT ON public.actions TO authenticated;

CREATE POLICY actions_finance_read ON public.actions FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.adjustments ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.adjustments FROM anon, authenticated;

GRANT SELECT ON public.adjustments TO authenticated;

CREATE POLICY adjustments_finance_read ON public.adjustments FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.audit ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.audit FROM anon, authenticated;

GRANT SELECT ON public.audit TO authenticated;

CREATE POLICY audit_finance_read ON public.audit FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.bind_codes ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.bind_codes FROM anon, authenticated;

ALTER TABLE public.bindings ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.bindings FROM anon, authenticated;

ALTER TABLE public.businesses ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.businesses FROM anon, authenticated;

GRANT SELECT ON public.businesses TO authenticated;

CREATE POLICY businesses_finance_read ON public.businesses FOR SELECT TO authenticated USING (public.kf_finance_member(id));

ALTER TABLE public.callbacks ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.callbacks FROM anon, authenticated;

ALTER TABLE public.cases ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.cases FROM anon, authenticated;

GRANT SELECT ON public.cases TO authenticated;

CREATE POLICY cases_finance_read ON public.cases FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.claims FROM anon, authenticated;

GRANT SELECT ON public.claims TO authenticated;

CREATE POLICY claims_finance_read ON public.claims FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.counterparties ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.counterparties FROM anon, authenticated;

GRANT SELECT ON public.counterparties TO authenticated;

CREATE POLICY counterparties_finance_read ON public.counterparties FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.deal_versions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.deal_versions FROM anon, authenticated;

GRANT SELECT ON public.deal_versions TO authenticated;

CREATE POLICY deal_versions_finance_read ON public.deal_versions FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.deliveries ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.deliveries FROM anon, authenticated;

GRANT SELECT ON public.deliveries TO authenticated;

CREATE POLICY deliveries_finance_read ON public.deliveries FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.evidence ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.evidence FROM anon, authenticated;

ALTER TABLE public.identities ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.identities FROM anon, authenticated;

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.jobs FROM anon, authenticated;

ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.memberships FROM anon, authenticated;

ALTER TABLE public.operations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.operations FROM anon, authenticated;

ALTER TABLE public.promises ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.promises FROM anon, authenticated;

GRANT SELECT ON public.promises TO authenticated;

CREATE POLICY promises_finance_read ON public.promises FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.receipts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.receipts FROM anon, authenticated;

GRANT SELECT ON public.receipts TO authenticated;

CREATE POLICY receipts_finance_read ON public.receipts FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.recipient_invites ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.recipient_invites FROM anon, authenticated;

ALTER TABLE public.scenarios ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.scenarios FROM anon, authenticated;

GRANT SELECT ON public.scenarios TO authenticated;

CREATE POLICY scenarios_finance_read ON public.scenarios FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.sessions FROM anon, authenticated;

ALTER TABLE public.supplements ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.supplements FROM anon, authenticated;

ALTER TABLE public.telegram_inbox ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.telegram_inbox FROM anon, authenticated;

ALTER TABLE public.deals ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.deals FROM anon, authenticated;

GRANT SELECT ON public.deals TO authenticated;

CREATE POLICY deals_finance_read ON public.deals FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.invoices FROM anon, authenticated;

GRANT SELECT ON public.invoices TO authenticated;

CREATE POLICY invoices_finance_read ON public.invoices FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

ALTER TABLE public.allocations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.allocations FROM anon, authenticated;

GRANT SELECT ON public.allocations TO authenticated;

CREATE POLICY allocations_finance_read ON public.allocations FOR SELECT TO authenticated USING (public.kf_finance_member(business_id));

COMMIT;