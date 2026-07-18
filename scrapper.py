"""Scrapers used by the Flask job-search application.

Every scraper returns the same dictionary shape so the template does not need
to know which job board supplied a result.
"""

from dataclasses import dataclass, asdict
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36"
    )
}
TIMEOUT_SECONDS = 15
MAX_PAGES = 3


@dataclass
class Job:
    title: str
    company: str
    description: str
    date: str
    link: str
    source: str

    def to_dict(self):
        return asdict(self)


class BaseScraper:
    name = ""
    base_url = ""

    def get_soup(self, url):
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    @staticmethod
    def text(element):
        return element.get_text(" ", strip=True) if element else ""

    def job(self, *, title="", company="", description="", date="", link=""):
        return Job(
            title=title,
            company=company,
            description=description,
            date=date,
            link=urljoin(self.base_url, link),
            source=self.name,
        ).to_dict()


class BerlinStartupScraper(BaseScraper):
    """Existing Berlin Startup Jobs scraper, adapted for keyword searches."""

    name = "Berlin Startup Jobs"
    base_url = "https://berlinstartupjobs.com/"

    def parse_job(self, job):
        title_tag = job.select_one(".bjs-jlid__h a")
        company_tag = job.select_one(".bjs-jlid__b")
        desc_tag = job.select_one(".bjs-jlid__description")
        date_tag = job.select_one("time")
        return self.job(
            title=self.text(title_tag),
            company=self.text(company_tag),
            description=self.text(desc_tag),
            date=self.text(date_tag),
            link=title_tag.get("href", "") if title_tag else "",
        )

    def scrape(self, keyword):
        url = urljoin(self.base_url, f"skill-areas/{quote(keyword)}/")
        jobs = []
        for _ in range(MAX_PAGES):
            soup = self.get_soup(url)
            jobs.extend(self.parse_job(item) for item in soup.select("li.bjs-jlid"))
            next_page = soup.select_one("a.next.page-numbers[href]")
            if not next_page:
                break
            url = urljoin(self.base_url, next_page["href"])
        return jobs


class WeWorkRemotelyScraper(BaseScraper):
    name = "We Work Remotely"
    base_url = "https://weworkremotely.com/"

    def scrape(self, keyword):
        soup = self.get_soup(
            f"{self.base_url}remote-jobs/search?utf8=%E2%9C%93&term={quote(keyword)}"
        )
        jobs = []
        # Search results use the same job-row markup as the category pages.
        for item in soup.select("section.jobs li"):
            title_tag = item.select_one(".title")
            link_tag = item.select_one("a[href]")
            if not title_tag or not link_tag:
                continue
            title = self.text(title_tag)
            if not title:
                continue
            company = self.text(item.select_one(".company"))
            region = self.text(item.select_one(".region"))
            jobs.append(
                self.job(
                    title=title,
                    company=company,
                    description=region,
                    date=self.text(item.select_one("time")),
                    link=link_tag["href"],
                )
            )
        return jobs


class Web3CareerScraper(BaseScraper):
    name = "Web3 Career"
    base_url = "https://web3.career/"

    def scrape(self, keyword):
        soup = self.get_soup(f"{self.base_url}{quote(keyword)}-jobs")
        jobs = []
        # Job listings are table rows: position, company, posted, location,
        # salary and tags. Using cells keeps this resilient to cosmetic class
        # name changes on the site.
        for row in soup.select("table tbody tr"):
            cells = row.select("td")
            if len(cells) < 2:
                continue
            link_tag = cells[0].select_one("a[href]")
            title = self.text(cells[0])
            if not link_tag or not title:
                continue
            details = " · ".join(
                value
                for value in (self.text(cells[3]) if len(cells) > 3 else "",
                              self.text(cells[4]) if len(cells) > 4 else "")
                if value
            )
            jobs.append(
                self.job(
                    title=title,
                    company=self.text(cells[1]),
                    description=details,
                    date=self.text(cells[2]) if len(cells) > 2 else "",
                    link=link_tag["href"],
                )
            )
        return jobs


SCRAPERS = (BerlinStartupScraper(), WeWorkRemotelyScraper(), Web3CareerScraper())


def search_jobs(keyword):
    """Return results and source-specific errors without failing the page."""
    results = {}
    errors = {}
    for scraper in SCRAPERS:
        try:
            results[scraper.name] = scraper.scrape(keyword)
        except requests.RequestException:
            results[scraper.name] = []
            errors[scraper.name] = "현재 이 사이트의 결과를 가져올 수 없습니다."
    return results, errors
