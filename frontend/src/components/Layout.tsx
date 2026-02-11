import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { LogOut, FileText, Users, LayoutDashboard, Settings } from 'lucide-react';

const Layout = () => {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-8">
              <Link to="/dashboard" className="text-2xl font-bold text-primary-600">
                AI Resume Builder
              </Link>
              <nav className="hidden md:flex space-x-6">
                <Link
                  to="/dashboard"
                  className="flex items-center space-x-2 text-gray-700 hover:text-primary-600"
                >
                  <LayoutDashboard size={18} />
                  <span>Dashboard</span>
                </Link>
                <Link
                  to="/resumes"
                  className="flex items-center space-x-2 text-gray-700 hover:text-primary-600"
                >
                  <FileText size={18} />
                  <span>Resumes</span>
                </Link>
                {user?.role === 'TEAM_ADMIN' || user?.role === 'ADMIN' ? (
                  <Link
                    to="/teams"
                    className="flex items-center space-x-2 text-gray-700 hover:text-primary-600"
                  >
                    <Users size={18} />
                    <span>Teams</span>
                  </Link>
                ) : null}
                {user?.role === 'ADMIN' && (
                  <Link
                    to="/admin"
                    className="flex items-center space-x-2 text-gray-700 hover:text-primary-600"
                  >
                    <Settings size={18} />
                    <span>Admin</span>
                  </Link>
                )}
              </nav>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-sm">
                <div className="font-medium text-gray-900">
                  {user?.firstName || user?.email}
                </div>
                <div className="text-xs text-gray-500">
                  {user?.subscription?.tier || 'FREE'} Plan
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center space-x-2 text-gray-700 hover:text-red-600"
              >
                <LogOut size={18} />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
