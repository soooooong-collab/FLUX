"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getSlides, getPptxUrl, getDiscussionTranscript } from "@/lib/api";

interface Slide {
  step_key: string;
  phase: string;
  title: string;
  subtitle: string;
  body: string;
  layout: string;
  key_points?: string;
}

const PHASE_COLORS: Record<string, string> = {
  cover: "from-gray-800 to-gray-900",
  phase1: "from-blue-600 to-blue-800",
  phase2: "from-purple-600 to-purple-800",
  phase3: "from-flux-blue to-blue-800",
};

function ResultContent() {
  const params = useSearchParams();
  const projectId = params.get("projectId");

  const [slides, setSlides] = useState<Slide[]>([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [title, setTitle] = useState("");
  const [transcriptBusy, setTranscriptBusy] = useState<"copy" | "save" | null>(null);
  const [transcriptNotice, setTranscriptNotice] = useState("");

  useEffect(() => {
    if (!projectId) return;
    getSlides(projectId)
      .then((data) => {
        setSlides(data.slides);
        setTitle(data.title);
      })
      .catch(console.error);
  }, [projectId]);

  if (!slides.length) {
    return (
      <div className="flex items-center justify-center min-h-[50vh] text-flux-muted">
        Loading slides...
      </div>
    );
  }

  const slide = slides[currentSlide];

  const handleCopyTranscript = async () => {
    if (!projectId) return;
    setTranscriptBusy("copy");
    setTranscriptNotice("");
    try {
      const markdown = await getDiscussionTranscript(projectId);
      await navigator.clipboard.writeText(markdown);
      setTranscriptNotice("전체 회의내용 녹취를 클립보드에 복사했습니다.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "전체 회의내용 녹취 복사에 실패했습니다.";
      setTranscriptNotice(msg);
    } finally {
      setTranscriptBusy(null);
    }
  };

  const handleSaveTranscript = async () => {
    if (!projectId) return;
    setTranscriptBusy("save");
    setTranscriptNotice("");
    try {
      const markdown = await getDiscussionTranscript(projectId);
      const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `flux_full_transcript_${projectId.slice(0, 8)}.md`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      setTranscriptNotice("전체 회의내용 녹취 마크다운 파일을 저장했습니다.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "전체 회의내용 녹취 저장에 실패했습니다.";
      setTranscriptNotice(msg);
    } finally {
      setTranscriptBusy(null);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-extrabold text-flux-dark">{title}</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopyTranscript}
            disabled={transcriptBusy !== null}
            className="px-3.5 py-2 border border-flux-border text-flux-dark rounded-lg text-sm hover:bg-gray-50 transition disabled:opacity-50"
          >
            {transcriptBusy === "copy" ? "복사 중..." : "전체 녹취 복사"}
          </button>
          <button
            onClick={handleSaveTranscript}
            disabled={transcriptBusy !== null}
            className="px-3.5 py-2 border border-flux-border text-flux-dark rounded-lg text-sm hover:bg-gray-50 transition disabled:opacity-50"
          >
            {transcriptBusy === "save" ? "저장 중..." : "전체 녹취 저장(.md)"}
          </button>
          <a
            href={`/minutes?projectId=${projectId}`}
            className="px-3.5 py-2 border border-blue-200 bg-blue-50 text-blue-700 rounded-lg text-sm hover:bg-blue-100 transition"
          >
            회의록 보기
          </a>
          <a
            href={getPptxUrl(projectId!)}
            className="px-4 py-2 bg-flux-blue text-white rounded-lg text-sm hover:bg-flux-blue-hover transition font-medium"
            target="_blank"
          >
            Download PPTX
          </a>
        </div>
      </div>
      {transcriptNotice && (
        <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm text-blue-700">
          {transcriptNotice}
        </div>
      )}

      {/* Slide preview */}
      <div
        className={`relative w-full aspect-[16/9] rounded-2xl overflow-hidden bg-gradient-to-br ${PHASE_COLORS[slide.phase] || PHASE_COLORS.cover
          } mb-6 shadow-lg`}
      >
        <div className="absolute inset-0 p-12 flex flex-col justify-center">
          {slide.phase && (
            <div className="text-xs font-semibold text-blue-200 uppercase tracking-widest mb-4">
              {slide.phase}
            </div>
          )}
          <h2 className="text-3xl font-bold text-white mb-2">{slide.title}</h2>
          {slide.subtitle && (
            <p className="text-lg text-blue-200 mb-4">{slide.subtitle}</p>
          )}
          {slide.body && (
            <p className="text-sm text-white/80 whitespace-pre-wrap max-h-[50%] overflow-y-auto">
              {slide.body.slice(0, 1000)}
            </p>
          )}
          {slide.key_points && (
            <div className="mt-4 text-sm text-white/90">{slide.key_points}</div>
          )}
        </div>
      </div>

      {/* Slide navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setCurrentSlide(Math.max(0, currentSlide - 1))}
          disabled={currentSlide === 0}
          className="px-4 py-2 border border-flux-border rounded-lg text-sm hover:border-gray-400 text-flux-dark transition disabled:opacity-30"
        >
          ← Previous
        </button>
        <span className="text-sm text-flux-muted">
          {currentSlide + 1} / {slides.length}
        </span>
        <button
          onClick={() => setCurrentSlide(Math.min(slides.length - 1, currentSlide + 1))}
          disabled={currentSlide === slides.length - 1}
          className="px-4 py-2 border border-flux-border rounded-lg text-sm hover:border-gray-400 text-flux-dark transition disabled:opacity-30"
        >
          Next →
        </button>
      </div>

      {/* Slide thumbnails */}
      <div className="flex gap-2 mt-4 overflow-x-auto pb-2">
        {slides.map((s, i) => (
          <button
            key={i}
            onClick={() => setCurrentSlide(i)}
            className={`flex-shrink-0 w-32 h-20 rounded-lg border text-left p-2 transition ${i === currentSlide
              ? "border-flux-blue bg-flux-muted-blue"
              : "border-flux-border bg-white hover:border-gray-300"
              }`}
          >
            <div className="text-[8px] text-flux-blue">{s.phase}</div>
            <div className="text-[10px] text-flux-dark line-clamp-2">{s.title}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ResultPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-[50vh] text-flux-muted">
        Loading...
      </div>
    }>
      <ResultContent />
    </Suspense>
  );
}
