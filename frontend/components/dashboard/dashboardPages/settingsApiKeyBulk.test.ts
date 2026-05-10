import { describe, expect, it } from "vitest";

import type { DashboardApiKeyItem } from "../dashboardTypes";

import { primaryActiveKeyIdFromList, resolveApiKeyBulkTargets } from "./settingsApiKeyBulk";

const key = (id: string, created: string, revoked: string | null = null): DashboardApiKeyItem => ({
  key_id: id,
  created_at: created,
  revoked_at: revoked,
});

describe("primaryActiveKeyIdFromList", () => {
  it("returns null when no active keys", () => {
    expect(primaryActiveKeyIdFromList([key("a", "2026-01-02T00:00:00Z", "2026-01-03")])).toBeNull();
  });

  it("returns oldest active key by created_at", () => {
    const keys = [key("newer", "2026-01-02T00:00:00Z"), key("older", "2026-01-01T00:00:00Z")];
    expect(primaryActiveKeyIdFromList(keys)).toBe("older");
  });
});

describe("resolveApiKeyBulkTargets", () => {
  it("rotate: keeps only active selected ids", () => {
    const keys = [key("a", "2026-01-01T00:00:00Z"), key("b", "2026-01-02T00:00:00Z", "2026-01-03")];
    const r = resolveApiKeyBulkTargets("rotate", new Set(["a", "b"]), keys);
    expect(r).toEqual({ ok: true, targetIds: ["a"] });
  });

  it("revoke: rejects when only one active key", () => {
    const keys = [key("only", "2026-01-01T00:00:00Z")];
    const r = resolveApiKeyBulkTargets("revoke", new Set(["only"]), keys);
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.message).toContain("only active");
    }
  });

  it("revoke: drops primary from targets when multiple active", () => {
    const keys = [key("primary", "2026-01-01T00:00:00Z"), key("other", "2026-01-02T00:00:00Z")];
    const r = resolveApiKeyBulkTargets("revoke", new Set(["primary", "other"]), keys);
    expect(r).toEqual({ ok: true, targetIds: ["other"] });
  });

  it("revoke: fails when selection would only revoke primary", () => {
    const keys = [key("primary", "2026-01-01T00:00:00Z"), key("other", "2026-01-02T00:00:00Z")];
    const r = resolveApiKeyBulkTargets("revoke", new Set(["primary"]), keys);
    expect(r.ok).toBe(false);
  });
});
