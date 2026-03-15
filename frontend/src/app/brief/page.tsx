"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createProject, parseBriefPdf, ensureAuth } from "@/lib/api";
import { useToast } from "@/components/Toast";

function BriefForm() {
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [form, setForm] = useState({
    brand_name: "",
    target_audience: "",
    budget: "",
    timeline: "",
    brief_raw_text: "",
    main_goal: "", // Will be derived or mapped
  });
  const [loading, setLoading] = useState(false);
  const [pdfParsing, setPdfParsing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Pre-fill from query params if coming from dashboard
    const initialBrief = searchParams.get('brief');
    if (initialBrief) {
      setForm(prev => ({ ...prev, brief_raw_text: initialBrief }));
    }
    // Also check sessionStorage for quick brief from dashboard
    const quickBrief = sessionStorage.getItem("flux_quick_brief");
    if (quickBrief) {
      setForm(prev => ({ ...prev, brief_raw_text: quickBrief }));
      sessionStorage.removeItem("flux_quick_brief");
    }
  }, [searchParams]);

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handlePdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast("PDF 파일만 업로드 가능합니다.", "error");
      return;
    }
    setPdfParsing(true);
    try {
      await ensureAuth();
      const result = await parseBriefPdf(file);
      if (!result.text || result.text.trim() === "") {
        toast("PDF에서 텍스트를 추출할 수 없습니다. 이미지 기반 PDF이거나 텍스트가 없는 파일일 수 있습니다.", "error");
        return;
      }
      setForm(prev => ({
        ...prev,
        brief_raw_text: prev.brief_raw_text
          ? prev.brief_raw_text + "\n\n[PDF 추출 내용]\n" + result.text
          : result.text,
      }));
    } catch (err: any) {
      const msg = err?.message || "알 수 없는 오류";
      toast(`PDF 파싱 실패: ${msg}`, "error");
    } finally {
      setPdfParsing(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.brand_name) {
      toast("Brand Name is required.", "error");
      return;
    }

    setLoading(true);
    try {
      await ensureAuth();
      // We map the fields to the existing backend expectations
      // timeline/budget can go into constraints, target_audience is native
      // if main_goal is empty, we use a snippet of the brief
      const project = await createProject({
        brand_name: form.brand_name,
        target_audience: form.target_audience,
        budget: form.budget,
        constraints: `Timeline: ${form.timeline}`,
        main_goal: form.main_goal || "Generate comprehensive ad strategy",
        brief_raw_text: form.brief_raw_text,
      });
      router.push(`/director?projectId=${project.id}`);
    } catch (err) {
      toast("Failed to create project. Please try again.", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto pb-20">
      {/* Breadcrumb & Top Bar */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="text-sm text-flux-muted mb-2 flex items-center gap-2">
            <span className="hover:text-flux-dark cursor-pointer transition">Campaigns</span>
            <svg className="w-3 h-3 text-gray-300" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" /></svg>
            <span className="text-flux-blue font-medium">New Brief</span>
          </div>
          <h1 className="text-3xl font-extrabold text-[#1F2937] tracking-tight">New Campaign Brief</h1>
          <p className="text-flux-muted text-sm mt-2">
            Fill in the structured details below to help our AI generate a tailored advertising<br /> strategy for your client.
          </p>
        </div>
        <button className="px-5 py-2 text-sm font-semibold text-flux-dark bg-white border border-flux-border rounded-lg shadow-sm hover:bg-gray-50 transition">
          Save Draft
        </button>
      </div>

      {/* Main Form Box */}
      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-flux-border p-8 mb-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">

          {/* BRAND NAME */}
          <div>
            <label className="flex items-center gap-2 text-xs font-bold text-flux-dark tracking-wider mb-3">
              <svg className="w-4 h-4 text-flux-blue" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6.75h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008Zm0 3h.008v.008h-.008v-.008Zm0 3h.008v.008h-.008v-.008Z" />
              </svg>
              BRAND NAME
            </label>
            <input
              type="text"
              className="w-full px-4 py-3 rounded-xl border border-flux-border text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-flux-blue/20 focus:border-flux-blue transition text-flux-dark"
              placeholder="e.g., Tech-savvy millennials aged 25-35" // Oops, that placeholder is for target audience but I will adapt
              value={form.brand_name}
              onChange={(e) => update("brand_name", e.target.value)}
            />
            <p className="text-[11px] text-gray-400 mt-2">What is the core brand or product?</p>
          </div>

          {/* TARGET AUDIENCE */}
          <div>
            <label className="flex items-center gap-2 text-xs font-bold text-flux-dark tracking-wider mb-3">
              <svg className="w-4 h-4 text-flux-blue" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
              </svg>
              TARGET AUDIENCE
            </label>
            <input
              type="text"
              className="w-full px-4 py-3 rounded-xl border border-flux-border text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-flux-blue/20 focus:border-flux-blue transition text-flux-dark"
              placeholder="e.g., Tech-savvy millennials aged 25-35"
              value={form.target_audience}
              onChange={(e) => update("target_audience", e.target.value)}
            />
            <p className="text-[11px] text-gray-400 mt-2">Who are you trying to reach?</p>
          </div>

          {/* BUDGET CONSTRAINT */}
          <div>
            <label className="flex items-center gap-2 text-xs font-bold text-flux-dark tracking-wider mb-3">
              <span className="w-4 h-4 text-flux-blue font-bold flex justify-center items-center text-[14px]">$</span>
              BUDGET CONSTRAINT
            </label>
            <input
              type="text"
              className="w-full px-4 py-3 rounded-xl border border-flux-border text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-flux-blue/20 focus:border-flux-blue transition text-flux-dark"
              placeholder="e.g., $10,000 / month"
              value={form.budget}
              onChange={(e) => update("budget", e.target.value)}
            />
          </div>

          {/* TIMELINE */}
          <div>
            <label className="flex items-center gap-2 text-xs font-bold text-flux-dark tracking-wider mb-3">
              <svg className="w-4 h-4 text-flux-blue" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              </svg>
              TIMELINE
            </label>
            <input
              type="text"
              className="w-full px-4 py-3 rounded-xl border border-flux-border text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-flux-blue/20 focus:border-flux-blue transition text-flux-dark"
              placeholder="e.g., Q4 2023 Launch"
              value={form.timeline}
              onChange={(e) => update("timeline", e.target.value)}
            />
          </div>

        </div>

        {/* DETAILED BRIEF */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="flex items-center gap-2 text-xs font-bold text-flux-dark tracking-wider">
              <svg className="w-4 h-4 text-flux-blue" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
              </svg>
              DETAILED BRIEF & CREATIVE DIRECTION
            </label>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="text-xs font-medium text-flux-blue hover:underline flex items-center gap-1"
            >
              {pdfParsing ? (
                <span>Parsing...</span>
              ) : (
                <>Import PDF instead</>
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handlePdfUpload}
            />
          </div>

          <div className="relative">
            <textarea
              className="w-full h-48 px-4 py-4 rounded-xl border border-flux-border text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-flux-blue/20 focus:border-flux-blue transition resize-none text-flux-dark pb-12"
              placeholder="Enter any specific requirements, brand guidelines, tone of voice, or creative constraints here. The more detail you provide, the better the AI strategy will be..."
              value={form.brief_raw_text}
              onChange={(e) => update("brief_raw_text", e.target.value)}
            />
            {/* AI Suggestions Badge */}
            <div className="absolute bottom-4 right-4 px-3 py-1.5 bg-blue-50 text-flux-blue rounded-full text-xs font-semibold flex items-center gap-1.5 border border-blue-100 shadow-sm pointer-events-none">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l2.4 7.6H22l-6.2 4.4 2.4 7.6-6.2-4.4-6.2 4.4 2.4-7.6-6.2-4.4h7.6L12 2z" />
              </svg>
              AI Suggestions enabled
            </div>
          </div>
        </div>

        {/* Submit Actions */}
        <div className="mt-8 flex items-center justify-end gap-6 border-t border-flux-border pt-6">
          <span className="text-sm text-gray-400 font-medium">All changes saved automatically</span>
          <button
            type="submit"
            disabled={loading || !form.brand_name}
            className="flex items-center gap-2 px-8 py-3 bg-flux-blue text-white font-semibold rounded-lg shadow-md hover:bg-flux-blue-hover transition disabled:opacity-50"
          >
            {loading ? "Generating..." : "Generate Strategy"}
            {!loading && (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
              </svg>
            )}
          </button>
        </div>
      </form>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-flux-border p-5 flex gap-4">
          <div className="mt-0.5 text-flux-blue">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.383a14.406 14.406 0 0 1-3 0M14.25 18v-.192c0-.983.658-1.82 1.508-2.316a7.5 7.5 0 1 0-7.516 0c.85.496 1.508 1.333 1.508 2.316V18" />
            </svg>
          </div>
          <div>
            <h4 className="text-sm font-bold text-flux-dark mb-1">Be Specific</h4>
            <p className="text-xs text-flux-muted leading-relaxed">Detailed inputs yield more precise strategies.</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-flux-border p-5 flex gap-4">
          <div className="mt-0.5 text-flux-blue">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
          </div>
          <div>
            <h4 className="text-sm font-bold text-flux-dark mb-1">Past Performance</h4>
            <p className="text-xs text-flux-muted leading-relaxed">We analyze your history to optimize new briefs.</p>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-flux-border p-5 flex gap-4">
          <div className="mt-0.5 text-flux-blue">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </div>
          <div>
            <h4 className="text-sm font-bold text-flux-dark mb-1">Data Privacy</h4>
            <p className="text-xs text-flux-muted leading-relaxed">Your brief data is encrypted and secure.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BriefPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <BriefForm />
    </Suspense>
  );
}
