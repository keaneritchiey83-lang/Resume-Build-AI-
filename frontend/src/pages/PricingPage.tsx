import { Link } from 'react-router-dom';
import { Check } from 'lucide-react';

const PricingPage = () => {
  const plans = [
    {
      name: 'Free',
      price: '$0',
      description: 'Perfect for getting started',
      features: [
        '1 Resume',
        'Basic Templates',
        'PDF Export',
        'Basic ATS Scoring',
      ],
      cta: 'Get Started',
      ctaLink: '/register',
    },
    {
      name: 'Pro',
      price: '$29',
      period: '/month',
      description: 'For serious job seekers',
      features: [
        'Unlimited Resumes',
        'All Premium Templates',
        'Advanced ATS Analysis',
        'Callback Predictions',
        'Priority Support',
        'No Watermark',
      ],
      cta: 'Start Pro Trial',
      ctaLink: '/register',
      highlighted: true,
    },
    {
      name: 'Enterprise',
      price: '$99',
      period: '/month',
      description: 'For teams and organizations',
      features: [
        'Everything in Pro',
        'Team Collaboration',
        'Up to 50 Members',
        'Admin Dashboard',
        'Custom Branding',
        'Dedicated Support',
        'API Access',
      ],
      cta: 'Contact Sales',
      ctaLink: '/register',
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/" className="text-2xl font-bold text-primary-600">
              AI Resume Builder
            </Link>
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

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            Simple, Transparent Pricing
          </h1>
          <p className="text-xl text-gray-600">
            Choose the perfect plan for your job search journey
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {plans.map((plan, idx) => (
            <div
              key={idx}
              className={`card ${
                plan.highlighted
                  ? 'ring-2 ring-primary-600 shadow-xl'
                  : ''
              }`}
            >
              {plan.highlighted && (
                <div className="text-center mb-4">
                  <span className="bg-primary-600 text-white px-4 py-1 rounded-full text-sm font-semibold">
                    Most Popular
                  </span>
                </div>
              )}

              <h3 className="text-2xl font-bold text-gray-900 mb-2">
                {plan.name}
              </h3>
              <div className="mb-4">
                <span className="text-4xl font-bold text-gray-900">
                  {plan.price}
                </span>
                {plan.period && (
                  <span className="text-gray-600">{plan.period}</span>
                )}
              </div>
              <p className="text-gray-600 mb-6">{plan.description}</p>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature, fidx) => (
                  <li key={fidx} className="flex items-center space-x-2">
                    <Check className="text-green-600" size={20} />
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>

              <Link
                to={plan.ctaLink}
                className={`btn w-full text-center ${
                  plan.highlighted ? 'btn-primary' : 'btn-outline'
                }`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default PricingPage;
