import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request, setTokens } from "./client";
import {
  driveListSchema,
  driveSchema,
  profileSchema,
  skillsAnalyticsSchema,
  summaryAnalyticsSchema,
  tokenSchema,
  type Drive,
  type DriveInfo,
  type DriveStatus,
  type ProfileUpdate,
} from "./schemas";
import { z } from "zod";

export interface Credentials {
  email: string;
  password: string;
}

export function useLogin() {
  return useMutation({
    mutationFn: (c: Credentials) =>
      request("/auth/login", tokenSchema, { method: "POST", json: c, auth: false }),
    onSuccess: setTokens,
  });
}

export function useSignup() {
  return useMutation({
    mutationFn: (c: Credentials & { name?: string }) =>
      request("/auth/signup", tokenSchema, { method: "POST", json: c, auth: false }),
    onSuccess: setTokens,
  });
}

export function useProfile(enabled = true) {
  return useQuery({
    queryKey: ["profile"],
    queryFn: () => request("/me/profile", profileSchema),
    enabled,
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: ProfileUpdate) =>
      request("/me/profile", profileSchema, { method: "PUT", json: p }),
    onSuccess: (profile) => {
      qc.setQueryData(["profile"], profile);
      // Eligibility and match scores were recomputed on the server.
      void qc.invalidateQueries({ queryKey: ["drives"] });
    },
  });
}

export interface DriveFilters {
  status?: DriveStatus | "";
  eligibility?: string;
  closingSoon?: boolean;
}

export function useDrives(filters: DriveFilters = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.eligibility) params.set("eligibility", filters.eligibility);
  if (filters.closingSoon) params.set("closing_soon", "true");
  const qs = params.toString();
  return useQuery({
    queryKey: ["drives", qs],
    queryFn: async () => (await request(`/drives${qs ? `?${qs}` : ""}`, driveListSchema)).drives,
  });
}

export function useDrive(id: string) {
  return useQuery({
    queryKey: ["drives", "one", id],
    queryFn: () => request(`/drives/${id}`, driveSchema),
  });
}

export function useUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { file?: File; text?: string }) => {
      const form = new FormData();
      if (input.file) form.append("file", input.file);
      else form.append("text", input.text ?? "");
      return request("/drives/upload", z.object({ drives: z.array(driveSchema) }), {
        method: "POST",
        form,
      });
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["drives"] }),
  });
}

function useDriveMutation<V>(fn: (vars: V) => Promise<Drive>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (drive) => {
      qc.setQueryData(["drives", "one", drive.id], drive);
      void qc.invalidateQueries({ queryKey: ["drives"] });
    },
  });
}

export function useUpdateStatus() {
  return useDriveMutation((v: { id: string; status: DriveStatus }) =>
    request(`/drives/${v.id}/status`, driveSchema, {
      method: "PATCH",
      json: { status: v.status },
    }),
  );
}

export function useEditDrive() {
  return useDriveMutation((v: { id: string; info: DriveInfo }) =>
    request(`/drives/${v.id}`, driveSchema, { method: "PATCH", json: v.info }),
  );
}

export function useDeleteDrive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => request(`/drives/${id}`, null, { method: "DELETE" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["drives"] }),
  });
}

export function useAnalytics() {
  const skills = useQuery({
    queryKey: ["analytics", "skills"],
    queryFn: () => request("/analytics/skills", skillsAnalyticsSchema),
  });
  const summary = useQuery({
    queryKey: ["analytics", "summary"],
    queryFn: () => request("/analytics/summary", summaryAnalyticsSchema),
  });
  return { skills, summary };
}
