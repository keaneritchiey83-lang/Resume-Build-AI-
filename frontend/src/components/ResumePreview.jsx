import './ResumePreview.css';

function ResumePreview({ resume }) {
  if (!resume) return null;

  return (
    <div className="resume-preview">
      <h2>Resume Preview</h2>
      <div className="preview-content">
        <pre>{resume.content}</pre>
      </div>
      {resume.keywords && (
        <div className="keywords-section">
          <h3>ATS Keywords</h3>
          <div className="keywords">
            {resume.keywords.map((keyword, index) => (
              <span key={index} className="keyword">
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ResumePreview;
