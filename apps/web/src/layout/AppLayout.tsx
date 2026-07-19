import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../auth";

const NAV = [
  {
    group: "Inicio",
    items: [{ to: "/", label: "Resumen", icon: "⌂" }],
  },
  {
    group: "Riesgo",
    items: [
      { to: "/riesgo", label: "Priorización", icon: "⚑" },
      { to: "/riesgo/actividad", label: "Por actividad", icon: "▦" },
    ],
  },
  {
    group: "Sistema",
    items: [{ to: "/exportaciones", label: "Exportaciones", icon: "⇩" }],
  },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`app-shell${collapsed ? " collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" />
          <div className="brand-text">
            <strong>PFI Prevención</strong>
            <span>Prioridad de visitas</span>
          </div>
        </div>

        {NAV.map((section) => (
          <div className="nav-group" key={section.group}>
            <div className="nav-label">{section.group}</div>
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="label">{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}

        <div style={{ marginTop: "auto" }}>
          <button className="ghost-btn" style={{ width: "100%" }} onClick={() => setCollapsed((v) => !v)}>
            {collapsed ? "»" : "« Colapsar"}
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-left">
            <span className="muted">Holdout operativo · score = prioridad</span>
          </div>
          <div className="topbar-right">
            <span className="muted">
              {user?.nombre} · {user?.rol}
            </span>
            <button
              className="ghost-btn"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Salir
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
