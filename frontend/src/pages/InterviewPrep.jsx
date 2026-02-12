import { useState } from 'react';
import { prepareInterview } from '../services/api';
import './InterviewPrep.css';

function InterviewPrep() {
  const [jobDescription, setJobDescription] = useState('');
  const [interviewType, setInterviewType] = useState('behavioral');
  const [questions, setQuestions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handlePrepare = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await prepareInterview({
        jobDescription,
        interviewType,
      });

      setQuestions(result.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to prepare interview questions');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="interview-prep">
      <h1>Interview Preparation</h1>

      <div className="prep-container">
        <form onSubmit={handlePrepare} className="prep-form">
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
            <label htmlFor="interviewType">Interview Type</label>
            <select
              id="interviewType"
              value={interviewType}
              onChange={(e) => setInterviewType(e.target.value)}
            >
              <option value="behavioral">Behavioral</option>
              <option value="technical">Technical</option>
              <option value="federal">Federal Panel</option>
            </select>
          </div>

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Preparing...' : 'Generate Questions'}
          </button>
        </form>

        {error && <div className="error-message">{error}</div>}

        {questions && (
          <div className="questions-section">
            <h2>{questions.interviewType} Interview Questions</h2>
            <div className="questions-list">
              {questions.questions.map((q, index) => (
                <div key={index} className="question-card">
                  <h3>Question {index + 1}</h3>
                  <p className="question">{q.question}</p>
                  <div className="guidance">
                    <strong>Guidance:</strong>
                    <p>{q.guidance}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default InterviewPrep;
