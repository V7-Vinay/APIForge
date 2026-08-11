import { FormEvent, useState } from "react";

type User = { id: string; name: string; email: string; created_at: string };
type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export default function App() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [message, setMessage] = useState("Authentication is ready.");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      if (mode === "register") {
        const r = await fetch("/api/v1/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, email, password }),
        });
        const body = await r.json();
        if (!r.ok) throw new Error(body.detail ?? "Registration failed.");
        setMode("login");
        setMessage("Account created. Log in to continue.");
        return;
      }
      const r = await fetch("/api/v1/auth/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const body = (await r.json()) as TokenResponse | { detail: string };
      if (!r.ok)
        throw new Error((body as { detail: string }).detail ?? "Login failed.");
      const token = (body as TokenResponse).access_token;
      const me = await fetch("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!me.ok) throw new Error("Could not load authenticated user.");
      setUser((await me.json()) as User);
      setMessage("Authenticated successfully.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    setUser(null);
    setMessage("Logged out.");
  }

  return (
    <main className="shell">
      <section className="hero">
        <span className="eyebrow">APIForge · Phase 2</span>
        {user ? (
          <>
            <h1>Welcome, {user.name}.</h1>
            <p>
              Authentication is working. The access token is used for the
              protected API, while the refresh token is protected by an HttpOnly
              cookie.
            </p>
            <div className="status-card">
              <div>
                <span className="label">Authenticated user</span>
                <strong className="ok">{user.email}</strong>
              </div>
              <button onClick={logout}>Log out</button>
            </div>
          </>
        ) : (
          <>
            <h1>Secure identity for APIForge.</h1>
            <p>
              Registration, Argon2 password hashing, JWT access tokens, rotating
              refresh tokens, protected routes, and logout are now in place.
            </p>
            <form onSubmit={submit} className="auth-form">
              {mode === "register" && (
                <label>
                  Name
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </label>
              )}
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  required
                />
              </label>
              <button disabled={loading}>
                {loading
                  ? "Working…"
                  : mode === "login"
                    ? "Log in"
                    : "Create account"}
              </button>
            </form>
            <button
              className="link-button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setMessage("");
              }}
            >
              {mode === "login"
                ? "Need an account? Register"
                : "Already have an account? Log in"}
            </button>
            {message && <div className="message">{message}</div>}
          </>
        )}
      </section>
    </main>
  );
}
