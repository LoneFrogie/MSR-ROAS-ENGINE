import { useState, useEffect } from 'react';
import { Settings, Clock, CheckCircle, XCircle, AlertTriangle, Zap, Brain, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useData } from '../hooks/useDataContext';
import {
  updateConfig, approveAction, rejectAction, approveAllActions,
  getLearningStats, getLearningHistory
} from '../services/api';
import ActionLog from '../components/ActionLog';

// ─── Config Editor ──────────────────────────────────────────────────

function ConfigEditor({ config, onSaved }) {
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  if (!config) return null;

  const handleChange = (key, value) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    if (Object.keys(form).length === 0) return;
    setSaving(true);
    setMessage(null);
    try {
      const result = await updateConfig(form);
      setMessage({ type: 'success', text: `Updated: ${result.updated?.join(', ')}` });
      setForm({});
      onSaved?.();
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail?.errors?.join(', ') || 'Update failed' });
    } finally {
      setSaving(false);
    }
  };

  const val = (key) => form[key] !== undefined ? form[key] : config[key];
  const changed = (key) => form[key] !== undefined && form[key] !== config[key];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Settings size={18} /> Engine Configuration
      </h3>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Approval Mode */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Approval Mode</label>
          <select
            value={val('approval_mode')}
            onChange={e => handleChange('approval_mode', e.target.value)}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('approval_mode') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          >
            <option value="full_auto">Full Auto</option>
            <option value="semi_auto">Semi Auto (approve medium confidence)</option>
            <option value="full_manual">Full Manual (approve everything)</option>
          </select>
        </div>

        {/* Optimization Mode */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Optimization Mode</label>
          <select
            value={val('optimization_mode')}
            onChange={e => handleChange('optimization_mode', e.target.value)}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('optimization_mode') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          >
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
            <option value="conservative">Conservative</option>
          </select>
        </div>

        {/* Target ROAS */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Target ROAS</label>
          <input
            type="number" step="0.1" min="0.1" max="50"
            value={val('target_roas')}
            onChange={e => handleChange('target_roas', parseFloat(e.target.value))}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('target_roas') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          />
        </div>

        {/* Confidence Threshold */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Confidence Threshold</label>
          <input
            type="number" step="0.05" min="0.1" max="1.0"
            value={val('confidence_threshold')}
            onChange={e => handleChange('confidence_threshold', parseFloat(e.target.value))}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('confidence_threshold') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          />
        </div>

        {/* Max Daily Budget Change */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Max Budget Change %</label>
          <input
            type="number" step="0.05" min="0.01" max="1.0"
            value={val('max_daily_budget_change_pct')}
            onChange={e => handleChange('max_daily_budget_change_pct', parseFloat(e.target.value))}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('max_daily_budget_change_pct') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          />
        </div>

        {/* Max Total Daily Budget */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Daily Budget Cap ($)</label>
          <input
            type="number" step="100" min="100" max="1000000"
            value={val('max_total_daily_budget')}
            onChange={e => handleChange('max_total_daily_budget', parseFloat(e.target.value))}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('max_total_daily_budget') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          />
        </div>

        {/* Max Single Campaign Budget */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Per-Campaign Cap ($)</label>
          <input
            type="number" step="50" min="10" max="100000"
            value={val('max_single_campaign_budget')}
            onChange={e => handleChange('max_single_campaign_budget', parseFloat(e.target.value))}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('max_single_campaign_budget') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          />
        </div>

        {/* Lookback Days */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Lookback Days</label>
          <input
            type="number" step="1" min="1" max="90"
            value={val('lookback_days')}
            onChange={e => handleChange('lookback_days', parseInt(e.target.value))}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('lookback_days') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          />
        </div>

        {/* Optimization Cycle Minutes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Cycle Interval (min)</label>
          <input
            type="number" step="5" min="5" max="1440"
            value={val('optimization_cycle_minutes')}
            onChange={e => handleChange('optimization_cycle_minutes', parseInt(e.target.value))}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('optimization_cycle_minutes') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          />
        </div>

        {/* Emergency Stop ROAS */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Emergency Stop ROAS</label>
          <input
            type="number" step="0.1" min="0" max="5"
            value={val('emergency_stop_roas_below')}
            onChange={e => handleChange('emergency_stop_roas_below', parseFloat(e.target.value))}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('emergency_stop_roas_below') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          />
        </div>

        {/* SEO Audit Interval */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">SEO Audit (hours)</label>
          <input
            type="number" step="1" min="1" max="168"
            value={val('seo_audit_interval_hours')}
            onChange={e => handleChange('seo_audit_interval_hours', parseInt(e.target.value))}
            className={`w-full border rounded-lg px-3 py-2 text-sm ${changed('seo_audit_interval_hours') ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300'}`}
          />
        </div>
      </div>

      {Object.keys(form).length > 0 && (
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            onClick={() => setForm({})}
            className="px-4 py-2 text-gray-600 hover:text-gray-900 text-sm"
          >
            Reset
          </button>
          <span className="text-xs text-gray-400">
            {Object.keys(form).length} change{Object.keys(form).length > 1 ? 's' : ''} pending
          </span>
        </div>
      )}
    </div>
  );
}

// ─── Approval Queue ─────────────────────────────────────────────────

const typeColors = {
  increase_budget: 'bg-emerald-100 text-emerald-700',
  decrease_budget: 'bg-amber-100 text-amber-700',
  pause_campaign: 'bg-red-100 text-red-700',
  emergency_stop: 'bg-red-200 text-red-800',
  reallocate_budget: 'bg-indigo-100 text-indigo-700',
  pause_keyword: 'bg-orange-100 text-orange-700',
  decrease_bid: 'bg-yellow-100 text-yellow-700',
  seo_fix: 'bg-teal-100 text-teal-700',
};

function ApprovalQueue({ pending, onUpdate }) {
  const [processing, setProcessing] = useState({});

  const handleApprove = async (id) => {
    setProcessing(p => ({ ...p, [id]: 'approving' }));
    try {
      await approveAction(id);
      onUpdate?.();
    } catch (err) {
      console.error(err);
    } finally {
      setProcessing(p => ({ ...p, [id]: null }));
    }
  };

  const handleReject = async (id) => {
    setProcessing(p => ({ ...p, [id]: 'rejecting' }));
    try {
      await rejectAction(id);
      onUpdate?.();
    } catch (err) {
      console.error(err);
    } finally {
      setProcessing(p => ({ ...p, [id]: null }));
    }
  };

  const handleApproveAll = async () => {
    try {
      await approveAllActions();
      onUpdate?.();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Clock size={18} /> Pending Approvals
          {pending?.length > 0 && (
            <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-medium rounded-full">
              {pending.length}
            </span>
          )}
        </h3>
        {pending?.length > 0 && (
          <button
            onClick={handleApproveAll}
            className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 text-xs font-medium"
          >
            Approve All
          </button>
        )}
      </div>

      {(!pending || pending.length === 0) ? (
        <div className="text-center py-8 text-gray-400 text-sm">
          No pending actions. {' '}
          <span className="text-gray-500">
            Switch to Semi-Auto or Full Manual mode to see actions here.
          </span>
        </div>
      ) : (
        <div className="space-y-3">
          {pending.map((action) => (
            <div key={action.id} className="flex items-start gap-3 p-4 rounded-lg bg-gray-50 border border-gray-100">
              <span className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap ${
                typeColors[action.action_type] || 'bg-gray-100 text-gray-600'
              }`}>
                {action.action_type?.replace(/_/g, ' ')}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-gray-700">{action.reason}</div>
                <div className="text-xs text-gray-400 mt-1 flex gap-3">
                  <span>{action.platform}</span>
                  <span>Confidence: {(action.confidence * 100).toFixed(0)}%</span>
                  {action.old_value !== null && action.new_value !== null && (
                    <span>
                      {typeof action.old_value === 'number' ? `$${action.old_value.toFixed(0)}` : action.old_value}
                      {' → '}
                      {typeof action.new_value === 'number' ? `$${action.new_value.toFixed(0)}` : action.new_value}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => handleApprove(action.id)}
                  disabled={processing[action.id]}
                  className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 text-xs font-medium disabled:opacity-50"
                >
                  <CheckCircle size={14} /> Approve
                </button>
                <button
                  onClick={() => handleReject(action.id)}
                  disabled={processing[action.id]}
                  className="flex items-center gap-1 px-3 py-1.5 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 text-xs font-medium disabled:opacity-50"
                >
                  <XCircle size={14} /> Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Action History with Filters ────────────────────────────────────

function ActionHistory({ actions }) {
  const [filter, setFilter] = useState('all');

  const filtered = filter === 'all'
    ? actions
    : actions?.filter(a => a.status === filter);

  const counts = {
    all: actions?.length || 0,
    executed: actions?.filter(a => a.status === 'executed').length || 0,
    approved: actions?.filter(a => a.status === 'approved').length || 0,
    rejected: actions?.filter(a => a.status === 'rejected').length || 0,
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Zap size={18} /> Action History
      </h3>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-4">
        {Object.entries(counts).map(([key, count]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === key
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {key === 'all' ? 'All' : key.charAt(0).toUpperCase() + key.slice(1)} ({count})
          </button>
        ))}
      </div>

      <ActionLog actions={filtered?.slice(-30)} title="" maxHeight="max-h-[600px]" />
    </div>
  );
}

// ─── Learning Insights ─────────────────────────────────────────────

function LearningInsights() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getLearningStats()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Brain size={18} /> Self-Improvement Engine
        </h3>
        <div className="text-center py-8 text-gray-400 text-sm">Loading learning data...</div>
      </div>
    );
  }

  if (!stats) return null;

  const DirectionIcon = ({ dir }) => {
    if (dir === 'up') return <TrendingUp size={14} className="text-emerald-500" />;
    if (dir === 'down') return <TrendingDown size={14} className="text-red-500" />;
    return <Minus size={14} className="text-gray-400" />;
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Brain size={18} /> Self-Improvement Engine
        </h3>
        <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
          stats.learning_active
            ? 'bg-emerald-100 text-emerald-700'
            : 'bg-gray-100 text-gray-500'
        }`}>
          {stats.learning_active ? 'Active' : `Inactive (${stats.total_evaluations}/${20} samples)`}
        </span>
      </div>

      {/* Status Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-xs text-gray-500">Evaluations</div>
          <div className="text-xl font-bold text-gray-900">{stats.total_evaluations}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-xs text-gray-500">Learning Cycles</div>
          <div className="text-xl font-bold text-gray-900">{stats.cycles_with_learning}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-xs text-gray-500">Calibrated Types</div>
          <div className="text-xl font-bold text-gray-900">{stats.calibration?.length || 0}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-xs text-gray-500">Last Update</div>
          <div className="text-sm font-medium text-gray-900">
            {stats.last_weight_update
              ? new Date(stats.last_weight_update).toLocaleDateString()
              : '—'}
          </div>
        </div>
      </div>

      {/* Weight Evolution */}
      {stats.weights && (
        <div className="mb-5">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Scoring Weights (Learned vs Initial)</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(stats.weights).map(([dim, w]) => (
              <div key={dim} className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-600 capitalize">{dim}</span>
                  <DirectionIcon dir={w.direction} />
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-lg font-bold text-gray-900">{(w.current * 100).toFixed(1)}%</span>
                  <span className="text-xs text-gray-400">from {(w.initial * 100).toFixed(0)}%</span>
                </div>
                {w.delta !== 0 && (
                  <div className={`text-xs mt-0.5 ${w.delta > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {w.delta > 0 ? '+' : ''}{(w.delta * 100).toFixed(1)}pp
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Effectiveness */}
      {stats.action_effectiveness?.length > 0 && (
        <div className="mb-5">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Action Effectiveness</h4>
          <div className="space-y-2">
            {stats.action_effectiveness.map((ae) => (
              <div key={ae.action_type} className="flex items-center gap-3">
                <span className="text-xs text-gray-600 w-32 truncate">{ae.action_type.replace(/_/g, ' ')}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      ae.effectiveness_pct >= 70 ? 'bg-emerald-500' :
                      ae.effectiveness_pct >= 40 ? 'bg-amber-400' : 'bg-red-400'
                    }`}
                    style={{ width: `${Math.max(ae.effectiveness_pct, 2)}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-gray-700 w-16 text-right">
                  {ae.effectiveness_pct}% ({ae.total})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Confidence Calibration */}
      {stats.calibration?.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Confidence Calibration</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b">
                  <th className="text-left py-1.5 pr-3 font-medium">Action Type</th>
                  <th className="text-right py-1.5 px-2 font-medium">Predicted</th>
                  <th className="text-right py-1.5 px-2 font-medium">Actual</th>
                  <th className="text-right py-1.5 px-2 font-medium">Ratio</th>
                  <th className="text-right py-1.5 px-2 font-medium">ROAS Delta</th>
                  <th className="text-right py-1.5 pl-2 font-medium">Samples</th>
                </tr>
              </thead>
              <tbody>
                {stats.calibration.map((c) => (
                  <tr key={c.action_type} className="border-b border-gray-50">
                    <td className="py-1.5 pr-3 text-gray-700">{c.action_type.replace(/_/g, ' ')}</td>
                    <td className="py-1.5 px-2 text-right text-gray-600">{(c.predicted_avg * 100).toFixed(0)}%</td>
                    <td className="py-1.5 px-2 text-right text-gray-600">{(c.actual_success_rate * 100).toFixed(0)}%</td>
                    <td className={`py-1.5 px-2 text-right font-medium ${
                      c.calibration_ratio > 1.05 ? 'text-emerald-600' :
                      c.calibration_ratio < 0.95 ? 'text-red-600' : 'text-gray-600'
                    }`}>
                      {c.calibration_ratio.toFixed(2)}x
                    </td>
                    <td className={`py-1.5 px-2 text-right ${c.avg_roas_delta >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {c.avg_roas_delta >= 0 ? '+' : ''}{c.avg_roas_delta.toFixed(3)}
                    </td>
                    <td className="py-1.5 pl-2 text-right text-gray-500">{c.sample_size}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {stats.total_evaluations === 0 && (
        <div className="text-center py-6 text-gray-400 text-sm">
          No evaluations yet. The engine needs a few optimization cycles to start learning.
        </div>
      )}
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────

export default function DetailsPage() {
  const { config, pending, actions, refetch } = useData();

  return (
    <div className="space-y-6">
      <ConfigEditor config={config} onSaved={refetch} />
      <ApprovalQueue pending={pending} onUpdate={refetch} />
      <LearningInsights />
      <ActionHistory actions={actions} />
    </div>
  );
}
