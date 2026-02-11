import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { resumeAPI } from '../services/api';
import { FileText, Plus, TrendingUp, Award } from 'lucide-react';
import { Resume } from '../types';

const DashboardPage = () => {
  const { user } = useAuthStore();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadResumes();
  }, []);

  const loadResumes = async () => {
    try {
      const response = await resumeAPI.getAll();
      setResumes(response.data.data);
    } catch (error) {
      console.error('Failed to load resumes:', error);
    } finally {
      setLoading(false);
    }
  };

  const averageScore = resumes.length > 0
    ? resumes.reduce((sum, r) => sum + (r.atsScore || 0), 0) / resumes.filter(r => r.atsScore).length
    : 0;

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          Welcome back, {user?.firstName || 'there'}!
        </h1>
        <p className="text-gray-600 mt-2">
          Here's an overview of your resume building progress
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Total Resumes</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {resumes.length}
              </p>
            </div>
            <FileText className="text-primary-600" size={40} />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Average ATS Score</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {averageScore > 0 ? Math.round(averageScore * 100) : 'N/A'}
                {averageScore > 0 && '%'}
              </p>
            </div>
            <TrendingUp className="text-green-600" size={40} />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Subscription</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {user?.subscription?.tier || 'FREE'}
              </p>
            </div>
            <Award className="text-yellow-600" size={40} />
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <Link
          to="/resumes/new"
          className="card hover:shadow-lg transition-shadow cursor-pointer"
        >
          <div className="flex items-center space-x-4">
            <div className="bg-primary-100 p-3 rounded-lg">
              <Plus className="text-primary-600" size={32} />
            </div>
            <div>
              <h3 className="text-xl font-semibold">Create New Resume</h3>
              <p className="text-gray-600">Start building a new ATS-optimized resume</p>
            </div>
          </div>
        </Link>

        <Link
          to="/resumes"
          className="card hover:shadow-lg transition-shadow cursor-pointer"
        >
          <div className="flex items-center space-x-4">
            <div className="bg-blue-100 p-3 rounded-lg">
              <FileText className="text-blue-600" size={32} />
            </div>
            <div>
              <h3 className="text-xl font-semibold">View All Resumes</h3>
              <p className="text-gray-600">Manage and edit your existing resumes</p>
            </div>
          </div>
        </Link>
      </div>

      {/* Recent Resumes */}
      <div className="card">
        <h2 className="text-2xl font-bold mb-4">Recent Resumes</h2>
        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : resumes.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-500 mb-4">You haven't created any resumes yet.</p>
            <Link to="/resumes/new" className="btn btn-primary">
              Create Your First Resume
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {resumes.slice(0, 5).map((resume) => (
              <Link
                key={resume.id}
                to={`/resumes/${resume.id}/edit`}
                className="block p-4 border border-gray-200 rounded-lg hover:border-primary-500 hover:shadow-md transition-all"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <FileText className="text-gray-400" size={24} />
                    <div>
                      <h3 className="font-semibold text-gray-900">{resume.title}</h3>
                      <p className="text-sm text-gray-500">
                        Updated {new Date(resume.updatedAt).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  {resume.atsScore && (
                    <div className="text-right">
                      <p className="text-sm text-gray-500">ATS Score</p>
                      <p className="text-lg font-bold text-primary-600">
                        {Math.round(resume.atsScore * 100)}%
                      </p>
                    </div>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Upgrade CTA */}
      {user?.subscription?.tier === 'FREE' && (
        <div className="card bg-gradient-to-r from-primary-500 to-primary-600 text-white mt-8">
          <h2 className="text-2xl font-bold mb-2">Upgrade to Pro</h2>
          <p className="mb-4">
            Unlock unlimited resumes, advanced ATS analysis, and callback predictions
          </p>
          <Link to="/pricing" className="btn bg-white text-primary-600 hover:bg-gray-100">
            View Pricing Plans
          </Link>
        </div>
      )}
    </div>
  );
};

export default DashboardPage;
