import { Link } from 'react-router-dom';
import './Navigation.css';

function Navigation() {
  return (
    <nav className="navigation">
      <div className="nav-container">
        <Link to="/" className="nav-logo">
          Resume Build AI
        </Link>
        <ul className="nav-menu">
          <li className="nav-item">
            <Link to="/resume" className="nav-link">
              Resume Builder
            </Link>
          </li>
          <li className="nav-item">
            <Link to="/interview" className="nav-link">
              Interview Prep
            </Link>
          </li>
          <li className="nav-item">
            <Link to="/dashboard" className="nav-link">
              Dashboard
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  );
}

export default Navigation;
