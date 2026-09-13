"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Farm", match: (p: string) => p === "/" },
  { href: "/window/", label: "Window", match: (p: string) => p.startsWith("/window") },
  { href: "/results/", label: "Results", match: (p: string) => p.startsWith("/results") },
];

export default function NavTabs({ className }: { className?: string }) {
  const pathname = usePathname() ?? "/";
  return (
    <nav className={className} aria-label="Views">
      {TABS.map((t) => (
        <Link key={t.href} href={t.href} aria-current={t.match(pathname) ? "page" : undefined}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
