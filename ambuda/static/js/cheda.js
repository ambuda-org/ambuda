export default () => ({
    input: null,

    init() {
        console.log("init");
    },
    analyze() {
        console.log("analyze", this.input);
    },
});
