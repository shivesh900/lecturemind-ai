import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./layouts/AppLayout";
import { Skeleton } from "./components/ui/skeleton";

const Landing = lazy(() => import("./pages/Landing"));
const Login = lazy(() => import("./pages/Auth").then((m) => ({ default: m.Login })));
const Register = lazy(() => import("./pages/Auth").then((m) => ({ default: m.Register })));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Upload = lazy(() => import("./pages/Upload"));
const Library = lazy(() => import("./pages/Library"));
const SearchPage = lazy(() => import("./pages/Search"));
const Study = lazy(() => import("./pages/Study"));
const ExportCenter = lazy(() => import("./pages/ExportCenter"));
const Settings = lazy(() => import("./pages/Settings"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Workspace = lazy(() => import("./pages/lecture/Workspace"));
const OverviewTab = lazy(() => import("./pages/lecture/OverviewTab"));
const TranscriptTab = lazy(() => import("./pages/lecture/TranscriptTab"));
const SummaryTab = lazy(() => import("./pages/lecture/SummaryTab"));
const NotesTab = lazy(() => import("./pages/lecture/NotesTab"));
const ChatTab = lazy(() => import("./pages/lecture/ChatTab"));
const QuizTab = lazy(() => import("./pages/lecture/QuizTab"));
const FlashcardsTab = lazy(() => import("./pages/lecture/FlashcardsTab"));
const KnowledgeTab = lazy(() => import("./pages/lecture/KnowledgeTab"));
const SafetyTab = lazy(() => import("./pages/lecture/SafetyTab"));

function PageFallback() {
  return (
    <div className="space-y-4 p-6">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-4 w-80" />
      <div className="grid gap-4 sm:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/app" element={<ProtectedRoute />}>
          <Route index element={<Dashboard />} />
          <Route path="upload" element={<Upload />} />
          <Route path="library" element={<Library />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="study" element={<Study />} />
          <Route path="exports" element={<ExportCenter />} />
          <Route path="settings" element={<Settings />} />
          <Route path="lectures/:id" element={<Workspace />}>
            <Route index element={<OverviewTab />} />
            <Route path="transcript" element={<TranscriptTab />} />
            <Route path="summary" element={<SummaryTab />} />
            <Route path="notes" element={<NotesTab />} />
            <Route path="chat" element={<ChatTab />} />
            <Route path="quiz" element={<QuizTab />} />
            <Route path="flashcards" element={<FlashcardsTab />} />
            <Route path="knowledge" element={<KnowledgeTab />} />
            <Route path="safety" element={<SafetyTab />} />
          </Route>
        </Route>
        <Route path="/dashboard" element={<Navigate to="/app" replace />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
