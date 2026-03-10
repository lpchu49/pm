import { expect, test, type Page } from "@playwright/test";

type BoardPayload = {
  columns: Array<{ id: string; title: string; cardIds: string[] }>;
  cards: Record<string, { id: string; title: string; details: string }>;
};

const buildDeterministicBoard = (): BoardPayload => ({
  columns: [
    { id: "col-backlog", title: "Backlog", cardIds: ["card-1", "card-2"] },
    { id: "col-discovery", title: "Discovery", cardIds: ["card-3"] },
    { id: "col-progress", title: "In Progress", cardIds: ["card-4"] },
    { id: "col-review", title: "Review", cardIds: [] },
    { id: "col-done", title: "Done", cardIds: [] },
  ],
  cards: {
    "card-1": {
      id: "card-1",
      title: "Align roadmap themes",
      details: "Draft quarterly themes with impact statements and metrics.",
    },
    "card-2": {
      id: "card-2",
      title: "Gather customer signals",
      details: "Review support tags, sales notes, and churn feedback.",
    },
    "card-3": {
      id: "card-3",
      title: "Prototype analytics view",
      details: "Sketch initial dashboard layout and key drill-downs.",
    },
    "card-4": {
      id: "card-4",
      title: "Refine status language",
      details: "Standardize column labels and tone across the board.",
    },
  },
});

const resetBoard = async (page: Page) => {
  const board = buildDeterministicBoard();
  const response = await page.evaluate(async (nextBoard) => {
    const apiResponse = await fetch("/api/board", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(nextBoard),
    });

    return { ok: apiResponse.ok };
  }, board);

  expect(response.ok).toBeTruthy();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
};

const login = async (page: Page) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
};

const getFirstCardTestId = async (column: ReturnType<Page["getByTestId"]>) => {
  const card = column.locator('[data-testid^="card-"]').first();
  const testId = await card.getAttribute("data-testid");
  if (!testId) {
    throw new Error("No source card found in column.");
  }

  return testId;
};

test("requires login before showing the board", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(0);
});

test("rejects invalid credentials", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("bad-user");
  await page.getByLabel("Password").fill("bad-pass");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByText(/incorrect username or password/i)).toBeVisible();
});

test("loads the kanban board after login", async ({ page }) => {
  await login(page);
  await resetBoard(page);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await login(page);
  await resetBoard(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  const cardTitle = `Playwright card ${Date.now()}`;
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill(cardTitle);
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText(cardTitle)).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await login(page);
  await resetBoard(page);
  const sourceColumn = page.getByTestId("column-col-backlog");
  const sourceCardTestId = await getFirstCardTestId(sourceColumn);
  const card = page.getByTestId(sourceCardTestId);
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(targetColumn.getByTestId(sourceCardTestId)).toBeVisible();
});

test("moves a card into an empty column", async ({ page }) => {
  await login(page);
  await resetBoard(page);

  const reviewColumn = page.getByTestId("column-col-review");
  const backlogColumn = page.getByTestId("column-col-backlog");
  const reviewCards = reviewColumn.locator('[data-testid^="card-"]');

  if ((await reviewCards.count()) > 0) {
    const reviewCard = reviewCards.first();
    const backlogDropTarget = backlogColumn.getByTestId("dropzone-col-backlog");
    const backlogDropBox = await backlogDropTarget.boundingBox();
    const reviewCardBox = await reviewCard.boundingBox();
    if (!backlogDropBox || !reviewCardBox) {
      throw new Error("Unable to resolve coordinates for empty-column setup.");
    }

    await page.mouse.move(
      reviewCardBox.x + reviewCardBox.width / 2,
      reviewCardBox.y + reviewCardBox.height / 2
    );
    await page.mouse.down();
    await page.mouse.move(
      backlogDropBox.x + backlogDropBox.width / 2,
      backlogDropBox.y + backlogDropBox.height / 2,
      { steps: 12 }
    );
    await page.mouse.up();
    await expect(reviewCards).toHaveCount(0);
  }

  const sourceColumn = page.getByTestId("column-col-backlog");
  const sourceCardTestId = await getFirstCardTestId(sourceColumn);
  const cardToMove = page.getByTestId(sourceCardTestId);
  const cardToMoveBox = await cardToMove.boundingBox();
  const reviewDropTarget = reviewColumn.getByTestId("dropzone-col-review");
  const reviewDropBox = await reviewDropTarget.boundingBox();
  if (!cardToMoveBox || !reviewDropBox) {
    throw new Error("Unable to resolve coordinates for empty-column drop.");
  }

  await page.mouse.move(
    cardToMoveBox.x + cardToMoveBox.width / 2,
    cardToMoveBox.y + cardToMoveBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    reviewDropBox.x + reviewDropBox.width / 2,
    reviewDropBox.y + reviewDropBox.height / 2,
    { steps: 12 }
  );
  await page.mouse.up();

  await expect(reviewColumn.getByTestId(sourceCardTestId)).toBeVisible();
});

test("logs out back to sign-in screen", async ({ page }) => {
  await login(page);
  await resetBoard(page);
  await page.getByRole("button", { name: /log out/i }).click();
  await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
});

test("persists board changes across logout and login", async ({ page }) => {
  await login(page);
  await resetBoard(page);

  const firstColumn = page.locator('[data-testid="column-col-backlog"]');
  const titleInput = firstColumn.getByLabel("Column title");
  await titleInput.fill("Persisted Backlog");
  await expect(titleInput).toHaveValue("Persisted Backlog");

  await page.getByRole("button", { name: /log out/i }).click();
  await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();

  await login(page);
  await expect(
    page.locator('[data-testid="column-col-backlog"]').getByLabel("Column title")
  ).toHaveValue("Persisted Backlog");
});

test("persists board changes after page refresh", async ({ page }) => {
  await login(page);
  await resetBoard(page);

  const firstColumn = page.locator('[data-testid="column-col-backlog"]');
  const titleInput = firstColumn.getByLabel("Column title");
  await titleInput.fill("Refresh Persisted Backlog");
  await expect(titleInput).toHaveValue("Refresh Persisted Backlog");

  await page.reload();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(
    page.locator('[data-testid="column-col-backlog"]').getByLabel("Column title")
  ).toHaveValue("Refresh Persisted Backlog");
});
