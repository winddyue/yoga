import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth';
import AssessmentForm from './pages/AssessmentForm';
import ClientDetail from './pages/ClientDetail';
import Clients from './pages/Clients';
import Courses from './pages/Courses';
import CustomFields from './pages/CustomFields';
import Dashboard from './pages/Dashboard';
import Diets from './pages/Diets';
import Intake from './pages/Intake';
import Login from './pages/Login';
import Plans from './pages/Plans';
import Settings from './pages/Settings';
import Users from './pages/Users';

// 未登录跳登录页；role 限定角色可访问
function Guard({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8">加载中…</div>;
  if (!user) return <Navigate to="/login" />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" />;
  return children;
}

const STAFF = ['owner', 'coach'];

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Guard><Dashboard /></Guard>} />
          <Route path="/clients" element={<Guard roles={STAFF}><Clients /></Guard>} />
          <Route path="/clients/:id" element={<Guard roles={STAFF}><ClientDetail /></Guard>} />
          <Route path="/clients/:id/assess" element={<Guard roles={STAFF}><AssessmentForm /></Guard>} />
          <Route path="/clients/:id/plans" element={<Guard roles={STAFF}><Plans /></Guard>} />
          <Route path="/clients/:id/diets" element={<Guard roles={STAFF}><Diets /></Guard>} />
          <Route path="/courses" element={<Guard><Courses /></Guard>} />
          <Route path="/intake" element={<Guard roles={STAFF}><Intake /></Guard>} />
          <Route path="/users" element={<Guard roles={['owner']}><Users /></Guard>} />
          <Route path="/fields" element={<Guard roles={['owner']}><CustomFields /></Guard>} />
          <Route path="/settings" element={<Guard roles={['owner']}><Settings /></Guard>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
