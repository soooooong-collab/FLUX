"use client";

import Link from "next/link";

export default function HelpPage() {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh]">
      <svg className="w-16 h-16 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75m0 3.75h.008v.008H12v-.008Z" />
      </svg>
      <h1 className="text-xl font-bold text-flux-dark mb-2">Help & Support</h1>
      <p className="text-flux-muted mb-6">준비 중입니다</p>
      <Link href="/dashboard" className="text-sm text-flux-blue hover:underline">
        Dashboard로 돌아가기
      </Link>
    </div>
  );
}
