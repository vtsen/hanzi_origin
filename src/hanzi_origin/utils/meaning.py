import re
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.add_argument("--headless")


def fetch_ziyi(char: str) -> tuple[str, str]:
    """
    Fetch raw 'ziyi' text for a single Chinese character from ccamc.org.
    Returns the full text exactly as presented (no splitting).
    """
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)  # seconds
    driver.get(f"http://ccamc.org/cjkv.php?cjkv={char}")

    # Wait for page to fully load if needed
    driver.implicitly_wait(5 + random.randint(0, 3))

    soup = BeautifulSoup(driver.page_source, "html.parser")

    return get_initial_meaning(soup), get_contemporary_meanings(soup)


def matches_numbered_parenthesis(text: str) -> bool:
    """
    Returns True if the input string starts with a number '1.', optional spaces,
    followed by a full-width parenthesis '（...）', otherwise False.
    """
    pattern = r'^\s*1\.\s*（.*）\s*$'
    return bool(re.match(pattern, text, re.S))


def get_initial_meaning(soup: BeautifulSoup) -> str:
    start_tag = soup.find(lambda tag: tag.name == "p" and tag.get_text().strip() == "详细字义")
    end_tag = soup.find(lambda tag: tag.name == "p" and tag.get_text().strip().startswith("2."))

    initial_meaning = ""
    for tag in start_tag.find_all_next("p"):
        if tag == end_tag:
            break
        text = tag.get_text(strip=True)
        if matches_numbered_parenthesis(text):
            initial_meaning = text[2:]
            break

    return initial_meaning


def get_contemporary_meanings(soup: BeautifulSoup) -> str:
    start_tag = soup.find(lambda tag: tag.name == "p" and tag.get_text().strip() == "基本字义")
    end_tag = soup.find(lambda tag: tag.name == "p" and tag.get_text().strip() == "汉英互译")

    entries = []
    for tag in start_tag.find_all_next("p"):
        if tag == end_tag:
            break
        entries.append(tag.get_text(strip=True))

    return "\n".join(entries)


if __name__ == "__main__":
    print(fetch_ziyi("上"))
