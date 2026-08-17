import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import { ApiError } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Input";

export function RegisterPage() {
  const { register } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(name.trim(), email.trim(), password);
      toast.success("Account created. Please sign in.");
      navigate("/login", {
        replace: true,
        state: {
          message: "Account created successfully. Sign in to continue.",
        },
      });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Unable to create account.";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      <h1 className="auth-title">Create account</h1>
      <p className="auth-subtitle">Start collaborating on APIs in minutes.</p>

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <Field label="Name" htmlFor="register-name">
          <Input
            id="register-name"
            type="text"
            name="name"
            autoComplete="name"
            required
            minLength={2}
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={loading}
          />
        </Field>

        <Field label="Email" htmlFor="register-email">
          <Input
            id="register-email"
            type="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={loading}
          />
        </Field>

        <Field
          label="Password"
          htmlFor="register-password"
          hint="At least 8 characters."
        >
          <Input
            id="register-password"
            type="password"
            name="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={loading}
          />
        </Field>

        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}

        <Button type="submit" variant="primary" loading={loading}>
          Create account
        </Button>
      </form>

      <p className="auth-footer-link">
        <Link to="/login">Already registered? Sign in</Link>
      </p>
    </div>
  );
}
