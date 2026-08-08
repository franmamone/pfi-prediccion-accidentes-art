import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "../auth";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageTransition } from "../components/PageTransition";
import {
  getFocusMode,
  getSidebarCollapsed,
  setFocusMode,
  setSidebarCollapsed,
} from "../prefs";
import { useTheme } from "../theme";
import {
  IconCalendar,
  IconChart,
  IconCollapse,
  IconDownload,
  IconExpand,
  IconFlag,
  IconFocus,
  IconHistory,
  IconHome,
  IconLogout,
  IconMoon,
  IconSun,
  IconUser,
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
  const [collapsed, setCollapsed] = useState(() => getSidebarCollapsed());
  const [focus, setFocus] = useState(() => getFocusMode());
  const [confirmLogout, setConfirmLogout] = useState(false);

  useEffect(() => {
    setSidebarCollapsed(collapsed);
  }, [collapsed]);

  useEffect(() => {
    setFocusMode(focus);
  }, [focus]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && focus) setFocus(false);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === ".") {
        e.preventDefault();
        setFocus((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [focus]);

  return (
    <div
      className={`app-shell${collapsed ? " collapsed" : ""}${focus ? " focus-mode" : ""}`}
    >
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo" src="/logo-mark.png" alt="Prevex" width={34} height={34} />
          <div className="brand-text">
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
              className={`icon-btn${focus ? " primary" : ""}`}
              title={focus ? "Salir del modo enfoque (Esc)" : "Modo enfoque (Ctrl+.)"}
              aria-label="Modo enfoque"
              aria-pressed={focus}
              onClick={() => setFocus((v) => !v)}
            >
              <IconFocus />
            </button>
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
              onClick={() => setConfirmLogout(true)}
            >
              <IconLogout />
            </button>
          </div>
        </header>
        <main className="content">
          <PageTransition>
            <Outlet />
          </PageTransition>
        </main>
      </div>
      {confirmLogout && (
        <ConfirmDialog
          title="Cerrar sesión"
          detail="Vas a salir de Prevex. Podés volver a ingresar cuando quieras."
          confirmLabel="Cerrar sesión"
          cancelLabel="Seguir en la app"
          danger
          onClose={() => setConfirmLogout(false)}
          onConfirm={() => {
            setConfirmLogout(false);
            logout();
            navigate("/login");
          }}
        />
      )}
    </div>
  );
}
