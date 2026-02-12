import { useState } from 'react';
import { generateResume, optimizeResume } from '../services/api';
import { downloadResumePDF } from '../utils/pdfGenerator';
import ResumePreview from '../components/ResumePreview';
import './ResumeBuilder.css';

function ResumeBuilder() {
  const [jobDescription, setJobDescription] = useState('');
  const [experience, setExperience] = useState('');
  const [resumeType, setResumeType] = useState('private');
  const [generatedResume, setGeneratedResume] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const experienceArray = experience
        .split('\n')
        .filter((line) => line.trim())
        .map((line) => ({ description: line.trim() }));

      const result = await generateResume({
        jobDescription,
        experience: experienceArray,
        resumeType,
      });

      setGeneratedResume(result.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to generate resume');
    } finally {
      setLoading(false);
    }
  };

  const handleOptimize = async () => {
    if (!generatedResume) return;

    setLoading(true);
    setError(null);

    try {
      const result = await optimizeResume({
        resumeContent: generatedResume.content,
        jobDescription,
      });

      setGeneratedResume({
        ...generatedResume,
        content: result.data.optimizedContent,
        keywords: result.data.keywords,
      });
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to optimize resume');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!generatedResume) return;
    downloadResumePDF(
      { content: generatedResume.content, type: resumeType },
      `resume-${new Date().getTime()}.pdf`
    );
  };

  return (
    <div className="resume-builder">
      <h1>Resume Builder</h1>

      <div className="builder-container">
        <div className="input-section">
          <form onSubmit={handleGenerate}>
            <div className="form-group">
              <label htmlFor="jobDescription">Job Description</label>
              <textarea
                id="jobDescription"
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the job description here..."
                rows="8"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="experience">Your Experience</label>
              <textarea
                id="experience"
                value={experience}
                onChange={(e) => setExperience(e.target.value)}
                placeholder="List your experience (one per line)..."
                rows="8"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="resumeType">Resume Type</label>
              <select
                id="resumeType"
                value={resumeType}
                onChange={(e) => setResumeType(e.target.value)}
              >
                <option value="private">Private Sector (2-page)</option>
                <option value="federal">Federal (USAJOBS)</option>
              </select>
            </div>

            <button type="submit" disabled={loading} className="btn-primary">
              {loading ? 'Generating...' : 'Generate Resume'}
            </button>
          </form>

          {generatedResume && (
            <div className="action-buttons">
              <button
                onClick={handleOptimize}
                disabled={loading}
                className="btn-secondary"
              >
                Optimize for ATS
              </button>
              <button onClick={handleDownload} className="btn-success">
                Download PDF
              </button>
            </div>
          )}

          {error && <div className="error-message">{error}</div>}
        </div>

        {generatedResume && (
          <div className="preview-section">
            <ResumePreview resume={generatedResume} />
          </div>
        )}
      </div>
    </div>
  );
}

export default ResumeBuilder;
