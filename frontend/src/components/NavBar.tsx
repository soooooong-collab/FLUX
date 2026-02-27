"use client";

import { useEffect, useState } from "react";
import { isLoggedIn, logout } from "@/lib/api";

export default function NavBar() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(isLoggedIn());
  }, []);

  return (
    <nav className="border-b border-white/10 px-6 py-4 flex items-center justify-between">
      <a href="/" className="text-xl font-bold text-white tracking-wider">
        FLUX<span className="text-flux-accent">.</span>
      </a>
      <div className="flex gap-4 text-sm items-center">
        <a href="/dashboard" className="hover:text-white transition">
          Dashboard
        </a>
        <a href="/brief" className="hover:text-white transition">
          New Project
        </a>
        <a href="/admin" className="hover:text-white transition text-flux-muted/50">
          Admin
        </a>
        {loggedIn ? (
          <button
            onClick={() => {
              logout();
              setLoggedIn(false);
              window.location.href = "/";
            }}
            className="text-flux-muted/40 hover:text-red-400 transition"
          >
            Logout
          </button>
        ) : (
          <a
            href="/login"
            className="px-3 py-1.5 bg-flux-accent/20 text-flux-accent rounded-lg hover:bg-flux-accent/30 transition text-xs font-medium"
          >
            Login
          </a>
        )}
      </div>
    </nav>
  );
}
