import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { Shield, ExternalLink, ArrowRight } from "lucide-react";

const ECOSYSTEM_SITES = [
    {
        name: "Perceptor",
        domain: "perceptor.us",
        description: "AI-Powered Computer Vision",
        color: "from-blue-500 to-cyan-400",
    },
    {
        name: "AetherPro",
        domain: "aetherpro.tech",
        description: "Sovereign AI Infrastructure",
        color: "from-orange-500 to-amber-400",
    },
    {
        name: "AetherOps",
        domain: "operations.aetherpro.us",
        description: "Autonomous Agent Operations",
        color: "from-purple-500 to-pink-400",
    },
    {
        name: "MCP Fabric",
        domain: "mcpfabric.space",
        description: "Agent-to-Agent Protocol Layer",
        color: "from-green-500 to-emerald-400",
    },
    {
        name: "BlackBox Audio",
        domain: "blackboxaudio.tech",
        description: "Neural Audio Processing",
        color: "from-red-500 to-rose-400",
    },
    {
        name: "Passport Alliance",
        domain: "passportalliance.org",
        description: "Decentralized Identity Standard",
        color: "from-indigo-500 to-violet-400",
    },
];

export default function Logout() {
    const [, navigate] = useLocation();
    const [fadeIn, setFadeIn] = useState(false);
    const [showSites, setShowSites] = useState(false);

    useEffect(() => {
        // Trigger entrance animation
        requestAnimationFrame(() => setFadeIn(true));
        const timer = setTimeout(() => setShowSites(true), 400);
        return () => clearTimeout(timer);
    }, []);

    return (
        <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-4 overflow-hidden relative">
            {/* Animated background gradient */}
            <div className="absolute inset-0 overflow-hidden">
                <div className="absolute -top-1/2 -left-1/2 w-full h-full bg-gradient-radial from-orange-500/5 to-transparent rounded-full animate-pulse" />
                <div className="absolute -bottom-1/2 -right-1/2 w-full h-full bg-gradient-radial from-cyan-500/5 to-transparent rounded-full animate-pulse" style={{ animationDelay: "1s" }} />
            </div>

            <div
                className={`relative z-10 max-w-2xl w-full transition-all duration-700 ${fadeIn ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                    }`}
            >
                {/* Logo & Header */}
                <div className="text-center mb-10">
                    <div className="relative inline-block mb-6">
                        <div className="absolute inset-0 bg-orange-500/20 blur-2xl rounded-full animate-pulse" />
                        <img
                            src="/logo.png"
                            alt="AetherPro"
                            className="w-20 h-20 object-contain relative z-10 drop-shadow-[0_0_20px_rgba(249,115,22,0.6)]"
                        />
                    </div>
                    <h1 className="text-3xl font-bold text-white mb-3">
                        You've been signed out
                    </h1>
                    <p className="text-gray-400 text-lg">
                        Your session has been secured. See you next time.
                    </p>
                </div>

                {/* Passport Ecosystem Section */}
                <div
                    className={`bg-white/[0.03] backdrop-blur-sm border border-white/10 rounded-2xl p-6 mb-8 transition-all duration-700 delay-200 ${fadeIn ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
                        }`}
                >
                    <div className="flex items-center gap-3 mb-5">
                        <div className="p-2 bg-orange-500/10 rounded-lg">
                            <Shield className="w-5 h-5 text-orange-400" />
                        </div>
                        <div>
                            <h2 className="text-white font-semibold">
                                Your Passport. Every Platform.
                            </h2>
                            <p className="text-gray-500 text-sm">
                                One identity across the entire AetherPro ecosystem
                            </p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {ECOSYSTEM_SITES.map((site, i) => (
                            <a
                                key={site.domain}
                                href={`https://${site.domain}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={`group flex items-center gap-3 p-3 rounded-xl border border-white/5 hover:border-white/15 bg-white/[0.02] hover:bg-white/[0.05] transition-all duration-300 ${showSites
                                        ? "opacity-100 translate-x-0"
                                        : "opacity-0 -translate-x-4"
                                    }`}
                                style={{ transitionDelay: `${300 + i * 80}ms` }}
                            >
                                <div
                                    className={`w-10 h-10 rounded-lg bg-gradient-to-br ${site.color} flex items-center justify-center text-white font-bold text-sm shrink-0 shadow-lg`}
                                >
                                    {site.name[0]}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm text-white font-medium group-hover:text-orange-300 transition-colors truncate">
                                        {site.name}
                                    </p>
                                    <p className="text-xs text-gray-500 truncate">
                                        {site.description}
                                    </p>
                                </div>
                                <ExternalLink className="w-3.5 h-3.5 text-gray-600 group-hover:text-orange-400 transition-colors shrink-0" />
                            </a>
                        ))}
                    </div>
                </div>

                {/* Return Button */}
                <div className="text-center">
                    <button
                        onClick={() => navigate("/")}
                        className="inline-flex items-center gap-2 px-6 py-3 bg-orange-600 hover:bg-orange-500 text-white font-medium rounded-xl transition-all duration-200 hover:shadow-[0_0_30px_rgba(249,115,22,0.3)] group"
                    >
                        Back to AetherOps
                        <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </button>
                    <p className="text-gray-600 text-xs mt-4">
                        Secured by Passport • AetherPro Identity Federation
                    </p>
                </div>
            </div>
        </div>
    );
}
