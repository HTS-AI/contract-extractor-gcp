# Invoice to AP – React frontend

Full React UI for the Invoice to AP application. All sections (Login, Home, Dashboard, Selected Factors, Data Table, Payment Table, Buyer Portal, File Manager) are implemented in React. The **backend remains the existing FastAPI app** (Python); the frontend talks to it via `/api`.

## Run

1. **Start the FastAPI backend** (from project root):
   ```bash
   python app.py
   ```
   Backend runs at http://127.0.0.1:8000

2. **Install and run the React app**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Frontend runs at http://localhost:5173 and proxies `/api` to the backend.

3. Open **http://localhost:5173** in the browser.
   - Log in with main user (`HtsAI-testuser` / `HTStest@2025`) for the main app.
   - Log in with buyer (`buyer` / `buyer@2025`) to open the Buyer Portal.

## Sections (all in React)

- **Login** – Auth; redirects buyer to Buyer Portal, main user to Home.
- **Home** – Upload invoice, extract, view results, dashboard stats, document selector, File Manager modal.
- **Selected Factors** – Select document, view factors (from JSON or Excel).
- **Data Table** – Excel-style table of extractions; refresh and download Excel.
- **JSON Dashboard** – View all extractions as JSON; search and filter by type.
- **Payment Table** – Invoice payment status, amount received, due date filters.
- **Buyer Portal** – Upload PO and GRN; view match status (PO + GRN + Invoice).

## Build for production

```bash
cd frontend
npm run build
```

To serve the built app from FastAPI, copy `frontend/dist` into `static/` and serve `index.html` for SPA routes, or host the `dist` folder with any static server and set the API base URL to your backend.

## Stack

- **React 18** – UI
- **Vite** – build and dev server
- **Tailwind CSS** – styling
- **React Router** – routing
- **Backend** – existing FastAPI app (unchanged)
