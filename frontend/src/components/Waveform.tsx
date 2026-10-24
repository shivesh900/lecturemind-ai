import { cn } from "@/utils/cn";

/** Decorative animated audio waveform. */
export function Waveform({ bars = 48, className, active = true }: { bars?: number; className?: string; active?: boolean }) {
  return (
    <div className={cn("flex h-16 items-center gap-[3px]", className)} aria-hidden>
      {Array.from({ length: bars }).map((_, i) => {
        const h = 25 + Math.abs(Math.sin(i * 0.55) * 55) + ((i * 37) % 20);
        return (
          <span
            key={i}
            className={cn("w-[3px] rounded-full bg-gradient-to-t from-indigo-500 to-fuchsia-400", active && "animate-wave")}
            style={{ height: `${Math.min(100, h)}%`, animationDelay: `${(i % 12) * 0.09}s`, opacity: 0.55 + ((i * 13) % 45) / 100 }}
          />
        );
      })}
    </div>
  );
}
