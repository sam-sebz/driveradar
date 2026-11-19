/** Runtime-validated API types (zod). If the backend shape changes, parsing fails loudly. */
import { z } from "zod";

export const tokenSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string(),
  expires_in: z.number(),
  role: z.enum(["student", "coordinator"]),
});
export type Tokens = z.infer<typeof tokenSchema>;

export const profileSchema = z.object({
  id: z.string(),
  email: z.string(),
  role: z.enum(["student", "coordinator"]),
  name: z.string().nullable(),
  branch: z.string().nullable(),
  batch: z.number().nullable(),
  cgpa: z.number().nullable(),
  pct_10: z.number().nullable(),
  pct_12: z.number().nullable(),
  backlogs: z.number().nullable(),
  skills: z.array(z.string()),
});
export type Profile = z.infer<typeof profileSchema>;
export type ProfileUpdate = Omit<Profile, "id" | "email" | "role">;

const nStr = z.string().nullable();
const nNum = z.number().nullable();

export const driveInfoSchema = z.object({
  company: nStr,
  role: nStr,
  location: nStr,
  ctc_lpa_min: nNum,
  ctc_lpa_max: nNum,
  stipend_per_month: nNum,
  deadline: nStr,
  joining_date: nStr,
  bond_years: nNum,
  bond_penalty_inr: nNum,
  min_cgpa: nNum,
  min_ug_percent: nNum,
  min_percent_10th: nNum,
  min_percent_12th: nNum,
  max_active_backlogs: nNum,
  eligible_branches: z.array(z.string()).nullable(),
  eligible_batch: z.array(z.number()).nullable(),
  required_skills: z.array(z.string()).nullable(),
  selection_process: z.array(z.string()).nullable(),
  notes: nStr,
});
export type DriveInfo = z.infer<typeof driveInfoSchema>;

export const DRIVE_STATUSES = ["saved", "applied", "shortlisted", "rejected", "selected"] as const;
export type DriveStatus = (typeof DRIVE_STATUSES)[number];
export type Eligibility = "eligible" | "not_eligible" | "unknown";

export const driveSchema = z.object({
  id: z.string(),
  info: driveInfoSchema,
  role_category: nStr,
  source_filename: nStr,
  extraction_provider: z.string(),
  created_at: z.string(),
  eligibility: z.enum(["eligible", "not_eligible", "unknown"]),
  eligibility_reasons: z.array(
    z.object({
      rule: z.string(),
      status: z.enum(["pass", "fail", "unknown", "not_specified"]),
      reason: z.string(),
    }),
  ),
  match_score: nNum,
  matched_skills: z.array(z.string()),
  missing_skills: z.array(z.string()),
  status: z.enum(DRIVE_STATUSES),
  closes_within_24h: z.boolean(),
  is_closed: z.boolean(),
});
export type Drive = z.infer<typeof driveSchema>;

export const driveListSchema = z.object({ drives: z.array(driveSchema) });

export const skillsAnalyticsSchema = z.object({
  total_drives: z.number(),
  top_skills: z.array(z.object({ skill: z.string(), count: z.number() })),
});
export type SkillsAnalytics = z.infer<typeof skillsAnalyticsSchema>;

export const summaryAnalyticsSchema = z.object({
  total_drives: z.number(),
  total_companies: z.number(),
  drives_by_role_category: z.array(z.object({ role_category: z.string(), count: z.number() })),
  median_ctc_lpa: nNum,
  drives_with_ctc: z.number(),
  drives_with_bond: z.number(),
});
export type SummaryAnalytics = z.infer<typeof summaryAnalyticsSchema>;

export const errorSchema = z.object({
  error: z.object({ code: z.string(), message: z.string() }),
});
