import { Link } from "react-router-dom";
import { cn } from "@/utils/cn";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("h-8 w-8", className)} aria-hidden>
      <defs>
        <linearGradient id="lm-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#a855f7" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#lm-g)" />
      <g fill="#fff">
        <rect x="13" y="26" width="5" height="12" rx="2.5" />
        <rect x="22" y="18" width="5" height="28" rx="2.5" />
        <rect x="31" y="22" width="5" height="20" rx="2.5" />
        <rect x="40" y="14" width="5" height="36" rx="2.5" />
        <rect x="49" y="27" width="4" height="10" rx="2" />
      </g>
    </svg>
  );
}

export function Logo({ to = "/", className, compact }: { to?: string; className?: string; compact?: boolean }) {
  return (
    <Link to={to} className={cn("flex items-center gap-2.5 font-semibold tracking-tight", className)} aria-label="LectureMind AI home">
      <LogoMark />
      {!compact && (
        <span className="text-[17px]">
          LectureMind <span className="gradient-text">AI</span>
        </span>
      )}
    </Link>
  );
}
