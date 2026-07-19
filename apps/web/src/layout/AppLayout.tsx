import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useState, type ReactNode } from "react";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import {
  IconCalendar,
  IconChart,
  IconCollapse,
  IconDownload,
  IconExpand,
  IconFlag,
  IconHistory,
  IconHome,
  IconLogout,
  IconMoon,
  IconSun,
  IconUser,
  LogoMark,
} from "../icons";

type NavItem = {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
  match?: (pathname: string) => boolean;
};

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Inicio",
    items: [{ to: "/", label: "Resumen", icon: <IconHome />, end: true }],
  },
  {
    group: "Operación",
    items: [
      {
        to: "/riesgo",
        label: "Priorización",
        icon: <IconFlag />,
        end: true,
        match: (p) => p === "/riesgo" || p.startsWith("/riesgo/"),
      },
      {
        to: "/agenda",
        label: "Agenda",
        icon: <IconCalendar />,
        end: true,
      },
      {
        to: "/auditoria",
        label: "Auditoría",
        icon: <IconHistory />,
        end: true,
      },
    ],
  },
  {
    group: "Análisis",
    items: [{ to: "/estadisticas", label: "Estadísticas", icon: <IconChart /> }],
  },
  {
    group: "Sistema",
    items: [
      { to: "/exportaciones", label: "Exportaciones", icon: <IconDownload /> },
      { to: "/perfil", label: "Perfil", icon: <IconUser /> },
    ],
  },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`app-shell${collapsed ? " collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <LogoMark className="brand-logo" size={34} />
          <div className="brand-text">
            <strong>Predictia</strong>
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
                end={item.end}
                className={() => {
                  const active = item.match
                    ? item.match(location.pathname)
                    : item.end
                      ? location.pathname === item.to
                      : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
                  return `nav-item${active ? " active" : ""}`;
                }}
                title={item.label}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="label">{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}

        <div className="sidebar-footer">
          <button
            className="icon-btn"
            title={collapsed ? "Expandir menú" : "Colapsar menú"}
            aria-label={collapsed ? "Expandir menú" : "Colapsar menú"}
            onClick={() => setCollapsed((v) => !v)}
          >
            {collapsed ? <IconExpand /> : <IconCollapse />}
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-left" />
          <div className="topbar-right">
            <button
              className="icon-btn"
              title={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
              aria-label="Cambiar tema"
              onClick={toggleTheme}
            >
              {theme === "dark" ? <IconSun /> : <IconMoon />}
            </button>
            <button
              className="icon-btn"
              title="Perfil"
              aria-label="Perfil"
              onClick={() => navigate("/perfil")}
            >
              <IconUser />
            </button>
            <span className="muted">
              {user?.nombre} · {user?.rol}
            </span>
            <button
              className="icon-btn"
              title="Salir"
              aria-label="Salir"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              <IconLogout />
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
