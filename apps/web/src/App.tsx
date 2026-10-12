import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { esAdmin, esPreventor, landingFor } from "./roles";
import { needsMfaSetup } from "./mfa";
import { rememberPostLoginNext } from "./loginRedirect";
import { ThemeProvider } from "./theme";
import { ToastProvider } from "./toast";
import { AppLayout } from "./layout/AppLayout";
import { AgendaPage } from "./pages/AgendaPage";
import { DetallePage } from "./pages/DetallePage";
import { EstadisticasPage } from "./pages/EstadisticasPage";
import { InvitarPage } from "./pages/InvitarPage";
import { LoginPage } from "./pages/LoginPage";
import { MfaSetupPage } from "./pages/MfaSetupPage";
import { PerfilPage } from "./pages/PerfilPage";
import { RecuperarPage } from "./pages/RecuperarPage";
import { RiesgoPage } from "./pages/RiesgoPage";
import { UsuariosPage } from "./pages/UsuariosPage";

function Protected() {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) {
    const next = `${location.pathname}${location.search}`;
    rememberPostLoginNext(next);
    const q = next && next !== "/" ? `?next=${encodeURIComponent(next)}` : "";
    return <Navigate to={`/login${q}`} replace />;
  }
  return <Outlet />;
}

function RequireMfaComplete() {
  const { user } = useAuth();
  if (needsMfaSetup(user)) {
    rememberPostLoginNext(`${window.location.pathname}${window.location.search}`);
    return <Navigate to="/mfa-setup" replace />;
  }
  return <Outlet />;
}

function SoloGestion() {
  const { user } = useAuth();
  if (esPreventor(user?.rol)) return <Navigate to="/agenda" replace />;
  return <Outlet />;
}

function SoloAdmin() {
  const { user } = useAuth();
  if (!esAdmin(user?.rol)) return <Navigate to="/perfil" replace />;
  return <Outlet />;
}

function LandingRedirect() {
  const { user } = useAuth();
  if (needsMfaSetup(user)) return <Navigate to="/mfa-setup" replace />;
  return <Navigate to={landingFor(user?.rol)} replace />;
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/invitar" element={<InvitarPage />} />
            <Route path="/recuperar" element={<RecuperarPage />} />
            <Route element={<Protected />}>
              <Route path="mfa-setup" element={<MfaSetupPage />} />
              <Route element={<RequireMfaComplete />}>
                <Route element={<AppLayout />}>
                  <Route index element={<LandingRedirect />} />
                  <Route element={<SoloGestion />}>
                    <Route path="riesgo" element={<RiesgoPage />} />
                  </Route>
                  <Route path="agenda" element={<AgendaPage />} />
                  <Route path="estadisticas" element={<EstadisticasPage />} />
                  <Route path="establecimientos/:id" element={<DetallePage />} />
                  <Route path="perfil" element={<PerfilPage />} />
                  <Route element={<SoloAdmin />}>
                    <Route path="usuarios" element={<UsuariosPage />} />
                  </Route>
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
