import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/Logo";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <Logo />
      <h1 className="mt-6 text-6xl font-extrabold gradient-text">404</h1>
      <p className="text-muted-foreground">This page doesn't exist.</p>
      <Button asChild><Link to="/">Go home</Link></Button>
    </div>
  );
}
