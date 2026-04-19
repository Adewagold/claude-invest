"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview", icon: "📊" },
  { href: "/positions", label: "Positions", icon: "💼" },
  { href: "/trades", label: "Trades", icon: "📋" },
  { href: "/signals", label: "Signals", icon: "📡" },
  { href: "/discovery", label: "Discovery", icon: "🔍" },
  { href: "/config", label: "Config", icon: "⚙️" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="w-56 min-h-screen bg-zinc-900 border-r border-zinc-800 p-4 flex flex-col gap-1">
      <div className="text-lg font-bold text-white mb-6 px-3">
        Claude Invest
      </div>
      {links.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
              active
                ? "bg-zinc-800 text-white"
                : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
            }`}
          >
            <span>{link.icon}</span>
            <span>{link.label}</span>
          </Link>
        );
      })}
      <div className="mt-auto px-3 py-2 text-xs text-zinc-600">
        Paper Trading
      </div>
    </nav>
  );
}
