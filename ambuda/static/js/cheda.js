const CHEDA_URL = "/api/vidyut/cheda"

export default () => ({
    input: null,
    output: null,

    init() {
        this.input = "बाह्योद्यानस्थितहरशिरश्चन्द्रिकाधौतहर्म्या";
        this.analyze();
    },
    async analyze() {
        console.log("analyze", this.input);

        const response = await fetch(CHEDA_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ input: this.input }),
        });
        this.output = await response.text();
    },
});
