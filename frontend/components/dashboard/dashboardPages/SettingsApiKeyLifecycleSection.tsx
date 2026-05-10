"use client";

import type { DashboardApiKeyItem } from "../dashboardTypes";

type KeyBulkAction = "" | "rotate" | "revoke";

type SettingsApiKeyLifecycleSectionProps = {
  canMutateApiKeys: boolean;
  isApiSubpathDashboard: boolean;
  activeKeyIds: string[];
  keyBulkAction: KeyBulkAction;
  selectedKeyIds: Set<string>;
  allKeysSelected: boolean;
  apiKeys: DashboardApiKeyItem[];
  lastIssuedApiKey: string | null;
  apiKeyMessage: string | null;
  onIssueKey: () => void | Promise<void>;
  onRefreshKeys: () => void | Promise<void>;
  onKeyBulkActionChange: (next: KeyBulkAction) => void;
  onApplyBulk: () => void | Promise<void>;
  onToggleSelectAll: () => void;
  onToggleKeySelected: (keyId: string) => void;
};

export function SettingsApiKeyLifecycleSection({
  canMutateApiKeys,
  isApiSubpathDashboard,
  activeKeyIds,
  keyBulkAction,
  selectedKeyIds,
  allKeysSelected,
  apiKeys,
  lastIssuedApiKey,
  apiKeyMessage,
  onIssueKey,
  onRefreshKeys,
  onKeyBulkActionChange,
  onApplyBulk,
  onToggleSelectAll,
  onToggleKeySelected,
}: SettingsApiKeyLifecycleSectionProps) {
  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">API key lifecycle</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
        {canMutateApiKeys
          ? "Issue, rotate, and revoke ingest keys (owners and admins). All changes are audited."
          : "Active keys for this project (read-only). Ask an owner or admin to issue or rotate keys."}
      </p>
      {isApiSubpathDashboard ? (
        <p className="mt-2 text-xs text-slate-600 dark:text-neutral-400">
          First boot writes <code className="rounded bg-slate-100 px-1 font-mono dark:bg-neutral-950">.env.lumonox</code>{" "}
          - source before <code className="rounded bg-slate-100 px-1 font-mono dark:bg-neutral-950">npm run build</code>.
          New keys here: paste both API_KEY lines there, rebuild, restart.
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" disabled={!canMutateApiKeys} onClick={() => void onIssueKey()} className="ap-btn-primary">
          Issue new key
        </button>
        <button type="button" onClick={() => void onRefreshKeys()} className="ap-btn">
          Refresh
        </button>
      </div>
      {lastIssuedApiKey ? (
        <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-200">
          <p className="font-semibold">Copy this key now (shown once):</p>
          <code className="mt-1 block break-all">{lastIssuedApiKey}</code>
        </div>
      ) : null}
      {activeKeyIds.length > 0 && canMutateApiKeys ? (
        <div className="mt-3 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-slate-50/90 px-4 py-3 dark:border-neutral-700 dark:bg-neutral-800/60">
          <label className="block min-w-[12rem] text-sm font-medium text-slate-700 dark:text-neutral-200">
            Action
            <select
              value={keyBulkAction}
              onChange={(event) => onKeyBulkActionChange(event.target.value as KeyBulkAction)}
              className="ap-select mt-1 w-full"
              aria-label="Bulk API key action"
            >
              <option value="">Choose action...</option>
              <option value="rotate">Rotate selected</option>
              <option value="revoke">Revoke selected</option>
            </select>
          </label>
          <button
            type="button"
            disabled={!keyBulkAction || selectedKeyIds.size === 0}
            onClick={() => void onApplyBulk()}
            className={
              keyBulkAction === "revoke"
                ? "ap-btn-danger disabled:cursor-not-allowed disabled:opacity-50"
                : "ap-btn-primary disabled:cursor-not-allowed disabled:opacity-50"
            }
          >
            Apply
          </button>
          <p className="max-w-md text-xs text-slate-500 dark:text-neutral-400">
            Select active keys, choose an action, Apply, then confirm. With multiple active keys, the oldest active key
            cannot be bulk-revoked.
          </p>
        </div>
      ) : null}
      <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
        <table className="min-w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
            <tr>
              <th className="w-10 px-2 py-2">
                {activeKeyIds.length > 0 && canMutateApiKeys ? (
                  <input
                    type="checkbox"
                    className="size-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-neutral-600"
                    checked={allKeysSelected}
                    onChange={onToggleSelectAll}
                    aria-label="Select all active API keys"
                  />
                ) : null}
              </th>
              <th className="px-3 py-2 font-semibold">Key ID</th>
              <th className="px-3 py-2 font-semibold">Created</th>
              <th className="px-3 py-2 font-semibold">Revoked</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
            {apiKeys.map((item) => (
              <tr key={item.key_id}>
                <td className="px-2 py-2 align-middle">
                  {!item.revoked_at && canMutateApiKeys ? (
                    <input
                      type="checkbox"
                      className="size-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-neutral-600"
                      checked={selectedKeyIds.has(item.key_id)}
                      onChange={() => onToggleKeySelected(item.key_id)}
                      aria-label={`Select key ${item.key_id}`}
                    />
                  ) : (
                    <span className="inline-block w-4" aria-hidden />
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-slate-700 dark:text-neutral-200">{item.key_id}</td>
                <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                  {new Date(item.created_at).toLocaleString()}
                </td>
                <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                  {item.revoked_at ? new Date(item.revoked_at).toLocaleString() : "active"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {apiKeyMessage ? <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">{apiKeyMessage}</p> : null}
    </section>
  );
}
