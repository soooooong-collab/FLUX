"use client";

import { useEffect, useState } from "react";
import { listProjects, isLoggedIn } from "@/lib/api";

interface ProjectSummary {
  id: string;
  brand_name: string;
  main_goal: string;
  director_type: string;
  status: string;
  created_at: string;
}

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-gray-500/20 text-gray-400",
  running: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
};

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);

  useEffect(() => {
    if (isLoggedIn()) {
      listProjects().then(setProjects).catch(console.error);
    }
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-white">Dashboard</h1>
        <a
          href="/brief"
          className="px-6 py-2 bg-flux-accent text-white rounded-lg text-sm hover:bg-flux-accent-light transition"
        >
          + New Project
        </a>
      </div>

      {projects.length === 0 ? (
        <div className="text-center py-20 text-flux-muted/50">
          <p className="text-lg mb-2">No projects yet</p>
          <p className="text-sm">Create your first campaign brief to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map((p) => (
            <a
              key={p.id}
              href={p.status === "completed" ? `/result?projectId=${p.id}` : `/pipeline?projectId=${p.id}`}
              className="block p-5 rounded-xl border border-white/10 hover:border-white/20 transition"
            >
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold text-white">{p.brand_name}</h3>
                <span className={`px-2 py-0.5 rounded text-xs ${STATUS_STYLES[p.status] || ""}`}>
                  {p.status}
                </span>
              </div>
              <p className="text-sm text-flux-muted/60 line-clamp-1">{p.main_goal}</p>
              <div className="flex gap-4 mt-2 text-xs text-flux-muted/40">
                <span>Director: {p.director_type}</span>
                <span>{new Date(p.created_at).toLocaleDateString("ko-KR")}</span>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
