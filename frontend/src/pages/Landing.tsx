import { Link } from "react-router-dom";
import {
  ArrowRight, AudioLines, BookOpenCheck, Brain, FileText, Layers, MessagesSquare, Network, Search, ShieldCheck, Sparkles, UploadCloud, Wand2, Github, Mail,
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Waveform } from "@/components/Waveform";
import { useAuth } from "@/hooks/useAuth";

const FEATURES = [
  { icon: AudioLines, title: "Accurate transcription", text: "Whisper speech-to-text with timestamped segments, click-to-seek playback and an editable transcript." },
  { icon: FileText, title: "Summaries that scale", text: "Map-reduce summarisation keeps every part of a long lecture: executive, five-line and detailed views." },
  { icon: BookOpenCheck, title: "Exam-ready notes", text: "Structured notes with headings, definitions, formulas and examples. Edit, then export to PDF, DOCX or Markdown." },
  { icon: Brain, title: "Quizzes & flashcards", text: "MCQ, true/false, short and long questions at three difficulty levels, plus flip-card revision with spaced ratings." },
  { icon: MessagesSquare, title: "Grounded lecture chat", text: "Ask anything about a lecture. Answers cite the exact timestamps, and say so when the lecture doesn't cover it." },
  { icon: Network, title: "Knowledge map", text: "An interactive graph of topics, concepts, people and formulas, each linked back to the moment it was said." },
];

const STEPS = [
  { icon: UploadCloud, title: "Upload", text: "Drop an MP3, WAV, M4A, MP4, MOV or WebM recording." },
  { icon: AudioLines, title: "Transcribe", text: "FFmpeg extracts the audio; Whisper writes a timestamped transcript." },
  { icon: Wand2, title: "Extract", text: "AI builds summaries, notes, concepts, quizzes and flashcards from the transcript only." },
  { icon: Search, title: "Study & search", text: "Review, quiz yourself, chat with the lecture and search across everything." },
];

const TECH = ["React + TypeScript", "Tailwind CSS", "FastAPI", "MongoDB", "OpenAI", "Whisper", "FFmpeg", "Embeddings search"];

export default function Landing() {
  const { user } = useAuth();
  const primary = user ? "/app/upload" : "/register";
  return (
    <div className="min-h-screen overflow-x-hidden bg-background">
      <header className="sticky top-0 z-40 border-b border-transparent bg-background/70 backdrop-blur-xl">
        <div className="container flex h-16 items-center justify-between">
          <Logo />
          <nav className="hidden items-center gap-7 text-sm text-muted-foreground md:flex">
            <a href="#features" className="hover:text-foreground">Features</a>
            <a href="#how" className="hover:text-foreground">How it works</a>
            <a href="#tech" className="hover:text-foreground">Technology</a>
            <a href="#privacy" className="hover:text-foreground">Privacy</a>
          </nav>
          <div className="flex items-center gap-2">
            {user ? (
              <Button asChild size="sm"><Link to="/app">Open dashboard</Link></Button>
            ) : (
              <>
                <Button asChild variant="ghost" size="sm"><Link to="/login">Sign in</Link></Button>
                <Button asChild size="sm" variant="gradient"><Link to="/register">Get started</Link></Button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="relative">
        <div className="hero-glow pointer-events-none absolute inset-0" />
        <div className="bg-grid pointer-events-none absolute inset-0 [mask-image:radial-gradient(70%_60%_at_50%_0%,black,transparent)] opacity-60" />
        <div className="container relative pb-20 pt-16 text-center sm:pt-24">
          <div className="mx-auto inline-flex animate-fade-up items-center gap-2 rounded-full border bg-card/60 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-violet-400" /> AI-powered lecture transcription & knowledge extraction
          </div>
          <h1 className="mx-auto mt-6 max-w-4xl animate-fade-up text-4xl font-extrabold tracking-tight sm:text-6xl [animation-delay:60ms]">
            Turn Every Lecture Into Your <span className="gradient-text">Personal Knowledge Base</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl animate-fade-up text-base text-muted-foreground sm:text-lg [animation-delay:120ms]">
            Upload a recording and LectureMind transcribes it, then turns it into summaries, structured notes, quizzes, flashcards and a
            searchable knowledge map, all grounded in what your professor actually said.
          </p>
          <div className="mt-8 flex animate-fade-up flex-col items-center justify-center gap-3 sm:flex-row [animation-delay:180ms]">
            <Button asChild size="lg" variant="gradient"><Link to={primary}><UploadCloud className="!h-5 !w-5" /> Upload Lecture</Link></Button>
            <Button asChild size="lg" variant="outline"><a href="#features">Explore Features <ArrowRight /></a></Button>
          </div>

          {/* Visual: pipeline */}
          <div className="relative mx-auto mt-14 max-w-4xl animate-fade-up [animation-delay:240ms]">
            <div className="absolute -inset-x-10 -top-6 bottom-0 rounded-[2rem] bg-gradient-to-b from-indigo-500/20 via-violet-500/10 to-transparent blur-2xl" />
            <div className="relative rounded-3xl border bg-card/80 p-5 text-left shadow-2xl backdrop-blur-xl sm:p-7">
              <div className="mb-4 flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-red-400/80" /><span className="h-3 w-3 rounded-full bg-amber-400/80" /><span className="h-3 w-3 rounded-full bg-emerald-400/80" />
                <span className="ml-3 text-xs text-muted-foreground">lecture-recording.mp4</span>
                <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-primary/15 px-2.5 py-0.5 text-[11px] font-medium text-primary">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" /> Processing
                </span>
              </div>
              <div className="rounded-2xl border bg-background/60 p-4">
                <Waveform bars={72} className="h-20 w-full justify-between" />
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-4">
                {[["Transcript", AudioLines, 100], ["Summary", FileText, 80], ["Quiz", Brain, 55], ["Knowledge map", Network, 30]].map(([label, Icon, w]: any, i) => (
                  <div key={label} className="rounded-xl border bg-background/50 p-3">
                    <div className="mb-2 flex items-center gap-2 text-xs font-medium"><Icon className="h-3.5 w-3.5 text-primary" />{label}</div>
                    <div className="space-y-1.5">
                      {[0, 1, 2].map((j) => (
                        <div key={j} className="h-1.5 rounded-full bg-muted">
                          <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all" style={{ width: `${Math.max(10, w - j * 18)}%`, opacity: 1 - i * 0.15 }} />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="container scroll-mt-20 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary">Features</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Everything you need to master a lecture</h2>
          <p className="mt-3 text-muted-foreground">From raw recording to revision-ready material, every output is generated from the lecture's own transcript.</p>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="card-hover group rounded-2xl border bg-card p-6">
              <div className="mb-4 inline-flex rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 p-3 text-primary transition-transform group-hover:scale-110">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* HOW */}
      <section id="how" className="scroll-mt-20 border-y bg-card/40 py-20">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary">How it works</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">From recording to revision in four steps</h2>
          </div>
          <div className="relative mt-12 grid gap-6 md:grid-cols-4">
            <div className="absolute left-[12%] right-[12%] top-7 hidden h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent md:block" />
            {STEPS.map(({ icon: Icon, title, text }, i) => (
              <div key={title} className="relative text-center">
                <div className="relative mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-glow">
                  <Icon className="h-6 w-6" />
                  <span className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full border bg-background text-xs font-bold">{i + 1}</span>
                </div>
                <h3 className="mt-4 font-semibold">{title}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* TECH */}
      <section id="tech" className="container scroll-mt-20 py-20">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-primary">Technology</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Built like a real product</h2>
            <p className="mt-3 text-muted-foreground">
              A FastAPI backend with a background job pipeline, MongoDB persistence, FFmpeg audio extraction, local or cloud Whisper,
              structured AI outputs validated against schemas, and embedding-based semantic search.
            </p>
            <ul className="mt-6 space-y-3 text-sm">
              {["Long lectures are chunked and summarised map-reduce style, never one giant prompt", "Every answer and note is grounded in the transcript, with timestamps", "Per-step processing status with retries and clear failure messages"].map((t) => (
                <li key={t} className="flex gap-3"><Layers className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{t}</li>
              ))}
            </ul>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {TECH.map((t, i) => (
              <div key={t} className="animate-float rounded-2xl border bg-card p-4 text-center text-sm font-medium shadow-soft" style={{ animationDelay: `${i * 0.3}s` }}>{t}</div>
            ))}
          </div>
        </div>
      </section>

      {/* PRIVACY + CTA */}
      <section id="privacy" className="container scroll-mt-20 pb-20">
        <div className="relative overflow-hidden rounded-3xl border bg-gradient-to-br from-indigo-600/25 via-violet-600/15 to-fuchsia-600/10 p-8 sm:p-12">
          <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr] lg:items-center">
            <div>
              <ShieldCheck className="h-8 w-8 text-primary" />
              <h2 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Your lectures stay yours</h2>
              <p className="mt-3 text-sm leading-6 text-muted-foreground sm:text-base">
                Passwords are hashed with bcrypt and sessions use secure httpOnly cookies. Every lecture is private to your account.
                When an OpenAI key is configured, transcripts (and audio, if cloud transcription is enabled) are sent to OpenAI to generate
                study material. Without a key, transcription runs locally and nothing leaves the server.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row lg:flex-col">
              <Button asChild size="lg" variant="gradient"><Link to={primary}>Start for free <ArrowRight /></Link></Button>
              <Button asChild size="lg" variant="outline"><Link to="/login">I already have an account</Link></Button>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t">
        <div className="container flex flex-col gap-6 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Logo />
            <p className="mt-2 text-sm text-muted-foreground">AI lecture transcription & knowledge extraction.</p>
          </div>
          <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
            <a href="#features" className="hover:text-foreground">Features</a>
            <a href="#how" className="hover:text-foreground">How it works</a>
            <Link to="/login" className="hover:text-foreground">Sign in</Link>
            <Link to="/register" className="hover:text-foreground">Create account</Link>
            <a href="https://github.com/shivesh900/lecturemind-ai" className="inline-flex items-center gap-1.5 hover:text-foreground"><Github className="h-4 w-4" />GitHub</a>
            <a href="https://github.com/shivesh900" className="inline-flex items-center gap-1.5 hover:text-foreground"><Mail className="h-4 w-4" />Contact</a>
          </nav>
        </div>
        <div className="border-t py-4 text-center text-xs text-muted-foreground">© {new Date().getFullYear()} LectureMind AI · Built for the Automatic Speech Recognition course project</div>
      </footer>
    </div>
  );
}
