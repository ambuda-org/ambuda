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
};
