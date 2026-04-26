"use client";

import { useEffect, useMemo, useState } from "react";

type OverviewBucket = {
  minute: string;
  request_count: number;
  error_count: number;
  avg_latency_ms: number;
};

type OverviewResponse = {
  from_timestamp: string;
  to_timestamp: string;
  request_count: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
  requests_per_minute: number;
  series: OverviewBucket[];
};

type RequestItem = {
  timestamp: string;
  method: string;
  path: string;
  status_code: number;
  latency_ms: number;
  service_name: string;
  environment: string;
  request_id: string | null;
};

type RequestsResponse = {
  from_timestamp: string;
  to_timestamp: string;
  total: number;
  limit: number;
  offset: number;
  items: RequestItem[];
};

const apiBaseUrl = process.env.NEXT_PUBLIC_AUTOPULSE_API_BASE_URL ?? "http://localhost:8000";
const apiKey = process.env.NEXT_PUBLIC_AUTOPULSE_API_KEY;

const WINDOW_OPTIONS = [15, 60, 240, 1440];
const METHOD_OPTIONS = ["ALL", "GET", "POST", "PUT", "PATCH", "DELETE"];
const STATUS_CLASS_OPTIONS = ["ALL", "2", "4", "5"];

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

export default function DashboardPage() {
  const [windowMinutes, setWindowMinutes] = useState(60);
  const [method, setMethod] = useState("ALL");
  const [statusClass, setStatusClass] = useState("ALL");
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [requests, setRequests] = useState<RequestsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const toIsoWindow = useMemo(() => {
    const to = new Date();
    const from = new Date(to.getTime() - windowMinutes * 60 * 1000);
    return { from: from.toISOString(), to: to.toISOString() };
  }, [windowMinutes]);

  useEffect(() => {
    if (!apiKey) {
      return;
    }

    const run = async () => {
      setLoading(true);
      setErrorMessage(null);
      try {
        const headers = { Authorization: `Bearer ${apiKey}` };
        const overviewParams = new URLSearchParams({
          from_timestamp: toIsoWindow.from,
          to_timestamp: toIsoWindow.to,
        });

        const requestsParams = new URLSearchParams({
          from_timestamp: toIsoWindow.from,
          to_timestamp: toIsoWindow.to,
          limit: "50",
        });
        if (method !== "ALL") {
          requestsParams.set("method", method);
        }
        if (statusClass !== "ALL") {
          requestsParams.set("status_class", statusClass);
        }

        const [overviewResponse, requestsResponse] = await Promise.all([
          fetch(`${apiBaseUrl}/dashboard/overview?${overviewParams.toString()}`, { headers }),
          fetch(`${apiBaseUrl}/dashboard/requests?${requestsParams.toString()}`, { headers }),
        ]);
        if (!overviewResponse.ok || !requestsResponse.ok) {
          throw new Error("Dashboard API request failed. Check API URL/key and backend status.");
        }
        const overviewData = (await overviewResponse.json()) as OverviewResponse;
        const requestsData = (await requestsResponse.json()) as RequestsResponse;
        setOverview(overviewData);
        setRequests(requestsData);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unexpected dashboard loading failure.";
        setErrorMessage(message);
      } finally {
        setLoading(false);
      }
    };

    void run();
  }, [method, statusClass, toIsoWindow]);

  if (!apiKey) {
    return (
      <main className="page">
        <h1>AutoPulse Dashboard</h1>
        <section className="state-card">
          <h2>Setup required</h2>
          <p>
            Set <code>NEXT_PUBLIC_AUTOPULSE_API_KEY</code> and{" "}
            <code>NEXT_PUBLIC_AUTOPULSE_API_BASE_URL</code> to load project data.
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <h1>AutoPulse Dashboard</h1>
          <p>Fast diagnosis: request rate, error rate, latency, and recent traffic.</p>
        </div>
        <div className="filters">
          <label>
            Time window
            <select
              value={windowMinutes}
              onChange={(event) => setWindowMinutes(Number(event.target.value))}
            >
              {WINDOW_OPTIONS.map((minutes) => (
                <option key={minutes} value={minutes}>
                  Last {minutes}m
                </option>
              ))}
            </select>
          </label>
          <label>
            Method
            <select value={method} onChange={(event) => setMethod(event.target.value)}>
              {METHOD_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Status class
            <select value={statusClass} onChange={(event) => setStatusClass(event.target.value)}>
              {STATUS_CLASS_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value === "ALL" ? value : `${value}xx`}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {loading && (
        <section className="state-card">
          <h2>Loading dashboard data...</h2>
        </section>
      )}

      {!loading && errorMessage && (
        <section className="state-card error">
          <h2>Unable to load dashboard data</h2>
          <p>{errorMessage}</p>
        </section>
      )}

      {!loading && !errorMessage && overview && requests && (
        <>
          <section className="overview-grid">
            <article className="metric-card">
              <h2>Requests / min</h2>
              <p>{overview.requests_per_minute.toFixed(2)}</p>
            </article>
            <article className="metric-card">
              <h2>Error rate</h2>
              <p>{(overview.error_rate * 100).toFixed(1)}%</p>
            </article>
            <article className="metric-card">
              <h2>Average latency</h2>
              <p>{overview.avg_latency_ms.toFixed(1)} ms</p>
            </article>
          </section>

          <section className="state-card">
            <h2>Recent requests</h2>
            {requests.items.length === 0 ? (
              <p>
                No requests in this time window yet. Generate traffic in your instrumented app and
                reload.
              </p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Method</th>
                      <th>Path</th>
                      <th>Status</th>
                      <th>Latency</th>
                      <th>Service</th>
                      <th>Environment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.items.map((item) => (
                      <tr key={`${item.timestamp}-${item.request_id ?? item.path}`}>
                        <td>{formatTimestamp(item.timestamp)}</td>
                        <td>{item.method}</td>
                        <td>{item.path}</td>
                        <td>{item.status_code}</td>
                        <td>{item.latency_ms.toFixed(1)} ms</td>
                        <td>{item.service_name}</td>
                        <td>{item.environment}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
