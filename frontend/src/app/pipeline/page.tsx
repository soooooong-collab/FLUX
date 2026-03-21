"use client";

import { Suspense, useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { runPipelineSSE, DiscussionTurn, getDiscussionTranscript, getMeetingPptxUrl } from "@/lib/api";
import SlideArtifactPanel from "@/components/SlideArtifactPanel";

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
              key={`${stepKey}-${turn.turn_number}-${turn.speaker}-${turn.type}-${i}`}
              turn={turn}
              isLatest={i === turns.length - 1 && isActive}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Main Component ── */

function PipelineContent() {
  const params = useSearchParams();
  const projectId = params.get("projectId");
  const director = params.get("director") || "strategist";

  const [events, setEvents] = useState<StepEvent[]>([]);
  const [discussions, setDiscussions] = useState<Record<string, DiscussionTurn[]>>({});
  const [currentStep, setCurrentStep] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [runAttempt, setRunAttempt] = useState(0);
  const [transcriptBusy, setTranscriptBusy] = useState<"copy" | "save" | null>(null);
  const [transcriptNotice, setTranscriptNotice] = useState("");
  const [isArtifactOpen, setIsArtifactOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const startedRunKeyRef = useRef("");

  const handleEvent = useCallback((event: string, data: any) => {
    if (event === "discussion_turn") {
      const turn: DiscussionTurn | undefined = (data?.data || data) as DiscussionTurn | undefined;
      if (!turn?.step_key) return;
      setDiscussions((prev) => ({
        ...prev,
        [turn.step_key]: (() => {
          const current = prev[turn.step_key] || [];
          const duplicate = current.some(
            (t) =>
              t.turn_number === turn.turn_number &&
              t.speaker === turn.speaker &&
              t.type === turn.type &&
              t.content === turn.content,
          );
          if (duplicate) return current;
          return [...current, turn].sort((a, b) => a.turn_number - b.turn_number);
        })(),
      }));
      return;
    }
    if (event === "error") {
      setErrorMessage(data?.error || "파이프라인 실행 중 오류가 발생했습니다.");
      setIsRunning(false);
      return;
    }
    if (!data?.step_key) return;

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
    const runKey = `${projectId}:${director}:${runAttempt}`;
    if (startedRunKeyRef.current === runKey) return;
    startedRunKeyRef.current = runKey;

    setEvents([]);
    setDiscussions({});
    setCurrentStep("");
    setIsComplete(false);
    setErrorMessage("");
    setIsRunning(true);

    runPipelineSSE(
      projectId,
      director,
      handleEvent,
      (err) => {
        console.error("Pipeline error:", err);
        const msg = typeof err?.message === "string"
          ? err.message
          : "파이프라인 실행 중 오류가 발생했습니다.";
        setErrorMessage(
          msg.includes("409")
            ? "이미 실행 중인 프로젝트입니다. 기존 실행이 끝난 뒤 다시 시도해주세요."
            : msg,
        );
        setIsRunning(false);
        setIsComplete(false);
      },
      () => {
        setIsRunning(false);
        setIsComplete(true);
      },
    );
  }, [projectId, director, handleEvent, runAttempt]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [discussions, events]);

  const completedSteps = events
    .filter((e) => e.event === "step_complete")
    .map((e) => e.step_key);
  const hasDiscussionTurns = Object.values(discussions).some((turns) => turns.length > 0);

  const allSteps = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"];
  const progress =
    (completedSteps.filter((s) => allSteps.includes(s)).length / allSteps.length) * 100;

  const directorLabel = DIRECTOR_LABELS[director] || director;
  const showTranscriptActions = Boolean(projectId) && (isComplete || hasDiscussionTurns);

  const handleCopyTranscript = useCallback(async () => {
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
  }, [projectId]);

  const handleSaveTranscript = useCallback(async () => {
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
  }, [projectId]);

  return (
    <div className={`max-w-4xl mx-auto transition-all duration-300 ${isArtifactOpen ? "mr-[520px]" : ""}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold text-flux-dark">Team Discussion</h1>
          <p className="text-sm text-gray-500 mt-1">
            Director: <span className="text-flux-blue font-semibold">{directorLabel}</span>
            <span className="text-gray-400 ml-2">— AP, BS, CD가 함께 논의합니다</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {showTranscriptActions && (
            <>
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
              {isComplete && (
                <a
                  href={getMeetingPptxUrl(projectId!)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3.5 py-2 bg-flux-accent text-white rounded-lg text-sm hover:opacity-90 transition font-medium"
                >
                  Meeting PPTX
                </a>
              )}
            </>
          )}
          {isComplete && (
            <button
              onClick={() => setIsArtifactOpen(true)}
              className="px-6 py-2.5 bg-flux-blue text-white rounded-lg hover:bg-flux-blue-hover transition font-medium shadow-sm"
            >
              PPTX 생성결과
            </button>
          )}
        </div>
      </div>
      {transcriptNotice && (
        <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm text-blue-700">
          {transcriptNotice}
        </div>
      )}

      {/* Progress bar */}
      {errorMessage && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700 whitespace-pre-wrap break-words">{errorMessage}</p>
          <button
            onClick={() => setRunAttempt((prev) => prev + 1)}
            className="mt-2 inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md border border-red-300 text-red-700 hover:bg-red-100 transition"
          >
            다시 실행
          </button>
        </div>
      )}

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
        {isRunning && currentStep && !currentStep.startsWith("slide") && (
          <div className="flex items-center gap-2 text-gray-400 text-sm px-1">
            <div className="w-2 h-2 bg-flux-blue rounded-full animate-ping" />
            팀 토론 진행 중...
          </div>
        )}
      </div>

      <div ref={bottomRef} className="h-8" />

      {/* Slide Artifact Panel */}
      {projectId && (
        <SlideArtifactPanel
          projectId={projectId}
          isOpen={isArtifactOpen}
          onClose={() => setIsArtifactOpen(false)}
        />
      )}

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
