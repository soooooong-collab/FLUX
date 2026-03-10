"use client";

import { useEffect, useState } from "react";
import { isLoggedIn, logout } from "@/lib/api";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Sidebar() {
    const [loggedIn, setLoggedIn] = useState(false);
    const pathname = usePathname();

    useEffect(() => {
        setLoggedIn(isLoggedIn());
    }, []);

    // Hide sidebar on login page
    if (pathname === "/login") return null;

    const navItemClass = (path: string) => {
        const isActive = pathname === path;
        return `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${isActive
                ? "bg-flux-blue/10 text-flux-blue"
                : "text-flux-muted hover:text-flux-dark hover:bg-flux-border/30"
            }`;
    };

    return (
        <aside className="w-64 flex-shrink-0 h-screen bg-white border-r border-flux-border flex flex-col justify-between py-6 px-4">
            {/* Top Section */}
            <div>
                <div className="flex items-center gap-2 px-2 mb-8">
                    <div className="w-8 h-8 bg-flux-blue rounded-lg flex items-center justify-center text-white font-bold">
                        F
                    </div>
                    <span className="text-xl font-bold text-flux-dark tracking-tight">FLUX AI</span>
                </div>

                <Link
                    href="/brief"
                    className="flex items-center justify-center gap-2 w-full py-2.5 bg-flux-muted-blue text-flux-blue font-semibold rounded-lg hover:bg-blue-100 transition mb-8 text-sm"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                    </svg>
                    New Strategy
                </Link>

                {/* Library Section */}
                <div className="mb-8">
                    <p className="px-3 text-xs font-semibold text-flux-muted uppercase tracking-wider mb-2">Library</p>
                    <nav className="flex flex-col gap-1">
                        <Link href="/dashboard" className={navItemClass("/dashboard")}>
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                            </svg>
                            Recent Strategies
                        </Link>
<Link href="/projects" className={navItemClass("/projects")}>
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v12a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z" />
                            </svg>
                            My Projects
                        </Link>
                    </nav>
                </div>

                {/* System Section */}
                <div>
                    <p className="px-3 text-xs font-semibold text-flux-muted uppercase tracking-wider mb-2">System</p>
                    <nav className="flex flex-col gap-1">
                        <Link href="/settings" className={navItemClass("/settings")}>
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                            </svg>
                            Settings
                        </Link>
                        <Link href="/help" className={navItemClass("/help")}>
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75m0 3.75h.008v.008H12v-.008Z" />
                            </svg>
                            Help & Support
                        </Link>
                    </nav>
                </div>
            </div>

            {/* Bottom Section */}
            <div>
                <div className="flex items-center gap-3 px-3 py-4 border-t border-flux-border mt-4">
                    <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center font-bold text-gray-500 overflow-hidden">
                        {/* Using a placeholder avatar initials for now */}
                        SC
                    </div>
                    <div className="flex-1">
                        <p className="text-sm font-semibold text-flux-dark leading-tight">Sarah Chen</p>
                        <p className="text-xs text-flux-blue font-medium mt-0.5">Pro Plan</p>
                    </div>
                </div>
                <button className="w-full mt-2 flex items-center justify-center gap-2 py-2 bg-flux-dark text-white rounded-lg text-sm font-medium hover:bg-black transition">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m3.75 13.5 10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75Z" />
                    </svg>
                    Upgrade Plan
                </button>
                {loggedIn && (
                    <button
                        onClick={() => {
                            logout();
                            setLoggedIn(false);
                            window.location.href = "/";
                        }}
                        className="w-full mt-3 text-center text-xs text-red-500 hover:text-red-600 transition"
                    >
                        Logout
                    </button>
                )}
            </div>
        </aside>
    );
}
