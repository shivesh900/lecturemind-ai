import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import App from "./App";
import { AuthProvider } from "./hooks/useAuth";
import { ThemeProvider, useTheme } from "./hooks/useTheme";
import { SystemStatusProvider } from "./hooks/useSystemStatus";
import { TooltipProvider } from "./components/ui/tooltip";
import "./index.css";

function ThemedToaster() {
  const { resolved } = useTheme();
  return <Toaster theme={resolved} position="top-right" richColors closeButton />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <SystemStatusProvider>
            <TooltipProvider>
              <App />
              <ThemedToaster />
            </TooltipProvider>
          </SystemStatusProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
