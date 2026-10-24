export type Theme = "dark" | "light" | "system";
export type NoteStyle = "concise" | "detailed" | "exam";

export interface Preferences {
  theme: Theme;
  default_language: string;
  note_style: NoteStyle;
}

export interface User {
  id: string;
  name: string;
  email: string;
  preferences: Preferences;
  created_at: string;
}

export type LectureStatus = "queued" | "processing" | "completed" | "failed";
export type StepStatus = "pending" | "running" | "completed" | "skipped" | "failed";

export interface StepState {
  status: StepStatus;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Lecture {
  id: string;
  title: string;
  subject: string | null;
  description: string | null;
  tags: string[];
  status: LectureStatus;
  progress: number;
  current_step: string | null;
  current_step_label?: string | null;
  steps: Record<string, StepState>;
  steps_order: string[];
  step_labels: Record<string, string>;
  error: string | null;
  duration: number | null;
  language: string | null;
  kind: "audio" | "video";
  mode?: "ai" | "demo";
  has_video: boolean;
  has_audio: boolean;
  original_filename?: string;
  file_size?: number;
  word_count?: number;
  segment_count?: number;
  transcription?: { provider: string; model: string; language_probability?: number };
  created_at: string;
  updated_at: string;
  processed_at?: string;
  available?: Record<string, boolean>;
}

export interface LectureStatusResponse {
  id: string;
  status: LectureStatus;
  progress: number;
  current_step: string | null;
  current_step_label: string | null;
  current_step_progress: number | null;
  steps: Record<string, StepState>;
  steps_order: string[];
  step_labels: Record<string, string>;
  error: string | null;
}

export interface Segment {
  idx: number;
  start: number;
  end: number;
  text: string;
  speaker: string | null;
  edited: boolean;
}

export interface Transcript {
  lecture_id: string;
  language: string | null;
  duration: number | null;
  has_speakers: boolean;
  transcription?: { provider: string; model: string };
  segments: Segment[];
  text: string;
}

export interface Definition { term: string; definition: string }
export interface Formula { expression: string; meaning: string }

export interface SummaryDoc {
  id: string;
  mode: "ai" | "demo";
  model?: string;
  summary: {
    executive_summary: string;
    quick_summary: string[];
    detailed_summary: { heading: string; content: string }[];
    main_topics: { title: string; description: string; chunk_index: number | null }[];
    arguments: string[];
    key_takeaways: string[];
    definitions: Definition[];
    formulas: Formula[];
    examples: string[];
  };
  chapters: { title: string; start: number; end: number; summary: string; chunk_index: number }[];
  updated_at: string;
}

export interface NotesDoc {
  id: string;
  markdown: string;
  edited: boolean;
  mode: "ai" | "demo";
  updated_at: string;
}

export type QuestionType = "mcq" | "true_false" | "short" | "long";
export type Difficulty = "easy" | "medium" | "hard";

export interface QuizQuestion {
  id: string;
  type: QuestionType;
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  difficulty: Difficulty;
  important: boolean;
}

export interface Quiz {
  id: string;
  lecture_id: string;
  title: string;
  questions: QuizQuestion[];
  difficulty: Difficulty | "mixed";
  source: "auto" | "user";
  mode: "ai" | "demo";
  created_at: string;
}

export interface QuizResult {
  question_id: string;
  type: QuestionType;
  given: string;
  correct: boolean | null;
  correct_answer: string;
  explanation: string;
}

export interface QuizAttempt {
  id: string;
  quiz_id: string;
  lecture_id: string;
  score: number;
  correct: number;
  gradable: number;
  total: number;
  results?: QuizResult[];
  duration_seconds?: number | null;
  created_at: string;
  lecture_title?: string;
}

export interface Flashcard {
  id: string;
  front: string;
  back: string;
  difficulty: Difficulty;
  rating: Difficulty | null;
  review_count: number;
  last_reviewed_at: string | null;
}

export interface FlashcardSet {
  id: string;
  cards: Flashcard[];
  mode: "ai" | "demo";
  updated_at: string;
}

export interface KnowledgeNode {
  id: string;
  label: string;
  type: "topic" | "subtopic" | "concept" | "definition" | "entity" | "date" | "formula" | "keyword";
  description: string;
  chunk_index: number | null;
  timestamp: number | null;
}

export interface KnowledgeMap {
  id: string;
  nodes: KnowledgeNode[];
  edges: { source: string; target: string; relation: string }[];
  keywords: string[];
  mode: "ai" | "demo";
}

export interface Citation {
  chunk_index: number;
  timestamp: number;
  start: number;
  end: number;
  excerpt: string;
  score?: number | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  supported?: boolean;
  citations?: Citation[];
  mode?: "ai" | "demo";
  created_at: string;
}

export interface SystemStatus {
  ai_enabled: boolean;
  demo_mode: boolean;
  chat_model: string | null;
  embedding_model: string | null;
  custom_ai_endpoint: boolean;
  transcription_provider: string;
  transcription_model: string;
  ffmpeg_available: boolean;
  database_ok: boolean;
  max_upload_mb: number;
  data_disclosure: string;
}

export interface DashboardStats {
  total_lectures: number;
  completed_lectures: number;
  learning_hours: number;
  learning_minutes: number;
  notes_count: number;
  quizzes_completed: number;
  average_quiz_score: number | null;
  flashcards_reviewed: number;
  recent_lectures: Lecture[];
  recent_materials: { kind: string; lecture_id: string; lecture_title: string; updated_at: string; mode: string }[];
  jobs: Lecture[];
}

export interface ActivityDay {
  date: string;
  label: string;
  lectures: number;
  minutes: number;
  quiz_attempts: number;
  flashcard_reviews: number;
  chat_messages: number;
  study_actions: number;
}

export interface SearchMatch {
  kind: "lecture" | "transcript" | "notes" | "concept" | "semantic";
  text: string;
  timestamp: number | null;
  score: number;
  similarity?: number;
}

export interface SearchGroup {
  lecture_id: string;
  title: string;
  subject: string | null;
  matches: SearchMatch[];
  score: number;
}

// ---- content safety (harsh / threatening language) ----
export type SafetyCategory = "threat" | "hate" | "insult" | "profanity";
export type SafetySeverity = "low" | "medium" | "high";
export interface SafetyMatch { term: string; masked: string; start: number; end: number; category: SafetyCategory; severity: SafetySeverity; label: string; kind: "word" | "phrase"; }
export interface SafetyFlag { category: SafetyCategory; severity: SafetySeverity; source: "lexicon" | "ai_moderation"; terms: string[]; matches: SafetyMatch[]; score?: number; moderation_categories?: string[]; }
export interface FlaggedSegment { segment_idx: number; start: number; end: number; text: string; categories: SafetyCategory[]; severity: SafetySeverity; sources: string[]; terms: string[]; flags: SafetyFlag[]; }
export interface ModerationInfo { status: "used" | "disabled" | "failed"; model: string | null; error: string | null; reason?: string; }
export interface SafetyReport {
  lecture_id: string; scanned_at: string; segments_scanned: number; lexicon_version: string; moderation: ModerationInfo;
  summary: { total_flagged: number; by_category: Record<SafetyCategory, number>; by_severity: Record<SafetySeverity, number> };
  flagged: FlaggedSegment[];
}
export interface SafetyCheckResult { text: string; flagged: boolean; categories: SafetyCategory[]; severity: SafetySeverity | null; sources: string[]; terms: string[]; flags: SafetyFlag[]; matches: SafetyMatch[]; moderation: ModerationInfo; }
