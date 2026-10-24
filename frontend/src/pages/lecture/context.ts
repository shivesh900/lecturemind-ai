import { useOutletContext } from "react-router-dom";
import type { Lecture } from "@/types";

export interface Player {
  currentTime: number;
  duration: number;
  playing: boolean;
  seek: (t: number, play?: boolean) => void;
  toggle: () => void;
  available: boolean;
}

export interface WorkspaceCtx {
  lecture: Lecture;
  reload: (silent?: boolean) => Promise<void>;
  player: Player;
  /** seek and switch to the transcript tab */
  jumpTo: (t: number) => void;
}

export const useWorkspace = () => useOutletContext<WorkspaceCtx>();
