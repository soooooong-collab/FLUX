"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getDiscussionMinutes } from "@/lib/api";

function MinutesContent() {
  const params = useSearchParams();
  const projectId = params.get("projectId");

  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"copy" | "save" | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!projectId) {
      setError("projectId가 없습니다.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");
    getDiscussionMinutes(projectId)
      .then((text) => setMarkdown(text))
      .catch((err) => {
        const msg = err instanceof Error ? err.message : "회의록을 불러오지 못했습니다.";
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleCopy = async () => {
    if (!markdown) return;
    setBusy("copy");
    setNotice("");
    try {
      await navigator.clipboard.writeText(markdown);
      setNotice("회의록을 클립보드에 복사했습니다.");
    } catch {
      setNotice("회의록 복사에 실패했습니다.");
    } finally {
      setBusy(null);
    }
  };

  const handleSave = async () => {
    if (!markdown || !projectId) return;
    setBusy("save");
    setNotice("");
    try {
      const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `flux_minutes_${projectId.slice(0, 8)}.md`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      setNotice("회의록 마크다운 파일을 저장했습니다.");
    } catch {
      setNotice("회의록 저장에 실패했습니다.");
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center text-flux-muted">
        회의록 불러오는 중...
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-extrabold text-flux-dark">회의록</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            disabled={busy !== null}
            className="px-3.5 py-2 border border-flux-border text-flux-dark rounded-lg text-sm hover:bg-gray-50 transition disabled:opacity-50"
          >
            {busy === "copy" ? "복사 중..." : "회의록 복사"}
          </button>
          <button
            onClick={handleSave}
            disabled={busy !== null}
            className="px-3.5 py-2 border border-flux-border text-flux-dark rounded-lg text-sm hover:bg-gray-50 transition disabled:opacity-50"
          >
            {busy === "save" ? "저장 중..." : "회의록 저장(.md)"}
          </button>
        </div>
      </div>
      {notice && (
        <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm text-blue-700">
          {notice}
        </div>
      )}
      <div className="rounded-xl border border-flux-border bg-white p-4">
        <pre className="whitespace-pre-wrap break-words text-sm leading-6 text-flux-dark">{markdown}</pre>
      </div>
    </div>
  );
}

export default function MinutesPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[50vh] flex items-center justify-center text-flux-muted">
          회의록 로딩 중...
        </div>
      }
    >
      <MinutesContent />
    </Suspense>
  );
}

