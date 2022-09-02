/**
 * Poll the given URL every 5 seconds and replace this component's innerHTML
 * with the result.
 */
export default (url) => ({
  init() {
    // Use an arrow function so that `this` is bound to the Alpine component.
    // If we use `function`, `this` will be bound to the function.
    setInterval(async () => {
      const resp = await fetch(url);
      const progress = await resp.text();
      this.$root.innerHTML = progress;
    }, 5000);
  }
});
