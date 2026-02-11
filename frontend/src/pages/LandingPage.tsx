import { Link } from 'react-router-dom';
import { FileText, Zap, TrendingUp, Users, CheckCircle } from 'lucide-react';

const LandingPage = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="text-2xl font-bold text-primary-600">
              AI Resume Builder
            </div>
            <div className="space-x-4">
              <Link to="/login" className="btn btn-outline">
                Login
              </Link>
              <Link to="/register" className="btn btn-primary">
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6">
            Build ATS-Optimized Resumes
            <span className="block text-primary-600 mt-2">Powered by AI</span>
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
            Create professional, job-winning resumes in minutes. Get instant ATS scores,
            AI-powered suggestions, and predictive callback analysis.
          </p>
          <Link to="/register" className="btn btn-primary text-lg px-8 py-3">
            Start Building Your Resume
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <h2 className="text-3xl font-bold text-center mb-12">
          Everything You Need to Land Your Dream Job
        </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          <div className="card text-center">
            <div className="flex justify-center mb-4">
              <FileText className="text-primary-600" size={48} />
            </div>
            <h3 className="text-xl font-semibold mb-2">Professional Templates</h3>
            <p className="text-gray-600">
              Choose from modern, ATS-friendly templates designed to get you noticed.
            </p>
          </div>

          <div className="card text-center">
            <div className="flex justify-center mb-4">
              <Zap className="text-primary-600" size={48} />
            </div>
            <h3 className="text-xl font-semibold mb-2">Real-time ATS Scoring</h3>
            <p className="text-gray-600">
              Get instant feedback on keyword matching, semantic similarity, and impact.
            </p>
          </div>

          <div className="card text-center">
            <div className="flex justify-center mb-4">
              <TrendingUp className="text-primary-600" size={48} />
            </div>
            <h3 className="text-xl font-semibold mb-2">Callback Prediction</h3>
            <p className="text-gray-600">
              AI-powered model predicts your likelihood of getting a callback.
            </p>
          </div>

          <div className="card text-center">
            <div className="flex justify-center mb-4">
              <Users className="text-primary-600" size={48} />
            </div>
            <h3 className="text-xl font-semibold mb-2">Team Collaboration</h3>
            <p className="text-gray-600">
              Enterprise features for teams to collaborate and manage resumes together.
            </p>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-12 h-12 bg-primary-600 text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                1
              </div>
              <h3 className="text-xl font-semibold mb-2">Create Your Resume</h3>
              <p className="text-gray-600">
                Choose a template and fill in your information with our intuitive editor.
              </p>
            </div>

            <div className="text-center">
              <div className="w-12 h-12 bg-primary-600 text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                2
              </div>
              <h3 className="text-xl font-semibold mb-2">Optimize with AI</h3>
              <p className="text-gray-600">
                Paste a job description and get AI-powered optimization suggestions.
              </p>
            </div>

            <div className="text-center">
              <div className="w-12 h-12 bg-primary-600 text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                3
              </div>
              <h3 className="text-xl font-semibold mb-2">Download & Apply</h3>
              <p className="text-gray-600">
                Export your ATS-optimized resume and start applying with confidence.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
        <h2 className="text-4xl font-bold mb-6">Ready to Get Started?</h2>
        <p className="text-xl text-gray-600 mb-8">
          Join thousands of job seekers who've landed their dream jobs with our AI-powered platform.
        </p>
        <Link to="/register" className="btn btn-primary text-lg px-8 py-3">
          Create Your Free Resume
        </Link>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p>&copy; 2024 AI Resume Builder. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
