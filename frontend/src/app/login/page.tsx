"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, register } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        await register(email, password, displayName || undefined);
      } else {
        await login(email, password);
      }
      router.push("/dashboard");
    } catch (err: any) {
      setError(
        mode === "login"
          ? "이메일 또는 비밀번호가 올바르지 않습니다."
          : "회원가입에 실패했습니다. 이미 등록된 이메일일 수 있습니다."
      );
    } finally {
      setLoading(false);
    }
  };

  const inputCls =
    "w-full bg-white border border-flux-border rounded-xl px-4 py-3 text-flux-dark placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-flux-blue/20 focus:border-flux-blue transition";

  return (
    <div className="max-w-sm mx-auto mt-16">
      <h1 className="text-2xl font-bold text-flux-dark text-center mb-2">
        {mode === "login" ? "로그인" : "회원가입"}
      </h1>
      <p className="text-center text-flux-muted text-sm mb-8">
        {mode === "login"
          ? "계정에 로그인하세요"
          : "새 계정을 만들어 시작하세요"}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "register" && (
          <div>
            <label className="block text-sm text-flux-muted mb-1">이름</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className={inputCls}
              placeholder="홍길동"
            />
          </div>
        )}

        <div>
          <label className="block text-sm text-flux-muted mb-1">이메일</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputCls}
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label className="block text-sm text-flux-muted mb-1">비밀번호</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputCls}
            placeholder="6자 이상"
            minLength={6}
          />
        </div>

        {error && (
          <p className="text-red-500 text-sm text-center">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-flux-blue text-white font-semibold rounded-lg hover:bg-flux-blue-hover transition disabled:opacity-50"
        >
          {loading
            ? "처리 중..."
            : mode === "login"
              ? "로그인"
              : "회원가입"}
        </button>
      </form>

      <div className="mt-6 text-center">
        <button
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
          className="text-sm text-flux-muted hover:text-flux-blue transition"
        >
          {mode === "login"
            ? "계정이 없으신가요? 회원가입"
            : "이미 계정이 있으신가요? 로그인"}
        </button>
      </div>

      <div className="mt-4 text-center">
        <p className="text-xs text-gray-400">
          또는 바로{" "}
          <a href="/brief" className="text-flux-blue hover:underline transition">
            새 프로젝트 시작
          </a>
          {" "}(게스트 자동 생성)
        </p>
      </div>
    </div>
  );
}
