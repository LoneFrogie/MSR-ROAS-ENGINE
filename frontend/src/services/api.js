/**
 * API client for the ROAS Engine backend.
 */
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// ─── Dashboard Data ───

export const getHealth = () => api.get('/health').then(r => r.data);
export const getSnapshot = () => api.get('/snapshot').then(r => r.data);
export const getCampaigns = (platform) =>
  api.get('/campaigns', { params: platform ? { platform } : {} }).then(r => r.data);
export const getPlatformSummary = () => api.get('/platform-summary').then(r => r.data);
export const getActionHistory = (limit = 50) =>
  api.get('/actions', { params: { limit } }).then(r => r.data);
export const getConfig = () => api.get('/config').then(r => r.data);

// ─── Config Management ───

export const updateConfig = (data) =>
  api.put('/config', data).then(r => r.data);

// ─── SEO ───

export const getSEOOverview = () => api.get('/seo/overview').then(r => r.data);
export const getSiteCrawl = () => api.get('/seo/crawl').then(r => r.data);
export const triggerSiteCrawl = (urls) => api.post('/seo/crawl', urls ? { urls } : null).then(r => r.data);
export const generateSeoSuggestions = (maxPages = 5) =>
  api.post('/seo/suggestions/generate', null, { params: { max_pages: maxPages } }).then(r => r.data);
export const getThemeSnippet = () => api.get('/seo/theme-snippet').then(r => r.data);
export const getPostScoringConfig = () => api.get('/social/posts/scoring-config').then(r => r.data);
export const refreshPostMetrics = () => api.post('/social/posts/refresh-metrics').then(r => r.data);
export const getTrendingInspiration = (params = {}) =>
  api.get('/social/trends/inspiration', { params, timeout: 180000 }).then(r => r.data);
export const adaptTrendToBrand = (trend, opts = {}) =>
  api.post('/social/trends/adapt', { trend, ...opts }, { timeout: 120000 }).then(r => r.data);
export const listDraftScores = (startDate = null, endDate = null) =>
  api.get('/social/posts/drafts', { params: { start_date: startDate, end_date: endDate } }).then(r => r.data);
export const getPredictionAccuracy = () => api.get('/social/posts/prediction-accuracy').then(r => r.data);
export const scoreDraftPost = (caption, platform, mediaType, file) => {
  const form = new FormData();
  form.append('caption', caption || '');
  form.append('platform', platform || 'instagram');
  form.append('media_type', mediaType || 'IMAGE');
  if (file) form.append('file', file);
  return api.post('/social/posts/score-draft', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,  // Gemini multimodal can take 60-90s for video
  }).then(r => r.data);
};
export const getPendingSeoSuggestions = () =>
  api.get('/seo/suggestions/pending').then(r => r.data);
export const approveSeoSuggestion = (id, selectedFields = null) =>
  api.post(`/seo/suggestions/${id}/approve`, selectedFields, { params: {} })
    .then(r => r.data);
export const rejectSeoField = (id, field) =>
  api.post(`/seo/suggestions/${id}/reject-field`, null, { params: { field } })
    .then(r => r.data);

// ─── Social ───

export const getSocialOverview = () => api.get('/social/overview').then(r => r.data);
// Trigger NEW scoring (slow — Gemini takes ~15s/post). Returns existing + new in range.
export const scorePosts = (maxPosts = 4, startDate = null, endDate = null) =>
  api.get('/social/posts/scored', {
    params: { max_posts: maxPosts, start_date: startDate, end_date: endDate, score_new: true },
    timeout: 5 * 60 * 1000,
  }).then(r => r.data);

// Fast — fetch previously-scored posts only (for initial tab load + filter changes)
export const listSavedScoredPosts = (startDate = null, endDate = null) =>
  api.get('/social/posts/saved', {
    params: { start_date: startDate, end_date: endDate },
  }).then(r => r.data);

// ─── GEO ───

export const getGeoOverview = () => api.get('/geo/overview').then(r => r.data);

// ─── Controls ───

export const triggerOptimization = () => api.post('/trigger/optimize').then(r => r.data);
export const pauseCampaign = (platform, id) =>
  api.post(`/campaigns/${platform}/${id}/pause`).then(r => r.data);
export const enableCampaign = (platform, id) =>
  api.post(`/campaigns/${platform}/${id}/enable`).then(r => r.data);
export const updateBudget = (platform, id, budget) =>
  api.post(`/campaigns/${platform}/${id}/budget`, null, { params: { budget } }).then(r => r.data);

// ─── Learning / Self-Improvement ───

export const getLearningStats = () => api.get('/learning/stats').then(r => r.data);
export const getLearningHistory = (limit = 50) =>
  api.get('/learning/history', { params: { limit } }).then(r => r.data);

// ─── Action Approval ───

export const getPendingActions = () => api.get('/actions/pending').then(r => r.data);
export const approveAction = (id) => api.post(`/actions/${id}/approve`).then(r => r.data);
export const rejectAction = (id, reason = '') =>
  api.post(`/actions/${id}/reject`, null, { params: { reason } }).then(r => r.data);
export const approveAllActions = () => api.post('/actions/approve-all').then(r => r.data);

export default api;
