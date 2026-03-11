"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type CollisionDetection,
  DndContext,
  DragOverlay,
  PointerSensor,
  rectIntersection,
  useSensor,
  useSensors,
  pointerWithin,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import { createId, initialData, moveCard, type BoardData } from "@/lib/kanban";

type KanbanBoardProps = {
  onLogout?: () => void;
  username?: string;
};

export const KanbanBoard = ({ onLogout, username = "user" }: KanbanBoardProps) => {
  const [board, setBoard] = useState<BoardData | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [isLoadingBoard, setIsLoadingBoard] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "error">("idle");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const failedSaveBoardRef = useRef<BoardData | null>(null);

  const loadBoard = useCallback(async () => {
    setIsLoadingBoard(true);
    setLoadError(null);

    try {
      const response = await fetch("/api/board");
      if (!response.ok) {
        throw new Error("Board request failed");
      }

      const payload = (await response.json()) as { board?: BoardData };
      setBoard(payload.board ?? initialData);
    } catch {
      setLoadError("Unable to load the board right now.");
      setBoard(null);
    } finally {
      setIsLoadingBoard(false);
    }
  }, []);

  // Silent background refresh used by AI chat — does not show loading state
  // so AIChatSidebar stays mounted and preserves message history
  const refreshBoardSilently = useCallback(async () => {
    try {
      const response = await fetch("/api/board");
      if (!response.ok) return;
      const payload = (await response.json()) as { board?: BoardData };
      setBoard(payload.board ?? initialData);
    } catch {
      // Silent fail — keep showing existing board
    }
  }, []);

  useEffect(() => {
    void loadBoard();
  }, [loadBoard]);

  const persistBoard = useCallback(async (nextBoard: BoardData) => {
    setSaveState("saving");
    try {
      const response = await fetch("/api/board", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(nextBoard),
      });

      if (!response.ok) {
        throw new Error("Board save failed");
      }

      failedSaveBoardRef.current = null;
      setSaveState("idle");
    } catch {
      failedSaveBoardRef.current = nextBoard;
      setSaveState("error");
    }
  }, []);

  const retrySave = useCallback(() => {
    if (!failedSaveBoardRef.current) {
      return;
    }

    void persistBoard(failedSaveBoardRef.current);
  }, [persistBoard]);

  const updateBoard = useCallback(
    (updater: (prev: BoardData) => BoardData) => {
      setBoard((prev) => {
        if (!prev) {
          return prev;
        }

        const nextBoard = updater(prev);
        void persistBoard(nextBoard);
        return nextBoard;
      });
    },
    [persistBoard]
  );

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board?.cards ?? {}, [board]);

  const collisionDetectionStrategy = useCallback<CollisionDetection>((args) => {
    const pointerCollisions = pointerWithin(args);
    if (pointerCollisions.length > 0) {
      return pointerCollisions;
    }

    return rectIntersection(args);
  }, []);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active } = event;
    setActiveCardId(null);

    const overId = event.over?.id as string | undefined;

    if (!overId || active.id === overId) {
      return;
    }

    updateBoard((prev) => ({
      ...prev,
      columns: moveCard(prev.columns, active.id as string, overId),
    }));
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    updateBoard((prev) => ({
      ...prev,
      columns: prev.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    }));
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    const id = createId("card");
    updateBoard((prev) => ({
      ...prev,
      cards: {
        ...prev.cards,
        [id]: { id, title, details: details || "No details yet." },
      },
      columns: prev.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: [...column.cardIds, id] }
          : column
      ),
    }));
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    updateBoard((prev) => {
      return {
        ...prev,
        cards: Object.fromEntries(
          Object.entries(prev.cards).filter(([id]) => id !== cardId)
        ),
        columns: prev.columns.map((column) =>
          column.id === columnId
            ? {
              ...column,
              cardIds: column.cardIds.filter((id) => id !== cardId),
            }
            : column
        ),
      };
    });
  };

  if (isLoadingBoard) {
    return (
      <main className="mx-auto flex min-h-screen max-w-[480px] items-center px-6">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
          Loading board...
        </p>
      </main>
    );
  }

  if (!board) {
    return (
      <main className="mx-auto flex min-h-screen max-w-[520px] items-center px-6">
        <section className="w-full rounded-3xl border border-[var(--stroke)] bg-white/85 p-8 shadow-[var(--shadow)]">
          <h1 className="font-display text-3xl font-semibold text-[var(--navy-dark)]">
            Board unavailable
          </h1>
          <p className="mt-3 text-sm font-medium text-[var(--gray-text)]">
            {loadError ?? "Unable to load the board right now."}
          </p>
          <button
            type="button"
            onClick={() => {
              void loadBoard();
            }}
            className="mt-6 rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-white transition hover:brightness-110"
          >
            Retry
          </button>
        </section>
      </main>
    );
  }

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                One board. Five columns. Zero clutter.
              </p>
              <div className="mt-3 flex items-center gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                  Signed in as {username}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setSidebarOpen((prev) => !prev)}
                    aria-label="Toggle AI chat sidebar"
                    className="rounded-full border border-[var(--primary-blue)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-[var(--primary-blue)] transition hover:bg-[var(--primary-blue)] hover:text-white"
                  >
                    AI Chat
                  </button>
                  {onLogout ? (
                    <button
                      type="button"
                      onClick={onLogout}
                      className="rounded-full border border-[var(--stroke)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-[var(--navy-dark)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
                    >
                      Log out
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
          <div className="min-h-5" aria-live="polite">
            {saveState === "saving" ? (
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                Saving changes...
              </p>
            ) : null}
            {saveState === "error" ? (
              <div className="flex items-center gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--secondary-purple)]">
                  Save failed. Changes are local until retry succeeds.
                </p>
                <button
                  type="button"
                  onClick={retrySave}
                  className="rounded-full border border-[var(--stroke)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--navy-dark)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
                >
                  Retry save
                </button>
              </div>
            ) : null}
          </div>
        </header>

        <DndContext
          sensors={sensors}
          collisionDetection={collisionDetectionStrategy}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <section className="grid gap-6 lg:grid-cols-5">
            {board.columns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                cards={column.cardIds
                  .map((cardId) => board.cards[cardId])
                  .filter((card): card is (typeof board.cards)[string] => Boolean(card))}
                onRename={handleRenameColumn}
                onAddCard={handleAddCard}
                onDeleteCard={handleDeleteCard}
              />
            ))}
          </section>
          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>

      <AIChatSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onBoardUpdated={() => void refreshBoardSilently()}
      />
    </div>
  );
};
