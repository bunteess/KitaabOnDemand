import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { ApiError, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Button, ErrorBox, TextInput } from "../components/ui";

export function LoginPage() {
  const { user, login, expired } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [error, setError] = useState<string | null>(
    expired ? "Your session expired. Please sign in again." : null,
  );
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={user.role === "VENDOR" ? "/vendor" : "/admin"} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await login(email, password, needsTotp ? totp : undefined);
      navigate(me.role === "VENDOR" ? "/vendor" : "/admin", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.code === "totp-required") {
        setNeedsTotp(true);
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-slate-200 bg-white p-6"
      >
        <div>
          <h1 className="text-xl font-semibold text-brand-800">KitaabOnDemand</h1>
          <p className="text-sm text-slate-600">Admin and vendor portal</p>
        </div>
        {error && <ErrorBox message={error} />}
        <TextInput
          label="Email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextInput
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {needsTotp && (
          <TextInput
            label="Authenticator code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            maxLength={6}
            required
            autoFocus
            value={totp}
            onChange={(e) => setTotp(e.target.value)}
            hint="Six digits from your authenticator app"
          />
        )}
        <Button type="submit" busy={busy} className="w-full">
          Sign in
        </Button>
      </form>
    </div>
  );
}
