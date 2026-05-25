import { useState, useEffect } from 'react';
import {
  Search, Globe, TrendingUp, AlertTriangle, FileText,
  Zap, ExternalLink, ChevronDown, ChevronUp, Monitor,
  Image, Link2, Code, CheckCircle, XCircle, AlertCircle, Info,
  Sparkles, ArrowRight, Loader2, Calendar
} from 'lucide-react';
import {
  getSEOOverview, getSiteCrawl,
  generateSeoSuggestions, getPendingSeoSuggestions,
  approveAction, rejectAction, approveSeoSuggestion, rejectSeoField,
  scorePosts, listSavedScoredPosts, getThemeSnippet, refreshPostMetrics, scoreDraftPost,
  listDraftScores, getPredictionAccuracy, getTrendingInspiration, adaptTrendToBrand,
} from '../services/api';
import MetricCard from '../components/MetricCard';

function Section({ title, icon: Icon, children, count, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-5 text-left"
      >
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Icon size={18} /> {title}
          {count !== undefined && (
            <span className="text-sm font-normal text-gray-400">({count})</span>
          )}
        </h3>
        {open ? <ChevronUp size={18} className="text-gray-400" /> : <ChevronDown size={18} className="text-gray-400" />}
      </button>
      {open && <div className="px-5 pb-5 border-t border-gray-50 pt-4">{children}</div>}
    </div>
  );
}

function ScoreBadge({ score }) {
  const color = score >= 90 ? 'bg-emerald-100 text-emerald-700'
    : score >= 70 ? 'bg-amber-100 text-amber-700'
    : score >= 50 ? 'bg-orange-100 text-orange-700'
    : 'bg-red-100 text-red-700';
  return <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${color}`}>{score}</span>;
}

function SeverityIcon({ severity }) {
  if (severity === 'critical') return <XCircle size={14} className="text-red-500 flex-shrink-0" />;
  if (severity === 'warning') return <AlertCircle size={14} className="text-amber-500 flex-shrink-0" />;
  return <Info size={14} className="text-blue-400 flex-shrink-0" />;
}

export default function SEOPage() {
  const [data, setData] = useState(null);
  const [crawlData, setCrawlData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [crawlLoading, setCrawlLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('onpage'); // 'onpage' | 'organic'
  const [expandedPage, setExpandedPage] = useState(null);

  useEffect(() => {
    getSEOOverview()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
    getSiteCrawl()
      .then(setCrawlData)
      .catch(console.error)
      .finally(() => setCrawlLoading(false));
  }, []);

  const tabs = [
    { id: 'onpage', label: 'On-Page SEO Audit', icon: Monitor },
    { id: 'social', label: 'Social Post Performance', icon: Sparkles },
    { id: 'prepost', label: 'Pre-Post Scoring', icon: Sparkles },
    { id: 'trends', label: 'Viral Pattern Recognition', icon: TrendingUp },
    { id: 'organic', label: 'Organic & Paid Intelligence', icon: Search },
  ];

  return (
    <div className="space-y-6">
      {/* Tab Switcher */}
      <div className="flex gap-2 bg-gray-100 rounded-lg p-1 w-fit">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === t.id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <t.icon size={16} /> {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'onpage' && <OnPageTab crawlData={crawlData} crawlLoading={crawlLoading} expandedPage={expandedPage} setExpandedPage={setExpandedPage} />}
      {activeTab === 'social' && <PostScoring />}
      {activeTab === 'prepost' && <PrePostScoring />}
      {activeTab === 'trends' && <TrendingInspiration />}
      {activeTab === 'organic' && <OrganicTab data={data} loading={loading} />}
    </div>
  );
}

/* ─── AI Suggestions Section ─────────────────────────────────────── */

function AiSuggestions() {
  const [suggestions, setSuggestions] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [processing, setProcessing] = useState({});
  const [error, setError] = useState(null);

  const refresh = () => {
    getPendingSeoSuggestions().then(setSuggestions).catch(() => {});
  };

  useEffect(() => { refresh(); }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateSeoSuggestions(5);
      console.log('Generated:', result);
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate suggestions');
    } finally {
      setGenerating(false);
    }
  };

  const handleApproveField = async (id, field) => {
    setProcessing(p => ({ ...p, [id]: `approve:${field}` }));
    try {
      await approveSeoSuggestion(id, [field]);
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Approve failed');
    } finally {
      setProcessing(p => ({ ...p, [id]: null }));
    }
  };

  const handleRejectField = async (id, field) => {
    setProcessing(p => ({ ...p, [id]: `reject:${field}` }));
    try {
      await rejectSeoField(id, field);
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Reject failed');
    } finally {
      setProcessing(p => ({ ...p, [id]: null }));
    }
  };

  const handleRejectAll = async (id) => {
    setProcessing(p => ({ ...p, [id]: 'reject_all' }));
    try {
      await rejectAction(id);
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Reject failed');
    } finally {
      setProcessing(p => ({ ...p, [id]: null }));
    }
  };

  return (
    <div className="bg-gradient-to-br from-violet-50 to-indigo-50 rounded-xl shadow-sm border border-violet-100 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Sparkles size={18} className="text-violet-600" /> AI SEO Suggestions
          {suggestions.length > 0 && (
            <span className="px-2 py-0.5 bg-violet-100 text-violet-700 text-xs font-medium rounded-full">
              {suggestions.length} pending
            </span>
          )}
        </h3>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 text-sm font-medium disabled:opacity-50 flex items-center gap-2"
        >
          {generating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {generating ? 'Generating...' : 'Generate AI Fixes'}
        </button>
      </div>

      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm">
          {typeof error === 'string' ? error : JSON.stringify(error)}
        </div>
      )}

      {suggestions.length === 0 && !generating && (
        <div className="text-center py-6 text-gray-500 text-sm">
          Click "Generate AI Fixes" — Gemini will scan low-scoring pages and propose SEO improvements.
          You review each suggestion and approve to push directly to Shopify.
        </div>
      )}

      <div className="space-y-3">
        {suggestions.map(s => (
          <SuggestionCard
            key={s.id}
            suggestion={s}
            onApproveField={handleApproveField}
            onRejectField={handleRejectField}
            onRejectAll={() => handleRejectAll(s.id)}
            processing={processing[s.id]}
          />
        ))}
      </div>
    </div>
  );
}

function SuggestionCard({ suggestion, onApproveField, onRejectField, onRejectAll, processing }) {
  const { id, url, current = {}, fixes = {}, alt_text_suggestions = [], rationale, shopify_resource } = suggestion;
  const fields = Object.keys(fixes);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-start justify-between mb-3 gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-indigo-600 hover:underline truncate flex items-center gap-1"
            >
              {url} <ExternalLink size={12} />
            </a>
            {shopify_resource && (
              <span className="px-2 py-0.5 rounded text-xs bg-emerald-50 text-emerald-700 font-medium">
                Shopify {shopify_resource.type}
              </span>
            )}
            {!shopify_resource && (
              <span className="px-2 py-0.5 rounded text-xs bg-amber-50 text-amber-700 font-medium">
                No Shopify match · manual apply
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 italic">{rationale}</p>
        </div>
        <button
          onClick={onRejectAll}
          disabled={processing === 'reject_all'}
          className="flex items-center gap-1 px-3 py-1.5 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 text-xs font-medium disabled:opacity-50 shrink-0"
          title="Reject this entire suggestion"
        >
          <XCircle size={14} /> Reject All
        </button>
      </div>

      <div className="space-y-3">
        {fields.map(field => (
          <DiffRow
            key={field}
            label={fieldLabel(field)}
            currentValue={current[currentKey(field)]}
            suggestedValue={fixes[field]}
            shopifyMatched={!!shopify_resource}
            processing={processing}
            field={field}
            onApprove={() => onApproveField(id, field)}
            onReject={() => onRejectField(id, field)}
          />
        ))}
        {alt_text_suggestions?.length > 0 && (
          <div className="mt-2 p-2 rounded bg-blue-50 text-xs">
            <span className="font-medium text-blue-700">+ {alt_text_suggestions.length} alt text suggestions</span>
          </div>
        )}
      </div>
    </div>
  );
}

function fieldLabel(field) {
  return {
    seo_title: 'SEO Title',
    meta_description: 'Meta Description',
    h1: 'H1 Heading',
    body_html: 'Body HTML',
    schema_jsonld: 'JSON-LD Schema',
  }[field] || field;
}
function currentKey(field) {
  return {
    seo_title: 'title',
    meta_description: 'meta_description',
    h1: 'h1',
    body_html: 'body_html',
    schema_jsonld: 'schema_jsonld',
  }[field] || field;
}

function DiffRow({ label, currentValue, suggestedValue, shopifyMatched, processing, field, onApprove, onReject }) {
  const isProcessing = processing === `approve:${field}` || processing === `reject:${field}`;
  const isSchema = field === 'schema_jsonld';
  return (
    <div className="border border-gray-100 rounded-lg p-3 bg-gray-50/50">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-700 uppercase tracking-wide">{label}</span>
        <div className="flex gap-2">
          <button
            onClick={onApprove}
            disabled={isProcessing}
            className="flex items-center gap-1 px-2.5 py-1 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 text-[11px] font-medium disabled:opacity-50"
            title={shopifyMatched ? `Apply this ${label} to Shopify` : `Approve this ${label} (manual apply required)`}
          >
            <CheckCircle size={12} />
            {processing === `approve:${field}`
              ? (shopifyMatched ? 'Applying...' : 'Approving...')
              : (shopifyMatched ? 'Approve & Apply' : 'Approve (Manual)')}
          </button>
          <button
            onClick={onReject}
            disabled={isProcessing}
            className="flex items-center gap-1 px-2.5 py-1 bg-red-50 text-red-600 rounded-md hover:bg-red-100 text-[11px] font-medium disabled:opacity-50"
            title={`Reject this ${label}`}
          >
            <XCircle size={12} />
            {processing === `reject:${field}` ? 'Rejecting...' : 'Reject'}
          </button>
        </div>
      </div>
      {isSchema ? (
        <div className="space-y-2 text-xs">
          <div className="bg-red-50 border border-red-100 rounded p-2 text-gray-700">
            <div className="text-[10px] text-red-500 font-bold uppercase mb-0.5">Current</div>
            <span className="text-gray-400 italic">No structured data on page</span>
          </div>
          <div className="bg-emerald-50 border border-emerald-100 rounded p-2">
            <div className="text-[10px] text-emerald-600 font-bold uppercase mb-1">Suggested JSON-LD (will be injected as &lt;script type="application/ld+json"&gt; into the page body)</div>
            <pre className="text-[11px] font-mono text-gray-800 bg-white border border-emerald-100 rounded p-2 max-h-64 overflow-auto whitespace-pre-wrap break-all">{suggestedValue}</pre>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-[1fr,16px,1fr] gap-2 items-start text-xs">
          <div className="bg-red-50 border border-red-100 rounded p-2 text-gray-700 break-words">
            <div className="text-[10px] text-red-500 font-bold uppercase mb-0.5">Current</div>
            {currentValue || <span className="text-gray-400 italic">empty</span>}
          </div>
          <ArrowRight size={14} className="text-gray-400 self-center hidden md:block" />
          <div className="bg-emerald-50 border border-emerald-100 rounded p-2 text-gray-800 break-words">
            <div className="text-[10px] text-emerald-600 font-bold uppercase mb-0.5">Suggested</div>
            {suggestedValue}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Social Post Scoring ──────────────────────────────────────── */

// ─── Tier / scoring rubric explanations ──────────────────────────────

const TIER_LEGEND = [
  { tier: 'A', range: '85-100', label: 'Excellent', color: 'bg-emerald-100 text-emerald-700', desc: 'Top-tier creative — strong on every dimension. Replicate this format.' },
  { tier: 'B', range: '70-84', label: 'Good', color: 'bg-blue-100 text-blue-700', desc: 'Solid post with one or two small fixes for top tier.' },
  { tier: 'C', range: '50-69', label: 'Average', color: 'bg-amber-100 text-amber-700', desc: 'Underperforming on multiple criteria. Use suggested rewrites.' },
  { tier: 'D', range: '0-49', label: 'Poor', color: 'bg-red-100 text-red-700', desc: 'Major issues. Reshoot or rewrite before reposting variations.' },
];

const CRITERIA_LEGEND = [
  { key: 'hook', label: 'Hook', desc: 'Attention grab in first line / first 3 seconds. Stops the scroll.' },
  { key: 'message', label: 'Message', desc: 'Crystal-clear value prop and call-to-action. No fluff.' },
  { key: 'visual', label: 'Visual', desc: 'Image/video quality, composition, and lighting.' },
  { key: 'brand', label: 'Brand', desc: 'Logo, colors, voice — unmistakably MS. READ.' },
  { key: 'mobile', label: 'Mobile', desc: 'Vertical 9:16 for video, large readable text, safe zones.' },
  { key: 'script', label: 'Script', desc: 'Caption / VO copywriting — sharp, benefit-led, on tone.' },
  { key: 'pacing', label: 'Pacing', desc: 'Video edit rhythm; for images, narrative flow of the carousel.' },
];

function MetricChip({ label, value, tone, tooltip }) {
  const toneCls = tone === 'good' ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                : tone === 'weak' ? 'bg-red-50 text-red-700 border-red-100'
                : tone === 'ok'   ? 'bg-amber-50 text-amber-700 border-amber-100'
                : 'bg-gray-50 text-gray-700 border-gray-100';
  return (
    <div className={`rounded border ${toneCls} px-1.5 py-1`} title={tooltip}>
      <div className="text-[9px] uppercase tracking-wide opacity-70 leading-tight">{label}</div>
      <div className="font-semibold leading-tight">{value}</div>
    </div>
  );
}

/**
 * Engagement rate benchmarks (2026 data from Rival IQ, Hootsuite, Social Insider).
 * Returns {tone, label} for a given platform/media-type/ER decimal (0–1).
 */
// ─── Fashion-vertical benchmark sources (URLs verified live) ────────
const FASHION_ER_SOURCE = {
  url: 'https://www.rivaliq.com/blog/social-media-industry-benchmark-report/',
  label: 'Rival IQ 2025 — Fashion vertical',
};
const FASHION_REACH_SOURCE = {
  url: 'https://blog.hootsuite.com/instagram-statistics/',
  label: 'Hootsuite — Instagram benchmarks',
};
const APPAREL_CTR_SOURCE = {
  url: 'https://localiq.com/blog/search-advertising-benchmarks/',
  label: 'LocaliQ 2025 — Apparel/Fashion (search ads, 6.77% CTR)',
};

function erBenchmark(platform, mediaType, erDecimal, significance) {
  const er = (erDecimal || 0) * 100;
  const isReel = mediaType === 'VIDEO' || mediaType === 'REELS';

  if (significance === 'noise') {
    return {
      tone: 'weak',
      label: 'NOT MEANINGFUL — reach too low',
      benchmark: 'Need higher reach before ER% is interpretable',
      formula: 'ER = (likes + comments + shares + saves) ÷ reach',
      gated: true, source: FASHION_ER_SOURCE,
    };
  }
  if (significance === 'low') {
    return {
      tone: 'ok',
      label: 'Low sample — interpret with caution',
      benchmark: 'Reach below ER significance floor (FB ≥5% / IG ≥10% of followers)',
      formula: 'ER = (likes + comments + shares + saves) ÷ reach',
      gated: true, source: FASHION_ER_SOURCE,
    };
  }

  // Fashion-vertical (Rival IQ 2025 Fashion):
  // IG image median 0.68% · IG Reels median 2.0% · FB median 0.04% · TikTok median 2.5%
  let thresholds;
  if (platform === 'facebook')      thresholds = [0.04, 0.15, 0.5];   // Fashion FB
  else if (isReel)                  thresholds = [2.0, 4.0, 7.0];     // Fashion IG Reels
  else                              thresholds = [0.68, 1.5, 3.0];    // Fashion IG image/carousel
  const [weakMax, okMax, goodMax] = thresholds;
  const tone = er < weakMax ? 'weak' : er < okMax ? 'ok' : 'good';
  const label = er < weakMax ? 'Below Fashion median'
              : er < okMax   ? 'At Fashion median'
              : er < goodMax ? 'Top quartile in Fashion'
              : 'Top 10% in Fashion';
  const benchmark = `Fashion ${platform}${isReel ? ' Reels' : ''}: <${weakMax}% weak · ${weakMax}–${okMax}% median · ${okMax}–${goodMax}% top quartile · >${goodMax}% top 10%`;
  return { tone, label, benchmark, formula: 'ER = (likes + comments + shares + saves) ÷ reach', source: FASHION_ER_SOURCE };
}

/**
 * Views benchmark for video posts.
 * Uses views ÷ followers (true algorithm-amplification signal) rather than
 * views ÷ reach. Views > reach often just means the same small audience
 * replayed the video — that's not amplification, that's repetition.
 * Views ÷ followers > 1.0 means the algo pushed it to people outside
 * your audience, which IS amplification.
 */
function viewThroughBenchmark(platform, mediaType, views, reach, followers) {
  if (views == null) return { tone: 'neutral', label: '', benchmark: '' };
  const isVideo = mediaType === 'VIDEO' || mediaType === 'REELS';
  if (!isVideo) return { tone: 'neutral', label: '', benchmark: '' };
  if (!followers) {
    // Fall back to views vs reach as average watch frequency
    if (!reach) return { tone: 'neutral', label: '', benchmark: '' };
    const freq = views / reach;
    const tone = freq < 1.2 ? 'ok' : freq < 2 ? 'good' : 'good';
    return {
      tone,
      label: `Avg watch frequency: ${freq.toFixed(1)}× per reached person`,
      benchmark: 'Higher = strong replays; lower = single-watch behavior',
      source: FASHION_ER_SOURCE,
    };
  }
  const reachPct = (views / followers) * 100;
  // Thresholds: Fashion IG Reels typical median reach is ~20% of followers
  // <8%: weak distribution, 8-30%: ok, 30-100%: good, >100%: excellent (non-follower amplification)
  const tone = reachPct < 8 ? 'weak' : reachPct < 30 ? 'ok' : 'good';
  const label = reachPct < 8 ? 'Algorithm did not pick this up'
              : reachPct < 30 ? 'Distributed to your followers only'
              : reachPct < 100 ? 'Good distribution to followers + some non-followers'
              : 'Excellent — algorithm pushed beyond your audience';
  return {
    tone, label,
    benchmark: `Views ÷ Followers: <8% weak · 8-30% median · 30-100% good · >100% excellent (non-follower amplification)`,
    source: FASHION_ER_SOURCE,
  };
}

/** CTR benchmark — general social CTR (cited within Rival IQ industry context). */
function ctrBenchmark(platform, ctrDecimal) {
  const ctr = (ctrDecimal || 0) * 100;
  const [weakMax, okMax, goodMax] = platform === 'facebook' ? [0.5, 1.0, 2.0] : [0.5, 1.0, 2.0];
  const tone = ctr < weakMax ? 'weak' : ctr < okMax ? 'ok' : 'good';
  const label = ctr < weakMax ? 'Below industry CTR'
              : ctr < okMax   ? 'Median CTR'
              : ctr < goodMax ? 'Good CTR'
              : 'Excellent CTR';
  return { tone, label, benchmark: `CTR: <${weakMax}% weak · ${weakMax}–${okMax}% median · ${okMax}–${goodMax}% good · >${goodMax}% excellent`, source: APPAREL_CTR_SOURCE };
}

/** Engagement-count benchmark: scaled to follower base. */
function engagementCountBenchmark(metric, count, followers) {
  if (!followers) return { tone: 'neutral', label: '', benchmark: '' };
  const rate = count / followers;
  const thresholds = {
    likes:    [0.001, 0.005, 0.02],
    comments: [0.0001, 0.0005, 0.002],
    shares:   [0.0001, 0.0005, 0.002],
    saves:    [0.0001, 0.0005, 0.002],
  }[metric] || [0.0001, 0.001, 0.005];
  const [weakMax, okMax, goodMax] = thresholds;
  const tone = rate < weakMax ? 'weak' : rate < okMax ? 'ok' : 'good';
  return {
    tone,
    label: rate < weakMax ? 'Low' : rate < okMax ? 'Median' : rate < goodMax ? 'Good' : 'Excellent',
    benchmark: `Fashion ${metric} ÷ followers: <${(weakMax*100).toFixed(2)}% weak · ${(okMax*100).toFixed(2)}–${(goodMax*100).toFixed(2)}% good`,
    source: FASHION_ER_SOURCE,
  };
}

/** Reach penetration (reach / followers). */
function reachPenetrationBenchmark(platform, mediaType, penetrationPct) {
  const isReel = mediaType === 'VIDEO' || mediaType === 'REELS';
  // Fashion IG organic reach trends slightly higher than cross-industry (~10-20% vs 8-15%)
  let thresholds;
  if (platform === 'facebook') thresholds = [2, 5, 10];      // FB organic, post-algo
  else if (isReel)             thresholds = [20, 50, 100];   // IG Reels amplification
  else                         thresholds = [10, 20, 40];    // Fashion IG image/carousel
  const [weakMax, okMax, goodMax] = thresholds;
  const p = penetrationPct || 0;
  const tone = p < weakMax ? 'weak' : p < okMax ? 'ok' : 'good';
  const label = p < weakMax ? 'Poor distribution'
              : p < okMax   ? 'Median distribution'
              : p < goodMax ? 'Good distribution'
              : 'Excellent — algorithm amplified';
  const benchmark = `Fashion ${platform}${isReel ? ' Reels' : ''} penetration: <${weakMax}% poor · ${weakMax}–${okMax}% median · ${okMax}–${goodMax}% good · >${goodMax}% excellent`;
  return { tone, label, benchmark, source: FASHION_REACH_SOURCE };
}

function ScoringRubricInfo() {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState(null);

  useEffect(() => {
    if (open && !config) {
      import('../services/api').then(m => m.getPostScoringConfig().then(setConfig).catch(() => {}));
    }
  }, [open, config]);

  // Tier color map
  const tierColor = (t) => ({
    A: 'bg-emerald-100 text-emerald-800',
    B: 'bg-blue-100 text-blue-800',
    C: 'bg-amber-100 text-amber-800',
    D: 'bg-red-100 text-red-800',
  }[t] || 'bg-gray-100 text-gray-800');

  return (
    <div className="mb-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 font-medium"
      >
        <Info size={12} /> {open ? 'Hide' : 'How does scoring work?'}
      </button>
      {open && (
        <div className="mt-2 bg-white border border-violet-100 rounded-lg p-4 text-xs space-y-4">
          {!config ? (
            <div className="text-gray-500">Loading rubric…</div>
          ) : (
            <>
              {/* Formula */}
              <div className="bg-violet-50 border border-violet-100 rounded p-2 text-violet-900 font-mono text-[11px]">
                {config.formula}
              </div>

              {/* Criteria + Weights table */}
              <div>
                <div className="font-semibold text-gray-800 mb-1.5">7 Creative Criteria (each scored 0–10)</div>
                <div className="border border-gray-100 rounded overflow-hidden">
                  <table className="w-full text-[11px]">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="text-left px-2 py-1.5 font-semibold">Criterion</th>
                        <th className="text-left px-2 py-1.5 font-semibold">What it measures</th>
                        <th className="text-right px-2 py-1.5 font-semibold w-20">Weight</th>
                      </tr>
                    </thead>
                    <tbody>
                      {config.criteria.map(c => (
                        <tr key={c.key} className="border-t border-gray-100 hover:bg-gray-50">
                          <td className="px-2 py-1.5 font-semibold text-gray-800">{c.label}</td>
                          <td className="px-2 py-1.5 text-gray-600">{c.description}</td>
                          <td className="px-2 py-1.5 text-right font-mono text-violet-700">{Math.round(c.weight * 100)}%</td>
                        </tr>
                      ))}
                      <tr className="bg-gray-50 border-t border-gray-200 font-semibold">
                        <td className="px-2 py-1.5">Total</td>
                        <td></td>
                        <td className="px-2 py-1.5 text-right font-mono text-violet-700">100%</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Tiers */}
              <div>
                <div className="font-semibold text-gray-800 mb-1.5">Tier thresholds (applied to overall_score)</div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {Object.entries(config.tier_thresholds).map(([tier, threshold], i, arr) => {
                    const next = arr[i - 1]?.[1];
                    const range = next ? `${threshold}–${next - 1}` : `${threshold}+`;
                    return (
                      <div key={tier} className="rounded p-2 bg-gray-50 border border-gray-100">
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${tierColor(tier)}`}>{tier}</span>
                          <span className="text-gray-700 font-mono text-[10px]">{range}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Context signals note */}
              <div className="text-gray-600 italic pt-2 border-t border-gray-100">
                <span className="font-semibold text-gray-700 not-italic">Engagement signals:</span>{' '}
                {config.context_signals}
              </div>

              {/* Reach Penetration Benchmarks — calculated for THIS account */}
              {config.reach_benchmarks && (
                <div className="pt-3 border-t border-gray-100">
                  <div className="font-semibold text-gray-800 mb-1.5">
                    Reach Penetration — calibrated to your follower base
                  </div>
                  <div className="text-[11px] text-gray-600 mb-2">
                    ER% is only meaningful when reach hits a minimum % of followers
                    (industry standard). Below the floor, the ER chip is gated to
                    prevent false positives from internal-network engagement.
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {['facebook', 'instagram'].map(plat => {
                      const r = config.reach_benchmarks[plat];
                      if (!r) return null;
                      const Color = plat === 'facebook' ? 'blue' : 'pink';
                      return (
                        <div key={plat} className="bg-gray-50 rounded p-2 border border-gray-100">
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-${Color}-100 text-${Color}-700`}>{plat}</span>
                            <span className="text-[10px] text-gray-500">
                              {r.followers ? `${r.followers.toLocaleString()} followers` : 'follower count unavailable'}
                            </span>
                          </div>
                          {plat === 'facebook' && r.followers > 0 && (
                            <table className="w-full text-[10px]">
                              <tbody>
                                <tr><td className="py-0.5 text-gray-500">Poor reach (&lt;2%)</td><td className="py-0.5 text-right font-mono text-red-600">&lt; {r.image_carousel.poor.toLocaleString()}</td></tr>
                                <tr><td className="py-0.5 text-gray-500">Median reach (2-5%)</td><td className="py-0.5 text-right font-mono text-amber-600">{r.image_carousel.poor.toLocaleString()}-{r.image_carousel.median.toLocaleString()}</td></tr>
                                <tr><td className="py-0.5 text-gray-500">Good reach (5-10%)</td><td className="py-0.5 text-right font-mono text-emerald-600">{r.image_carousel.median.toLocaleString()}-{r.image_carousel.good.toLocaleString()}</td></tr>
                                <tr><td className="py-0.5 text-gray-500">Excellent (&gt;10%)</td><td className="py-0.5 text-right font-mono text-emerald-700">&gt; {r.image_carousel.good.toLocaleString()}</td></tr>
                                <tr className="border-t border-gray-200"><td className="py-1 text-violet-700 font-semibold">ER significance floor</td><td className="py-1 text-right font-mono text-violet-700 font-bold">≥ {r.er_significance_floor.toLocaleString()}</td></tr>
                              </tbody>
                            </table>
                          )}
                          {plat === 'instagram' && r.followers > 0 && (
                            <>
                              <div className="text-[10px] font-semibold text-gray-700 mt-1 mb-0.5">Image / Carousel</div>
                              <table className="w-full text-[10px]">
                                <tbody>
                                  <tr><td className="py-0.5 text-gray-500">Poor (&lt;8%)</td><td className="py-0.5 text-right font-mono text-red-600">&lt; {r.image_carousel.poor.toLocaleString()}</td></tr>
                                  <tr><td className="py-0.5 text-gray-500">Median (8-20%)</td><td className="py-0.5 text-right font-mono text-amber-600">{r.image_carousel.poor.toLocaleString()}-{r.image_carousel.median.toLocaleString()}</td></tr>
                                  <tr><td className="py-0.5 text-gray-500">Good (20-40%)</td><td className="py-0.5 text-right font-mono text-emerald-600">{r.image_carousel.median.toLocaleString()}-{r.image_carousel.good.toLocaleString()}</td></tr>
                                  <tr><td className="py-0.5 text-gray-500">Excellent (&gt;40%)</td><td className="py-0.5 text-right font-mono text-emerald-700">&gt; {r.image_carousel.good.toLocaleString()}</td></tr>
                                </tbody>
                              </table>
                              <div className="text-[10px] font-semibold text-gray-700 mt-1.5 mb-0.5">Reel / Video</div>
                              <table className="w-full text-[10px]">
                                <tbody>
                                  <tr><td className="py-0.5 text-gray-500">Poor (&lt;20%)</td><td className="py-0.5 text-right font-mono text-red-600">&lt; {r.video_reel.poor.toLocaleString()}</td></tr>
                                  <tr><td className="py-0.5 text-gray-500">Median (20-50%)</td><td className="py-0.5 text-right font-mono text-amber-600">{r.video_reel.poor.toLocaleString()}-{r.video_reel.median.toLocaleString()}</td></tr>
                                  <tr><td className="py-0.5 text-gray-500">Good (50-100%)</td><td className="py-0.5 text-right font-mono text-emerald-600">{r.video_reel.median.toLocaleString()}-{r.video_reel.good.toLocaleString()}</td></tr>
                                  <tr><td className="py-0.5 text-gray-500">Excellent (&gt;100%)</td><td className="py-0.5 text-right font-mono text-emerald-700">&gt; {r.video_reel.good.toLocaleString()}</td></tr>
                                </tbody>
                              </table>
                              <table className="w-full text-[10px] mt-1 border-t border-gray-200">
                                <tbody>
                                  <tr><td className="py-1 text-violet-700 font-semibold">ER significance floor</td><td className="py-1 text-right font-mono text-violet-700 font-bold">≥ {r.er_significance_floor.toLocaleString()}</td></tr>
                                </tbody>
                              </table>
                            </>
                          )}
                          {!r.followers && (
                            <div className="text-[10px] text-gray-500 italic">Follower count not available — connect Meta API</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* What each metric chip measures + how it's color-graded */}
              <div className="pt-3 border-t border-gray-100">
                <div className="font-semibold text-gray-800 mb-1.5">What each metric chip means</div>
                <div className="bg-blue-50 border border-blue-100 rounded p-2 text-[11px] text-blue-900 mb-2">
                  <b>Why there's no Impressions chip:</b> Meta deprecated the public <code>post_impressions</code> field
                  for organic posts in Graph API v22. Only <i>reach</i> (unique users) is exposed now.
                  Showing both would duplicate the same number. Use Reach + Reach % for distribution; Views for video.
                </div>
                <div className="border border-gray-100 rounded overflow-hidden">
                  <table className="w-full text-[11px]">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="text-left px-2 py-1.5 font-semibold w-20">Chip</th>
                        <th className="text-left px-2 py-1.5 font-semibold">Formula</th>
                        <th className="text-left px-2 py-1.5 font-semibold w-44">Color logic</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-t border-gray-100">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">Reach</td>
                        <td className="px-2 py-1.5 text-gray-600">Unique people who saw the post</td>
                        <td className="px-2 py-1.5 text-gray-600">Tone follows Reach % (reach ÷ followers)</td>
                      </tr>
                      <tr className="border-t border-gray-100 bg-gray-50">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">Reach %</td>
                        <td className="px-2 py-1.5 text-gray-600">reach ÷ followers (audience penetration)</td>
                        <td className="px-2 py-1.5 text-gray-600">FB: &lt;2/5/10% · IG image: &lt;10/20/40% · Reels: &lt;20/50/100%</td>
                      </tr>
                      <tr className="border-t border-gray-100 bg-gray-50">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">Views <span className="text-[9px] text-gray-400 font-normal">(video only)</span></td>
                        <td className="px-2 py-1.5 text-gray-600">
                          <b>views ÷ followers</b> — true algorithm-amplification signal (NOT views÷reach, which gets inflated by replays from the same small audience). <i>Chip hidden on image/carousel posts since views don't apply.</i>
                        </td>
                        <td className="px-2 py-1.5 text-gray-600">
                          &lt;8% 🔴 didn't pick up · 8-30% 🟡 followers only · 30-100% 🟢 followers + some non-followers · &gt;100% 🟢 pushed beyond audience
                        </td>
                      </tr>
                      <tr className="border-t border-gray-100">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">Likes</td>
                        <td className="px-2 py-1.5 text-gray-600">likes ÷ followers</td>
                        <td className="px-2 py-1.5 text-gray-600">&lt;0.1% / 0.5% / 2% thresholds</td>
                      </tr>
                      <tr className="border-t border-gray-100 bg-gray-50">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">Comments/Shares/Saves</td>
                        <td className="px-2 py-1.5 text-gray-600">metric ÷ followers</td>
                        <td className="px-2 py-1.5 text-gray-600">&lt;0.01% / 0.05% / 0.2% thresholds (rarer signals)</td>
                      </tr>
                      <tr className="border-t border-gray-100">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">ER</td>
                        <td className="px-2 py-1.5 text-gray-600">(likes + comments + shares + saves) ÷ reach</td>
                        <td className="px-2 py-1.5 text-gray-600">Fashion ER benchmarks per platform; gated to gray when reach is below significance floor</td>
                      </tr>
                      <tr className="border-t border-gray-100 bg-gray-50">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">CTR</td>
                        <td className="px-2 py-1.5 text-gray-600">clicks ÷ impressions (paid posts only)</td>
                        <td className="px-2 py-1.5 text-gray-600">&lt;0.5% / 1% / 2% thresholds</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div className="text-[10px] text-gray-500 italic mt-2">
                  <b>Significance gate:</b> when reach is below the floor (FB ≥5% / IG ≥10% of followers), the ER chip is grayed out with ⚠ and engagement chips downgrade. Prevents internal-staff likes from looking healthy on a small-reach post.
                </div>
              </div>

              {/* Pre-score vs Live-score gap explanation */}
              <div className="pt-3 border-t border-gray-100">
                <div className="font-semibold text-gray-800 mb-1.5">Why Pre-Post and Live scores can differ</div>
                <p className="text-[11px] text-gray-600 mb-2">
                  A pre-score and a live score on the same content often don't match exactly. The gap
                  is meaningful — it's how the system learns over time. Three causes, with typical impact:
                </p>
                <div className="bg-cyan-50 border border-cyan-100 rounded p-2 mb-2 text-[11px] text-cyan-900">
                  <b>Live-score formula:</b> <code className="bg-white px-1 rounded">overall = 0.80 × creative + 0.20 × engagement</code><br/>
                  <span className="text-cyan-800">where <b>creative</b> is the weighted Gemini score on the 7 criteria (same math as pre-score), and <b>engagement</b> is a 0-100 score derived deterministically from your ER + reach-penetration vs Fashion benchmarks.</span>
                </div>
                <div className="border border-gray-100 rounded overflow-hidden">
                  <table className="w-full text-[11px]">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="text-left px-2 py-1.5 font-semibold w-40">Cause</th>
                        <th className="text-left px-2 py-1.5 font-semibold">What it means</th>
                        <th className="text-left px-2 py-1.5 font-semibold w-24">Direction</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-t border-gray-100">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">1. Engagement data (intentional)</td>
                        <td className="px-2 py-1.5 text-gray-600">
                          Pre-score sees only the creative; live score sees creative <b>+ actual reach, likes, ER</b>.
                          Engagement is blended in at <b>20% weight</b> (creative stays 80%). A post that performs
                          below Fashion median on ER + reach can lose up to <b>~15 points</b> from this blend alone;
                          a post that exceeds top quartile can gain up to <b>+10 points</b>.
                        </td>
                        <td className="px-2 py-1.5 text-red-600">±15 pts<br/><span className="text-[9px] text-gray-500">20% of total</span></td>
                      </tr>
                      <tr className="border-t border-gray-100 bg-gray-50">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">2. Visual analysis (now fixed)</td>
                        <td className="px-2 py-1.5 text-gray-600">
                          Pre-score and live score now both let Gemini <b>actually look at the image or video</b>.
                          Same input, same method — no more guessing on visuals.
                        </td>
                        <td className="px-2 py-1.5 text-emerald-600">±8 pts<br/><span className="text-[9px] text-gray-500">Now aligned</span></td>
                      </tr>
                      <tr className="border-t border-gray-100">
                        <td className="px-2 py-1.5 font-semibold text-gray-800">3. AI's natural variance</td>
                        <td className="px-2 py-1.5 text-gray-600">
                          AI doesn't always give the exact same answer twice — it has a "creativity dial"
                          called temperature. Lower = more predictable, higher = more varied. We set it
                          to <b>0.4</b> (mostly consistent with a small amount of judgment) on both scorers.
                          So even scoring the same post twice in a row may show a 2-3 point difference.
                          That's normal AI behaviour, not a bug.
                        </td>
                        <td className="px-2 py-1.5 text-gray-500">±3 pts<br/><span className="text-[9px] text-gray-500">Inherent</span></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div className="bg-violet-50 border border-violet-100 rounded p-2 mt-2 text-[11px] text-violet-900">
                  <b>How to read the delta:</b> after cause #2 is closed, the remaining gap is the honest
                  signal — pre-score = creative potential, live score = creative × execution × audience response.
                  Prediction-accuracy tracking in Past Drafts will tell you if pre-scoring is systematically
                  too optimistic or pessimistic, and we can recalibrate the prompt over time.
                </div>
              </div>

              {/* Sources — all benchmark references, hyperlinked */}
              <div className="pt-3 border-t border-gray-100">
                <div className="font-semibold text-gray-800 mb-1.5">Benchmark sources (Fashion vertical)</div>
                <ul className="text-[11px] text-gray-600 space-y-1 list-disc ml-4">
                  <li>
                    Engagement rates by platform —{' '}
                    <a href={FASHION_ER_SOURCE.url} target="_blank" rel="noopener noreferrer"
                       className="text-cyan-700 hover:underline">{FASHION_ER_SOURCE.label} ↗</a>
                    {' '}<span className="text-gray-500">(Fashion median IG image 0.68%, IG Reels 2.0%, FB 0.04%, TikTok 2.5%)</span>
                  </li>
                  <li>
                    Reach penetration thresholds —{' '}
                    <a href={FASHION_REACH_SOURCE.url} target="_blank" rel="noopener noreferrer"
                       className="text-cyan-700 hover:underline">{FASHION_REACH_SOURCE.label} ↗</a>
                  </li>
                  <li>
                    CTR (Apparel/Fashion vertical) —{' '}
                    <a href={APPAREL_CTR_SOURCE.url} target="_blank" rel="noopener noreferrer"
                       className="text-cyan-700 hover:underline">{APPAREL_CTR_SOURCE.label} ↗</a>
                    {' '}<span className="text-gray-500">(LocaliQ publishes the Apparel benchmark for search ads at 6.77%; no equivalent public report exists for social-feed CTR, so general 0.5/1/2% thresholds apply on social posts)</span>
                  </li>
                </ul>
                <div className="text-[10px] text-gray-500 italic mt-2">
                  Thresholds last reviewed against published reports. If your sub-niche (e.g. modest fashion, plus-size, ethnic wear) shows different baseline behavior, we can recalibrate the thresholds from your own historical posts.
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Pre-Post Scoring (draft before publishing) ─────────────────── */

function PrePostScoring() {
  const [caption, setCaption] = useState('');
  const [platform, setPlatform] = useState('instagram');
  const [mediaType, setMediaType] = useState('IMAGE');
  const [files, setFiles] = useState([]);          // array of File objects
  const [previewUrls, setPreviewUrls] = useState([]); // matching object URLs
  const [scoring, setScoring] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const MAX_FILES = 20;

  // ── History view ──
  const today = new Date().toISOString().split('T')[0];
  const monthAgo = new Date(Date.now() - 28 * 86400000).toISOString().split('T')[0];
  const [histStart, setHistStart] = useState(monthAgo);
  const [histEnd, setHistEnd] = useState(today);
  const [drafts, setDrafts] = useState([]);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [accuracy, setAccuracy] = useState(null);

  const refreshDrafts = async () => {
    setDraftsLoading(true);
    try {
      const r = await listDraftScores(histStart, histEnd);
      setDrafts(r.drafts || []);
    } catch (_) {} finally { setDraftsLoading(false); }
    try { setAccuracy(await getPredictionAccuracy()); } catch (_) {}
  };

  useEffect(() => { refreshDrafts(); /* eslint-disable-next-line */ }, []);
  // Refresh history after a new score saves
  useEffect(() => { if (result?.persisted) refreshDrafts(); /* eslint-disable-next-line */ }, [result]);

  const tierColor = (t) => ({
    A: 'bg-emerald-100 text-emerald-700',
    B: 'bg-blue-100 text-blue-700',
    C: 'bg-amber-100 text-amber-700',
    D: 'bg-red-100 text-red-700',
  }[t] || 'bg-gray-100 text-gray-600');

  const onFiles = (e) => {
    const incoming = Array.from(e.target.files || []);
    if (!incoming.length) return;
    // Append to existing (so user can add in multiple drags) and cap at 20
    const merged = [...files, ...incoming].slice(0, MAX_FILES);
    setFiles(merged);
    // Revoke previous URLs, build new
    previewUrls.forEach(u => URL.revokeObjectURL(u));
    setPreviewUrls(merged.map(f => URL.createObjectURL(f)));
    // Auto-detect media type
    if (merged.length === 0) return;
    if (merged.length >= 2) setMediaType('CAROUSEL_ALBUM');
    else if (merged[0].type.startsWith('video/')) setMediaType('VIDEO');
    else if (merged[0].type.startsWith('image/')) setMediaType('IMAGE');
    // Reset input so the same file can be re-selected
    if (e.target) e.target.value = '';
  };

  const removeFile = (idx) => {
    const newFiles = files.filter((_, i) => i !== idx);
    URL.revokeObjectURL(previewUrls[idx]);
    setFiles(newFiles);
    setPreviewUrls(previewUrls.filter((_, i) => i !== idx));
    if (newFiles.length === 0) {
      // Reset to single-IMAGE default
      setMediaType('IMAGE');
    } else if (newFiles.length === 1) {
      setMediaType(newFiles[0].type.startsWith('video/') ? 'VIDEO' : 'IMAGE');
    }
  };

  const handleScore = async () => {
    if (!caption.trim() && files.length === 0) {
      setError('Add a caption or upload media to score');
      return;
    }
    setScoring(true);
    setError(null);
    setResult(null);
    try {
      // Pass array if 2+ files, single file otherwise (back-compat)
      const payload = files.length > 1 ? files : (files[0] || null);
      const r = await scoreDraftPost(caption, platform, mediaType, payload);
      setResult(r);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Scoring failed');
    } finally {
      setScoring(false);
    }
  };

  return (
    <div className="bg-gradient-to-br from-violet-50 to-pink-50 rounded-xl shadow-sm border border-violet-100 p-5 space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Sparkles size={18} className="text-violet-600" /> Pre-Post Scoring
        </h3>
        <p className="text-xs text-gray-600 mt-0.5">
          Score a draft post before publishing using the same 7-criteria rubric.
          Gemini analyzes the caption + visual and predicts performance risk.
        </p>
      </div>

      {/* Show the rubric reference */}
      <ScoringRubricInfo />

      {/* Input form */}
      <div className="bg-white rounded-lg border border-gray-100 p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-semibold text-gray-700 block mb-1">Platform</label>
            <select
              value={platform}
              onChange={e => setPlatform(e.target.value)}
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
            >
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-700 block mb-1">Media Type</label>
            <select
              value={mediaType}
              onChange={e => setMediaType(e.target.value)}
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm"
            >
              <option value="IMAGE">Image / Photo</option>
              <option value="VIDEO">Video / Reel</option>
              <option value="CAROUSEL_ALBUM">Carousel</option>
              <option value="TEXT">Text only</option>
            </select>
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-gray-700 block mb-1">
            Caption / Description <span className="text-gray-400 font-normal">(supports emojis + line breaks)</span>
          </label>
          <textarea
            value={caption}
            onChange={e => setCaption(e.target.value)}
            placeholder="Paste your draft caption here..."
            rows={5}
            className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm font-mono"
          />
          <div className="text-[10px] text-gray-400 mt-0.5 text-right">{caption.length}/1500</div>
        </div>

        <div>
          <label className="text-xs font-semibold text-gray-700 block mb-1">
            Upload Image(s) or Video <span className="text-gray-400 font-normal">
              (optional, ≤20MB each, up to {MAX_FILES} files for IG carousel — current: {files.length}/{MAX_FILES})
            </span>
          </label>
          <input
            type="file"
            accept="image/*,video/*"
            multiple
            onChange={onFiles}
            disabled={files.length >= MAX_FILES}
            className="block w-full text-xs file:mr-3 file:px-3 file:py-1.5 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-violet-100 file:text-violet-700 hover:file:bg-violet-200 disabled:opacity-50"
          />
          {files.length > 0 && (
            <div className="mt-2 grid grid-cols-3 md:grid-cols-5 lg:grid-cols-6 gap-2">
              {files.map((f, idx) => (
                <div key={idx} className="relative group">
                  <div className="absolute top-1 left-1 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded font-bold z-10">
                    {idx + 1}
                  </div>
                  <button
                    onClick={() => removeFile(idx)}
                    className="absolute top-1 right-1 bg-red-600 text-white text-[10px] w-5 h-5 rounded-full flex items-center justify-center opacity-80 hover:opacity-100 z-10"
                    title="Remove this slide"
                  >×</button>
                  {f.type.startsWith('video/') ? (
                    <video src={previewUrls[idx]} className="w-full aspect-square object-cover rounded border border-gray-200" />
                  ) : (
                    <img src={previewUrls[idx]} alt={`slide ${idx+1}`} className="w-full aspect-square object-cover rounded border border-gray-200" />
                  )}
                </div>
              ))}
            </div>
          )}
          {files.length > 1 && (
            <div className="text-[11px] text-violet-700 mt-2">
              Carousel mode: slide 1 is the cover/hook (most important for stop rate). Gemini will analyze swipe-through coherence.
            </div>
          )}
        </div>

        <button
          onClick={handleScore}
          disabled={scoring}
          className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 text-sm font-medium disabled:opacity-50 flex items-center gap-2"
        >
          {scoring ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {scoring ? 'Gemini scoring draft…' : 'Score draft'}
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>
      )}

      {/* Result card */}
      {result && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex gap-4">
            {previewUrls.length > 0 && (
              <div className="shrink-0 relative">
                {files[0]?.type.startsWith('video/') ? (
                  <video src={previewUrls[0]} className="w-24 h-24 object-cover rounded-lg border border-gray-100" />
                ) : (
                  <img src={previewUrls[0]} alt="" className="w-24 h-24 object-cover rounded-lg border border-gray-100" />
                )}
                {files.length > 1 && (
                  <div className="absolute -top-1 -right-1 bg-violet-600 text-white text-[10px] px-1.5 py-0.5 rounded-full font-bold">
                    +{files.length - 1}
                  </div>
                )}
              </div>
            )}
            <div className="flex-1 min-w-0">
              {/* Header */}
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${result.platform === 'instagram' ? 'bg-pink-100 text-pink-700' : 'bg-blue-100 text-blue-700'}`}>{result.platform}</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${tierColor(result.tier)}`}>Tier {result.tier} · {result.overall_score}/100</span>
                <span className="text-[11px] text-gray-500 uppercase">{result.media_type}</span>
                <span className="text-[11px] px-1.5 py-0.5 bg-violet-100 text-violet-700 rounded font-semibold">DRAFT</span>
              </div>

              {/* Score grid */}
              <div className="grid grid-cols-7 gap-1 mb-3">
                {CRITERIA_LEGEND.map(c => {
                  const v = (result.scores || {})[c.key] || 0;
                  return (
                    <div key={c.key} className="text-center" title={c.desc}>
                      <div className={`text-sm font-bold ${v >= 8 ? 'text-emerald-600' : v >= 5 ? 'text-amber-600' : 'text-red-600'}`}>{v}</div>
                      <div className="text-[9px] text-gray-500 uppercase">{c.label}</div>
                    </div>
                  );
                })}
              </div>

              {/* Predicted performance */}
              {result.predicted_performance && (
                <div className="bg-amber-50 border border-amber-100 rounded p-2 mb-3 text-xs">
                  <span className="font-semibold text-amber-700">Predicted performance: </span>
                  <span className="text-gray-700">{result.predicted_performance}</span>
                </div>
              )}

              {/* Strengths / Weaknesses */}
              <div className="grid grid-cols-2 gap-3 mb-3 text-xs">
                <div>
                  <div className="font-semibold text-emerald-700 mb-1">Strengths</div>
                  <ul className="text-gray-700 space-y-0.5 list-disc ml-4">
                    {(result.strengths || []).map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
                <div>
                  <div className="font-semibold text-red-700 mb-1">Weaknesses</div>
                  <ul className="text-gray-700 space-y-0.5 list-disc ml-4">
                    {(result.weaknesses || []).map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              </div>

              {result.recommendations?.length > 0 && (
                <div className="bg-violet-50 rounded p-2 mb-2 text-xs">
                  <div className="font-semibold text-violet-700 mb-1">Recommendations</div>
                  <ul className="text-gray-700 space-y-0.5 list-disc ml-4">
                    {result.recommendations.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}

              {result.suggested_hook && (
                <div className="text-xs mb-1">
                  <span className="font-semibold text-gray-600">Suggested hook: </span>
                  <span className="text-gray-800 italic">"{result.suggested_hook}"</span>
                </div>
              )}
              {result.suggested_caption && (
                <div className="text-xs">
                  <div className="font-semibold text-gray-600 mb-0.5">Suggested caption:</div>
                  <div className="text-gray-800 italic bg-gray-50 rounded p-2 whitespace-pre-line">{result.suggested_caption}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Past Drafts history ── */}
      <div className="bg-white rounded-lg border border-gray-100 p-4">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div>
            <h4 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <Calendar size={14} /> Past Drafts ({drafts.length})
            </h4>
            {accuracy?.matched_count > 0 && (
              <div className="text-[11px] text-gray-500 mt-0.5">
                {accuracy.matched_count} matched to live posts ·
                MAE <b>{accuracy.mean_absolute_error}</b> pts · {accuracy.bias_label}
              </div>
            )}
          </div>
          <div className="flex items-center gap-1 text-xs">
            <input type="date" value={histStart} max={histEnd}
              onChange={e => setHistStart(e.target.value)}
              className="border border-gray-200 rounded px-2 py-1 bg-white" />
            <span className="text-gray-400">to</span>
            <input type="date" value={histEnd} min={histStart} max={today}
              onChange={e => setHistEnd(e.target.value)}
              className="border border-gray-200 rounded px-2 py-1 bg-white" />
            <button onClick={refreshDrafts} disabled={draftsLoading}
              className="px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded text-xs font-medium disabled:opacity-50">
              {draftsLoading ? '…' : 'Apply'}
            </button>
          </div>
        </div>

        {drafts.length === 0 ? (
          <div className="text-xs text-gray-500 py-4 text-center">
            No drafts in this date range. Score a draft above and it'll appear here.
          </div>
        ) : (
          <div className="space-y-2">
            {drafts.map(d => (
              <div key={d.caption_hash} className="border border-gray-100 rounded p-2 text-xs hover:bg-gray-50">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${d.platform === 'instagram' ? 'bg-pink-100 text-pink-700' : 'bg-blue-100 text-blue-700'}`}>{d.platform}</span>
                  <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${tierColor(d.tier)}`}>
                    Tier {d.tier} · {d.overall_score}/100
                  </span>
                  <span className="text-[10px] text-gray-500 uppercase">{d.media_type}</span>
                  <span className="text-[10px] text-gray-400">
                    {d.scored_at ? new Date(d.scored_at).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''}
                  </span>
                  {d.actual_score && (
                    <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold border ${
                      (d.actual_score.overall_score - d.overall_score) >= 0
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-red-50 text-red-700 border-red-200'
                    }`}>
                      Live {d.actual_score.overall_score} · Δ{(d.actual_score.overall_score - d.overall_score) >= 0 ? '+' : ''}{d.actual_score.overall_score - d.overall_score}
                    </span>
                  )}
                </div>
                <div className="text-gray-700 italic line-clamp-2 leading-snug">
                  "{d.caption || '(no caption)'}"
                </div>
                {d.suggested_caption && (
                  <details className="mt-1">
                    <summary className="text-[10px] text-violet-600 cursor-pointer hover:underline">Show suggested rewrite</summary>
                    <div className="text-gray-700 italic bg-violet-50 rounded p-1.5 mt-1 whitespace-pre-line">{d.suggested_caption}</div>
                  </details>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Trending Inspiration (live viral content research) ─────────── */

function TrendingInspiration() {
  const [industry, setIndustry] = useState('fashion plus-size women');
  const [region, setRegion] = useState('Malaysia / Southeast Asia');
  const [platforms, setPlatforms] = useState({ instagram: true, tiktok: true });
  const [count, setCount] = useState(10);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [adaptingId, setAdaptingId] = useState(null);
  const [adapted, setAdapted] = useState({});  // trend_id -> adapted result

  const tierColor = (t) => ({
    A: 'bg-emerald-100 text-emerald-700',
    B: 'bg-blue-100 text-blue-700',
    C: 'bg-amber-100 text-amber-700',
    D: 'bg-red-100 text-red-700',
  }[t] || 'bg-gray-100 text-gray-600');

  const handleResearch = async () => {
    setLoading(true);
    setError(null);
    setData(null);
    setAdapted({});
    try {
      const platformList = Object.keys(platforms).filter(k => platforms[k]).join(',');
      const r = await getTrendingInspiration({
        industry, region, platforms: platformList, count,
      });
      setData(r);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Research failed');
    } finally {
      setLoading(false);
    }
  };

  const handleAdapt = async (trend) => {
    setAdaptingId(trend.trend_id);
    try {
      const r = await adaptTrendToBrand(trend, { target_platform: trend.platform });
      setAdapted(prev => ({ ...prev, [trend.trend_id]: r }));
    } catch (e) {
      setAdapted(prev => ({ ...prev, [trend.trend_id]: { error: e.response?.data?.detail || e.message } }));
    } finally {
      setAdaptingId(null);
    }
  };

  return (
    <div className="bg-gradient-to-br from-cyan-50 to-violet-50 rounded-xl shadow-sm border border-cyan-100 p-5 space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <TrendingUp size={18} className="text-cyan-600" /> Viral Pattern Recognition
        </h3>
        <p className="text-xs text-gray-600 mt-0.5">
          Identifies trending content <span className="font-semibold">patterns / templates</span> on
          IG + TikTok in your niche, scored on the same 7-criteria rubric so you see
          WHY the format works. Click "Adapt to brand" to rewrite the pattern in MS. READ
          voice and save as a draft.
        </p>
      </div>

      {/* Honest disclaimer about what's scored */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900">
        <div className="font-semibold mb-0.5 flex items-center gap-1">⚠ What the score means</div>
        <p>
          The 0-100 score and tier are applied to the <b>pattern/template</b> Gemini identified
          from current web research — NOT to a specific TikTok or IG post. Use this as
          creative direction, not as endorsement of any individual creator's content.
          When real platform-post URLs are surfaced (from research citations), they're
          labeled "example matching this pattern", not "the post that scored 84/100".
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg border border-gray-100 p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-semibold text-gray-700 block mb-1">Industry / Niche</label>
            <input value={industry} onChange={e => setIndustry(e.target.value)}
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-700 block mb-1">Region</label>
            <input value={region} onChange={e => setRegion(e.target.value)}
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm" />
          </div>
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2 text-sm">
            <label className="font-semibold text-gray-700">Platforms:</label>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={platforms.instagram}
                onChange={e => setPlatforms(p => ({...p, instagram: e.target.checked}))} />
              <span className="text-pink-700">IG</span>
            </label>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={platforms.tiktok}
                onChange={e => setPlatforms(p => ({...p, tiktok: e.target.checked}))} />
              <span className="text-gray-700">TikTok</span>
            </label>
          </div>
          <div className="flex items-center gap-1 text-sm">
            <label className="font-semibold text-gray-700">Count:</label>
            <select value={count} onChange={e => setCount(parseInt(e.target.value))}
              className="border border-gray-200 rounded px-2 py-1">
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={20}>20</option>
            </select>
          </div>
          <button onClick={handleResearch} disabled={loading}
            className="ml-auto px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 text-sm font-medium disabled:opacity-50 flex items-center gap-2">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
            {loading ? 'Researching viral content…' : 'Research trends'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>
      )}

      {loading && (
        <div className="bg-cyan-50 border border-cyan-100 rounded-lg p-3 text-cyan-700 text-sm flex items-center gap-2">
          <Loader2 size={14} className="animate-spin" /> Gemini is searching the web for viral content. This takes 30–90 sec.
        </div>
      )}

      {data?.summary && (
        <div className="bg-violet-50 border border-violet-100 rounded p-3 text-sm">
          <div className="font-semibold text-violet-800 mb-1">This week's pattern</div>
          <div className="text-gray-700">{data.summary}</div>
          {data.fetched_at && (
            <div className="text-[10px] text-gray-500 mt-1">As of {new Date(data.fetched_at).toLocaleString()}</div>
          )}
        </div>
      )}

      {data?.trends?.length > 0 && (
        <div className="space-y-3">
          {data.trends.map(t => (
            <div key={t.trend_id} className="bg-white rounded-lg border border-gray-200 p-4">
              {/* Header */}
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${t.platform === 'instagram' ? 'bg-pink-100 text-pink-700' : 'bg-gray-900 text-white'}`}>{t.platform}</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${tierColor(t.tier)}`}>Tier {t.tier} · {t.overall_score}/100</span>
                <span className="text-[11px] text-gray-500 uppercase">{t.content_type}</span>
                {t.adaptability_for_ms_read != null && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold border bg-cyan-50 text-cyan-700 border-cyan-200"
                    title="How easily this can be adapted to MS. READ brand voice">
                    Adapt {t.adaptability_for_ms_read}/10
                  </span>
                )}
                {t.creator_or_brand && (
                  <span className="text-[11px] text-gray-500">by {t.creator_or_brand}</span>
                )}
              </div>

              {/* Hook + theme */}
              <div className="mb-3">
                <div className="text-xs font-semibold text-gray-600 mb-0.5">Viral hook</div>
                <div className="text-sm text-gray-900 italic bg-gray-50 rounded p-2 mb-2">"{t.hook}"</div>
                <div className="text-xs text-gray-600">{t.theme}</div>
              </div>

              {/* Scores grid */}
              <div className="grid grid-cols-7 gap-1 mb-3">
                {CRITERIA_LEGEND.map(c => {
                  const v = (t.scores || {})[c.key] || 0;
                  return (
                    <div key={c.key} className="text-center" title={c.desc}>
                      <div className={`text-sm font-bold ${v >= 8 ? 'text-emerald-600' : v >= 5 ? 'text-amber-600' : 'text-red-600'}`}>{v}</div>
                      <div className="text-[9px] text-gray-500 uppercase">{c.label}</div>
                    </div>
                  );
                })}
              </div>

              {/* Why it works */}
              <div className="bg-emerald-50 border border-emerald-100 rounded p-2 mb-2 text-xs">
                <div className="font-semibold text-emerald-800 mb-0.5">Why it works</div>
                <div className="text-gray-700">{t.why_it_works}</div>
              </div>

              {/* Format template */}
              {t.format_template && (
                <div className="text-xs mb-2">
                  <span className="font-semibold text-gray-600">Replicable template: </span>
                  <span className="text-gray-800 italic">"{t.format_template}"</span>
                </div>
              )}

              {/* Hashtags */}
              {t.hashtags?.length > 0 && (
                <div className="mb-2">
                  <div className="flex flex-wrap gap-1">
                    {t.hashtags.map((h, i) => (
                      <span key={i} className="px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded text-[10px]">{h}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex items-center gap-2 flex-wrap mt-3 pt-2 border-t border-gray-100">
                <button onClick={() => handleAdapt(t)}
                  disabled={adaptingId === t.trend_id}
                  className="px-3 py-1.5 bg-violet-600 text-white rounded-lg hover:bg-violet-700 text-xs font-medium disabled:opacity-50 flex items-center gap-1">
                  {adaptingId === t.trend_id ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                  {adaptingId === t.trend_id ? 'Adapting + saving draft…' : 'Adapt to brand voice'}
                </button>
                {/* Platform-native deeplinks — find live examples of this pattern */}
                <span className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold mr-1">
                  Find live examples →
                </span>
                {t.platform_links?.map((lnk, i) => (
                  <a key={i} href={lnk.url} target="_blank" rel="noopener noreferrer"
                    className="text-xs text-cyan-700 hover:underline flex items-center gap-1"
                    title={lnk.label}>
                    {lnk.label} <ExternalLink size={10} />
                  </a>
                ))}
                {/* If we happen to have a validated platform-post URL, label it honestly */}
                {t.direct_post_url && (
                  <a href={t.direct_post_url} target="_blank" rel="noopener noreferrer"
                    className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700 hover:bg-gray-200 flex items-center gap-1"
                    title="A real post that matches this pattern — NOT the specific post that was scored">
                    Example post (real) <ExternalLink size={10} />
                  </a>
                )}
                {t.grounding_sources?.length > 0 && (
                  <details className="text-xs">
                    <summary className="text-cyan-700 hover:underline cursor-pointer">
                      {t.grounding_sources.length} research source{t.grounding_sources.length > 1 ? 's' : ''}
                    </summary>
                    <div className="mt-1 ml-2 space-y-0.5">
                      {t.grounding_sources.map((s, i) => (
                        <div key={i}>
                          <a href={s.url} target="_blank" rel="noopener noreferrer"
                            className="text-cyan-700 hover:underline">
                            {s.title || s.url} <ExternalLink size={9} className="inline" />
                          </a>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>

              {/* Adapted result */}
              {adapted[t.trend_id] && !adapted[t.trend_id].error && (
                <div className="mt-3 bg-violet-50 border border-violet-200 rounded p-3 text-xs">
                  <div className="font-semibold text-violet-800 mb-1 flex items-center gap-1">
                    <CheckCircle size={12} /> Adapted to brand voice
                    {adapted[t.trend_id].saved_draft?.persisted && (
                      <span className="ml-1 text-[10px] font-normal text-emerald-600">✓ saved to Past Drafts</span>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <div>
                      <span className="font-semibold text-gray-600">Hook: </span>
                      <span className="text-gray-800 italic">"{adapted[t.trend_id].adapted.adapted_hook}"</span>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-600 mb-0.5">Caption:</div>
                      <div className="text-gray-800 italic bg-white rounded p-2 whitespace-pre-line">{adapted[t.trend_id].adapted.adapted_caption}</div>
                    </div>
                    <div>
                      <span className="font-semibold text-gray-600">Shoot direction: </span>
                      <span className="text-gray-700">{adapted[t.trend_id].adapted.media_direction}</span>
                    </div>
                    {adapted[t.trend_id].adapted.predicted_performance && (
                      <div className="text-gray-600">
                        <span className="font-semibold">Predicted: </span>{adapted[t.trend_id].adapted.predicted_performance}
                      </div>
                    )}
                  </div>
                </div>
              )}
              {adapted[t.trend_id]?.error && (
                <div className="mt-3 bg-red-50 border border-red-200 rounded p-2 text-xs text-red-700">
                  Adapt failed: {adapted[t.trend_id].error}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {data?.trends?.length === 0 && !loading && (
        <div className="text-center py-6 text-gray-500 text-sm">
          No trends returned. Try widening industry or region.
        </div>
      )}
    </div>
  );
}

function PostScoring() {
  // Default range: last 28 days
  const today = new Date().toISOString().split('T')[0];
  const monthAgo = new Date(Date.now() - 28 * 86400000).toISOString().split('T')[0];

  const [start, setStart] = useState(monthAgo);
  const [end, setEnd] = useState(today);
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [refreshingMetrics, setRefreshingMetrics] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all' | platform | tier

  // Load saved scored posts on mount + whenever date range changes
  const refreshSaved = async (s, e) => {
    setLoading(true);
    try {
      const result = await listSavedScoredPosts(s || start, e || end);
      setPosts(result.posts || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load saved posts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refreshSaved(); }, []);

  const handleApplyDate = () => {
    refreshSaved(start, end);
  };

  const handleScore = async () => {
    setScoring(true);
    setError(null);
    try {
      const result = await scorePosts(4, start, end);
      setPosts(result.posts || []);
    } catch (err) {
      const code = err.code;
      const detail = err.response?.data?.detail;
      if (code === 'ECONNABORTED' || (err.message || '').includes('timeout')) {
        setError('Scoring still running — wait a moment then click again, or try a smaller date range.');
      } else if (detail) {
        setError(detail);
      } else {
        setError('Scoring failed: ' + (err.message || 'unknown error'));
      }
    } finally {
      setScoring(false);
    }
  };

  // Apply UI filter
  const filtered = posts.filter(p => {
    if (filter === 'all') return true;
    if (filter.startsWith('tier:')) return p.tier === filter.split(':')[1];
    if (filter.startsWith('platform:')) return p.platform === filter.split(':')[1];
    return true;
  });

  const tierColor = (tier) => ({
    A: 'bg-emerald-100 text-emerald-700',
    B: 'bg-blue-100 text-blue-700',
    C: 'bg-amber-100 text-amber-700',
    D: 'bg-red-100 text-red-700',
  }[tier] || 'bg-gray-100 text-gray-600');

  // Tier counts for filter chips
  const tierCounts = posts.reduce((acc, p) => {
    acc[p.tier] = (acc[p.tier] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="bg-gradient-to-br from-pink-50 to-violet-50 rounded-xl shadow-sm border border-pink-100 p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Sparkles size={18} className="text-pink-600" /> Social Post Performance
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={async () => {
              setRefreshingMetrics(true);
              try {
                const result = await refreshPostMetrics();
                setRefreshMsg(`Updated metrics for ${result.updated} of ${result.total} posts`);
                await refreshSaved();
              } catch (e) {
                setRefreshMsg('Refresh failed: ' + (e.response?.data?.detail || e.message));
              } finally {
                setRefreshingMetrics(false);
                setTimeout(() => setRefreshMsg(null), 5000);
              }
            }}
            disabled={refreshingMetrics || scoring}
            className="px-3 py-2 bg-white border border-pink-200 text-pink-700 rounded-lg hover:bg-pink-50 text-xs font-medium disabled:opacity-50 flex items-center gap-2"
            title="Re-fetch reach/likes/views/etc for already-scored posts (no re-scoring)"
          >
            {refreshingMetrics ? <Loader2 size={12} className="animate-spin" /> : <TrendingUp size={12} />}
            {refreshingMetrics ? 'Refreshing…' : 'Refresh metrics'}
          </button>
          <button
            onClick={handleScore}
            disabled={scoring}
            className="px-4 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700 text-sm font-medium disabled:opacity-50 flex items-center gap-2"
          >
            {scoring ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {scoring ? 'Scoring new posts...' : 'Score 4 New Posts'}
          </button>
        </div>
      </div>
      {refreshMsg && (
        <div className="mb-2 p-2 rounded bg-pink-50 border border-pink-100 text-pink-800 text-xs">{refreshMsg}</div>
      )}

      {/* Date range filter */}
      <div className="flex items-center gap-2 mb-3 flex-wrap text-xs">
        <Calendar size={14} className="text-gray-400" />
        <input
          type="date"
          value={start}
          max={end}
          onChange={e => setStart(e.target.value)}
          className="border border-gray-200 rounded px-2 py-1 bg-white"
        />
        <span className="text-gray-400">to</span>
        <input
          type="date"
          value={end}
          max={today}
          min={start}
          onChange={e => setEnd(e.target.value)}
          className="border border-gray-200 rounded px-2 py-1 bg-white"
        />
        <button
          onClick={handleApplyDate}
          disabled={loading}
          className="px-2.5 py-1 bg-violet-600 text-white rounded font-medium disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Apply'}
        </button>
        <span className="text-gray-500 ml-2">{posts.length} scored posts</span>
      </div>

      {/* Tier / platform filter chips */}
      {posts.length > 0 && (
        <div className="flex gap-1.5 mb-3 flex-wrap">
          {[
            { id: 'all', label: `All (${posts.length})` },
            { id: 'platform:instagram', label: `IG (${posts.filter(p => p.platform === 'instagram').length})` },
            { id: 'platform:facebook', label: `FB (${posts.filter(p => p.platform === 'facebook').length})` },
            ...['A', 'B', 'C', 'D'].filter(t => tierCounts[t]).map(t => ({ id: `tier:${t}`, label: `${t}-tier (${tierCounts[t]})` })),
          ].map(c => (
            <button
              key={c.id}
              onClick={() => setFilter(c.id)}
              className={`px-2 py-0.5 rounded text-[11px] font-medium ${filter === c.id ? 'bg-violet-600 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:border-violet-300'}`}
            >
              {c.label}
            </button>
          ))}
        </div>
      )}

      <ScoringRubricInfo />

      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{typeof error === 'string' ? error : JSON.stringify(error)}</div>
      )}
      {loading && (
        <div className="space-y-2">
          {[0, 1, 2].map(i => (
            <div key={i} className="bg-white/70 rounded-lg border border-gray-100 p-4 animate-pulse">
              <div className="flex gap-4">
                <div className="w-24 h-24 bg-gray-200 rounded-lg shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-1/3" />
                  <div className="h-3 bg-gray-200 rounded w-2/3" />
                  <div className="grid grid-cols-7 gap-1 mt-2">
                    {[...Array(7)].map((_, j) => <div key={j} className="h-6 bg-gray-200 rounded" />)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {scoring && (
        <div className="mb-3 p-3 rounded-lg bg-violet-50 border border-violet-100 text-violet-700 text-sm flex items-center gap-2">
          <Loader2 size={14} className="animate-spin" />
          Gemini is scoring up to 4 new posts (~15 sec each). Existing scores stay visible during this.
        </div>
      )}
      {posts.length === 0 && !loading && !scoring && !error && (
        <div className="text-center py-6 text-gray-500 text-sm">
          No scored posts in this range yet. Click "Score 4 New Posts" — Gemini rates
          posts on 7 industry criteria. Already-scored posts will be kept in the list.
        </div>
      )}
      {posts.length === 0 && !loading && error && /permission|instagram_|pages_read/i.test(String(error)) && (
        <div className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded p-3 mt-2 leading-snug">
          Reading FB/Instagram posts needs Meta App permissions. The current System User
          token may need to be regenerated with <code>instagram_basic</code>,
          <code>instagram_manage_insights</code>, and <code>pages_read_engagement</code>.
        </div>
      )}

      <div className="space-y-3">
        {filtered.map(p => (
          <div key={p.post_id} className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex gap-4">
              {(p.media_url || p.thumbnail_url) && (
                <a href={p.permalink_url} target="_blank" rel="noopener noreferrer" className="shrink-0">
                  <img src={p.media_url || p.thumbnail_url} alt="" className="w-24 h-24 object-cover rounded-lg border border-gray-100" onError={(e) => { e.target.style.display = 'none'; }} />
                </a>
              )}
              <div className="flex-1 min-w-0">
                {/* Header line */}
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${p.platform === 'instagram' ? 'bg-pink-100 text-pink-700' : 'bg-blue-100 text-blue-700'}`}>{p.platform}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${tierColor(p.tier)}`}
                        title={p.engagement_score != null ? `Live blend (80/20):\nCreative ${p.creative_only_score}/100\nEngagement ${p.engagement_score}/100\nFinal ${p.overall_score}/100 (${p.engagement_adjustment >= 0 ? '+' : ''}${p.engagement_adjustment} from engagement)` : `Creative-only ${p.creative_only_score ?? p.overall_score}/100`}>
                    Tier {p.tier} · {p.overall_score}/100
                    {p.engagement_adjustment != null && p.engagement_adjustment !== 0 && (
                      <span className={`ml-1 ${p.engagement_adjustment >= 0 ? 'opacity-70' : 'opacity-70'}`}>
                        ({p.engagement_adjustment >= 0 ? '+' : ''}{p.engagement_adjustment})
                      </span>
                    )}
                  </span>
                  {p.pre_score && (
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                        p.pre_score.delta > 0
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : p.pre_score.delta < 0
                          ? 'bg-red-50 text-red-700 border-red-200'
                          : 'bg-gray-50 text-gray-700 border-gray-200'
                      }`}
                      title={`Pre-score on ${p.pre_score.scored_at?.slice(0,10)} predicted ${p.pre_score.overall_score}. Actual is ${p.overall_score}. Δ ${p.pre_score.delta >= 0 ? '+' : ''}${p.pre_score.delta}.`}
                    >
                      Pre {p.pre_score.overall_score} → Actual {p.overall_score} · {p.pre_score.delta >= 0 ? '+' : ''}{p.pre_score.delta}
                    </span>
                  )}
                  {p.created_time && (
                    <span className="text-[11px] text-gray-500">
                      📅 {new Date(p.created_time).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}
                    </span>
                  )}
                  {p.media_type && (
                    <span className="text-[11px] text-gray-500 uppercase">{p.media_type}</span>
                  )}
                  <a href={p.permalink_url} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-600 hover:underline flex items-center gap-1">
                    View <ExternalLink size={10} />
                  </a>
                </div>

                {/* Original caption */}
                {p.caption && (
                  <div className="text-xs text-gray-600 italic bg-gray-50 rounded p-2 mb-3 line-clamp-3 leading-snug">
                    "{p.caption.length > 240 ? p.caption.slice(0, 240) + '…' : p.caption}"
                  </div>
                )}

                {/* Score grid */}
                <div className="grid grid-cols-7 gap-1 mb-3">
                  {CRITERIA_LEGEND.map(c => {
                    const v = (p.scores || {})[c.key] || 0;
                    return (
                      <div key={c.key} className="text-center" title={c.desc}>
                        <div className={`text-sm font-bold ${v >= 8 ? 'text-emerald-600' : v >= 5 ? 'text-amber-600' : 'text-red-600'}`}>{v}</div>
                        <div className="text-[9px] text-gray-500 uppercase">{c.label}</div>
                      </div>
                    );
                  })}
                </div>

                {/* Strengths / Weaknesses */}
                <div className="grid grid-cols-2 gap-3 mb-3 text-xs">
                  <div>
                    <div className="font-semibold text-emerald-700 mb-1">Strengths</div>
                    <ul className="text-gray-700 space-y-0.5 list-disc ml-4">
                      {(p.strengths || []).map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold text-red-700 mb-1">Weaknesses</div>
                    <ul className="text-gray-700 space-y-0.5 list-disc ml-4">
                      {(p.weaknesses || []).map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                </div>

                {/* Recommendations */}
                {p.recommendations?.length > 0 && (
                  <div className="bg-violet-50 rounded p-2 mb-2 text-xs">
                    <div className="font-semibold text-violet-700 mb-1">Recommendations</div>
                    <ul className="text-gray-700 space-y-0.5 list-disc ml-4">
                      {p.recommendations.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                )}

                {/* Suggested rewrites */}
                {p.suggested_hook && (
                  <div className="text-xs mb-1">
                    <span className="font-semibold text-gray-600">Suggested hook: </span>
                    <span className="text-gray-800 italic">"{p.suggested_hook}"</span>
                  </div>
                )}
                {p.suggested_caption && (
                  <div className="text-xs">
                    <div className="font-semibold text-gray-600 mb-0.5">Suggested caption:</div>
                    <div className="text-gray-800 italic bg-gray-50 rounded p-2 whitespace-pre-line">{p.suggested_caption}</div>
                  </div>
                )}

                {/* Performance metrics — reference panel */}
                <div className="mt-3 pt-2 border-t border-gray-100">
                  <div className="text-[10px] uppercase tracking-wide text-gray-400 mb-1.5 font-semibold">
                    Actual performance (reference)
                  </div>
                  <div className="grid grid-cols-4 md:grid-cols-8 gap-2 text-[11px]">
                    {(() => {
                      const pen = p.metrics?.reach_penetration_pct;
                      const rp = pen != null ? reachPenetrationBenchmark(p.platform, p.media_type, pen) : null;
                      return (
                        <MetricChip label="Reach"
                                    value={(p.metrics?.reach || 0).toLocaleString()}
                                    tone={rp?.tone}
                                    tooltip={rp ? `${rp.label}\n${rp.benchmark}\nSource: ${rp.source?.label || ''}` : undefined} />
                      );
                    })()}
                    {(() => {
                      const sig = p.metrics?.er_significance;
                      const gated = sig === 'noise' || sig === 'low';
                      const followers = p.metrics?.followers_at_score_time || 0;
                      const vtr = viewThroughBenchmark(p.platform, p.media_type, p.metrics?.views, p.metrics?.reach, p.metrics?.followers_at_score_time);
                      const lk = engagementCountBenchmark('likes', p.metrics?.likes || 0, followers);
                      const cm = engagementCountBenchmark('comments', p.metrics?.comments || 0, followers);
                      const sh = engagementCountBenchmark('shares', p.metrics?.shares || 0, followers);
                      const sv = engagementCountBenchmark('saves', p.metrics?.saves || 0, followers);
                      // When ER is gated (reach too low) all engagement counts also become unreliable
                      const safeTone = (b) => gated ? (b.tone === 'good' ? 'ok' : 'weak') : b.tone;
                      // Only show Views chip on video media — images/carousels have no views concept
                      const isVideo = p.media_type === 'VIDEO' || p.media_type === 'REELS';
                      return (
                        <>
                          {isVideo && (
                            <MetricChip label="Views"    value={(p.metrics?.views || 0).toLocaleString()}
                                        tone={vtr.tone} tooltip={vtr.label ? `${vtr.label}\n${vtr.benchmark}` : undefined} />
                          )}
                          <MetricChip label="Likes"    value={(p.metrics?.likes || 0).toLocaleString()}
                                      tone={safeTone(lk)} tooltip={lk.benchmark ? `${lk.label}\n${lk.benchmark}${gated ? '\n⚠ Reach too low — interpret cautiously' : ''}` : undefined} />
                          <MetricChip label="Comments" value={(p.metrics?.comments || 0).toLocaleString()}
                                      tone={safeTone(cm)} tooltip={cm.benchmark ? `${cm.label}\n${cm.benchmark}${gated ? '\n⚠ Reach too low — interpret cautiously' : ''}` : undefined} />
                          <MetricChip label="Shares"   value={(p.metrics?.shares || 0).toLocaleString()}
                                      tone={safeTone(sh)} tooltip={sh.benchmark ? `${sh.label}\n${sh.benchmark}${gated ? '\n⚠ Reach too low — interpret cautiously' : ''}` : undefined} />
                          <MetricChip label="Saves"    value={(p.metrics?.saves || 0).toLocaleString()}
                                      tone={safeTone(sv)} tooltip={sv.benchmark ? `${sv.label}\n${sv.benchmark}${gated ? '\n⚠ Reach too low — interpret cautiously' : ''}` : undefined} />
                        </>
                      );
                    })()}
                    {(() => {
                      const sig = p.metrics?.er_significance;
                      const bm = erBenchmark(p.platform, p.media_type, p.metrics?.engagement_rate || 0, sig);
                      const display = bm.gated
                        ? `${((p.metrics?.engagement_rate || 0) * 100).toFixed(1)}% ⚠`
                        : `${((p.metrics?.engagement_rate || 0) * 100).toFixed(1)}%`;
                      return (
                        <MetricChip label={bm.gated ? 'ER (gated)' : 'ER'}
                                    value={display}
                                    tone={bm.tone}
                                    tooltip={`${bm.formula}\n${bm.label}\n${bm.benchmark}\nSource: ${bm.source?.label || ''}`} />
                      );
                    })()}
                    {p.metrics?.reach_penetration_pct != null && (() => {
                      const rp = reachPenetrationBenchmark(p.platform, p.media_type, p.metrics.reach_penetration_pct);
                      return (
                        <MetricChip label="Reach %"
                                    value={`${p.metrics.reach_penetration_pct.toFixed(1)}%`}
                                    tone={rp.tone}
                                    tooltip={`Reach ÷ Followers (${(p.metrics.followers_at_score_time || 0).toLocaleString()})\n${rp.label}\n${rp.benchmark}`} />
                      );
                    })()}
                  </div>
                  {(p.metrics?.clicks > 0 || p.metrics?.ctr > 0) && (
                    <div className="grid grid-cols-4 md:grid-cols-8 gap-2 text-[11px] mt-1.5">
                      <MetricChip label="Clicks" value={(p.metrics?.clicks || 0).toLocaleString()} />
                      {(() => {
                        const cb = ctrBenchmark(p.platform, p.metrics?.ctr || 0);
                        return (
                          <MetricChip label="CTR"
                                      value={`${((p.metrics?.ctr || 0) * 100).toFixed(2)}%`}
                                      tone={cb.tone}
                                      tooltip={`${cb.label}\n${cb.benchmark}`} />
                        );
                      })()}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Homepage Theme Schema Snippet ────────────────────────────── */

function HomepageSchemaSnippet() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState(false);

  const handleLoad = async () => {
    setLoading(true);
    try {
      const result = await getThemeSnippet();
      setData(result);
      setOpen(true);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(data?.snippet || '').then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <Code size={18} /> Homepage Schema (one-time theme install)
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Homepage JSON-LD lives in your Shopify theme — paste this snippet once and it covers your homepage forever.
          </p>
        </div>
        <button
          onClick={handleLoad}
          disabled={loading}
          className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-xs font-medium disabled:opacity-50"
        >
          {loading ? 'Loading…' : (data ? 'Refresh snippet' : 'Generate snippet')}
        </button>
      </div>

      {data && open && (
        <div className="mt-4 space-y-3">
          {/* Instructions */}
          <div className="bg-blue-50 border border-blue-100 rounded p-3 text-xs">
            <div className="font-semibold text-blue-800 mb-1">How to install</div>
            <ol className="list-decimal ml-4 space-y-0.5 text-blue-900">
              {(data.instructions || []).map((s, i) => <li key={i}>{s}</li>)}
            </ol>
          </div>

          {/* Snippet code block */}
          <div className="relative">
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 px-2 py-1 bg-white border border-gray-200 rounded text-[11px] font-medium hover:bg-gray-50 z-10"
            >
              {copied ? '✓ Copied' : 'Copy'}
            </button>
            <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 text-[11px] font-mono overflow-x-auto max-h-80 whitespace-pre-wrap">{data.snippet}</pre>
          </div>

          <div className="text-[11px] text-gray-500">
            After installing, validate at{' '}
            <a href="https://search.google.com/test/rich-results" target="_blank" rel="noopener" className="text-indigo-600 hover:underline">
              Google's Rich Results Test
            </a>{' '}
            — paste your homepage URL there.
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── On-Page SEO Audit Tab ──────────────────────────────────────── */

function OnPageTab({ crawlData, crawlLoading, expandedPage, setExpandedPage }) {
  if (crawlLoading) return <div className="text-center py-12 text-gray-400">Crawling site pages...</div>;
  if (!crawlData) return <div className="text-center py-12 text-red-400">Failed to load crawl data</div>;

  const { pages, summary } = crawlData;
  const s = summary || {};

  return (
    <div className="space-y-6">
      {/* AI Suggestions (top — most actionable) */}
      <AiSuggestions />

      {/* Homepage theme snippet (one-time install for homepage schema) */}
      <HomepageSchemaSnippet />

      {/* Score Overview */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
          <div className={`text-3xl font-bold ${s.avg_seo_score >= 80 ? 'text-emerald-600' : s.avg_seo_score >= 60 ? 'text-amber-600' : 'text-red-600'}`}>
            {s.avg_seo_score}
          </div>
          <div className="text-xs text-gray-500 mt-1">Avg SEO Score</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
          <div className="text-3xl font-bold text-gray-800">{s.pages_crawled}</div>
          <div className="text-xs text-gray-500 mt-1">Pages Crawled</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
          <div className="text-3xl font-bold text-red-600">{s.critical_issues}</div>
          <div className="text-xs text-gray-500 mt-1">Critical Issues</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
          <div className="text-3xl font-bold text-amber-600">{s.warning_issues}</div>
          <div className="text-xs text-gray-500 mt-1">Warnings</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
          <div className="text-3xl font-bold text-blue-500">{s.info_issues}</div>
          <div className="text-xs text-gray-500 mt-1">Suggestions</div>
        </div>
      </div>

      {/* Site-Wide Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard icon={FileText} label="Avg Word Count" value={s.avg_word_count?.toLocaleString() || '0'} color="indigo" />
        <MetricCard icon={Image} label="Alt Text Coverage" value={`${s.alt_coverage_pct || 0}%`} subvalue={`${s.images_missing_alt || 0} missing of ${s.total_images || 0}`} color={s.alt_coverage_pct >= 90 ? 'green' : 'amber'} />
        <MetricCard icon={Code} label="Schema Markup" value={`${s.pages_with_schema || 0}/${s.pages_crawled || 0}`} subvalue="pages with JSON-LD" color="indigo" />
        <MetricCard icon={Monitor} label="Mobile Ready" value={`${s.pages_mobile_ready || 0}/${s.pages_crawled || 0}`} subvalue="with viewport meta" color="green" />
      </div>

      {/* Top Issues */}
      {s.top_issues?.length > 0 && (
        <Section title="Top Issues Across Site" icon={AlertTriangle} count={s.total_issues}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {s.top_issues.map((issue, i) => (
              <div key={i} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3">
                <span className="text-sm text-gray-700">{issue.issue}</span>
                <span className="text-sm font-bold text-gray-500 bg-gray-200 rounded-full px-2.5 py-0.5">
                  {issue.count} page{issue.count !== 1 ? 's' : ''}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Page-by-Page Audit */}
      <Section title="Page Audit Details" icon={Globe} count={pages?.length}>
        <div className="space-y-2">
          {pages?.map((page, i) => (
            <div key={i} className="border border-gray-100 rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedPage(expandedPage === i ? null : i)}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <ScoreBadge score={page.score} />
                  <span className="text-sm font-medium text-gray-800 truncate">{page.url}</span>
                  {page.issues?.length > 0 && (
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {page.issues.length} issue{page.issues.length !== 1 ? 's' : ''}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-400 flex-shrink-0">
                  <span>{page.word_count} words</span>
                  <span>{page.load_time_ms}ms</span>
                  {expandedPage === i ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
              </button>
              {expandedPage === i && (
                <div className="px-4 pb-4 border-t border-gray-50 bg-gray-50/50">
                  <div className="pt-4 space-y-4">
                    {/* Meta Info */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs text-gray-400 mb-1">Title ({page.title_length} chars)</div>
                        <div className="text-sm font-medium text-gray-800 bg-white rounded px-3 py-2 border border-gray-100">
                          {page.title || <span className="text-red-400 italic">Missing</span>}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400 mb-1">Meta Description ({page.meta_description_length} chars)</div>
                        <div className="text-sm text-gray-700 bg-white rounded px-3 py-2 border border-gray-100">
                          {page.meta_description || <span className="text-red-400 italic">Missing</span>}
                        </div>
                      </div>
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-3 md:grid-cols-6 gap-3 text-center text-xs">
                      <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                        <div className="font-bold text-gray-800">{page.heading_count}</div>
                        <div className="text-gray-400">Headings</div>
                      </div>
                      <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                        <div className="font-bold text-gray-800">{page.h1_tags?.length || 0}</div>
                        <div className="text-gray-400">H1 Tags</div>
                      </div>
                      <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                        <div className="font-bold text-gray-800">{page.internal_links}</div>
                        <div className="text-gray-400">Int. Links</div>
                      </div>
                      <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                        <div className="font-bold text-gray-800">{page.external_links}</div>
                        <div className="text-gray-400">Ext. Links</div>
                      </div>
                      <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                        <div className={`font-bold ${page.alt_text_coverage >= 90 ? 'text-emerald-600' : 'text-amber-600'}`}>{page.alt_text_coverage?.toFixed(0)}%</div>
                        <div className="text-gray-400">Alt Coverage</div>
                      </div>
                      <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                        <div className="font-bold text-gray-800">{page.page_size_kb?.toFixed(0)}KB</div>
                        <div className="text-gray-400">Page Size</div>
                      </div>
                    </div>

                    {/* Tech Tags */}
                    <div className="flex flex-wrap gap-2 text-xs">
                      {page.has_canonical && <span className="bg-emerald-50 text-emerald-700 px-2 py-1 rounded">Canonical</span>}
                      {!page.has_canonical && <span className="bg-red-50 text-red-600 px-2 py-1 rounded">No Canonical</span>}
                      {page.viewport_meta && <span className="bg-emerald-50 text-emerald-700 px-2 py-1 rounded">Mobile Ready</span>}
                      {page.has_og_tags && <span className="bg-emerald-50 text-emerald-700 px-2 py-1 rounded">OG Tags</span>}
                      {!page.has_og_tags && <span className="bg-gray-100 text-gray-500 px-2 py-1 rounded">No OG Tags</span>}
                      {page.has_structured_data && <span className="bg-emerald-50 text-emerald-700 px-2 py-1 rounded">Schema: {page.structured_data_types?.join(', ')}</span>}
                      {!page.has_structured_data && <span className="bg-gray-100 text-gray-500 px-2 py-1 rounded">No Schema</span>}
                      {page.language && <span className="bg-blue-50 text-blue-600 px-2 py-1 rounded">Lang: {page.language}</span>}
                    </div>

                    {/* Issues */}
                    {page.issues?.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-gray-500 uppercase tracking-wider">Issues</div>
                        {page.issues.map((issue, j) => (
                          <div key={j} className="flex items-start gap-2 text-sm bg-white rounded-lg px-3 py-2 border border-gray-100">
                            <SeverityIcon severity={issue.severity} />
                            <div>
                              <span className="font-medium text-gray-800">{issue.issue}</span>
                              <span className="text-gray-500"> — {issue.detail}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {page.issues?.length === 0 && (
                      <div className="flex items-center gap-2 text-sm text-emerald-600">
                        <CheckCircle size={16} /> No issues found — page is well optimized
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

/* ─── Organic & Paid Intelligence Tab ─────────────────────────────── */

function OrganicTab({ data, loading }) {
  if (loading) return <div className="text-center py-12 text-gray-400">Loading SEO data...</div>;
  if (!data) return <div className="text-center py-12 text-red-400">Failed to load SEO data</div>;

  const { site_health, keyword_opportunities, content_gaps, quick_wins, cannibalization, competitors, autonomous_actions, _notice } = data;
  const aa = autonomous_actions || {};

  // Detect "not connected" state — all metrics zero AND notice present
  const noData = (!site_health?.total_clicks && !site_health?.total_impressions
                  && (!keyword_opportunities || keyword_opportunities.length === 0)
                  && (!quick_wins || quick_wins.length === 0));

  if (noData && _notice) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
        <Search size={40} className="mx-auto mb-4 text-gray-300" />
        <h3 className="text-lg font-semibold text-gray-800 mb-2">Google Search Console not connected</h3>
        <p className="text-sm text-gray-600 max-w-xl mx-auto mb-4">{_notice}</p>
        <div className="text-left max-w-xl mx-auto bg-gray-50 rounded-lg p-4 text-xs text-gray-600">
          <div className="font-semibold text-gray-700 mb-1">What this tab will show once connected:</div>
          <ul className="list-disc ml-4 space-y-0.5">
            <li>Site health: total organic clicks, impressions, avg position, ranking pages</li>
            <li>Keyword opportunities — terms you rank on but underspend in paid</li>
            <li>Content gaps — high-paid-spend terms with no organic page</li>
            <li>Quick wins — keywords ranking 4-15 (one push to top 3)</li>
            <li>Cannibalization — multiple URLs competing for the same query</li>
          </ul>
          <div className="mt-3 text-gray-500">
            Set <code className="bg-white px-1 rounded">GSC_CREDENTIALS_JSON</code> and{' '}
            <code className="bg-white px-1 rounded">GSC_SITE_URL</code> env vars to enable.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Site Health Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard icon={Globe} label="Organic Clicks" value={site_health?.total_clicks?.toLocaleString() || '0'} color="green" />
        <MetricCard icon={Search} label="Impressions" value={site_health?.total_impressions?.toLocaleString() || '0'} color="indigo" />
        <MetricCard icon={TrendingUp} label="Avg Position" value={site_health?.avg_position?.toFixed(1) || '0'} color="amber" />
        <MetricCard
          icon={FileText}
          label="Pages Ranking"
          value={`${site_health?.ranking_pages_top3 || 0} / ${site_health?.ranking_pages_top10 || 0} / ${site_health?.ranking_pages_top20 || 0}`}
          subvalue="Top 3 / Top 10 / Top 20"
          color="indigo"
        />
      </div>

      {/* Recommendations Summary — NOT executed actions */}
      {aa.total > 0 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-5">
          <h3 className="text-lg font-semibold text-indigo-900 flex items-center gap-2 mb-1">
            <Zap size={18} /> SEO Recommendations · {aa.total} suggestions
          </h3>
          <p className="text-xs text-indigo-700 mb-3">
            These are SEO/SEM analyzer suggestions for review only. Nothing here is applied — all execution requires explicit approval in the Pending queue.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="bg-white rounded-lg p-3">
              <div className="text-2xl font-bold text-emerald-600">${aa.total_estimated_savings?.toFixed(0) || 0}</div>
              <div className="text-gray-500">Est. Savings/Period</div>
            </div>
            <div className="bg-white rounded-lg p-3">
              <div className="text-2xl font-bold text-red-600">{aa.bid_reductions?.length || 0}</div>
              <div className="text-gray-500">Bid Reductions</div>
            </div>
            <div className="bg-white rounded-lg p-3">
              <div className="text-2xl font-bold text-amber-600">{aa.cannibalization_fixes?.length || 0}</div>
              <div className="text-gray-500">Cannibalization Fixes</div>
            </div>
            <div className="bg-white rounded-lg p-3">
              <div className="text-2xl font-bold text-blue-600">{(aa.content_gaps?.length || 0) + (aa.quick_wins?.length || 0)}</div>
              <div className="text-gray-500">Content Actions</div>
            </div>
          </div>
        </div>
      )}

      {/* Bid Reductions — RECOMMENDATIONS, not executed */}
      <Section title="Recommended Bid Reductions (review only — nothing applied)" icon={Zap} count={aa.bid_reductions?.length}>
        {aa.bid_reductions?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-500 border-b">
                <th className="pb-2 font-medium">Keyword</th>
                <th className="pb-2 font-medium">Action</th>
                <th className="pb-2 font-medium text-right">Organic #</th>
                <th className="pb-2 font-medium text-right">Paid Spend</th>
                <th className="pb-2 font-medium text-right">Savings</th>
                <th className="pb-2 font-medium text-right">Confidence</th>
              </tr></thead>
              <tbody>{aa.bid_reductions.map((a, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2 font-medium">{a.search_term}</td>
                  <td className="py-2"><span className={`px-2 py-1 rounded text-xs ${a.action_type === 'pause_keyword' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{a.action_type.replace(/_/g, ' ')}</span></td>
                  <td className="py-2 text-right">#{a.organic_position?.toFixed(1)}</td>
                  <td className="py-2 text-right">${a.paid_spend?.toFixed(0)}</td>
                  <td className="py-2 text-right text-emerald-600">${a.estimated_savings?.toFixed(0)}</td>
                  <td className="py-2 text-right">{(a.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="text-gray-400 text-sm">No bid reduction opportunities found</p>}
      </Section>

      {/* Keyword Opportunities */}
      <Section title="Keyword Opportunities (Paid/Organic Overlap)" icon={Search} count={keyword_opportunities?.length} defaultOpen={false}>
        {keyword_opportunities?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-500 border-b">
                <th className="pb-2 font-medium">Keyword</th>
                <th className="pb-2 font-medium text-right">Organic #</th>
                <th className="pb-2 font-medium text-right">Paid Spend</th>
                <th className="pb-2 font-medium text-right">Paid ROAS</th>
                <th className="pb-2 font-medium">Recommendation</th>
              </tr></thead>
              <tbody>{keyword_opportunities.map((k, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2 font-medium">{k.search_term}</td>
                  <td className="py-2 text-right">#{k.organic_position?.toFixed(1)}</td>
                  <td className="py-2 text-right">${k.paid_spend?.toFixed(0)}</td>
                  <td className="py-2 text-right">{k.paid_roas?.toFixed(2)}x</td>
                  <td className="py-2"><span className={`px-2 py-1 rounded text-xs ${k.recommendation === 'reduce_bid' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}`}>{k.recommendation}</span></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="text-gray-400 text-sm">No keyword opportunities found</p>}
      </Section>

      {/* Content Gaps */}
      <Section title="Content Gaps" icon={FileText} count={aa.content_gaps?.length}>
        {aa.content_gaps?.length > 0 ? (
          <div className="space-y-3">
            {aa.content_gaps.map((g, i) => (
              <div key={i} className="border border-gray-100 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-900">"{g.search_term}"</span>
                  <span className="text-emerald-600 font-semibold text-sm">~${g.estimated_annual_savings?.toLocaleString()}/yr savings</span>
                </div>
                <div className="flex gap-4 text-xs text-gray-500 mb-2">
                  <span>Paid spend: ${g.paid_spend?.toFixed(0)}/period</span>
                  <span>Confidence: {(g.confidence * 100).toFixed(0)}%</span>
                </div>
                {g.content_brief && (
                  <div className="bg-gray-50 rounded p-3 text-xs grid grid-cols-2 md:grid-cols-4 gap-2">
                    <div><span className="text-gray-400">Format:</span> <span className="font-medium">{g.content_brief.suggested_format?.replace('_', ' ')}</span></div>
                    <div><span className="text-gray-400">Words:</span> <span className="font-medium">{g.content_brief.target_word_count}</span></div>
                    <div><span className="text-gray-400">Intent:</span> <span className="font-medium">{g.content_brief.intent}</span></div>
                    <div><span className="text-gray-400">Priority:</span> <span className={`font-medium ${g.content_brief.priority === 'high' ? 'text-red-600' : 'text-amber-600'}`}>{g.content_brief.priority}</span></div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : <p className="text-gray-400 text-sm">No content gaps found</p>}
      </Section>

      {/* Quick Wins */}
      <Section title="Quick Wins" icon={TrendingUp} count={aa.quick_wins?.length}>
        {aa.quick_wins?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-500 border-b">
                <th className="pb-2 font-medium">Query</th>
                <th className="pb-2 font-medium text-right">Position</th>
                <th className="pb-2 font-medium text-right">Click Lift</th>
                <th className="pb-2 font-medium text-right">Confidence</th>
              </tr></thead>
              <tbody>{aa.quick_wins.map((w, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2 font-medium">{w.query}</td>
                  <td className="py-2 text-right">#{w.current_position?.toFixed(1)}</td>
                  <td className="py-2 text-right text-emerald-600">+{w.estimated_click_lift}</td>
                  <td className="py-2 text-right">{(w.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="text-gray-400 text-sm">No quick wins found</p>}
      </Section>

      {/* Cannibalization */}
      <Section title="Keyword Cannibalization" icon={AlertTriangle} count={cannibalization?.length} defaultOpen={false}>
        {cannibalization?.length > 0 ? (
          <div className="space-y-3">
            {cannibalization.map((c, i) => (
              <div key={i} className="border border-amber-100 bg-amber-50 rounded-lg p-4">
                <div className="font-medium text-gray-900 mb-1">"{c.query}"</div>
                <div className="text-xs text-gray-500 mb-2">{c.total_impressions?.toLocaleString()} impressions · {c.total_clicks} clicks</div>
                <div className="text-xs space-y-1">
                  {c.competing_pages?.map((p, j) => (
                    <div key={j} className={`flex items-center gap-1 ${j === 0 ? 'text-emerald-700 font-medium' : 'text-gray-500'}`}>
                      {j === 0 ? 'Primary:' : 'Competing:'} <span className="truncate">{p}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : <p className="text-gray-400 text-sm">No cannibalization detected</p>}
      </Section>

      {/* Competitors */}
      <Section title="Competitor Intelligence" icon={Globe} count={competitors?.length} defaultOpen={false}>
        {competitors?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-500 border-b">
                <th className="pb-2 font-medium">Competitor</th>
                <th className="pb-2 font-medium text-right">Overlap</th>
                <th className="pb-2 font-medium text-right">We Win</th>
                <th className="pb-2 font-medium text-right">They Win</th>
                <th className="pb-2 font-medium">Gap Keywords</th>
              </tr></thead>
              <tbody>{competitors.map((c, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2 font-medium">{c.competitor}</td>
                  <td className="py-2 text-right">{c.overlap_keywords}</td>
                  <td className="py-2 text-right text-emerald-600">{c.our_wins}</td>
                  <td className="py-2 text-right text-red-500">{c.their_wins}</td>
                  <td className="py-2 text-xs text-gray-500">{c.gap_keywords?.slice(0, 3).join(', ')}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="text-gray-400 text-sm">No competitor data available</p>}
      </Section>
    </div>
  );
}
