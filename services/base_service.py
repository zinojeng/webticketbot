"""
This module is base service using Selenium for web/Docker deployment
"""
from __future__ import annotations
import os
import logging
from configs.config import fields, user_agent

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class BaseService(object):
    """
    BaseService using Selenium WebDriver
    """

    def __init__(self, args):
        self.logger = args.log
        self.cookies = {}
        self.config = args.config
        self.service = args.service
        self.fields = fields[self.service]

        self.locale = args.locale
        self.auto = args.auto
        self.list = args.list

        # Initialize Selenium WebDriver
        self.driver = self._init_driver()
        self.logger.info("Selenium WebDriver initialized")

    def _init_driver(self):
        """Initialize Chrome WebDriver with appropriate settings"""
        chrome_options = Options()

        # Headless mode for Docker/server deployment
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')

        # Docker-specific settings
        chrome_options.add_argument('--no-zygote')
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--disable-setuid-sandbox')

        # User agent
        chrome_options.add_argument(f'--user-agent={user_agent}')

        # Disable automation detection
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Check for custom Chrome binary path (for Docker)
        chrome_binary = os.environ.get('CHROME_BIN')
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            self.logger.info(f"Using Chrome binary: {chrome_binary}")

        # Check for custom ChromeDriver path
        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')

        try:
            if chromedriver_path:
                self.logger.info(f"Using ChromeDriver: {chromedriver_path}")
                service = Service(chromedriver_path)
            else:
                # Use webdriver-manager to auto-download
                self.logger.info("Auto-downloading ChromeDriver...")
                service = Service(ChromeDriverManager().install())

            driver = webdriver.Chrome(service=service, options=chrome_options)

            # Set page load timeout
            driver.set_page_load_timeout(120)
            driver.implicitly_wait(10)

            return driver

        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome WebDriver: {e}")
            raise

    def __del__(self):
        """Close Selenium WebDriver"""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
                self.logger.info("WebDriver closed")
            except Exception:
                pass
