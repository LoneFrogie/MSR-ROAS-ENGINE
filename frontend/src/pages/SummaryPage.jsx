import { useState, useEffect } from 'react';
import {
  TrendingUp, DollarSign, Activity, Target, AlertTriangle,
  Calendar, Users, Heart, Eye,
} from 'lucide-react';
import { useData } from '../hooks/useDataContext';
import { getSocialOverview, updateConfig, triggerOptimization } from '../services/api';
import MetricCard from '../components/MetricCard';
import ActionLog from '../components/ActionLog';
import PlatformBreakdown from '../components/PlatformBreakdown';
import CampaignTable from '../components/CampaignTable';

// Date range filter — manual date pickers; engine uses LOOKBACK_DAYS calculated from selection

function PlatformCompareTile({ breakdown }) {
  if (!breakdown) return null;
  const google = breakdown.google_ads || {};
  const meta = breakdown.meta_ads || {};
  const totalSpend = (google.spend || 0) + (meta.spend || 0);
  const googleShare = totalSpend ? ((google.spend || 0) / totalSpend) * 100 : 0;
  const metaShare = totalSpend ? ((meta.spend || 0) / totalSpend) * 100 : 0;
  const winner =
    (google.roas || 0) > (meta.roas || 0) ? 'google' :
    (meta.roas || 0) > (google.roas || 0) ? 'meta' : null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Google vs Meta</h3>
      <div className="grid grid-cols-2 gap-4">
        <div className={`rounded-lg border p-4 ${winner === 'google' ? 'border-emerald-300 bg-emerald-50' : 'border-gray-100'}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">Google Ads</span>
            {winner === 'google' && <span className="text-[10px] font-bold text-emerald-600 uppercase">winner</span>}
          </div>
          <div className="text-2xl font-bold text-gray-900">{(google.roas || 0).toFixed(2)}x</div>
          <div className="text-xs text-gray-500 mt-1">ROAS</div>
          <div className="mt-3 text-sm text-gray-700">${(google.spend || 0).toLocaleString(undefined, {maximumFractionDigits: 0})} spend</div>
          <div className="text-xs text-gray-500">${(google.revenue || 0).toLocaleString(undefined, {maximumFractionDigits: 0})} revenue</div>
        </div>
        <div className={`rounded-lg border p-4 ${winner === 'meta' ? 'border-emerald-300 bg-emerald-50' : 'border-gray-100'}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">Meta Ads</span>
            {winner === 'meta' && <span className="text-[10px] font-bold text-emerald-600 uppercase">winner</span>}
          </div>
          <div className="text-2xl font-bold text-gray-900">{(meta.roas || 0).toFixed(2)}x</div>
          <div className="text-xs text-gray-500 mt-1">ROAS</div>
          <div className="mt-3 text-sm text-gray-700">${(meta.spend || 0).toLocaleString(undefined, {maximumFractionDigits: 0})} spend</div>
          <div className="text-xs text-gray-500">${(meta.revenue || 0).toLocaleString(undefined, {maximumFractionDigits: 0})} revenue</div>
        </div>
      </div>
      {/* Spend ratio bar */}
      <div className="mt-4">
        <div className="text-xs text-gray-500 mb-1">Spend ratio</div>
        <div className="flex h-3 rounded-full overflow-hidden bg-gray-100">
          <div className="bg-blue-500" style={{ width: `${googleShare}%` }} title={`Google ${googleShare.toFixed(0)}%`} />
          <div className="bg-violet-500" style={{ width: `${metaShare}%` }} title={`Meta ${metaShare.toFixed(0)}%`} />
        </div>
        <div className="flex justify-between text-[11px] text-gray-500 mt-1">
          <span>Google {googleShare.toFixed(0)}%</span>
          <span>Meta {metaShare.toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
}

function SocialKPIsTile({ social }) {
  if (!social) return null;
  const fb = social.facebook || {};
  const ig = social.instagram || {};
  const hasFB = fb.followers !== undefined;
  const hasIG = ig.followers !== undefined;

  if (!hasFB && !hasIG) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <Users size={18} /> Social Audiences
        </h3>
        <div className="text-sm text-gray-500">{social._notice || 'No social data available.'}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Users size={18} /> Social Audiences
      </h3>
      <div className="grid grid-cols-2 gap-4">
        {hasFB && (
          <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-4">
            <div className="text-xs text-blue-600 font-medium uppercase tracking-wide mb-1">Facebook</div>
            <div className="text-xs text-gray-500 mb-2">{fb.name || ''}</div>
            <div className="text-2xl font-bold text-gray-900">{(fb.followers || 0).toLocaleString()}</div>
            <div className="text-xs text-gray-500">followers</div>
            <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
              <SocialMetric label="Reach 28d" value={fb.impressions_28d} />
              <SocialMetric label="Engaged 28d" value={fb.engagements_28d} />
              <SocialMetric label="Reactions 28d" value={fb.reactions_28d} />
              <SocialMetric label="Video views 28d" value={fb.video_views_28d} />
            </div>
          </div>
        )}
        {hasIG && (
          <div className="rounded-lg border border-pink-100 bg-pink-50/40 p-4">
            <div className="text-xs text-pink-600 font-medium uppercase tracking-wide mb-1">Instagram</div>
            <div className="text-xs text-gray-500 mb-2">@{ig.username || ''}</div>
            <div className="text-2xl font-bold text-gray-900">{(ig.followers || 0).toLocaleString()}</div>
            <div className="text-xs text-gray-500">followers · {(ig.media_count || 0).toLocaleString()} posts total</div>
            <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
              <SocialMetric label="Posts 28d" value={ig.posts_28d} />
              <SocialMetric label="Engagement 28d" value={ig.engagement_28d} />
              <SocialMetric label="Likes 28d" value={ig.likes_28d} />
              <SocialMetric label="Comments 28d" value={ig.comments_28d} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SocialMetric({ label, value, positive }) {
  const v = value || 0;
  return (
    <div>
      <div className="text-gray-500">{label}</div>
      {v > 0 ? (
        <div className={`font-semibold ${positive ? 'text-emerald-700' : 'text-gray-800'}`}>
          {positive ? '+' : ''}{v.toLocaleString()}
        </div>
      ) : (
        <div className="text-gray-400 italic text-xs" title="Requires Meta App permissions (see notice below)">— not available</div>
      )}
    </div>
  );
}

function DateRangeFilter({ value, onChange }) {
  // Manual date pickers — user picks "from" and "to". Backend uses lookback_days
  // computed from the day count between dates.
  const today = new Date();
  const todayIso = today.toISOString().split('T')[0];
  const defaultStart = new Date(today.getTime() - (value || 14) * 86400_000)
    .toISOString().split('T')[0];

  const [start, setStart] = useState(defaultStart);
  const [end, setEnd] = useState(todayIso);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const dayCount = Math.max(1, Math.ceil(
    (new Date(end).getTime() - new Date(start).getTime()) / 86400_000
  ));

  const handleApply = async () => {
    if (new Date(start) > new Date(end)) {
      setMessage({ type: 'error', text: 'Start date must be before end date.' });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      await updateConfig({ lookback_days: dayCount });
      onChange?.(dayCount);
      await triggerOptimization();
      setMessage({ type: 'ok', text: `Refreshing ${dayCount}-day window…` });
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Update failed' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Calendar size={16} className="text-gray-400" />
      <input
        type="date"
        value={start}
        max={end}
        onChange={e => setStart(e.target.value)}
        className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white"
      />
      <span className="text-xs text-gray-400">to</span>
      <input
        type="date"
        value={end}
        max={todayIso}
        min={start}
        onChange={e => setEnd(e.target.value)}
        className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white"
      />
      <span className="text-xs text-gray-500">({dayCount}d)</span>
      <button
        onClick={handleApply}
        disabled={saving}
        className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-xs font-medium disabled:opacity-50"
      >
        {saving ? 'Applying...' : 'Apply'}
      </button>
      {message && (
        <span className={`text-xs ${message.type === 'ok' ? 'text-emerald-600' : 'text-red-600'}`}>{message.text}</span>
      )}
    </div>
  );
}

export default function SummaryPage() {
  const { snapshot, campaigns, platformData, actions, config, refetch } = useData();
  const [social, setSocial] = useState(null);
  const [range, setRange] = useState(config?.lookback_days || 14);

  useEffect(() => {
    if (config?.lookback_days) setRange(config.lookback_days);
  }, [config?.lookback_days]);

  useEffect(() => {
    getSocialOverview().then(setSocial).catch(() => setSocial(null));
  }, []);

  const blendedRoas = snapshot?.blended_roas || 0;
  const totalSpend = snapshot?.total_spend || 0;
  const totalRevenue = snapshot?.total_revenue || 0;
  const totalConversions = snapshot?.total_conversions || 0;

  return (
    <div className="space-y-6">
      {/* Header with date range */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-500">Performance Overview</h2>
        <DateRangeFilter value={range} onChange={(d) => { setRange(d); refetch?.(); }} />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          icon={TrendingUp}
          label="Blended ROAS"
          value={`${blendedRoas.toFixed(2)}x`}
          subvalue={`Target: ${config?.target_roas || 4}x`}
          color={blendedRoas >= (config?.target_roas || 4) ? 'green' : 'amber'}
        />
        <MetricCard
          icon={DollarSign}
          label="Total Spend"
          value={`$${totalSpend.toLocaleString(undefined, {maximumFractionDigits: 2})}`}
          subvalue={`${campaigns.length} active campaigns`}
          color="indigo"
        />
        <MetricCard
          icon={Activity}
          label="Total Revenue"
          value={`$${totalRevenue.toLocaleString(undefined, {maximumFractionDigits: 2})}`}
          color="green"
        />
        <MetricCard
          icon={Target}
          label="Conversions"
          value={totalConversions.toLocaleString()}
          subvalue={totalSpend > 0 ? `CPA: $${(totalSpend / Math.max(totalConversions, 1)).toFixed(2)}` : ''}
          color="indigo"
        />
      </div>

      {/* Alerts */}
      {snapshot?.alerts?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 text-amber-700 font-medium mb-2">
            <AlertTriangle size={18} /> Active Alerts
          </div>
          {snapshot.alerts.map((alert, i) => (
            <div key={i} className="text-sm text-amber-600 ml-6">{alert}</div>
          ))}
        </div>
      )}

      {/* Platform Compare + Social KPIs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PlatformCompareTile breakdown={snapshot?.platform_breakdown || platformData} />
        <SocialKPIsTile social={social} />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PlatformBreakdown data={snapshot?.platform_breakdown || platformData} />
        <ActionLog actions={actions?.slice(-20)} />
      </div>

      {/* Campaign Table */}
      <CampaignTable campaigns={
        [...campaigns].sort((a, b) => (b.roas || 0) - (a.roas || 0))
      } />
    </div>
  );
}
