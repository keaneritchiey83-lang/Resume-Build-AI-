import './Dashboard.css';

function Dashboard() {
  return (
    <div className="dashboard">
      <h1>Application Tracking Dashboard</h1>

      <div className="dashboard-grid">
        <div className="dashboard-card">
          <h2>Resumes Created</h2>
          <p className="stat">0</p>
          <p className="description">Total resumes generated</p>
        </div>

        <div className="dashboard-card">
          <h2>Interviews Prepared</h2>
          <p className="stat">0</p>
          <p className="description">Interview prep sessions</p>
        </div>

        <div className="dashboard-card">
          <h2>Applications</h2>
          <p className="stat">0</p>
          <p className="description">Job applications tracked</p>
        </div>

        <div className="dashboard-card">
          <h2>Success Rate</h2>
          <p className="stat">N/A</p>
          <p className="description">Interview to offer ratio</p>
        </div>
      </div>

      <div className="recent-activity">
        <h2>Recent Activity</h2>
        <p className="no-activity">No recent activity yet. Start by creating your first resume!</p>
      </div>
    </div>
  );
}

export default Dashboard;
