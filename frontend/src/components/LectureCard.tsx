import { Link } from "react-router-dom";
import { FileAudio, FileVideo, Clock } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { StatusBadge } from "@/components/common";
import { formatDuration, timeAgo } from "@/utils/format";
import type { Lecture } from "@/types";

export function LectureRow({ lecture }: { lecture: Lecture }) {
  const Icon = lecture.kind === "video" ? FileVideo : FileAudio;
  const busy = lecture.status === "processing" || lecture.status === "queued";
  return (
    <Link to={`/app/lectures/${lecture.id}`} className="group flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-secondary/70">
      <div className="rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-500/20 p-2 text-primary">
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium group-hover:text-primary">{lecture.title}</div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {lecture.subject && <span className="truncate">{lecture.subject}</span>}
          {lecture.subject && <span>·</span>}
          <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{formatDuration(lecture.duration)}</span>
          <span>·</span>
          <span>{timeAgo(lecture.created_at)}</span>
        </div>
        {busy && <Progress value={lecture.progress} className="mt-1.5 h-1" />}
      </div>
      <StatusBadge status={lecture.status} />
    </Link>
  );
}
