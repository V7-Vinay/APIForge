import { Link, Outlet, useLocation } from "react-router-dom";

export function AuthLayout() {
  const location = useLocation();
  const isLogin = location.pathname.startsWith("/login");

  return (
    <div className="auth-shell">
      <div className="auth-shell-inner">
        <header className="auth-brand">
          <p className="auth-brand-name">APIForge</p>
          <p className="auth-tagline">Your API workspace starts here.</p>
        </header>

        <div className="auth-outlet">
          <Outlet />
        </div>

        <p className="auth-switch">
          {isLogin ? (
            <>
              New here? <Link to="/register">Create an account</Link>
            </>
          ) : (
            <>
              Already have an account? <Link to="/login">Sign in</Link>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
