/* Shared small Markdown subset. Parse source tokens once; never reparse generated HTML. */
(function () {
  'use strict';
  function escape(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
    })[char]);
  }
  function link(label, href) {
    try {
      const url = new URL(href, location.href);
      if (!['http:', 'https:'].includes(url.protocol)) return escape(label);
      return `<a href="${escape(href)}" target="_blank" rel="noopener noreferrer">${escape(label)}</a>`;
    } catch (_) { return escape(label); }
  }
  function inline(value, depth = 0) {
    const source = String(value ?? '');
    if (depth > 3) return escape(source);
    const tokens = /`([^`\n]+)`|\[([^\]\n]+)\]\(([^)\s]+)\)|(https?:\/\/[^\s<）]+)|\*\*([^*]+)\*\*|\{(Q\d+(?:[–\-、,\s]*Q?\d*)*|new)\}|：(current|needs-review|stale|superseded)\b/g;
    let html = '', start = 0;
    for (const match of source.matchAll(tokens)) {
      html += escape(source.slice(start, match.index));
      if (match[1] !== undefined) html += '<code>' + escape(match[1]) + '</code>';
      else if (match[2] !== undefined) html += link(match[2], match[3]);
      else if (match[4] !== undefined) html += link(match[4], match[4]);
      else if (match[5] !== undefined) html += '<b>' + inline(match[5], depth + 1) + '</b>';
      else if (match[6] !== undefined) html += '<span class="qtag">' + escape(match[6]) + '</span>';
      else html += `：<span class="st st-${match[7]}">${match[7]}</span>`;
      start = match.index + match[0].length;
    }
    return html + escape(source.slice(start));
  }
  window.ResearchMarkdown = Object.freeze({escape, inline});
})();
