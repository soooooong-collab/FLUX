"use client";

import { useEffect, useState, useCallback } from "react";
import { getSlides, getPptxUrl, getMeetingPptxUrl } from "@/lib/api";

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

interface SlideArtifactPanelProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
}

export default function SlideArtifactPanel({ projectId, isOpen, onClose }: SlideArtifactPanelProps) {
  const [slides, setSlides] = useState<Slide[]>([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fetched, setFetched] = useState(false);

  // Fetch slides when panel opens (cache after first fetch)
  useEffect(() => {
    if (!isOpen || fetched || !projectId) return;
    setLoading(true);
    setError("");
    getSlides(projectId)
      .then((data) => {
        setSlides(data.slides);
        setTitle(data.title);
        setFetched(true);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "슬라이드를 불러올 수 없습니다.");
      })
      .finally(() => setLoading(false));
  }, [isOpen, fetched, projectId]);

  // Keyboard: Escape to close, arrows for navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowLeft") {
        setCurrentSlide((prev) => Math.max(0, prev - 1));
      } else if (e.key === "ArrowRight") {
        setCurrentSlide((prev) => Math.min(slides.length - 1, prev + 1));
      }
    },
    [isOpen, onClose, slides.length],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const slide = slides[currentSlide];

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/5 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-[500px] bg-white border-l border-flux-border shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-flux-border flex-shrink-0">
          <h2 className="text-lg font-bold text-flux-dark">PPTX 생성결과</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 transition text-gray-500"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center justify-center h-40 text-gray-400">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-flux-blue rounded-full animate-ping" />
                슬라이드 로딩 중...
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {slide && !loading && (
            <>
              {/* Title */}
              {title && (
                <div className="text-sm font-semibold text-gray-500 mb-3 truncate">{title}</div>
              )}

              {/* Slide Preview */}
              <div
                className={`relative w-full aspect-[16/9] rounded-xl overflow-hidden bg-gradient-to-br ${
                  PHASE_COLORS[slide.phase] || PHASE_COLORS.cover
                } shadow-md`}
              >
                <div className="absolute inset-0 p-6 flex flex-col justify-center">
                  {slide.phase && (
                    <div className="text-[10px] font-semibold text-blue-200 uppercase tracking-widest mb-2">
                      {slide.phase}
                    </div>
                  )}
                  <h3 className="text-lg font-bold text-white mb-1 leading-tight">{slide.title}</h3>
                  {slide.subtitle && (
                    <p className="text-sm text-blue-200 mb-2">{slide.subtitle}</p>
                  )}
                  {slide.body && (
                    <p className="text-xs text-white/80 whitespace-pre-wrap line-clamp-6">
                      {slide.body.slice(0, 500)}
                    </p>
                  )}
                  {slide.key_points && (
                    <div className="mt-2 text-xs text-white/90 line-clamp-3">{slide.key_points}</div>
                  )}
                </div>
              </div>

              {/* Navigation */}
              <div className="flex items-center justify-between mt-4">
                <button
                  onClick={() => setCurrentSlide(Math.max(0, currentSlide - 1))}
                  disabled={currentSlide === 0}
                  className="px-3 py-1.5 border border-flux-border rounded-lg text-xs hover:border-gray-400 text-flux-dark transition disabled:opacity-30"
                >
                  ← Prev
                </button>
                <span className="text-xs text-flux-muted">
                  {currentSlide + 1} / {slides.length}
                </span>
                <button
                  onClick={() => setCurrentSlide(Math.min(slides.length - 1, currentSlide + 1))}
                  disabled={currentSlide === slides.length - 1}
                  className="px-3 py-1.5 border border-flux-border rounded-lg text-xs hover:border-gray-400 text-flux-dark transition disabled:opacity-30"
                >
                  Next →
                </button>
              </div>

              {/* Thumbnails */}
              <div className="flex gap-1.5 mt-4 overflow-x-auto pb-2">
                {slides.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => setCurrentSlide(i)}
                    className={`flex-shrink-0 w-24 h-14 rounded-md border text-left p-1.5 transition ${
                      i === currentSlide
                        ? "border-flux-blue bg-flux-muted-blue ring-1 ring-flux-blue"
                        : "border-flux-border bg-white hover:border-gray-300"
                    }`}
                  >
                    <div className="text-[7px] text-flux-blue">{s.phase}</div>
                    <div className="text-[8px] text-flux-dark line-clamp-2 leading-tight">{s.title}</div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Footer: Download */}
        {slides.length > 0 && !loading && (
          <div className="px-5 py-4 border-t border-flux-border flex-shrink-0 space-y-2">
            <a
              href={getPptxUrl(projectId)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-flux-blue text-white rounded-lg text-sm hover:bg-flux-blue-hover transition font-medium"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Strategy PPTX
            </a>
            <a
              href={getMeetingPptxUrl(projectId)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-flux-accent text-white rounded-lg text-sm hover:opacity-90 transition font-medium"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Meeting PPTX
            </a>
          </div>
        )}
      </div>
    </>
  );
}
