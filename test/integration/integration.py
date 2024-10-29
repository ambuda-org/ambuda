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


# TODO: test that we can load a text page and click for translations
# TODO: test that we can create a proofing project, upload a PDF, run OCR, and save changes
