import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "../auth";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageTransition } from "../components/PageTransition";
import { getSidebarCollapsed, setSidebarCollapsed } from "../prefs";
import { useTheme } from "../theme";
import {
  IconCalendar,
  IconChart,
  IconCollapse,
  IconExpand,
  IconFlag,
  IconLogout,
  IconMenu,
  IconMoon,
  IconSun,
  IconUser,
  IconX,
} from "../icons";

type NavItem = {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
  match?: (pathname: string) => boolean;
};

function buildNav(rol: string | undefined): { group: string; items: NavItem[] }[] {
  const esPreventor = rol === "Prevencionista";
  const operacion: NavItem[] = [];
  if (!esPreventor) {
    operacion.push({
      to: "/riesgo",
      label: "Priorización",
      icon: <IconFlag />,
      end: true,
      match: (p) => p === "/riesgo" || p.startsWith("/riesgo/"),
    });
  }
  operacion.push({
    to: "/agenda",
    label: esPreventor ? "Mi agenda" : "Agenda",
    icon: <IconCalendar />,
    end: true,
  });

  return [
    { group: "Operación", items: operacion },
    { group: "Análisis", items: [{ to: "/estadisticas", label: "Estadísticas", icon: <IconChart /> }] },
    { group: "Sistema", items: [{ to: "/perfil", label: "Perfil", icon: <IconUser /> }] },
  ];
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => getSidebarCollapsed());
  const [confirmLogout, setConfirmLogout] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const nav = buildNav(user?.rol);

  useEffect(() => {
    setSidebarCollapsed(collapsed);
  }, [collapsed]);

  // Cerrar el menú móvil al navegar a otra ruta.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  // Bloquear el scroll del fondo mientras el drawer móvil está abierto.
  useEffect(() => {
    if (!mobileNavOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileNavOpen]);

  return (
    <div className={`app-shell${collapsed ? " collapsed" : ""}${mobileNavOpen ? " nav-open" : ""}`}>
      {mobileNavOpen && (
        <button
          type="button"
          className="nav-overlay"
          aria-label="Cerrar menú"
          onClick={() => setMobileNavOpen(false)}
        />
      )}
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo" src="/logo-mark.png" alt="Prevex" width={34} height={34} />
          <div className="brand-text">
            <strong>PREVEX</strong>
          </div>
          <button
            type="button"
            className="icon-btn nav-close"
            aria-label="Cerrar menú"
            onClick={() => setMobileNavOpen(false)}
          >
            <IconX />
          </button>
        </div>

        {nav.map((section) => (
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

      <div className={`main${location.pathname === "/riesgo" ? " main-fill" : ""}`}>
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="icon-btn nav-toggle"
              aria-label="Abrir menú"
              aria-expanded={mobileNavOpen}
              onClick={() => setMobileNavOpen((v) => !v)}
            >
              <IconMenu />
            </button>
            <div className="topbar-brand">
              <img src="/logo-mark.png" alt="Prevex" width={26} height={26} />
              <strong>PREVEX</strong>
            </div>
          </div>
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
