"use client";

import { Suspense, useEffect, useState, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { runPipelineSSE } from "@/lib/api";

interface StepEvent {
  event: string;
  step_key: string;
  data: string;
  timestamp: number;
}

const STEP_LABELS: Record<string, string> = {
  s1: "Campaign Goal",
  s2: "Market Analysis",
  s3: "Target Insight",
  s4: "Principle Competition",
  s5: "Target Definition",
  s6: "Winning Strategy",
  s7: "Consumer Promise",
  s8: "Creative Strategy",
  slides: "Presentation",
};

const STEP_PHASES: Record<string, string> = {
  s1: "Phase 1", s2: "Phase 1", s3: "Phase 1",
  s4: "Phase 2", s5: "Phase 2", s6: "Phase 2",
  s7: "Phase 3", s8: "Phase 3",
  slides: "Output",
};

function PipelineContent() {
  const params = useSearchParams();
  const router = useRouter();
  const projectId = params.get("projectId");
  const director = params.get("director") || "strategist";

  const [events, setEvents] = useState<StepEvent[]>([]);
  const [currentStep, setCurrentStep] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!projectId) return;
    setIsRunning(true);

    runPipelineSSE(
      projectId,
      director,
      (event, data) => {
        const stepEvent: StepEvent = {
          event,
          step_key: data.step_key,
          data: data.data,
          timestamp: Date.now(),
        };
        setEvents((prev) => [...prev, stepEvent]);

        if (event === "step_start") {
          setCurrentStep(data.step_key);
        }
      },
      (err) => {
        console.error("Pipeline error:", err);
        setIsRunning(false);
      },
      () => {
        setIsRunning(false);
        setIsComplete(true);
      },
    );
  }, [projectId, director]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const completedSteps = events
    .filter((e) => e.event === "step_complete")
    .map((e) => e.step_key);

  const allSteps = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"];
  const progress = (completedSteps.filter((s) => allSteps.includes(s)).length / allSteps.length) * 100;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Pipeline Running</h1>
          <p className="text-sm text-flux-muted/60">
            Director: <span className="text-flux-accent">{director}</span>
          </p>
        </div>
        {isComplete && (
          <a
            href={`/result?projectId=${projectId}`}
            className="px-6 py-2 bg-flux-accent text-white rounded-lg hover:bg-flux-accent-light transition"
          >
            View Results →
          </a>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full bg-white/10 rounded-full h-2 mb-8">
        <div
          className="bg-flux-accent h-2 rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Step indicators */}
      <div className="flex gap-2 mb-8 overflow-x-auto pb-2">
        {allSteps.map((step) => {
          const isDone = completedSteps.includes(step);
          const isCurrent = currentStep === step && isRunning;
          return (
            <div
              key={step}
              className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all ${isDone
                ? "bg-flux-accent/20 text-flux-accent"
                : isCurrent
                  ? "bg-white/20 text-white animate-pulse"
                  : "bg-white/5 text-white/30"
                }`}
            >
              {STEP_LABELS[step] || step}
            </div>
          );
        })}
      </div>

      {/* Event log */}
      <div className="space-y-3">
        {events.map((evt, i) => (
          <div
            key={i}
            className={`p-4 rounded-lg border ${evt.event === "step_complete"
              ? "border-flux-accent/30 bg-flux-accent/5"
              : evt.event === "step_start"
                ? "border-white/10 bg-white/5"
                : evt.event === "case_retrieved"
                  ? "border-green-500/30 bg-green-500/5"
                  : evt.event === "error"
                    ? "border-red-500/30 bg-red-500/5"
                    : "border-white/5 bg-white/[0.02]"
              }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs text-flux-muted/40">
                {STEP_PHASES[evt.step_key] || ""}
              </span>
              <span className="text-xs font-medium text-flux-accent">
                {STEP_LABELS[evt.step_key] || evt.step_key}
              </span>
              <span className="text-xs text-flux-muted/30">
                {evt.event === "step_start" && "▶ 시작"}
                {evt.event === "step_complete" && "✓ 완료"}
                {evt.event === "step_retry" && "↻ 재시도"}
                {evt.event === "case_retrieved" && "📚 사례 참조"}
              </span>
            </div>
            {evt.event === "step_complete" && (
              <p className="text-sm text-flux-muted/70 whitespace-pre-wrap break-words">
                {evt.data}
              </p>
            )}
          </div>
        ))}

        {isRunning && (
          <div className="flex items-center gap-2 text-flux-muted/50 text-sm">
            <div className="w-2 h-2 bg-flux-accent rounded-full animate-ping" />
            Processing...
          </div>
        )}
      </div>
      <div ref={bottomRef} />
    </div>
  );
}

export default function PipelinePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center p-6 text-xl text-flux-muted font-medium">
        Loading Pipeline...
      </div>
    }>
      <PipelineContent />
    </Suspense>
  );
}
