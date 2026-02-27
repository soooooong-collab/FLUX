"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getSlides, getPptxUrl } from "@/lib/api";

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
  cover: "from-flux-dark to-flux-deeper",
  phase1: "from-blue-900/30 to-flux-dark",
  phase2: "from-purple-900/30 to-flux-dark",
  phase3: "from-flux-accent/10 to-flux-dark",
};

function ResultContent() {
  const params = useSearchParams();
  const projectId = params.get("projectId");

  const [slides, setSlides] = useState<Slide[]>([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [title, setTitle] = useState("");

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
      <div className="flex items-center justify-center min-h-[50vh] text-flux-muted/50">
        Loading slides...
      </div>
    );
  }

  const slide = slides[currentSlide];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        <a
          href={getPptxUrl(projectId!)}
          className="px-4 py-2 bg-flux-accent text-white rounded-lg text-sm hover:bg-flux-accent-light transition"
          target="_blank"
        >
          Download PPTX
        </a>
      </div>

      {/* Slide preview */}
      <div
        className={`relative w-full aspect-[16/9] rounded-2xl border border-white/10 overflow-hidden bg-gradient-to-br ${PHASE_COLORS[slide.phase] || PHASE_COLORS.cover
          } mb-6`}
      >
        <div className="absolute inset-0 p-12 flex flex-col justify-center">
          {slide.phase && (
            <div className="text-xs font-semibold text-flux-accent uppercase tracking-widest mb-4">
              {slide.phase}
            </div>
          )}
          <h2 className="text-3xl font-bold text-white mb-2">{slide.title}</h2>
          {slide.subtitle && (
            <p className="text-lg text-flux-accent mb-4">{slide.subtitle}</p>
          )}
          {slide.body && (
            <p className="text-sm text-flux-muted/70 whitespace-pre-wrap max-h-[50%] overflow-y-auto">
              {slide.body.slice(0, 1000)}
            </p>
          )}
          {slide.key_points && (
            <div className="mt-4 text-sm text-white/80">{slide.key_points}</div>
          )}
        </div>
      </div>

      {/* Slide navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setCurrentSlide(Math.max(0, currentSlide - 1))}
          disabled={currentSlide === 0}
          className="px-4 py-2 border border-white/10 rounded-lg text-sm hover:border-white/30 transition disabled:opacity-30"
        >
          ← Previous
        </button>
        <span className="text-sm text-flux-muted/50">
          {currentSlide + 1} / {slides.length}
        </span>
        <button
          onClick={() => setCurrentSlide(Math.min(slides.length - 1, currentSlide + 1))}
          disabled={currentSlide === slides.length - 1}
          className="px-4 py-2 border border-white/10 rounded-lg text-sm hover:border-white/30 transition disabled:opacity-30"
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
                ? "border-flux-accent bg-flux-accent/10"
                : "border-white/10 hover:border-white/20"
              }`}
          >
            <div className="text-[8px] text-flux-accent">{s.phase}</div>
            <div className="text-[10px] text-white line-clamp-2">{s.title}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ResultPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-[50vh] text-flux-muted/50">
        Loading...
      </div>
    }>
      <ResultContent />
    </Suspense>
  );
}
