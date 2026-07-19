import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { ThemeProvider } from "./theme";
import { AppLayout } from "./layout/AppLayout";
import { AgendaPage } from "./pages/AgendaPage";
import { AuditoriaPage } from "./pages/AuditoriaPage";
import { DetallePage } from "./pages/DetallePage";
import { EstadisticasPage } from "./pages/EstadisticasPage";
import { ExportPage } from "./pages/ExportPage";
import { LoginPage } from "./pages/LoginPage";
import { PerfilPage } from "./pages/PerfilPage";
import { ResumenPage } from "./pages/ResumenPage";
import { RiesgoPage } from "./pages/RiesgoPage";

function Protected() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Protected />}>
            <Route element={<AppLayout />}>
              <Route index element={<ResumenPage />} />
              <Route path="riesgo" element={<RiesgoPage />} />
              <Route path="agenda" element={<AgendaPage />} />
              <Route path="auditoria" element={<AuditoriaPage />} />
              <Route path="estadisticas" element={<EstadisticasPage />} />
              <Route path="establecimientos/:id" element={<DetallePage />} />
              <Route path="exportaciones" element={<ExportPage />} />
              <Route path="perfil" element={<PerfilPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </ThemeProvider>
  );
}
