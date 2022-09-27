export default {
  ajaxDictionaryQuery: (version, query) => `/api/dictionaries/${version}/${query}`,
  dictionaryQuery: (version, query) => `/tools/dictionaries/${version}/${query}`,
  parseData: (textSlug, blockSlug) => `/api/parses/${textSlug}/${blockSlug}`,

  // TODO: where to put this?
  getTextSlug: () => {
    const { pathname } = window.location;
    const suffix = pathname.replace('/texts/', '');
    const slug = suffix.split('/')[0];
    return slug;
  },

  parseDictionaryURL: () => {
    const { pathname } = window.location;

    const prefix = '/tools/dictionaries/';
    const segments = pathname.split('/');
    // segments: "", "tools", "dictionaries", "<source>", "<query>"
    if (pathname.startsWith(prefix) && segments.length === 5) {
      return {
        source: segments[3],
        query: segments[4],
      };
    }
    return {
      source: null,
      query: null,
    };
  },
};
