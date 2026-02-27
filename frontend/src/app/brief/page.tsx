"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { createProject, parseBriefPdf, ensureAuth } from "@/lib/api";

type InputMode = "manual" | "pdf";

export default function BriefPage() {
  const router = useRouter();
  const [mode, setMode] = useState<InputMode>("manual");
  const [form, setForm] = useState({
    brand_name: "",
    product_service: "",
    industry: "",
    target_audience: "",
    main_goal: "",
    campaign_success: "",
    current_problem: "",
    constraints: "",
    budget: "",
  });
  const [loading, setLoading] = useState(false);

  // PDF state
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfText, setPdfText] = useState("");
  const [pdfParsing, setPdfParsing] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handlePdfSelect = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("PDF 파일만 업로드 가능합니다.");
      return;
    }
    setPdfFile(file);
    setPdfParsing(true);
    try {
      const result = await parseBriefPdf(file);
      setPdfText(result.text);
    } catch (err: any) {
      console.error("PDF parse error:", err);
      alert(`PDF 파싱에 실패했습니다: ${err?.message || "Unknown error"}`);
      setPdfFile(null);
    } finally {
      setPdfParsing(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handlePdfSelect(file);
    },
    [handlePdfSelect]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handlePdfSelect(file);
    },
    [handlePdfSelect]
  );

  const removePdf = () => {
    setPdfFile(null);
    setPdfText("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (mode === "pdf") {
      if (!form.brand_name || !pdfText) return;
      setLoading(true);
      try {
        await ensureAuth();
        const project = await createProject({
          brand_name: form.brand_name,
          brief_raw_text: pdfText,
          industry: form.industry || undefined,
        });
        router.push(`/director?projectId=${project.id}`);
      } catch (err) {
        alert("프로젝트 생성에 실패했습니다. 다시 시도해주세요.");
      } finally {
        setLoading(false);
      }
    } else {
      if (!form.brand_name || !form.main_goal) return;
      setLoading(true);
      try {
        await ensureAuth();
        const project = await createProject(form);
        router.push(`/director?projectId=${project.id}`);
      } catch (err) {
        alert("프로젝트 생성에 실패했습니다. 다시 시도해주세요.");
      } finally {
        setLoading(false);
      }
    }
  };

  const canSubmit =
    mode === "pdf"
      ? !!form.brand_name && !!pdfText && !pdfParsing
      : !!form.brand_name && !!form.main_goal;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2">New Campaign Brief</h1>
      <p className="text-flux-muted/60 mb-8">
        광고 캠페인 기본 정보를 입력해주세요. 직접 입력하거나 PDF 브리프를 업로드할 수 있습니다.
      </p>

      {/* Mode Tabs */}
      <div className="flex gap-1 mb-8 bg-white/5 rounded-lg p-1">
        <button
          type="button"
          onClick={() => setMode("manual")}
          className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition ${
            mode === "manual"
              ? "bg-flux-accent text-white"
              : "text-white/60 hover:text-white"
          }`}
        >
          직접 입력
        </button>
        <button
          type="button"
          onClick={() => setMode("pdf")}
          className={`flex-1 py-2.5 px-4 rounded-md text-sm font-medium transition ${
            mode === "pdf"
              ? "bg-flux-accent text-white"
              : "text-white/60 hover:text-white"
          }`}
        >
          PDF 업로드
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Brand name - always visible */}
        <Field
          label="브랜드/제품명 *"
          value={form.brand_name}
          onChange={(v) => update("brand_name", v)}
          placeholder="예: 삼양식품 불닭소스"
        />

        {mode === "pdf" ? (
          <>
            {/* PDF Upload Zone */}
            <div>
              <label className="block text-sm font-medium text-flux-muted/80 mb-1">
                브리프 PDF 파일 *
              </label>

              {!pdfFile ? (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(true);
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition ${
                    dragOver
                      ? "border-flux-accent bg-flux-accent/10"
                      : "border-white/20 hover:border-flux-accent/50 hover:bg-white/5"
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    onChange={handleFileInput}
                    className="hidden"
                  />
                  <svg
                    className="mx-auto h-12 w-12 text-white/30 mb-3"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                    />
                  </svg>
                  <p className="text-white/60 text-sm">
                    PDF 파일을 드래그하거나{" "}
                    <span className="text-flux-accent font-medium">클릭하여 선택</span>
                    하세요
                  </p>
                  <p className="text-white/30 text-xs mt-1">PDF 형식만 지원</p>
                </div>
              ) : (
                <div className="border border-white/10 rounded-lg p-4">
                  {/* File info */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-red-500/20 rounded-lg flex items-center justify-center">
                        <svg
                          className="w-5 h-5 text-red-400"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={1.5}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                          />
                        </svg>
                      </div>
                      <div>
                        <p className="text-white text-sm font-medium">
                          {pdfFile.name}
                        </p>
                        <p className="text-white/40 text-xs">
                          {(pdfFile.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={removePdf}
                      className="text-white/40 hover:text-red-400 transition p-1"
                    >
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={1.5}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>

                  {/* Parsing status / extracted text */}
                  {pdfParsing ? (
                    <div className="flex items-center gap-2 text-flux-accent text-sm py-4">
                      <svg
                        className="w-4 h-4 animate-spin"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        />
                      </svg>
                      PDF 내용을 분석하고 있습니다...
                    </div>
                  ) : pdfText ? (
                    <div>
                      <label className="block text-xs font-medium text-flux-muted/60 mb-1">
                        추출된 브리프 내용
                      </label>
                      <textarea
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-flux-accent transition min-h-[200px] text-sm"
                        value={pdfText}
                        onChange={(e) => setPdfText(e.target.value)}
                      />
                      <p className="text-white/30 text-xs mt-1">
                        추출된 내용을 확인하고 필요시 수정할 수 있습니다.
                      </p>
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            {/* Optional fields for PDF mode */}
            <Field
              label="산업분야/카테고리"
              value={form.industry}
              onChange={(v) => update("industry", v)}
              placeholder="예: 식음료"
            />
          </>
        ) : (
          <>
            {/* Manual entry fields */}
            <Field
              label="제품/서비스"
              value={form.product_service}
              onChange={(v) => update("product_service", v)}
              placeholder="예: 불닭소스 글로벌 확장"
            />
            <Field
              label="산업분야/카테고리"
              value={form.industry}
              onChange={(v) => update("industry", v)}
              placeholder="예: 식음료"
            />
            <Field
              label="타겟 오디언스"
              value={form.target_audience}
              onChange={(v) => update("target_audience", v)}
              placeholder="예: MZ세대 글로벌 매운맛 팬"
            />
            <Field
              label="캠페인 목표 *"
              value={form.main_goal}
              onChange={(v) => update("main_goal", v)}
              placeholder="예: 불닭소스의 글로벌 인지도를 높이고 신규 시장 진출"
              multiline
            />
            <Field
              label="캠페인의 성공 모습"
              value={form.campaign_success}
              onChange={(v) => update("campaign_success", v)}
              placeholder="예: SNS에서 불닭소스 챌린지가 바이럴되고, 해외 매출 30% 증가"
              multiline
            />
            <Field
              label="현재 상황의 문제"
              value={form.current_problem}
              onChange={(v) => update("current_problem", v)}
              placeholder="예: 국내에서는 1위이지만, 해외에서는 '극한 매운맛' 이미지에 갇혀 있음"
              multiline
            />
            <Field
              label="제약조건"
              value={form.constraints}
              onChange={(v) => update("constraints", v)}
              placeholder="예: 예산 5억, 3개월 내 론칭"
            />
            <Field
              label="예산"
              value={form.budget}
              onChange={(v) => update("budget", v)}
              placeholder="예: High / Medium / Low"
            />
          </>
        )}

        <button
          type="submit"
          disabled={loading || !canSubmit}
          className="w-full py-3 bg-flux-accent text-white font-semibold rounded-lg hover:bg-flux-accent-light transition disabled:opacity-50"
        >
          {loading ? "Creating..." : "다음: 디렉터 선택 →"}
        </button>
      </form>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  multiline,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  multiline?: boolean;
}) {
  const cls =
    "w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-flux-accent transition";
  return (
    <div>
      <label className="block text-sm font-medium text-flux-muted/80 mb-1">
        {label}
      </label>
      {multiline ? (
        <textarea
          className={cls + " min-h-[80px]"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      ) : (
        <input
          type="text"
          className={cls}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      )}
    </div>
  );
}
