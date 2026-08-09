import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { esPreventor, landingFor } from "./roles";
import { ThemeProvider } from "./theme";
import { ToastProvider } from "./toast";
import { AppLayout } from "./layout/AppLayout";
import { AgendaPage } from "./pages/AgendaPage";
import { DetallePage } from "./pages/DetallePage";
import { EstadisticasPage } from "./pages/EstadisticasPage";
import { LoginPage } from "./pages/LoginPage";
import { PerfilPage } from "./pages/PerfilPage";
import { RiesgoPage } from "./pages/RiesgoPage";

function Protected() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function SoloGestion() {
  const { user } = useAuth();
  if (esPreventor(user?.rol)) return <Navigate to="/agenda" replace />;
  return <Outlet />;
}

function LandingRedirect() {
  const { user } = useAuth();
  return <Navigate to={landingFor(user?.rol)} replace />;
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<Protected />}>
              <Route element={<AppLayout />}>
                <Route index element={<LandingRedirect />} />
                <Route element={<SoloGestion />}>
                  <Route path="riesgo" element={<RiesgoPage />} />
                </Route>
                <Route path="agenda" element={<AgendaPage />} />
                <Route path="estadisticas" element={<EstadisticasPage />} />
                <Route path="establecimientos/:id" element={<DetallePage />} />
                <Route path="perfil" element={<PerfilPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
