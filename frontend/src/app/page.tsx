export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] text-center">
      <h1 className="text-5xl font-bold text-flux-dark mb-4">
        Concept<span className="text-flux-blue">OS</span>
      </h1>
      <p className="text-xl text-flux-muted mb-2">
        AI-Powered Advertising Strategy & Concept Generator
      </p>
      <p className="text-sm text-flux-muted/70 mb-8 max-w-lg">
        RAG + Ontology 기반으로 할루시네이션 없이 실제 적용 가능한 광고 컨셉을 도출합니다.
        61개 전략 방법론과 21개 우수 캠페인 사례를 기반으로 작동합니다.
      </p>
      <a
        href="/brief"
        className="px-8 py-3 bg-flux-blue text-white font-semibold rounded-lg hover:bg-flux-blue-hover transition"
      >
        Start New Project
      </a>
    </div>
  );
}
