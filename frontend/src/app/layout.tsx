import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import { ToastProvider } from "@/components/Toast";

export const metadata: Metadata = {
  title: "FLUX — AI Ad Strategy Generator",
  description: "AI-powered advertising strategy & concept generation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="flex h-screen overflow-hidden bg-flux-background text-flux-dark antialiased">
        <ToastProvider>
          <Sidebar />
          <main className="flex-1 overflow-y-auto w-full">
            <div className="max-w-5xl mx-auto px-8 py-10">
              {children}
            </div>
          </main>
        </ToastProvider>
      </body>
    </html>
  );
}
