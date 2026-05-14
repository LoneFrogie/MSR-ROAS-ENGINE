import { Zap } from 'lucide-react';

const typeColors = {
  increase_budget: 'bg-emerald-100 text-emerald-700',
  decrease_budget: 'bg-amber-100 text-amber-700',
  pause_campaign: 'bg-red-100 text-red-700',
  emergency_stop: 'bg-red-200 text-red-800',
  enable_campaign: 'bg-blue-100 text-blue-700',
  update_targeting: 'bg-purple-100 text-purple-700',
  pause_keyword: 'bg-orange-100 text-orange-700',
  decrease_bid: 'bg-yellow-100 text-yellow-700',
  seo_fix: 'bg-teal-100 text-teal-700',
  reallocate_budget: 'bg-indigo-100 text-indigo-700',
};

const statusColors = {
  executed: 'text-emerald-600',
  approved: 'text-blue-600',
  pending: 'text-amber-600',
  rejected: 'text-red-500',
};

export default function ActionLog({ actions, title = "Autonomous Actions", maxHeight = "max-h-96" }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Zap size={18} /> {title}
      </h3>
      <div className={`space-y-3 ${maxHeight} overflow-y-auto`}>
        {(!actions || actions.length === 0) && (
          <div className="text-gray-400 text-sm text-center py-8">No actions yet</div>
        )}
        {actions?.map((action, i) => (
          <div key={action.id || i} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
            <span className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap ${
              typeColors[action.action_type] || 'bg-gray-100 text-gray-600'
            }`}>
              {action.action_type?.replace(/_/g, ' ')}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-sm text-gray-700 truncate">{action.reason}</div>
              <div className="text-xs text-gray-400 mt-1">
                {action.platform} · Confidence: {(action.confidence * 100).toFixed(0)}%
                {action.status && (
                  <span className={`ml-1 font-medium ${statusColors[action.status] || ''}`}>
                    · {action.status}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
