import asyncio
import logging
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

from playwright import async_api

from capture_webpage import Config, EmailConfig, SiteConfig

email_server: smtplib.SMTP_SSL | smtplib.SMTP = None
email_config: EmailConfig = EmailConfig.load(Path(__file__).parent / "config_email.yml")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _load_email_server() -> smtplib.SMTP_SSL | smtplib.SMTP:
    global email_server
    if email_server:
        return email_server

    if email_config.has_ssl:
        email_server = smtplib.SMTP_SSL(email_config.host, email_config.port or 0)
    else:
        email_server = smtplib.SMTP(email_config.host, email_config.port or 0)

    email_server.login(email_config.username, email_config.password)
    return email_server


def send_email(to: str, subject: str, contents: str) -> None:
    if sys.platform == "win32":
        logger.debug("Should have sent this email:")
        logger.debug("To: %s", to)
        logger.debug("Subject: %s", subject)
        logger.debug("Contents: %s", contents)
        return

    cfg = EmailConfig.load("config_email.yml")

    msg = EmailMessage()
    msg.set_content(contents)

    msg['Subject'] = subject
    msg['From'] = cfg.sender
    msg['To'] = to
    email_server.send_message(msg)


async def worker(task_queue, browser):
    try:
        while True:
            site_config: SiteConfig = await task_queue.get()
            if site_config is None:
                # None is used to signal the worker to exit
                break

            last_text = site_config.last_text or ""

            page = await browser.new_page()
            await page.goto(site_config.url, wait_until='load')
            try:
                # html = await page.inner_html('body')
                new_text = await page.locator(site_config.css).inner_text(timeout=5_000)

                if new_text.lower() != last_text.lower():
                    send_email(site_config.email, f"New page content for '{site_config.unique_name}'", f"Old content: {last_text}\n\nNew content: {new_text}")

            except async_api.TimeoutError:
                send_email(site_config.email, "Error: timeout", f"A timeout occured while trying to find {site_config.css} on {site_config.url}.")

            await page.close()

            task_queue.task_done()
    except BaseException as ex:
        logger.error("ERROR IN TASK: %s", ex)

async def run_tasks(task_queue, browser, num_workers):
    # Signal workers to exit
    for _ in range(num_workers):
        task_queue.put_nowait(None)

    workers = [asyncio.create_task(worker(task_queue, browser)) for _ in range(num_workers)]

    # Wait for all tasks to be processed
    await task_queue.join()

    # Wait for workers to finish
    await asyncio.gather(*workers)


async def main(num_workers: int = 4) -> None:
    task_queue = asyncio.Queue()

    async with async_api.async_playwright() as pw:
        cfg = Config.load("config_sites.yml")

        for site_config in cfg.sites.values():
            task_queue.put_nowait(site_config)

        browser = await pw.chromium.launch(headless=True)

        await run_tasks(task_queue, browser, num_workers)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
