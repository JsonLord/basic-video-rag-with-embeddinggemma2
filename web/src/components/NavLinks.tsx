"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Library" },
  { href: "/search", label: "Search" },
  { href: "/ask", label: "Ask" },
  { href: "/live", label: "Live" },
  { href: "/experiments", label: "Experiments" },
  { href: "/architecture", label: "Architecture" },
  { href: "/models", label: "Models & Routing" },
  { href: "/backups", label: "Backups" },
];

/** The links with the current page highlighted; `path` null renders them all inactive. */
export function NavLinksView({ path }: { path: string | null }) {
  return (
    <nav className="flex flex-wrap gap-1">
      {LINKS.map((l) => {
        const active =
          path != null && (l.href === "/" ? path === "/" || path.startsWith("/videos") : path.startsWith(l.href));
        return (
          <Link
            key={l.href}
            href={l.href}
            className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
              active ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface hover:text-ink"
            }`}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Reads the URL, so it must sit inside <Suspense> (it suspends while dynamic routes prerender). */
export function ActiveNavLinks() {
  return <NavLinksView path={usePathname()} />;
}
