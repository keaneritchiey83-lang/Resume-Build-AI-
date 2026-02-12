import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navigation from './components/Navigation';
import ErrorBoundary from './components/ErrorBoundary';
import Home from './pages/Home';
import ResumeBuilder from './pages/ResumeBuilder';
import InterviewPrep from './pages/InterviewPrep';
import Dashboard from './pages/Dashboard';
import './App.css';

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <div className="App">
          <Navigation />
          <main>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/resume" element={<ResumeBuilder />} />
              <Route path="/interview" element={<InterviewPrep />} />
              <Route path="/dashboard" element={<Dashboard />} />
            </Routes>
          </main>
        </div>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
