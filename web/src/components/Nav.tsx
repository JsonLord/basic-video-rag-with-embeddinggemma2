import Link from "next/link";
import { Suspense } from "react";
import { ActiveNavLinks, NavLinksView } from "./NavLinks";

// Server component: the header is part of the static shell. Only the links read the pathname, and
// usePathname() suspends while dynamic routes like /videos/[id] prerender, so they get their own
// Suspense boundary with an un-highlighted fallback of identical size.
export function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-page/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-6 py-3">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="text-base font-semibold">Visual Mentor</span>
          <span className="text-xs text-muted">Private · Remote inference</span>
        </Link>
        <Suspense fallback={<NavLinksView path={null} />}>
          <ActiveNavLinks />
        </Suspense>
      </div>
    </header>
  );
}
