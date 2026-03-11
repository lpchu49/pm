import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, vi } from "vitest";
import { AIChatSidebar } from "@/components/AIChatSidebar";

const fetchMock = vi.fn<typeof fetch>();

const renderSidebar = (overrides?: Partial<Parameters<typeof AIChatSidebar>[0]>) => {
    const defaults = {
        isOpen: true,
        onClose: vi.fn(),
        onBoardUpdated: vi.fn(),
    };
    return render(<AIChatSidebar {...defaults} {...overrides} />);
};

describe("AIChatSidebar", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("shows empty state placeholder when there are no messages", () => {
        renderSidebar();
        expect(screen.getByText(/ask the ai to create, move, or edit cards/i)).toBeInTheDocument();
    });

    it("disables send button when input is empty", () => {
        renderSidebar();
        expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
    });

    it("enables send button when input has text", async () => {
        renderSidebar();
        await userEvent.type(screen.getByLabelText("Chat message input"), "hello");
        expect(screen.getByRole("button", { name: /send/i })).toBeEnabled();
    });

    it("sends a message and renders user and assistant messages", async () => {
        fetchMock.mockResolvedValueOnce(
            new Response(
                JSON.stringify({ assistant_text: "I can help with that.", board_updated: false }),
                { status: 200, headers: { "Content-Type": "application/json" } }
            )
        );

        renderSidebar();
        await userEvent.type(screen.getByLabelText("Chat message input"), "Add a card");
        await userEvent.click(screen.getByRole("button", { name: /send/i }));

        expect(await screen.findByText("Add a card")).toBeInTheDocument();
        expect(await screen.findByText("I can help with that.")).toBeInTheDocument();
    });

    it("calls onBoardUpdated when board_updated is true", async () => {
        fetchMock.mockResolvedValueOnce(
            new Response(
                JSON.stringify({ assistant_text: "Done! Card added.", board_updated: true }),
                { status: 200, headers: { "Content-Type": "application/json" } }
            )
        );

        const onBoardUpdated = vi.fn();
        renderSidebar({ onBoardUpdated });
        await userEvent.type(screen.getByLabelText("Chat message input"), "Add a task");
        await userEvent.click(screen.getByRole("button", { name: /send/i }));

        await screen.findByText("Done! Card added.");
        expect(onBoardUpdated).toHaveBeenCalledOnce();
    });

    it("does not call onBoardUpdated when board_updated is false", async () => {
        fetchMock.mockResolvedValueOnce(
            new Response(
                JSON.stringify({ assistant_text: "No changes needed.", board_updated: false }),
                { status: 200, headers: { "Content-Type": "application/json" } }
            )
        );

        const onBoardUpdated = vi.fn();
        renderSidebar({ onBoardUpdated });
        await userEvent.type(screen.getByLabelText("Chat message input"), "How many cards?");
        await userEvent.click(screen.getByRole("button", { name: /send/i }));

        await screen.findByText("No changes needed.");
        expect(onBoardUpdated).not.toHaveBeenCalled();
    });

    it("shows error text when fetch fails", async () => {
        fetchMock.mockRejectedValueOnce(new Error("Network error"));

        renderSidebar();
        await userEvent.type(screen.getByLabelText("Chat message input"), "hello");
        await userEvent.click(screen.getByRole("button", { name: /send/i }));

        expect(await screen.findByTestId("ai-chat-error")).toHaveTextContent(
            /could not reach the ai/i
        );
    });

    it("shows error when response is not ok", async () => {
        fetchMock.mockResolvedValueOnce(
            new Response(JSON.stringify({ detail: "Server error" }), {
                status: 500,
                headers: { "Content-Type": "application/json" },
            })
        );

        renderSidebar();
        await userEvent.type(screen.getByLabelText("Chat message input"), "hello");
        await userEvent.click(screen.getByRole("button", { name: /send/i }));

        expect(await screen.findByTestId("ai-chat-error")).toBeInTheDocument();
    });

    it("calls onClose when the close button is clicked", async () => {
        const onClose = vi.fn();
        renderSidebar({ onClose });
        await userEvent.click(screen.getByRole("button", { name: /close ai chat sidebar/i }));
        expect(onClose).toHaveBeenCalledOnce();
    });

    it("clears the input after sending", async () => {
        fetchMock.mockResolvedValueOnce(
            new Response(
                JSON.stringify({ assistant_text: "Noted.", board_updated: false }),
                { status: 200, headers: { "Content-Type": "application/json" } }
            )
        );

        renderSidebar();
        const input = screen.getByLabelText("Chat message input");
        await userEvent.type(input, "test message");
        await userEvent.click(screen.getByRole("button", { name: /send/i }));

        await screen.findByText("Noted.");
        expect(input).toHaveValue("");
    });
});
