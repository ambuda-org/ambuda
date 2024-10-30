"""Integration tests with Playwright.

NOTE: these tests currently assume an initialized development database with
admins, etc. In the future, our test code will create a custom test database.
"""

import tempfile
from pathlib import Path

import fitz
from playwright.sync_api import Page, expect

TEST_INDEX_URL = "http://localhost:5000/"
ADMIN_USERNAME = "adhiraja"
ADMIN_PASSWORD = "password12345"


def _create_sample_pdf(output_path: str, num_pages: int):
    """Create a toy PDF with 10 pages."""
    doc = fitz.open()
    for i in range(1, num_pages + 1):
        page = doc.new_page()
        where = fitz.Point(50, 50)
        page.insert_text(where, f"This is page {i}", fontsize=30)
    doc.save(output_path)


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


def test_basic_reader_ui(page: Page) -> None:
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


def test_basic_dictionary_ui(page: Page) -> None:
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


def test_basic_proofing_ui(page: Page) -> None:
    """Tests that we can use basic functions on the proofing page.

    If the test fails:
    - Confirm that Celery is running.
    - Confirm that `My sample book` doesn't exist.
    """

    page.goto(TEST_INDEX_URL)

    # Log in as admin. Admin should have the `p2` role.
    # (./cli.py add-role --username $ADMIN --role p2)
    page.locator("#navbar").get_by_role("link", name="Proofing").click()
    page.locator("#navbar").get_by_role("link", name="Sign in").click()
    page.get_by_label("Username").click()
    page.get_by_label("Username").fill(ADMIN_USERNAME)
    page.get_by_label("Password").click()
    page.get_by_label("Password").fill(ADMIN_PASSWORD)
    page.get_by_role("button", name="Sign in").click()

    # Upload project to celery.
    page.get_by_role("link", name="Create project").click()
    page.get_by_label("From my computer").check()


    with page.expect_file_chooser() as fc:
        page.locator("#local_file").click()

    f = tempfile.NamedTemporaryFile(suffix=".pdf")
    _create_sample_pdf(f.name, num_pages=10)
    fc.value.set_files(f.name)

    page.get_by_placeholder("My book title").click()
    page.get_by_placeholder("My book title").fill("My sample book")
    page.get_by_label("Public domain").check()
    page.get_by_role("button", name="Create project").click()

    # Waiting ...

    # Project ready. Move to project page ...
    page.get_by_role("link", name="Click here").click()

    page.get_by_role("link", name="Activity").click()
    page.get_by_role("link", name="Edit", exact=True).click()
    page.get_by_role("link", name="Download").click()
    page.get_by_role("link", name="Stats").click()

    # TODO: add more interesting logic here.

    # Delete project.
    page.get_by_role("link", name="Admin").click()
    page.locator("#slug").click()
    page.locator("#slug").fill("my-sample-book")
    page.get_by_role("button", name="Permanently delete this").click()
