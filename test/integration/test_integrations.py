"""Integration tests with Playwright."""

from playwright.sync_api import Page, expect

TEST_INDEX_URL = "http://localhost:5000/"


def test_i18n_switching(page: Page) -> None:
    """Tests that users can switch the page language by clicking options in the i18n menu."""
    page.goto(TEST_INDEX_URL)

    expect(page.locator("header h1")).to_contain_text("A breakthrough Sanskrit library")

    page.locator("[name=i18n-menu]").get_by_role("link", name="संस्कृतम्").click()
    expect(page.locator("header h1")).to_contain_text("आधुनिकः संस्कृतग्रन्थालयः")

    page.locator("[name=i18n-menu]").get_by_role("link", name="हिन्दी").click()
    expect(page.locator("header h1")).to_contain_text("एक आधुनिक संस्कृत ग्रन्थालय")

    page.locator("[name=i18n-menu]").get_by_role("link", name="मराठी").click()
    expect(page.locator("header h1")).to_contain_text("एक चाकोरीबाहेरचे संस्कृत ग्रंथालय")

    page.locator("[name=i18n-menu]").get_by_role("link", name="తెలుగు").click()
    expect(page.locator("header h1")).to_contain_text("ఒక ఆధునిక సంస్కృత గ్రంథాలయము")


def test_basic_reader(page: Page) -> None:
    """Tests that we can use basic functions on the reader page."""

    page.goto(TEST_INDEX_URL)

    page.locator("#navbar").get_by_role("link", name="Texts").click()
    page.get_by_role("link", name="रामायणम्").click()
    page.get_by_role("link", name="१.१", exact=True).click()

    # Expand text in-place
    page.get_by_text("तपःस्वाध्यायनिरतं तपस्वी वाग्विदां वरम् ।").nth(1).click()

    # Click words for meaning
    page.get_by_text("तपः", exact=True).click()
    expect(page.get_by_text("त/पस् n. warmth, heat")).to_be_visible()
    page.get_by_text("स्वाध्याय", exact=True).click()
    expect(page.get_by_text("स्वाध्याय/ m. reciting or")).to_be_visible()
    page.get_by_text("निरतम्").click()
    expect(page.get_by_text("नि-√ रम् Ā. -रमते (aor. 3. pl")).to_be_visible()
    page.get_by_role("button", name="×").click()

    # Switch script, text size, view mode
    page.locator("#switch-sa").select_option("iast")
    page.get_by_text("tapaḥ", exact=True).click()
    page.get_by_role("combobox").first.select_option("md:text-2xl")
    page.get_by_role("combobox").first.select_option("md:text-lg")
    page.locator("#switch-parse-options").select_option("side-by-side")
    page.locator("#switch-parse-options").select_option("in-place")

    # Change pages
    page.get_by_role("link", name="»").click()
    page.get_by_role("heading", name="1.2").click()
    page.get_by_role("link", name="«").click()
    page.get_by_role("heading", name="1.1").click()


def test_dictionary_options(page: Page) -> None:
    """Tests that we can make dictionary queries against our production dictionaries.

    NOTE: this test expects that the site has all production dictionary data.
    """
    page.goto(TEST_INDEX_URL)

    page.locator("#navbar").get_by_role("link", name="Dictionaries").click()
    page.get_by_placeholder("राम, ರಾಮ, rāma, rAma,").click()
    page.get_by_placeholder("राम, ರಾಮ, rāma, rAma,").fill("rAma")
    page.get_by_placeholder("राम, ರಾಮ, rāma, rAma,").press("Enter")

    expect(page.get_by_text("राम mf(आ/)n. (prob. ‘causing")).to_be_visible()

    page.get_by_text("(choose dictionaries) ▼").click()
    page.get_by_label("Apte (1890)").check()
    page.get_by_label("Shabdasagara (1900)").check()
    page.get_by_label("Vācaspatyam (1873)").check()
    page.get_by_label("Śabdakalpadrumaḥ (1886)").check()
    page.get_by_label("Amarakosha").check()
    page.get_by_label("Apte Sanskrit-Hindi Kosh (").check()
    page.get_by_label("Shabdarthakaustubha").check()
    page.get_by_placeholder("राम, ರಾಮ, rāma, rAma,").click()

    # Collapse dictionaries
    expect(
        page.locator("header").filter(has_text="Monier-Williams Sanskrit-")
    ).to_be_visible()
    expect(
        page.locator("header").filter(has_text="Apte Practical Sanskrit-")
    ).to_be_visible()
    expect(
        page.locator("header").filter(has_text="Shabda-Sagara (1900) ▼")
    ).to_be_visible()
    expect(
        page.locator("header").filter(has_text="Vācaspatyam (1873) ▼")
    ).to_be_visible()
    expect(page.locator("header").filter(has_text="अमरकोशः ▼")).to_be_visible()
    expect(
        page.locator("header").filter(has_text="आप्टे संस्कृत-हिन्दी कोश (")
    ).to_be_visible()


# TODO: test that we can create a proofing project, upload a PDF, run OCR, and save changes
