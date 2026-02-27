"use client";

import { useEffect, useState, useRef } from "react";
import {
  getSystemHealth,
  syncData,
  buildGraph,
  getGraphStats,
  runEmbeddings,
  getEmbeddingStatus,
  listMethods,
  getMethodCategories,
  listCases,
  adminListDirectors,
  uploadDataset,
  runFullPipeline,
} from "@/lib/api";

/* ──────────────────────────────────────────────────────────
   Types
   ────────────────────────────────────────────────────────── */

type Tab = "overview" | "methods" | "cases" | "directors" | "data";

interface HealthData {
  postgresql: boolean;
  neo4j: boolean;
  data?: { methods: number; cases: number; directors: number };
  graph?: Record<string, number>;
  embedding?: {
    methods: { total: number; embedded: number; pending: number; coverage: number };
    cases: { total: number; embedded: number; pending: number; coverage: number };
  };
}

/* ──────────────────────────────────────────────────────────
   Helper Components
   ────────────────────────────────────────────────────────── */

function Badge({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${ok ? "bg-green-400" : "bg-red-400"
        }`}
    />
  );
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="bg-white border border-flux-border rounded-xl p-5">
      <p className="text-xs text-flux-muted uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-flux-dark">{value}</p>
      {sub && <p className="text-xs text-flux-muted mt-1">{sub}</p>}
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  loading,
  variant = "primary",
}: {
  children: React.ReactNode;
  onClick: () => void;
  loading?: boolean;
  variant?: "primary" | "secondary" | "danger";
}) {
  const base = "px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-40";
  const variants = {
    primary: "bg-flux-blue hover:bg-flux-blue-hover text-flux-dark",
    secondary: "bg-gray-100 hover:bg-gray-200 text-flux-muted",
    danger: "bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30",
  };
  return (
    <button
      className={`${base} ${variants[variant]}`}
      onClick={onClick}
      disabled={loading}
    >
      {loading ? (
        <span className="flex items-center gap-2">
          <span className="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          Processing...
        </span>
      ) : (
        children
      )}
    </button>
  );
}

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-flux-blue rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-flux-muted min-w-[3rem] text-right">{pct}%</span>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────
   Tab: Overview
   ────────────────────────────────────────────────────────── */

function OverviewTab({
  health,
  refreshHealth,
}: {
  health: HealthData | null;
  refreshHealth: () => void;
}) {
  const [graphStats, setGraphStats] = useState<Record<string, number> | null>(null);
  const [embStatus, setEmbStatus] = useState<HealthData["embedding"] | null>(null);

  useEffect(() => {
    getGraphStats().then(setGraphStats).catch(() => { });
    getEmbeddingStatus().then(setEmbStatus).catch(() => { });
  }, []);

  return (
    <div className="space-y-8">
      {/* Connection Status */}
      <section>
        <h3 className="text-lg font-semibold text-flux-dark mb-4">System Status</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white border border-flux-border rounded-xl p-5 flex items-center gap-3">
            <Badge ok={health?.postgresql ?? false} />
            <div>
              <p className="text-sm font-medium text-flux-dark">PostgreSQL</p>
              <p className="text-xs text-flux-muted">
                {health?.data
                  ? `${health.data.methods}M / ${health.data.cases}C / ${health.data.directors}D`
                  : "Not connected"}
              </p>
            </div>
          </div>
          <div className="bg-white border border-flux-border rounded-xl p-5 flex items-center gap-3">
            <Badge ok={health?.neo4j ?? false} />
            <div>
              <p className="text-sm font-medium text-flux-dark">Neo4j</p>
              <p className="text-xs text-flux-muted">
                {health?.neo4j ? "Connected" : "Not connected"}
              </p>
            </div>
          </div>
          <div className="bg-white border border-flux-border rounded-xl p-5 flex items-center gap-3">
            <Badge ok={(embStatus?.methods?.coverage ?? 0) > 0} />
            <div>
              <p className="text-sm font-medium text-flux-dark">Embeddings</p>
              <p className="text-xs text-flux-muted">
                {embStatus
                  ? `M: ${embStatus.methods.coverage}% / C: ${embStatus.cases.coverage}%`
                  : "Unknown"}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Data Counts */}
      {health?.data && (
        <section>
          <h3 className="text-lg font-semibold text-flux-dark mb-4">Data Counts</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard label="Methods" value={health.data.methods} />
            <StatCard label="Cases" value={health.data.cases} />
            <StatCard label="Directors" value={health.data.directors} />
            <StatCard
              label="Graph Nodes"
              value={
                graphStats
                  ? Object.entries(graphStats)
                    .filter(([k]) => k.endsWith("_nodes"))
                    .reduce((a, [, v]) => a + v, 0)
                  : "—"
              }
            />
          </div>
        </section>
      )}

      {/* Graph Stats */}
      {graphStats && (
        <section>
          <h3 className="text-lg font-semibold text-flux-dark mb-4">Graph Topology</h3>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {Object.entries(graphStats).map(([key, val]) => (
              <StatCard
                key={key}
                label={key.replace(/_/g, " ")}
                value={val}
              />
            ))}
          </div>
        </section>
      )}

      {/* Embedding Coverage */}
      {embStatus && (
        <section>
          <h3 className="text-lg font-semibold text-flux-dark mb-4">Embedding Coverage</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="bg-white border border-flux-border rounded-xl p-5">
              <p className="text-sm font-medium text-flux-dark mb-2">Methods</p>
              <ProgressBar value={embStatus.methods.embedded} max={embStatus.methods.total} />
              <p className="text-xs text-flux-muted mt-2">
                {embStatus.methods.embedded}/{embStatus.methods.total} embedded
                {embStatus.methods.pending > 0 &&
                  ` (${embStatus.methods.pending} pending)`}
              </p>
            </div>
            <div className="bg-white border border-flux-border rounded-xl p-5">
              <p className="text-sm font-medium text-flux-dark mb-2">Cases</p>
              <ProgressBar value={embStatus.cases.embedded} max={embStatus.cases.total} />
              <p className="text-xs text-flux-muted mt-2">
                {embStatus.cases.embedded}/{embStatus.cases.total} embedded
                {embStatus.cases.pending > 0 &&
                  ` (${embStatus.cases.pending} pending)`}
              </p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────
   Tab: Methods
   ────────────────────────────────────────────────────────── */

function MethodsTab() {
  const [methods, setMethods] = useState<any[]>([]);
  const [categories, setCategories] = useState<{ category: string; count: number }[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listMethods(), getMethodCategories()])
      .then(([m, c]) => {
        setMethods(m);
        setCategories(c);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter
    ? methods.filter((m) => m.category === filter)
    : methods;

  if (loading) return <p className="text-flux-muted">Loading methods...</p>;

  return (
    <div className="space-y-6">
      {/* Category Filter */}
      <div className="flex flex-wrap gap-2">
        <button
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${!filter
              ? "bg-flux-blue text-flux-dark"
              : "bg-gray-100 text-flux-muted hover:bg-gray-200"
            }`}
          onClick={() => setFilter("")}
        >
          All ({methods.length})
        </button>
        {categories.map((cat) => (
          <button
            key={cat.category}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${filter === cat.category
                ? "bg-flux-blue text-flux-dark"
                : "bg-gray-100 text-flux-muted hover:bg-gray-200"
              }`}
            onClick={() => setFilter(cat.category)}
          >
            {cat.category} ({cat.count})
          </button>
        ))}
      </div>

      {/* Methods Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-flux-border text-left text-flux-muted text-xs uppercase">
              <th className="pb-3 pr-4">Name</th>
              <th className="pb-3 pr-4">Category</th>
              <th className="pb-3 pr-4">Core Principle</th>
              <th className="pb-3 pr-4">Embedding</th>
              <th className="pb-3">Active</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((m) => (
              <tr
                key={m.id}
                className="border-b border-flux-border/50 hover:bg-gray-100 transition"
              >
                <td className="py-3 pr-4 font-medium text-flux-dark">{m.method_name}</td>
                <td className="py-3 pr-4">
                  <span className="px-2 py-0.5 rounded bg-blue-50 text-xs">
                    {m.category}
                  </span>
                </td>
                <td className="py-3 pr-4 text-flux-muted max-w-xs truncate">
                  {m.core_principle || "—"}
                </td>
                <td className="py-3 pr-4">
                  <Badge ok={m.has_embedding} />
                </td>
                <td className="py-3">
                  <Badge ok={m.is_active} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length === 0 && (
        <p className="text-center text-gray-400 py-8">No methods found</p>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────
   Tab: Cases
   ────────────────────────────────────────────────────────── */

function CasesTab() {
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [industryFilter, setIndustryFilter] = useState("");

  useEffect(() => {
    loadCases();
  }, []);

  function loadCases(industry?: string) {
    setLoading(true);
    listCases(industry)
      .then(setCases)
      .finally(() => setLoading(false));
  }

  const industries = Array.from(new Set(cases.map((c) => c.industry).filter(Boolean)));

  if (loading) return <p className="text-flux-muted">Loading cases...</p>;

  return (
    <div className="space-y-6">
      {/* Industry Filter */}
      <div className="flex flex-wrap gap-2">
        <button
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${!industryFilter
              ? "bg-flux-blue text-flux-dark"
              : "bg-gray-100 text-flux-muted hover:bg-gray-200"
            }`}
          onClick={() => {
            setIndustryFilter("");
            loadCases();
          }}
        >
          All ({cases.length})
        </button>
        {industries.map((ind) => (
          <button
            key={ind}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${industryFilter === ind
                ? "bg-flux-blue text-flux-dark"
                : "bg-gray-100 text-flux-muted hover:bg-gray-200"
              }`}
            onClick={() => {
              setIndustryFilter(ind);
              loadCases(ind);
            }}
          >
            {ind}
          </button>
        ))}
      </div>

      {/* Cases Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-flux-border text-left text-flux-muted text-xs uppercase">
              <th className="pb-3 pr-4">Brand</th>
              <th className="pb-3 pr-4">Campaign</th>
              <th className="pb-3 pr-4">Industry</th>
              <th className="pb-3 pr-4">Methods</th>
              <th className="pb-3 pr-4">Budget</th>
              <th className="pb-3">Emb</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr
                key={c.case_id}
                className="border-b border-flux-border/50 hover:bg-gray-100 transition"
              >
                <td className="py-3 pr-4 font-medium text-flux-dark">{c.brand}</td>
                <td className="py-3 pr-4 text-flux-muted max-w-[200px] truncate">
                  {c.campaign_title || "—"}
                </td>
                <td className="py-3 pr-4">
                  <span className="px-2 py-0.5 rounded bg-blue-50 text-xs">
                    {c.industry}
                  </span>
                </td>
                <td className="py-3 pr-4 text-xs text-flux-muted max-w-[200px] truncate">
                  {c.applied_methods?.join(", ") || "—"}
                </td>
                <td className="py-3 pr-4 text-xs">{c.budget_tier || "—"}</td>
                <td className="py-3">
                  <Badge ok={c.has_embedding} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {cases.length === 0 && (
        <p className="text-center text-gray-400 py-8">No cases found</p>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────
   Tab: Directors
   ────────────────────────────────────────────────────────── */

function DirectorsTab() {
  const [directors, setDirectors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminListDirectors()
      .then(setDirectors)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-flux-muted">Loading directors...</p>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {directors.map((d) => (
        <div
          key={d.id}
          className="bg-white border border-flux-border rounded-xl p-5 space-y-3"
        >
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-base font-semibold text-flux-dark">{d.name}</h4>
              <p className="text-xs text-flux-blue">{d.archetype}</p>
            </div>
            <Badge ok={d.is_active} />
          </div>
          {d.tagline && (
            <p className="text-sm text-flux-muted italic">{d.tagline}</p>
          )}
          {d.description && (
            <p className="text-xs text-flux-muted line-clamp-2">{d.description}</p>
          )}
          {/* Weight bars */}
          <div className="space-y-1.5">
            {Object.entries(d.weights as Record<string, number>).map(([dim, val]) => (
              <div key={dim} className="flex items-center gap-2 text-xs">
                <span className="w-20 text-flux-muted capitalize">{dim}</span>
                <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-flux-blue/70 rounded-full"
                    style={{ width: `${(val / 5) * 100}%` }}
                  />
                </div>
                <span className="w-6 text-right text-gray-400">{val}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
      {directors.length === 0 && (
        <p className="text-center text-gray-400 py-8 col-span-2">
          No directors found
        </p>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────
   Tab: Data Operations
   ────────────────────────────────────────────────────────── */

function DataTab({ refreshHealth }: { refreshHealth: () => void }) {
  const [syncResult, setSyncResult] = useState<any>(null);
  const [graphResult, setGraphResult] = useState<any>(null);
  const [embResult, setEmbResult] = useState<any>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [uploadDatasetType, setUploadDatasetType] = useState("methods");
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleSync() {
    setLoading("sync");
    try {
      const res = await syncData();
      setSyncResult(res);
      refreshHealth();
    } catch (e: any) {
      setSyncResult({ error: e.message });
    }
    setLoading(null);
  }

  async function handleGraphBuild(clear: boolean) {
    setLoading("graph");
    try {
      const res = await buildGraph(clear);
      setGraphResult(res);
      refreshHealth();
    } catch (e: any) {
      setGraphResult({ error: e.message });
    }
    setLoading(null);
  }

  async function handleEmbeddings(force: boolean) {
    setLoading("embed");
    try {
      const res = await runEmbeddings(force);
      setEmbResult(res);
      refreshHealth();
    } catch (e: any) {
      setEmbResult({ error: e.message });
    }
    setLoading(null);
  }

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setLoading("upload");
    try {
      const res = await uploadDataset(uploadDatasetType, file);
      setUploadResult(res);
      refreshHealth();
    } catch (e: any) {
      setUploadResult({ error: e.message });
    }
    setLoading(null);
  }

  return (
    <div className="space-y-8">
      {/* Full Pipeline */}
      <section className="bg-flux-muted-blue border border-flux-accent/20 rounded-xl p-6">
        <h3 className="text-base font-semibold text-flux-blue mb-2">Run Full Data Pipeline</h3>
        <p className="text-xs text-flux-muted mb-4">
          Runs 1) DB Sync (Upsert), 2) Neo4j Graph Rebuild, and 3) Vector Embedding Generation sequentially. Use this after replacing raw Excel files.
        </p>
        <div className="flex items-center gap-3">
          <ActionButton
            onClick={async () => {
              setLoading("full");
              try {
                const res = await runFullPipeline();
                setSyncResult(res);
                refreshHealth();
              } catch (e: any) {
                setSyncResult({ error: e.message });
              }
              setLoading(null);
            }}
            loading={loading === "full"}
            variant="primary"
          >
            Run Full Pipeline
          </ActionButton>
          {syncResult && loading !== "full" && syncResult.status === "success" && (
            <span className="text-xs text-green-400">
              Pipeline completed successfully! (M:{syncResult.sync.methods_upserted}, C:{syncResult.sync.cases_upserted}, D:{syncResult.sync.directors_upserted})
            </span>
          )}
        </div>
      </section>

      {/* Sync from default Excel */}
      <section className="bg-white border border-flux-border rounded-xl p-6">
        <h3 className="text-base font-semibold text-flux-dark mb-2">Manual Data Sync</h3>
        <p className="text-xs text-flux-muted mb-4">
          Sync raw Excel files from <code className="text-flux-blue">data/raw/</code> into PostgreSQL only.
        </p>
        <div className="flex items-center gap-3">
          <ActionButton onClick={handleSync} loading={loading === "sync"} variant="secondary">
            Sync DB Only
          </ActionButton>
          {syncResult && loading !== "full" && !syncResult.status && (
            <span className="text-xs text-flux-muted">
              {syncResult.error
                ? syncResult.error
                : `M:${syncResult.methods_inserted} C:${syncResult.cases_inserted} D:${syncResult.directors_inserted}`}
            </span>
          )}
        </div>
      </section>

      {/* Excel Upload */}
      <section className="bg-white border border-flux-border rounded-xl p-6">
        <h3 className="text-base font-semibold text-flux-dark mb-2">Excel Upload</h3>
        <p className="text-xs text-flux-muted mb-4">
          Upload an .xlsx file to add new records to a specific dataset
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={uploadDatasetType}
            onChange={(e) => setUploadDatasetType(e.target.value)}
            className="bg-gray-100 border border-flux-border rounded-lg px-3 py-2 text-sm text-flux-dark"
          >
            <option value="methods">Methods</option>
            <option value="cases">Cases</option>
            <option value="directors">Directors</option>
          </select>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls"
            className="text-sm text-flux-muted file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-gray-100 file:text-flux-muted file:text-sm file:cursor-pointer"
          />
          <ActionButton onClick={handleUpload} loading={loading === "upload"} variant="secondary">
            Upload
          </ActionButton>
          {uploadResult && (
            <span className="text-xs text-flux-muted">
              {uploadResult.error
                ? uploadResult.error
                : `${uploadResult.inserted} records inserted from ${uploadResult.filename}`}
            </span>
          )}
        </div>
      </section>

      {/* Graph Build */}
      <section className="bg-white border border-flux-border rounded-xl p-6">
        <h3 className="text-base font-semibold text-flux-dark mb-2">Neo4j Graph Build</h3>
        <p className="text-xs text-flux-muted mb-4">
          Build ontology graph from PostgreSQL data. Creates nodes, edges, and similarity links.
        </p>
        <div className="flex items-center gap-3">
          <ActionButton onClick={() => handleGraphBuild(false)} loading={loading === "graph"}>
            Build Graph
          </ActionButton>
          <ActionButton
            onClick={() => handleGraphBuild(true)}
            loading={loading === "graph"}
            variant="danger"
          >
            Rebuild (Clear + Build)
          </ActionButton>
          {graphResult && (
            <span className="text-xs text-flux-muted">
              {graphResult.error
                ? graphResult.error
                : `Nodes: M${graphResult.methods_nodes} C${graphResult.cases_nodes} D${graphResult.directors_nodes} | Edges: Pref${graphResult.director_preferences} Sim${graphResult.case_similarity} Rel${graphResult.method_relatedness}`}
            </span>
          )}
        </div>
      </section>

      {/* Embeddings */}
      <section className="bg-white border border-flux-border rounded-xl p-6">
        <h3 className="text-base font-semibold text-flux-dark mb-2">Embedding Pipeline</h3>
        <p className="text-xs text-flux-muted mb-4">
          Generate vector embeddings for methods and cases. Only processes records without embeddings unless forced.
        </p>
        <div className="flex items-center gap-3">
          <ActionButton
            onClick={() => handleEmbeddings(false)}
            loading={loading === "embed"}
          >
            Run (Pending Only)
          </ActionButton>
          <ActionButton
            onClick={() => handleEmbeddings(true)}
            loading={loading === "embed"}
            variant="danger"
          >
            Force Re-embed All
          </ActionButton>
          {embResult && (
            <span className="text-xs text-flux-muted">
              {embResult.error
                ? embResult.error
                : `Methods: ${embResult.methods?.embedded}/${embResult.methods?.total} | Cases: ${embResult.cases?.embedded}/${embResult.cases?.total}`}
            </span>
          )}
        </div>
      </section>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────
   Main Admin Page
   ────────────────────────────────────────────────────────── */

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [health, setHealth] = useState<HealthData | null>(null);

  function refreshHealth() {
    getSystemHealth().then(setHealth).catch(() => { });
  }

  useEffect(() => {
    refreshHealth();
  }, []);

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "methods", label: "Methods" },
    { key: "cases", label: "Cases" },
    { key: "directors", label: "Directors" },
    { key: "data", label: "Data Ops" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-flux-dark">
          Admin<span className="text-flux-blue">.</span>
        </h1>
        <button
          onClick={refreshHealth}
          className="text-xs text-flux-muted hover:text-flux-blue transition"
        >
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-50 rounded-xl p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition ${tab === t.key
                ? "bg-flux-blue text-flux-dark"
                : "text-flux-muted hover:text-flux-blue hover:bg-gray-200"
              }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {tab === "overview" && (
          <OverviewTab health={health} refreshHealth={refreshHealth} />
        )}
        {tab === "methods" && <MethodsTab />}
        {tab === "cases" && <CasesTab />}
        {tab === "directors" && <DirectorsTab />}
        {tab === "data" && <DataTab refreshHealth={refreshHealth} />}
      </div>
    </div>
  );
}
