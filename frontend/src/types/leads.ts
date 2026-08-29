export type LeadSource = {
  source_uid: string; name: string; type: string; enabled: boolean; configured: boolean;
  bulk_support: boolean; query_support: boolean; geo_support: string; credentials_required: boolean;
  freshness: string; last_run?: string; last_success?: string; terms_status: string;
  storage_policy: string; rate_limit: string; status: string; status_detail?: string;
};

export type LeadControl = {
  workbook: { available: boolean; status: string; active_command_source: string; placement: string; filename?: string; sheet_counts: Record<string, number>; query_matrix_rows: number; enabled_query_jobs: number; errors: string[] };
  active_command_source: string;
  query_matrix_rows: number;
  enabled_query_jobs: number;
  segments: { category_id: string; name: string; tier: number; buyer_type: string; terms: string[] }[];
  keywords: { set: string; count: number; languages: string[] };
  governorates: { id: string; name: string; name_ar: string; bbox: number[]; density: string }[];
  country: { code: string; name: string; bbox: number[]; polygon: number[][] };
  run_modes: string[];
};

export type LeadRunRequest = {
  name: string; mode: string; sources: string[]; governorates: string[]; segments: string[];
  keyword_set: "approved" | "custom"; keywords: string[]; dry_run: boolean; execute: boolean;
  adaptive_tiling: boolean; max_records_per_job?: number; source_options: Record<string, unknown>;
};

export type LeadRunPlan = {
  dry_run: true; enabled_sources: string[]; governorates: string[]; segments: string[];
  keyword_count: number; planned_jobs: number; missing_credentials: string[]; warnings: string[];
};

export type LeadJob = {
  job_uid: string; source_uid: string; governorate?: string; category?: string; status: string;
  processed: number; found: number; unique_count: number; duplicates: number; error?: string;
};

export type LeadRun = {
  dry_run: false; run_uid: string; name: string; mode: string; sources: string[]; geography: Record<string, unknown>;
  segments: string[]; keywords: string[]; status: string; planned_jobs: number; processed: number;
  found: number; unique_count: number; duplicates: number; errors: number; current_source?: string;
  current_governorate?: string; current_category?: string; warnings: string[]; progress_percent: number;
  started_at?: string; completed_at?: string; created_at: string; jobs?: LeadJob[];
};

export type LeadSummary = {
  lead_uid: string; business: string; category?: string; fit_class: string; governorate?: string;
  city?: string; phone?: string; website?: string; source: string; score: number;
  freshness: string; verification: string;
};

export type Page<T> = { items: T[]; total: number; offset: number; limit: number };
export type LeadStats = { total_leads: number; classes: Record<"A+" | "A" | "B" | "C", number>; active_runs: number; sources: number; last_run?: string; last_run_status?: string; errors: number };

