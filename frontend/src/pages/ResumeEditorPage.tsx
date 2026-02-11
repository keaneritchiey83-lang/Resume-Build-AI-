import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { resumeAPI } from '../services/api';
import { ResumeContent } from '../types';

const ResumeEditorPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState('My Resume');
  const [content, setContent] = useState<ResumeContent>({
    personalInfo: {},
    summary: '',
    experience: [],
    education: [],
    skills: [],
  });
  const [loading, setLoading] = useState(!!id);
  const [saving, setSaving] = useState(false);

  const loadResume = async () => {
    try {
      const response = await resumeAPI.getOne(id!);
      const data = response.data.data;
      setTitle(data.title);
      setContent(data.content as ResumeContent);
    } catch (error) {
      console.error('Failed to load resume:', error);
      alert('Failed to load resume');
      navigate('/resumes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) {
      loadResume();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (id) {
        await resumeAPI.update(id, { title, content });
        alert('Resume updated successfully');
      } else {
        const response = await resumeAPI.create({ title, content, template: 'modern' });
        navigate(`/resumes/${response.data.data.id}/edit`);
      }
    } catch (error) {
      console.error('Failed to save resume:', error);
      alert('Failed to save resume');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-xl text-gray-500">Loading resume...</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="text-3xl font-bold border-none focus:outline-none focus:ring-2 focus:ring-primary-500 rounded px-2"
            placeholder="Resume Title"
          />
        </div>
        <div className="space-x-2">
          <button
            onClick={() => navigate('/resumes')}
            className="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn btn-primary"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Editor */}
        <div className="space-y-6">
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Personal Information</h2>
            <div className="space-y-4">
              <input
                type="text"
                placeholder="Full Name"
                value={content.personalInfo?.name || ''}
                onChange={(e) =>
                  setContent({
                    ...content,
                    personalInfo: { ...content.personalInfo, name: e.target.value },
                  })
                }
                className="input"
              />
              <input
                type="email"
                placeholder="Email"
                value={content.personalInfo?.email || ''}
                onChange={(e) =>
                  setContent({
                    ...content,
                    personalInfo: { ...content.personalInfo, email: e.target.value },
                  })
                }
                className="input"
              />
              <input
                type="tel"
                placeholder="Phone"
                value={content.personalInfo?.phone || ''}
                onChange={(e) =>
                  setContent({
                    ...content,
                    personalInfo: { ...content.personalInfo, phone: e.target.value },
                  })
                }
                className="input"
              />
            </div>
          </div>

          <div className="card">
            <h2 className="text-xl font-bold mb-4">Summary</h2>
            <textarea
              placeholder="Brief professional summary..."
              value={content.summary || ''}
              onChange={(e) => setContent({ ...content, summary: e.target.value })}
              className="input min-h-[120px]"
            />
          </div>

          <div className="card">
            <h2 className="text-xl font-bold mb-4">Skills</h2>
            <input
              type="text"
              placeholder="e.g. JavaScript, React, Node.js (comma-separated)"
              value={content.skills?.join(', ') || ''}
              onChange={(e) =>
                setContent({
                  ...content,
                  skills: e.target.value.split(',').map((s) => s.trim()),
                })
              }
              className="input"
            />
          </div>
        </div>

        {/* Preview */}
        <div className="card bg-white">
          <h2 className="text-xl font-bold mb-4">Preview</h2>
          <div className="border border-gray-300 rounded p-6 bg-white min-h-[600px]">
            {/* Personal Info */}
            {content.personalInfo?.name && (
              <div className="mb-6">
                <h1 className="text-3xl font-bold text-gray-900">
                  {content.personalInfo.name}
                </h1>
                {content.personalInfo.email && (
                  <p className="text-gray-600">{content.personalInfo.email}</p>
                )}
                {content.personalInfo.phone && (
                  <p className="text-gray-600">{content.personalInfo.phone}</p>
                )}
              </div>
            )}

            {/* Summary */}
            {content.summary && (
              <div className="mb-6">
                <h2 className="text-xl font-bold text-gray-900 mb-2">Summary</h2>
                <p className="text-gray-700">{content.summary}</p>
              </div>
            )}

            {/* Skills */}
            {content.skills && content.skills.length > 0 && (
              <div className="mb-6">
                <h2 className="text-xl font-bold text-gray-900 mb-2">Skills</h2>
                <div className="flex flex-wrap gap-2">
                  {content.skills.map((skill, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-primary-100 text-primary-700 rounded-full text-sm"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResumeEditorPage;
