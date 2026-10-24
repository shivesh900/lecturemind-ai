import { FlaskConical } from "lucide-react";
import { Link } from "react-router-dom";
import { useSystemStatus } from "@/hooks/useSystemStatus";

export function DemoBanner() {
  const { status } = useSystemStatus();
  if (!status || status.ai_enabled) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-warning/30 bg-warning/10 px-4 py-2 text-xs text-foreground/90 sm:text-sm">
      <FlaskConical className="h-4 w-4 shrink-0 text-warning" />
      <span>
        <strong>Demo mode:</strong> no OpenAI key is configured. Transcription is real (local Whisper), but summaries, notes and quizzes use simple keyword/extractive methods, not AI.
      </span>
      <Link to="/app/settings#ai" className="font-medium text-primary hover:underline">Set up AI →</Link>
    </div>
  );
}
