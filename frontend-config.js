// Simple frontend config loader for static pages
// Priority order: URL ?api=..., localStorage MUNBON_API_BASE, default
(function () {
  function getQueryParam(name) {
    const m = new RegExp('(?:[?&])' + name + '=([^&]+)').exec(window.location.search);
    return m && decodeURIComponent(m[1]);
  }

  const fromUrl = getQueryParam('api');
  if (fromUrl) {
    try {
      localStorage.setItem('MUNBON_API_BASE', fromUrl);
    } catch (_) {}
  }

  const stored = (function () {
    try { return localStorage.getItem('MUNBON_API_BASE'); } catch (_) { return null; }
  })();

  const defaultBase = 'http://localhost:3001/api/v1';
  const apiBase = fromUrl || stored || defaultBase;
  window.API_BASE = apiBase;
})();

