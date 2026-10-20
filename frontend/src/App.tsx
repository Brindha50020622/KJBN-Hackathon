import { NavLink, Route, Routes } from "react-router-dom";

import BatchesPage from "./pages/BatchesPage";
import DashboardPage from "./pages/DashboardPage";
import TransactionsPage from "./pages/TransactionsPage";
import UploadPage from "./pages/UploadPage";

const LINKS = [
  ["/", "Upload"],
  ["/batches", "Batches"],
  ["/dashboard", "Dashboard"],
  ["/transactions", "Transactions"],
] as const;

export default function App() {
  return (
    <>
      <header className="top">
        <h1>Sales Import &amp; Dashboard</h1>
        <nav>
          {LINKS.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/batches" element={<BatchesPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Routes>
      </main>
    </>
  );
}