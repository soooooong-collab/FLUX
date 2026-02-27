"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { parseBriefPdf, ensureAuth } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [briefText, setBriefText] = useState("");
  const [pdfParsing, setPdfParsing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleGenerate = () => {
    if (briefText.trim()) {
      // Pass the brief text via sessionStorage so it survives navigation
      sessionStorage.setItem("flux_quick_brief", briefText);
    }
    router.push(`/brief`);
  };

  const handlePdfImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("PDF 파일만 업로드 가능합니다.");
      return;
    }
    setPdfParsing(true);
    try {
      await ensureAuth();
      const result = await parseBriefPdf(file);
      setBriefText((prev) => prev + (prev ? "\n\n" : "") + result.text);
    } catch (err: any) {
      alert(`PDF 파싱 실패: ${err?.message || "Unknown error"}`);
    } finally {
      setPdfParsing(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleTemplate = (templateId: string) => {
    router.push(`/brief?template=${templateId}`);
  };

  return (
    <div className="flex flex-col items-center justify-center max-w-4xl mx-auto py-10">

      {/* Hero Section */}
      <div className="text-center mb-10 w-full">
        <h1 className="text-5xl font-extrabold text-[#1F2937] tracking-tight mb-2">
          Generate Advertising
          <br />
          <span className="text-flux-blue">Strategy</span>
        </h1>
        <p className="text-flux-muted text-lg mt-4 max-w-2xl mx-auto">
          Paste your client brief below to generate a comprehensive AI strategy tailored
          <br className="hidden md:block" /> to your objectives and audience.
        </p>
      </div>

      {/* Quick Brief Box */}
      <div className="w-full bg-white rounded-2xl shadow-sm border border-flux-border mb-12">
        {/* Header */}
        <div className="flex justify-between items-center px-6 py-4 border-b border-flux-border">
          <div className="flex items-center gap-2 text-xs font-semibold text-flux-muted tracking-wide uppercase">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
            Client Brief
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={pdfParsing}
            className="flex items-center gap-1.5 text-xs font-medium text-flux-blue hover:text-blue-700 transition disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
            </svg>
            {pdfParsing ? "Parsing..." : "Import PDF"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={handlePdfImport}
          />
        </div>

        {/* Text Area */}
        <div className="p-6 relative">
          <textarea
            className="w-full h-40 resize-none text-flux-dark placeholder:text-gray-400 focus:outline-none focus:ring-0 border-none p-0 text-base bg-transparent"
            placeholder="e.g. Create a marketing strategy for a new organic coffee brand targeting young professionals in urban areas. Key objective is brand awareness. Budget is $50k..."
            value={briefText}
            onChange={(e) => setBriefText(e.target.value)}
          />
          <div className="absolute bottom-6 right-6 text-xs text-gray-400 font-medium">
            {briefText.trim().split(/\s+/).filter(w => w.length > 0).length} / 2000 words
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50/50 rounded-b-2xl border-t border-flux-border flex justify-between items-center">
          <div className="flex items-center gap-4 text-gray-400">
            <button className="hover:text-gray-600 transition">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
              </svg>
            </button>
            <button className="hover:text-gray-600 transition">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
              </svg>
            </button>
          </div>
          <button
            onClick={handleGenerate}
            className="flex items-center gap-2 px-6 py-2.5 bg-flux-blue text-white text-sm font-semibold rounded-lg hover:bg-flux-blue-hover transition"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
            </svg>
            Generate Strategy
          </button>
        </div>
      </div>

      {/* Templates Section */}
      <div className="w-full">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xs font-semibold text-flux-muted uppercase tracking-wide">
            Start from a template
          </h2>
          <button className="text-sm font-medium text-flux-blue hover:underline">
            View all
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Template 1: PPC */}
          <button
            onClick={() => handleTemplate('ppc')}
            className="text-left bg-white p-6 rounded-2xl border border-flux-border hover:shadow-md hover:border-blue-200 transition group"
          >
            <div className="flex justify-between items-start mb-4">
              <div className="w-10 h-10 rounded-xl bg-orange-100 flex items-center justify-center text-orange-500">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 1 1 0-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 0 1-1.44-4.282m3.102.069a18.03 18.03 0 0 1-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 0 1 8.835 2.535M10.34 6.66a23.847 23.847 0 0 0 8.835-2.535m0 0A23.74 23.74 0 0 0 18.795 3m.38 1.125a23.91 23.91 0 0 1 1.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 0 0 1.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 0 1 0 3.46" />
                </svg>
              </div>
              <svg className="w-5 h-5 text-gray-300 group-hover:text-flux-blue transition" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
              </svg>
            </div>
            <h3 className="font-semibold text-flux-dark mb-2">PPC Campaign</h3>
            <p className="text-sm text-flux-muted leading-relaxed">
              Structure a pay-per-click campaign for Google and Social Media ads.
            </p>
          </button>

          {/* Template 2: Product Launch */}
          <button
            onClick={() => handleTemplate('launch')}
            className="text-left bg-white p-6 rounded-2xl border border-flux-border hover:shadow-md hover:border-blue-200 transition group"
          >
            <div className="flex justify-between items-start mb-4">
              <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center text-purple-500">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.59 14.37a6 6 0 0 1-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 0 0 6.16-12.12A14.98 14.98 0 0 0 9.631 8.41m5.96 5.96a14.926 14.926 0 0 1-5.841 2.58m-.119-8.54a6 6 0 0 0-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 0 0-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 0 1-2.448-2.448 14.9 14.9 0 0 1 .06-.312m-2.24 2.39a4.493 4.493 0 0 0-1.757 4.306 4.438 4.438 0 0 0 2.746 2.746 4.493 4.493 0 0 0 4.306-1.758c.16-.24.313-.492.459-.753m-8.693-1.28a1.5 1.5 0 0 1-1.36-1.36m-1.36-4.644c-.261.146-.513.3-.753.459a4.493 4.493 0 0 0-1.758 4.306 4.438 4.438 0 0 0 2.746 2.746 4.493 4.493 0 0 0 4.306-1.758c.24-.16.492-.313.753-.459" />
                </svg>
              </div>
              <svg className="w-5 h-5 text-gray-300 group-hover:text-flux-blue transition" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
              </svg>
            </div>
            <h3 className="font-semibold text-flux-dark mb-2">Product Launch</h3>
            <p className="text-sm text-flux-muted leading-relaxed">
              Go-to-market strategy including timeline, channels, and key...
            </p>
          </button>

          {/* Template 3: Social Media */}
          <button
            onClick={() => handleTemplate('social')}
            className="text-left bg-white p-6 rounded-2xl border border-flux-border hover:shadow-md hover:border-blue-200 transition group"
          >
            <div className="flex justify-between items-start mb-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-500">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.217 10.907a2.25 2.25 0 1 0 0 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186 9.566-5.314m-9.566 7.5 9.566 5.314m0 0a2.25 2.25 0 1 0 3.935 2.186 2.25 2.25 0 0 0-3.935-2.186Zm0-12.814a2.25 2.25 0 1 0 3.933-2.185 2.25 2.25 0 0 0-3.933 2.185Z" />
                </svg>
              </div>
              <svg className="w-5 h-5 text-gray-300 group-hover:text-flux-blue transition" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
              </svg>
            </div>
            <h3 className="font-semibold text-flux-dark mb-2">Social Media Plan</h3>
            <p className="text-sm text-flux-muted leading-relaxed">
              Content calendar framework and engagement tactics for organic...
            </p>
          </button>
        </div>
      </div>

    </div>
  );
}
