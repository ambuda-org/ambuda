/**
 * Converts variables to URLs, and occasionally vice-versa.
 */
export default {
  ajaxDictionaryQuery: (sources, query) => {
    const sourcesStr = sources.join(',');
    return `/api/dictionaries/${sourcesStr}/${query}`;
  },

  dictionaryQuery: (sources, query) => {
    const sourcesStr = sources.join(',');
    return `/tools/dictionaries/${sourcesStr}/${query}`;
  },

  parseData: (textSlug, blockSlug) => `/api/parses/${textSlug}/${blockSlug}`,

  // TODO: where to put this?
  getTextSlug: () => {
    const { pathname } = window.location;
    const suffix = pathname.replace('/texts/', '');
    const slug = suffix.split('/')[0];
    return slug;
  },

  /**
   * Parse a dictionary URL for its source and query. We use this data to
   * initialize our form fields from the URL state.
   */
  parseDictionaryURL: () => {
    const { pathname } = window.location;

    const prefix = '/tools/dictionaries/';
    const segments = pathname.split('/');
    // segments: "", "tools", "dictionaries", "<source>", "<query>"
    if (pathname.startsWith(prefix) && segments.length === 5) {
      return {
        sources: segments[3].split(','),
        query: segments[4],
      };
    }
    return {
      sources: null,
      query: null,
    };
  },
};
