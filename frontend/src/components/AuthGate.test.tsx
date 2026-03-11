import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthGate } from "@/components/AuthGate";

const fetchMock = vi.fn<typeof fetch>();

describe("AuthGate", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("shows login form when session is not authenticated", async () => {
        fetchMock.mockResolvedValueOnce(
            new Response(JSON.stringify({ authenticated: false }), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            })
        );

        render(<AuthGate />);

        expect(await screen.findByRole("heading", { name: /sign in/i })).toBeInTheDocument();
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    it("shows an error for incorrect credentials", async () => {
        fetchMock.mockResolvedValueOnce(
            new Response(JSON.stringify({ authenticated: false }), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            })
        );
        fetchMock.mockResolvedValueOnce(
            new Response(JSON.stringify({ authenticated: false }), {
                status: 401,
                headers: { "Content-Type": "application/json" },
            })
        );

        render(<AuthGate />);

        await screen.findByRole("heading", { name: /sign in/i });
        await userEvent.clear(screen.getByLabelText(/username/i));
        await userEvent.type(screen.getByLabelText(/username/i), "bad");
        await userEvent.clear(screen.getByLabelText(/password/i));
        await userEvent.type(screen.getByLabelText(/password/i), "wrong");
        await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

        expect(await screen.findByRole("alert")).toHaveTextContent(/incorrect username or password/i);
    });

    it("allows login and logout", async () => {
        fetchMock.mockResolvedValueOnce(
            new Response(JSON.stringify({ authenticated: false }), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            })
        );
        fetchMock.mockResolvedValueOnce(
            new Response(JSON.stringify({ authenticated: true, username: "user" }), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            })
        );
        fetchMock.mockResolvedValueOnce(
            new Response(JSON.stringify({
                board: {
                    columns: [
                        { id: "col-1", title: "Todo", cardIds: ["card-1"] },
                    ],
                    cards: {
                        "card-1": { id: "card-1", title: "Task", details: "" },
                    },
                },
            }), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            })
        );
        fetchMock.mockResolvedValueOnce(
            new Response(JSON.stringify({ ok: true }), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            })
        );

        render(<AuthGate />);

        await screen.findByRole("heading", { name: /sign in/i });
        await userEvent.type(screen.getByLabelText(/username/i), "user");
        await userEvent.type(screen.getByLabelText(/password/i), "password");
        await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

        expect(await screen.findByRole("heading", { name: /kanban studio/i })).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: /log out/i }));

        await waitFor(() => {
            expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
        });
    });
});
