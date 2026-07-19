import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { AppLayout } from "./layout/AppLayout";
import { DetallePage } from "./pages/DetallePage";
import { ExportPage } from "./pages/ExportPage";
import { LoginPage } from "./pages/LoginPage";
import { ResumenPage } from "./pages/ResumenPage";
import { RiesgoPage } from "./pages/RiesgoPage";

function Protected() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Protected />}>
          <Route element={<AppLayout />}>
            <Route index element={<ResumenPage />} />
            <Route path="riesgo" element={<RiesgoPage />} />
            <Route path="riesgo/actividad" element={<RiesgoPage forceSectorFilter />} />
            <Route path="establecimientos/:id" element={<DetallePage />} />
            <Route path="exportaciones" element={<ExportPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
