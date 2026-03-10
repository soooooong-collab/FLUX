"use client";

import { Suspense, useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { runPipelineSSE, DiscussionTurn } from "@/lib/api";

/* ── Types ── */

interface StepEvent {
  event: string;
  step_key: string;
  data: string;
  timestamp: number;
}

/* ── Constants ── */

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

const STEP_LABELS_KR: Record<string, string> = {
  s1: "캠페인 목표",
  s2: "시장 분석",
  s3: "타겟 인사이트",
  s4: "본질적 경쟁",
  s5: "타겟 정의",
  s6: "승리 전략",
  s7: "소비자 약속",
  s8: "크리에이티브 전략",
  slides: "프레젠테이션",
};

const STEP_PHASES: Record<string, string> = {
  s1: "Phase 1",
  s2: "Phase 1",
  s3: "Phase 1",
  s4: "Phase 2",
  s5: "Phase 2",
  s6: "Phase 2",
  s7: "Phase 3",
  s8: "Phase 3",
  slides: "Output",
};

const AGENT_CONFIG: Record<
  string,
  { label: string; labelKr: string; color: string; bgColor: string; borderColor: string; icon: string }
> = {
  orchestrator: {
    label: "Chief Director",
    labelKr: "팀장",
    color: "text-amber-700",
    bgColor: "bg-amber-50",
    borderColor: "border-amber-200",
    icon: "👑",
  },
  account_planner: {
    label: "Account Planner",
    labelKr: "AP",
    color: "text-blue-700",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
    icon: "📊",
  },
  brand_strategist: {
    label: "Brand Strategist",
    labelKr: "BS",
    color: "text-purple-700",
    bgColor: "bg-purple-50",
    borderColor: "border-purple-200",
    icon: "🎯",
  },
  creative_director: {
    label: "Creative Director",
    labelKr: "CD",
    color: "text-pink-700",
    bgColor: "bg-pink-50",
    borderColor: "border-pink-200",
    icon: "💡",
  },
};

const TURN_TYPE_LABELS: Record<string, string> = {
  framing: "프레이밍",
  analysis: "리드 분석",
  reaction: "반응",
  synthesis: "종합",
};

const DIRECTOR_LABELS: Record<string, string> = {
  strategist: "The Strategist",
  provocateur: "The Provocateur",
  storyteller: "The Storyteller",
  emotional_minimalist: "The Emotional Minimalist",
  culture_hacker: "The Culture Hacker",
  performance_hacker: "The Performance Hacker",
};

/* ── Components ── */

function AgentAvatar({ speaker }: { speaker: string }) {
  const config = AGENT_CONFIG[speaker] || AGENT_CONFIG.orchestrator;
  return (
    <div
      className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${config.bgColor} ${config.borderColor} border flex-shrink-0`}
    >
      {config.icon}
    </div>
  );
}

function TurnTypeBadge({ turnType }: { turnType: string }) {
  const colors: Record<string, string> = {
    framing: "bg-amber-100 text-amber-700",
    analysis: "bg-blue-100 text-blue-700",
    reaction: "bg-gray-100 text-gray-600",
    synthesis: "bg-emerald-100 text-emerald-700",
  };
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${colors[turnType] || "bg-gray-100 text-gray-500"}`}
    >
      {TURN_TYPE_LABELS[turnType] || turnType}
    </span>
  );
}

function DiscussionTurnCard({ turn, isLatest }: { turn: DiscussionTurn; isLatest: boolean }) {
  const config = AGENT_CONFIG[turn.speaker] || AGENT_CONFIG.orchestrator;
  const isSynthesis = turn.type === "synthesis";

  return (
    <div className={`flex gap-3 ${isLatest ? "animate-fadeIn" : ""} ${isSynthesis ? "mt-2" : ""}`}>
      <AgentAvatar speaker={turn.speaker} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-sm font-semibold ${config.color}`}>{config.labelKr}</span>
          <span className="text-xs text-gray-400">{config.label}</span>
          <TurnTypeBadge turnType={turn.type} />
          {isSynthesis && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500 text-white font-bold">
              FINAL
            </span>
          )}
        </div>
        <div
          className={`text-sm leading-relaxed whitespace-pre-wrap break-words rounded-lg p-3 ${
            isSynthesis
              ? "bg-emerald-50 border-2 border-emerald-200 text-gray-800"
              : turn.type === "framing"
                ? `${config.bgColor} ${config.borderColor} border text-gray-700`
                : "bg-gray-50 border border-gray-100 text-gray-700"
          }`}
        >
          {turn.content}
        </div>
      </div>
    </div>
  );
}

function StepDiscussion({
  stepKey,
  turns,
  isActive,
  isComplete,
}: {
  stepKey: string;
  turns: DiscussionTurn[];
  isActive: boolean;
  isComplete: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Auto-collapse when step completes and next step starts
  useEffect(() => {
    if (isComplete && !isActive) {
      setIsExpanded(false);
    }
  }, [isComplete, isActive]);

  return (
    <div
      className={`rounded-xl border overflow-hidden transition-all ${
        isActive
          ? "border-blue-200 shadow-md shadow-blue-50"
          : isComplete
            ? "border-gray-200"
            : "border-gray-100 opacity-60"
      }`}
    >
      {/* Step Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50 transition"
      >
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400 font-mono">{STEP_PHASES[stepKey]}</span>
          <span className="text-sm font-bold text-flux-dark">{STEP_LABELS_KR[stepKey]}</span>
          <span className="text-xs text-gray-400">{STEP_LABELS[stepKey]}</span>
          {isActive && (
            <div className="flex items-center gap-1 text-flux-blue">
              <div className="w-1.5 h-1.5 bg-flux-blue rounded-full animate-ping" />
              <span className="text-xs font-medium">진행 중</span>
            </div>
          )}
          {isComplete && !isActive && (
            <span className="text-xs text-emerald-600 font-medium">✓ 완료</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {turns.length > 0 && <span className="text-xs text-gray-400">{turns.length}턴</span>}
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Discussion Turns */}
      {isExpanded && turns.length > 0 && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3">
          {turns.map((turn, i) => (
            <DiscussionTurnCard
              key={`${stepKey}-${turn.turn_number}`}
              turn={turn}
              isLatest={i === turns.length - 1 && isActive}
            />
          ))}
        </div>
      )}

      {/* Collapsed summary: show synthesis only */}
      {!isExpanded && isComplete && turns.length > 0 && (
        <div className="px-4 pb-3 border-t border-gray-100 pt-2">
          {(() => {
            const synthesisTurn = turns.find((t) => t.type === "synthesis");
            if (!synthesisTurn) return null;
            return (
              <div className="text-sm text-gray-600 whitespace-pre-wrap break-words line-clamp-3">
                <span className="text-emerald-600 font-semibold mr-1">종합:</span>
                {synthesisTurn.content.slice(0, 200)}
                {synthesisTurn.content.length > 200 && "..."}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

/* ── Main Component ── */

function PipelineContent() {
  const params = useSearchParams();
  const router = useRouter();
  const projectId = params.get("projectId");
  const director = params.get("director") || "strategist";

  const [events, setEvents] = useState<StepEvent[]>([]);
  const [discussions, setDiscussions] = useState<Record<string, DiscussionTurn[]>>({});
  const [currentStep, setCurrentStep] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const handleEvent = useCallback((event: string, data: any) => {
    if (event === "discussion_turn") {
      const turn: DiscussionTurn = data.data;
      setDiscussions((prev) => ({
        ...prev,
        [turn.step_key]: [...(prev[turn.step_key] || []), turn],
      }));
      return;
    }

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
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setIsRunning(true);

    runPipelineSSE(
      projectId,
      director,
      handleEvent,
      (err) => {
        console.error("Pipeline error:", err);
        setIsRunning(false);
      },
      () => {
        setIsRunning(false);
        setIsComplete(true);
      },
    );
  }, [projectId, director, handleEvent]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [discussions, events]);

  const completedSteps = events
    .filter((e) => e.event === "step_complete")
    .map((e) => e.step_key);

  const allSteps = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"];
  const progress =
    (completedSteps.filter((s) => allSteps.includes(s)).length / allSteps.length) * 100;

  const directorLabel = DIRECTOR_LABELS[director] || director;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold text-flux-dark">Team Discussion</h1>
          <p className="text-sm text-gray-500 mt-1">
            Director: <span className="text-flux-blue font-semibold">{directorLabel}</span>
            <span className="text-gray-400 ml-2">— AP, BS, CD가 함께 논의합니다</span>
          </p>
        </div>
        {isComplete && (
          <a
            href={`/result?projectId=${projectId}`}
            className="px-6 py-2.5 bg-flux-blue text-white rounded-lg hover:bg-flux-blue-hover transition font-medium shadow-sm"
          >
            결과 보기 →
          </a>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-100 rounded-full h-1.5 mb-6">
        <div
          className="bg-flux-blue h-1.5 rounded-full transition-all duration-700 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Step pills */}
      <div className="flex gap-1.5 mb-8 overflow-x-auto pb-2">
        {allSteps.map((step) => {
          const isDone = completedSteps.includes(step);
          const isCurrent = currentStep === step && isRunning;
          return (
            <div
              key={step}
              className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                isDone
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : isCurrent
                    ? "bg-blue-50 text-flux-blue border border-blue-200 animate-pulse"
                    : "bg-gray-50 text-gray-400 border border-gray-100"
              }`}
            >
              {STEP_LABELS_KR[step]}
            </div>
          );
        })}
      </div>

      {/* Team members indicator */}
      <div className="flex items-center gap-4 mb-6 px-1">
        <span className="text-xs text-gray-400 font-medium">참여 에이전트:</span>
        {Object.entries(AGENT_CONFIG).map(([key, config]) => (
          <div key={key} className="flex items-center gap-1">
            <span className="text-sm">{config.icon}</span>
            <span className={`text-xs font-medium ${config.color}`}>{config.labelKr}</span>
          </div>
        ))}
      </div>

      {/* Discussion Panels */}
      <div className="space-y-4">
        {allSteps.map((step) => {
          const turns = discussions[step] || [];
          const hasStarted = events.some((e) => e.step_key === step && e.event === "step_start");
          const isDone = completedSteps.includes(step);
          const isCurrent = currentStep === step && isRunning;

          if (!hasStarted && turns.length === 0) return null;

          return (
            <StepDiscussion
              key={step}
              stepKey={step}
              turns={turns}
              isActive={isCurrent}
              isComplete={isDone}
            />
          );
        })}

        {/* Slides generation indicator */}
        {events.some((e) => e.step_key === "slides" && e.event === "step_start") && (
          <div className="rounded-xl border border-gray-200 px-4 py-3 bg-white">
            <div className="flex items-center gap-3">
              <span className="text-sm">📑</span>
              <span className="text-sm font-bold text-flux-dark">{STEP_LABELS_KR.slides}</span>
              {completedSteps.includes("slides") ? (
                <span className="text-xs text-emerald-600 font-medium">✓ 생성 완료</span>
              ) : (
                <div className="flex items-center gap-1 text-flux-blue">
                  <div className="w-1.5 h-1.5 bg-flux-blue rounded-full animate-ping" />
                  <span className="text-xs font-medium">생성 중...</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Running indicator */}
        {isRunning && !currentStep.startsWith("slide") && (
          <div className="flex items-center gap-2 text-gray-400 text-sm px-1">
            <div className="w-2 h-2 bg-flux-blue rounded-full animate-ping" />
            팀 토론 진행 중...
          </div>
        )}
      </div>

      <div ref={bottomRef} className="h-8" />

      {/* Global animation styles */}
      <style jsx global>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}

export default function PipelinePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center p-6 text-xl text-gray-400 font-medium">
          Loading Pipeline...
        </div>
      }
    >
      <PipelineContent />
    </Suspense>
  );
}
