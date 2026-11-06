import { createFileRoute, redirect, useNavigate, useRouter } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";

import { login, register, type LoginRequest, type RegisterRequest, AuthError } from "@/api/auth";
import { useAuth } from "@/contexts/AuthContext";
import { userQueryKeys } from "@/hooks/useUser";

const title = "Sign in — CodePulse";
const description = "Sign in to your CodePulse account";

export const Route = createFileRoute("/auth")({
  beforeLoad: () => {
    // During SSR, we can't check localStorage, so don't redirect
    // The component will handle redirecting authenticated users
  },
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: AuthPage,
});

function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();
  const router = useRouter();
  const queryClient = useQueryClient();
  const auth = useAuth();

  // Redirect to dashboard if already authenticated
  if (auth.isAuthenticated && !auth.isLoading) {
    void navigate({ to: "/" });
  }

  const loginMutation = useMutation({
    mutationFn: (data: LoginRequest) => login(data),
    onSuccess: async () => {
      // Invalidate so useUser re-fetches the current user immediately
      await queryClient.invalidateQueries({ queryKey: userQueryKeys.me });
      // Invalidate the router so beforeLoad guards re-evaluate with fresh auth state
      await router.invalidate();
      // Refetch auth context
      auth.refetch();
      void navigate({ to: "/" });
    },
  });

  const registerMutation = useMutation({
    mutationFn: (data: RegisterRequest) => register(data),
    onSuccess: async (_user, variables) => {
      // After registration, automatically log in with the same credentials
      try {
        await login({ email: variables.email, password: variables.password });
        await queryClient.invalidateQueries({ queryKey: userQueryKeys.me });
        await router.invalidate();
        auth.refetch();
        void navigate({ to: "/" });
      } catch (error) {
        console.error("Auto-login after registration failed:", error);
      }
    },
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);

    if (isLogin) {
      loginMutation.mutate({
        email: formData.get("email") as string,
        password: formData.get("password") as string,
      });
    } else {
      const fullName = formData.get("full_name") as string | null;
      registerMutation.mutate({
        username: formData.get("username") as string,
        email: formData.get("email") as string,
        password: formData.get("password") as string,
        full_name: fullName || undefined,
      });
    }
  };

  const handleToggle = () => {
    setIsLogin(!isLogin);
    setShowPassword(false);
  };

  const error = loginMutation.error || registerMutation.error;
  const isLoading = loginMutation.isPending || registerMutation.isPending;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            {isLogin ? "Sign in" : "Create account"}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {isLogin
              ? "Enter your credentials to access your dashboard"
              : "Register to start tracking your competitive programming progress"}
          </p>
        </div>

        {/* Form */}
        <form id="auth-form" onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-4">
            {!isLogin && (
              <>
                <div>
                  <label htmlFor="username" className="block text-sm font-medium text-foreground">
                    Username
                  </label>
                  <input
                    id="username"
                    name="username"
                    type="text"
                    required={!isLogin}
                    disabled={isLoading}
                    autoComplete="username"
                    className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
                    placeholder="username"
                  />
                </div>
                <div>
                  <label htmlFor="full_name" className="block text-sm font-medium text-foreground">
                    Full Name (optional)
                  </label>
                  <input
                    id="full_name"
                    name="full_name"
                    type="text"
                    disabled={isLoading}
                    autoComplete="name"
                    className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
                    placeholder="John Doe"
                  />
                </div>
              </>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-foreground">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                disabled={isLoading}
                autoComplete={isLogin ? "email" : "email"}
                className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-foreground">
                Password
              </label>
              <div className="relative mt-1">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  disabled={isLoading}
                  autoComplete={isLogin ? "current-password" : "new-password"}
                  className="block w-full rounded-md border border-input bg-background px-3 py-2 pr-10 text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={isLoading}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground disabled:opacity-50"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" strokeWidth={1.6} />
                  ) : (
                    <Eye className="h-4 w-4" strokeWidth={1.6} />
                  )}
                </button>
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {error instanceof AuthError ? error.message : "An error occurred. Please try again."}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? "Loading..." : isLogin ? "Sign in" : "Create account"}
          </button>
        </form>

        {/* Toggle */}
        <div className="text-center text-sm">
          <button type="button" onClick={handleToggle} className="text-primary hover:underline">
            {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
