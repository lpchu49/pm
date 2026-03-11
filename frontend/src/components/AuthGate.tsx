"use client";

import { useEffect, useState, type FormEvent } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";

type SessionState = {
    status: "loading" | "authenticated" | "unauthenticated";
    username?: string;
};

export const AuthGate = () => {
    const [session, setSession] = useState<SessionState>({ status: "loading" });
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        const checkSession = async () => {
            try {
                const response = await fetch("/api/auth/session");
                if (!response.ok) {
                    setSession({ status: "unauthenticated" });
                    return;
                }
                const payload = await response.json();
                if (payload.authenticated) {
                    setSession({ status: "authenticated", username: payload.username });
                } else {
                    setSession({ status: "unauthenticated" });
                }
            } catch {
                setSession({ status: "unauthenticated" });
            }
        };

        checkSession();
    }, []);

    const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setError("");
        setIsSubmitting(true);

        try {
            const response = await fetch("/api/auth/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ username, password }),
            });
            const payload = await response.json();

            if (!response.ok || !payload.authenticated) {
                setError("Incorrect username or password.");
                return;
            }

            setSession({ status: "authenticated", username: payload.username });
        } catch {
            setError("Unable to sign in right now. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleLogout = async () => {
        try {
            await fetch("/api/auth/logout", { method: "POST" });
        } catch {
            // Network error — still transition to unauthenticated
        }
        setSession({ status: "unauthenticated" });
        setError("");
    };

    if (session.status === "loading") {
        return (
            <main className="mx-auto flex min-h-screen max-w-[480px] items-center px-6">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                    Loading workspace...
                </p>
            </main>
        );
    }

    if (session.status === "authenticated") {
        return <KanbanBoard onLogout={handleLogout} username={session.username ?? "user"} />;
    }

    return (
        <div className="relative overflow-hidden">
            <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
            <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

            <main className="relative mx-auto flex min-h-screen max-w-[540px] items-center px-6 py-10">
                <section className="w-full rounded-[32px] border border-[var(--stroke)] bg-white/85 p-8 shadow-[var(--shadow)] backdrop-blur">
                    <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                        Project Management MVP
                    </p>
                    <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                        Sign in
                    </h1>
                    <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
                        Use the MVP credentials to access your Kanban board.
                    </p>

                    <form className="mt-8 space-y-4" onSubmit={handleLogin}>
                        <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                            Username
                            <input
                                value={username}
                                onChange={(event) => setUsername(event.target.value)}
                                className="mt-2 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                                autoComplete="username"
                                required
                            />
                        </label>

                        <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                            Password
                            <input
                                type="password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                className="mt-2 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                                autoComplete="current-password"
                                required
                            />
                        </label>

                        {error ? (
                            <p className="text-sm font-semibold text-[var(--secondary-purple)]" role="alert">
                                {error}
                            </p>
                        ) : null}

                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className="w-full rounded-full bg-[var(--secondary-purple)] px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
                        >
                            {isSubmitting ? "Signing in..." : "Sign in"}
                        </button>
                    </form>
                </section>
            </main>
        </div>
    );
};
