import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const LoginPage = () => {
  const navigate = useNavigate();
  const { login, isLoading } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } };
      setError(error.response?.data?.message || 'Login failed. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <Link to="/" className="text-3xl font-bold text-primary-600">
            AI Resume Builder
          </Link>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            Welcome back
          </h2>
          <p className="mt-2 text-gray-600">
            Sign in to continue building your resume
          </p>
        </div>

        <div className="card">
          {error && (
            <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full btn btn-primary"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          <div className="mt-6 text-center text-sm">
            <span className="text-gray-600">Don't have an account?</span>{' '}
            <Link to="/register" className="text-primary-600 font-medium hover:text-primary-700">
              Sign up
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
