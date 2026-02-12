import { Link } from 'react-router-dom';
import './Home.css';

function Home() {
  return (
    <div className="home">
      <section className="hero">
        <h1>Resume Build AI</h1>
        <p className="tagline">
          AI-powered resume and interview preparation platform
        </p>
        <p className="description">
          Built for precision. Optimized for hiring systems. Designed for results.
        </p>
        <div className="cta-buttons">
          <Link to="/resume" className="btn-large btn-primary">
            Build Resume
          </Link>
          <Link to="/interview" className="btn-large btn-secondary">
            Interview Prep
          </Link>
        </div>
      </section>

      <section className="features">
        <h2>Core Capabilities</h2>
        <div className="features-grid">
          <div className="feature-card">
            <h3>📄 Resume Generation</h3>
            <p>AI-driven resume creation with ATS optimization</p>
            <ul>
              <li>Keyword extraction from job postings</li>
              <li>Achievement quantification</li>
              <li>Federal & private sector formats</li>
            </ul>
          </div>

          <div className="feature-card">
            <h3>🎯 Interview Preparation</h3>
            <p>Structured interview prep with AI guidance</p>
            <ul>
              <li>STAR method questions</li>
              <li>Technical scenarios</li>
              <li>Federal panel prep</li>
            </ul>
          </div>

          <div className="feature-card">
            <h3>📊 Career Strategy</h3>
            <p>Data-driven career advancement tools</p>
            <ul>
              <li>Skill gap analysis</li>
              <li>Certification recommendations</li>
              <li>Application tracking</li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Home;
