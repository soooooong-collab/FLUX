"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { listDirectors } from "@/lib/api";

interface Director {
  id: number;
  name: string;
  tagline: string;
  archetype: string;
  description: string;
  recommended_for: string;
  weights: Record<string, number>;
}

const ARCHETYPE_COLORS: Record<string, string> = {
  strategist: "border-blue-500 bg-blue-50",
  provocateur: "border-red-500 bg-red-50",
  storyteller: "border-purple-500 bg-purple-50",
  emotional_minimalist: "border-pink-400 bg-pink-50",
  culture_hacker: "border-green-500 bg-green-50",
  performance_hacker: "border-yellow-500 bg-yellow-50",
};

function DirectorContent() {
  const router = useRouter();
  const params = useSearchParams();
  const projectId = params.get("projectId");

  const [directors, setDirectors] = useState<Director[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    listDirectors().then(setDirectors).catch(console.error);
  }, []);

  const handleStart = () => {
    if (!selected || !projectId) return;
    router.push(`/pipeline?projectId=${projectId}&director=${selected}`);
  };

  return (
    <div>
      <h1 className="text-3xl font-extrabold text-flux-dark mb-2">Choose Your Director</h1>
      <p className="text-flux-muted mb-8">
        디렉터의 스타일에 따라 전략 접근 방식과 레퍼런스 활용 시점이 달라집니다.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {directors.map((d) => (
          <button
            key={d.archetype}
            onClick={() => setSelected(d.archetype)}
            className={`text-left p-5 rounded-2xl border-2 transition-all ${selected === d.archetype
              ? `${ARCHETYPE_COLORS[d.archetype] || "border-flux-blue bg-flux-muted-blue"}`
              : "border-flux-border bg-white hover:border-gray-300 hover:shadow-sm"
              }`}
          >
            <div className="text-lg font-bold text-flux-dark">{d.name}</div>
            <div className="text-flux-blue text-sm mb-2">{d.tagline}</div>
            <p className="text-xs text-flux-muted line-clamp-3">
              {d.description}
            </p>
            <div className="mt-3 text-xs text-gray-400">
              추천: {d.recommended_for?.slice(0, 60)}...
            </div>
          </button>
        ))}
      </div>

      <button
        onClick={handleStart}
        disabled={!selected}
        className="w-full py-3 bg-flux-blue text-white font-semibold rounded-lg hover:bg-flux-blue-hover transition disabled:opacity-50"
      >
        {selected ? `${selected} 디렉터로 시작 →` : "디렉터를 선택해주세요"}
      </button>
    </div>
  );
}

export default function DirectorPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-[50vh] text-flux-muted">
        Loading...
      </div>
    }>
      <DirectorContent />
    </Suspense>
  );
}
