import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth';
import AssessmentForm from './pages/AssessmentForm';
import ClientDetail from './pages/ClientDetail';
import Clients from './pages/Clients';
import CustomFields from './pages/CustomFields';
import Dashboard from './pages/Dashboard';
import Diets from './pages/Diets';
import Login from './pages/Login';
import Plans from './pages/Plans';
import Settings from './pages/Settings';
import Users from './pages/Users';

// 未登录跳登录页
function Guard({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8">加载中…</div>;
  return user ? children : <Navigate to="/login" />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Guard><Dashboard /></Guard>} />
          <Route path="/clients" element={<Guard><Clients /></Guard>} />
          <Route path="/clients/:id" element={<Guard><ClientDetail /></Guard>} />
          <Route path="/clients/:id/assess" element={<Guard><AssessmentForm /></Guard>} />
          <Route path="/clients/:id/plans" element={<Guard><Plans /></Guard>} />
          <Route path="/clients/:id/diets" element={<Guard><Diets /></Guard>} />
          <Route path="/users" element={<Guard><Users /></Guard>} />
          <Route path="/fields" element={<Guard><CustomFields /></Guard>} />
          <Route path="/settings" element={<Guard><Settings /></Guard>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
