/**
 * Poll the given URL every 5 seconds and replace this component's innerHTML
 * with the result.
 *
 * Stops polling once the response contains an element with [data-poll-final],
 * which the partial template should set on terminal states (SUCCESS, FAILURE).
 * This prevents the periodic refresh from collapsing user-expanded UI.
 */
export default (url) => ({
  intervalId: null,
  init() {
    if (this._isFinal()) return;
    this.intervalId = setInterval(async () => {
      const resp = await fetch(url);
      const progress = await resp.text();
      this.$root.innerHTML = progress;
      if (this._isFinal()) {
        clearInterval(this.intervalId);
        this.intervalId = null;
      }
    }, 5000);
  },
  _isFinal() {
    return this.$root.querySelector('[data-poll-final]') !== null;
  },
});
