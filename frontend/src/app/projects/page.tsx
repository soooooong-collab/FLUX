"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { listProjects, deleteProject, ensureAuth } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface Project {
  id: string;
  brand_name: string;
  main_goal: string;
  director_type: string;
  status: string;
  created_at: string;
}

const statusConfig: Record<string, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-gray-100 text-gray-600" },
  running: { label: "Running", className: "bg-blue-100 text-blue-700 animate-pulse" },
  completed: { label: "Completed", className: "bg-green-100 text-green-700" },
  failed: { label: "Failed", className: "bg-red-100 text-red-600" },
};

const directorLabels: Record<string, string> = {
  strategist: "Strategist",
  provocateur: "Provocateur",
  storyteller: "Storyteller",
  emotional_minimalist: "Emotional Minimalist",
  culture_hacker: "Culture Hacker",
  performance_hacker: "Performance Hacker",
};

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "방금 전";
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}일 전`;
  return new Date(dateStr).toLocaleDateString("ko-KR");
}

export default function ProjectsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        await ensureAuth();
        const data = await listProjects();
        setProjects(data);
      } catch {
        toast("프로젝트 목록을 불러오지 못했습니다.", "error");
      } finally {
        setLoading(false);
      }
    })();
  }, [toast]);

  const handleClick = (p: Project) => {
    switch (p.status) {
      case "completed":
      case "failed":
        router.push(`/result?projectId=${p.id}`);
        break;
      case "running":
        router.push(`/pipeline?projectId=${p.id}`);
        break;
      default:
        router.push(`/director?projectId=${p.id}`);
    }
  };

  const handleDelete = async (e: React.MouseEvent, p: Project) => {
    e.stopPropagation();
    if (!confirm(`"${p.brand_name}" 프로젝트를 삭제하시겠습니까?`)) return;
    setDeletingId(p.id);
    try {
      await deleteProject(p.id);
      setProjects((prev) => prev.filter((x) => x.id !== p.id));
      toast("프로젝트가 삭제되었습니다.", "success");
    } catch {
      toast("삭제에 실패했습니다.", "error");
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-3 border-flux-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-flux-dark">My Projects</h1>
          <span className="px-2.5 py-0.5 bg-flux-muted-blue text-flux-blue text-sm font-semibold rounded-full">
            {projects.length}
          </span>
        </div>
        <Link
          href="/brief"
          className="flex items-center gap-2 px-4 py-2 bg-flux-blue text-white text-sm font-semibold rounded-lg hover:bg-flux-blue-hover transition"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Strategy
        </Link>
      </div>

      {/* Empty State */}
      {projects.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-flux-border">
          <svg className="w-16 h-16 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v12a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z" />
          </svg>
          <p className="text-gray-500 text-lg mb-1">아직 프로젝트가 없습니다</p>
          <p className="text-gray-400 text-sm mb-6">새로운 광고 전략을 생성해보세요</p>
          <Link
            href="/brief"
            className="px-5 py-2.5 bg-flux-blue text-white text-sm font-semibold rounded-lg hover:bg-flux-blue-hover transition"
          >
            New Strategy
          </Link>
        </div>
      )}

      {/* Project Grid */}
      {projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {projects.map((p) => {
            const status = statusConfig[p.status] || statusConfig.draft;
            return (
              <div
                key={p.id}
                onClick={() => handleClick(p)}
                className="bg-white rounded-xl border border-flux-border p-5 hover:shadow-md hover:border-flux-blue/30 transition cursor-pointer group relative"
              >
                {/* Delete button */}
                <button
                  onClick={(e) => handleDelete(e, p)}
                  disabled={deletingId === p.id}
                  className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition"
                  title="삭제"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                  </svg>
                </button>

                <div className="flex items-start justify-between mb-3 pr-8">
                  <h3 className="text-lg font-bold text-flux-dark">{p.brand_name}</h3>
                </div>

                <p className="text-sm text-flux-muted line-clamp-2 mb-4">
                  {p.main_goal || "목표 미설정"}
                </p>

                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${status.className}`}>
                    {status.label}
                  </span>
                  <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-purple-50 text-purple-700">
                    {directorLabels[p.director_type] || p.director_type}
                  </span>
                  <span className="ml-auto text-xs text-gray-400">
                    {timeAgo(p.created_at)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
