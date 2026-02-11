import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { resumeAPI } from '../services/api';
import { Resume } from '../types';
import { FileText, Plus, Edit, Trash2, Download } from 'lucide-react';

const ResumeListPage = () => {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

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

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this resume?')) {
      return;
    }

    setDeleting(id);
    try {
      await resumeAPI.delete(id);
      setResumes(resumes.filter((r) => r.id !== id));
    } catch (error) {
      console.error('Failed to delete resume:', error);
      alert('Failed to delete resume');
    } finally {
      setDeleting(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-xl text-gray-500">Loading resumes...</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">My Resumes</h1>
          <p className="text-gray-600 mt-2">Manage all your resumes in one place</p>
        </div>
        <Link to="/resumes/new" className="btn btn-primary flex items-center space-x-2">
          <Plus size={20} />
          <span>New Resume</span>
        </Link>
      </div>

      {resumes.length === 0 ? (
        <div className="card text-center py-16">
          <FileText className="mx-auto text-gray-400 mb-4" size={64} />
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">
            No resumes yet
          </h2>
          <p className="text-gray-600 mb-6">
            Create your first resume to get started
          </p>
          <Link to="/resumes/new" className="btn btn-primary">
            Create Resume
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {resumes.map((resume) => (
            <div key={resume.id} className="card hover:shadow-lg transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <FileText className="text-primary-600" size={32} />
                {resume.atsScore && (
                  <div className="text-right">
                    <div className="text-xs text-gray-500">ATS Score</div>
                    <div className="text-lg font-bold text-primary-600">
                      {Math.round(resume.atsScore * 100)}%
                    </div>
                  </div>
                )}
              </div>

              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                {resume.title}
              </h3>

              <div className="text-sm text-gray-500 mb-4">
                <div>Template: {resume.template}</div>
                <div>Updated: {new Date(resume.updatedAt).toLocaleDateString()}</div>
              </div>

              <div className="flex items-center space-x-2 pt-4 border-t border-gray-200">
                <Link
                  to={`/resumes/${resume.id}/edit`}
                  className="flex-1 btn btn-primary text-sm flex items-center justify-center space-x-1"
                >
                  <Edit size={16} />
                  <span>Edit</span>
                </Link>
                <button
                  className="btn btn-secondary text-sm"
                  title="Download"
                >
                  <Download size={16} />
                </button>
                <button
                  onClick={() => handleDelete(resume.id)}
                  disabled={deleting === resume.id}
                  className="btn btn-secondary text-sm text-red-600 hover:bg-red-50"
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ResumeListPage;
