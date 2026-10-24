import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams, Navigate } from "react-router-dom";
import { toast } from "sonner";
import { Eye, EyeOff, Lock, Mail, User as UserIcon, CheckCircle2 } from "lucide-react";
import { Logo } from "@/components/Logo";
import { Waveform } from "@/components/Waveform";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/services/api";

function Shell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden border-r bg-gradient-to-br from-indigo-950 via-[#0b1030] to-violet-950 p-10 text-white lg:flex lg:flex-col">
        <div className="bg-grid absolute inset-0 opacity-20" />
        <div className="relative"><Logo /></div>
        <div className="relative mt-auto">
          <Waveform bars={40} className="mb-8 h-24" />
          <h2 className="text-3xl font-bold leading-tight">Your lectures,<br />searchable, summarised and quizzable.</h2>
          <ul className="mt-6 space-y-2.5 text-sm text-indigo-100/80">
            {["Timestamped transcripts with click-to-seek audio", "Notes, quizzes and flashcards from every lecture", "Chat that cites where your professor said it"].map((t) => (
              <li key={t} className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-violet-300" />{t}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex flex-col items-center justify-center px-5 py-10">
        <div className="mb-8 lg:hidden"><Logo /></div>
        <div className="w-full max-w-sm animate-fade-up">
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          <div className="mt-7">{children}</div>
          <p className="mt-6 text-center text-sm text-muted-foreground">{footer}</p>
        </div>
      </div>
    </div>
  );
}

function Field({ id, label, icon, error, ...props }: { id: string; label: string; icon: ReactNode; error?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground [&_svg]:h-4 [&_svg]:w-4">{icon}</span>
        <Input id={id} className="h-11 pl-9" aria-invalid={!!error} aria-describedby={error ? `${id}-err` : undefined} {...props} />
      </div>
      {error && <p id={`${id}-err`} className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function PasswordField({ value, onChange, autoComplete, error }: { value: string; onChange: (v: string) => void; autoComplete: string; error?: string }) {
  const [show, setShow] = useState(false);
  return (
    <div className="space-y-1.5">
      <Label htmlFor="password">Password</Label>
      <div className="relative">
        <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input id="password" type={show ? "text" : "password"} className="h-11 px-9" value={value} onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete} required aria-invalid={!!error} />
        <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground" aria-label={show ? "Hide password" : "Show password"}>
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export function Login() {
  const { login, user } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const next = params.get("next") || "/app";
  if (user) return <Navigate to={next} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const u = await login(email, password);
      toast.success(`Welcome back, ${u.name.split(" ")[0]}!`);
      nav(next, { replace: true });
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Shell title="Welcome back" subtitle="Sign in to your study workspace." footer={<>New here? <Link to="/register" className="font-medium text-primary hover:underline">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field id="email" label="Email" icon={<Mail />} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <PasswordField value={password} onChange={setPassword} autoComplete="current-password" />
        {error && <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <Button type="submit" className="h-11 w-full" variant="gradient" loading={loading}>Sign in</Button>
      </form>
    </Shell>
  );
}

export function Register() {
  const { register, user } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  if (user) return <Navigate to="/app" replace />;

  const validate = () => {
    const e: Record<string, string> = {};
    if (!name.trim()) e.name = "Please enter your name.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) e.email = "Enter a valid email address.";
    if (password.length < 8) e.password = "Use at least 8 characters.";
    else if (/^\d+$/.test(password) || /^[a-zA-Z]+$/.test(password)) e.password = "Use a mix of letters and numbers.";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      await register(name.trim(), email, password);
      toast.success("Account created. Let's upload your first lecture!");
      nav("/app/upload", { replace: true });
    } catch (err) {
      setErrors({ form: (err as ApiError).message });
    } finally {
      setLoading(false);
    }
  };

  const strength = Math.min(4, [password.length >= 8, /[A-Z]/.test(password), /\d/.test(password), /[^A-Za-z0-9]/.test(password) || password.length >= 12].filter(Boolean).length);

  return (
    <Shell title="Create your account" subtitle="Start turning lectures into study material." footer={<>Already have an account? <Link to="/login" className="font-medium text-primary hover:underline">Sign in</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field id="name" label="Full name" icon={<UserIcon />} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} error={errors.name} />
        <Field id="email" label="Email" icon={<Mail />} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={errors.email} />
        <PasswordField value={password} onChange={setPassword} autoComplete="new-password" error={errors.password} />
        {password && (
          <div className="flex gap-1" aria-label={`Password strength ${strength} of 4`}>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className={`h-1 flex-1 rounded-full ${i < strength ? (strength >= 3 ? "bg-success" : "bg-warning") : "bg-muted"}`} />
            ))}
          </div>
        )}
        {errors.form && <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{errors.form}</p>}
        <Button type="submit" className="h-11 w-full" variant="gradient" loading={loading}>Create account</Button>
        <p className="text-center text-xs text-muted-foreground">Passwords are hashed with bcrypt and never stored in plain text.</p>
      </form>
    </Shell>
  );
}
