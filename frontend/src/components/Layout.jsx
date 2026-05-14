import { Outlet, NavLink } from 'react-router-dom';
import { TrendingUp, Zap, RefreshCw, BarChart3, Search, Settings } from 'lucide-react';
import { useData } from '../hooks/useDataContext';
import { triggerOptimization } from '../services/api';

const tabs = [
  { to: '/', label: 'Summary', icon: BarChart3 },
  { to: '/seo', label: 'SEO Intelligence', icon: Search },
  { to: '/details', label: 'Details & Executions', icon: Settings },
];

export default function Layout() {
  const { health, pending, refetch } = useData();

  const handleTriggerOptimization = async () => {
    await triggerOptimization();
    setTimeout(refetch, 3000);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600 rounded-lg">
              <TrendingUp size={24} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">ROAS Engine</h1>
              <p className="text-xs text-gray-500">Autonomous Optimization</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                health?.status ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'
              }`} />
              <span className="text-sm text-gray-600">
                {health?.status ? 'Live' : 'Offline'}
              </span>
            </div>
            {pending?.length > 0 && (
              <span className="px-2 py-1 bg-amber-100 text-amber-700 text-xs font-medium rounded-full">
                {pending.length} pending
              </span>
            )}
            <button
              onClick={handleTriggerOptimization}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium"
            >
              <Zap size={16} /> Run Optimization
            </button>
            <button onClick={refetch} className="p-2 text-gray-400 hover:text-gray-600">
              <RefreshCw size={18} />
            </button>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <nav className="bg-white border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1">
            {tabs.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      </nav>

      {/* Page Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
