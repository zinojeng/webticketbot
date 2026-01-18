"""
This module is to buy tickets from THSRC using Selenium (Web/Docker version)
"""

from __future__ import annotations
import base64
import os
import random
import re
import sys
import time
from datetime import date, datetime, timedelta
from bs4 import BeautifulSoup
import pyperclip
from services.base_service import BaseService
from configs.config import user_agent
from utils.validate import check_roc_id, check_tax_id
from utils.captcha_ocr import CaptchaOCR

# Selenium imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import httpx


class THSRC(BaseService):
    """
    Service code for THSRC (https://irs.thsrc.com.tw/IMINT/) using Selenium
    """

    def __init__(self, args):
        super().__init__(args)
        self.start_station = self.select_station(
            'start', default_value=self.config['station']['Taipei'])
        self.dest_station = self.select_station(
            'dest', default_value=self.config['station']['Zuouing'])
        self.outbound_date = self.select_date()
        self.outbound_time = self.select_time(outbound_date=self.outbound_date)
        self.ticket_num = self.select_ticket_num()
        self.car_type = self.select_car_type()
        self.preferred_seat = self.select_preferred_seat()

        # Initialize dual OCR system (holey.cc + Gemini Vision)
        self.captcha_ocr = CaptchaOCR(self.config['api'].get('captcha_ocr'))

    def print_error_message(self, html_page):
        """Print error message"""
        if isinstance(html_page, str):
            page = BeautifulSoup(html_page, 'html.parser')
        else:
            page = html_page
        error_messages = []
        for error_text in page.find_all(class_='feedbackPanelERROR'):
            error_message = error_text.text.strip()
            self.logger.error('Error: %s', error_message)
            error_messages.append(error_message)
            if '選擇的日期超過目前開放預訂之日期' in error_message:
                self.logger.error("Date exceeds bookable range, please modify user_config.toml")
                sys.exit(1)
        return error_messages

    def get_station(self, station_name):
        """Get station value"""
        station_name = station_name.strip().lower().capitalize()

        station_translation = {
            '南港': 'Nangang',
            '台北': 'Taipei',
            '板橋': 'Banqiao',
            '桃園': 'Taoyuan',
            '新竹': 'Hsinchu',
            '苗栗': 'Miaoli',
            '台中': 'Taichung',
            '彰化': 'Changhua',
            '雲林': 'Yunlin',
            '嘉義': 'Chiayi',
            '台南': 'Tainan',
            '左營': 'Zuouing',
        }

        if not re.search(r'[a-zA-Z]+', station_name):
            station_name = station_translation.get(
                station_name.replace('臺', '台'))

        if self.config['station'].get(station_name):
            return self.config['station'].get(station_name)

        self.logger.error('Station not found: %s', station_name)
        sys.exit(1)

    def select_station(self, travel_type: str, default_value: int) -> int:
        """Select start/dest station"""
        if not self.fields[f'{travel_type}-station']:
            self.logger.info(f"\nSelect {travel_type} station:")
            for station_name in self.config['station']:
                self.logger.info(
                    '%s: %s', self.config['station'][station_name], station_name)
            input_value = input(
                f"{travel_type} station (default: {default_value}): ").strip()
            return default_value if input_value == '' or not input_value.isdigit() else int(input_value)
        else:
            return self.get_station(self.fields[f'{travel_type}-station'])

    def select_date(self) -> str:
        """Select date"""
        today = str(date.today())
        if not self.fields['outbound-date']:
            input_value = input(f"\nSelect outbound date (default: {today}): ")
            return input_value.replace('-', '/') or today.replace('-', '/')
        else:
            return self.fields['outbound-date'].replace('-', '/')

    def select_time(self, outbound_date: str, default_value: int = 10) -> str:
        """Select time"""
        if self.fields['inbound-time'] and datetime.strptime(self.fields['inbound-time'], '%H:%M').time() <= datetime.strptime(self.fields['outbound-time'], '%H:%M').time():
            self.logger.error("\nInbound time must be later than outbound time!")
            sys.exit(1)

        if not self.fields['outbound-time']:
            self.logger.info('\nSelect outbound time:')
            for idx, t_str in enumerate(self.config['available-timetable'], start=1):
                t_int = int(t_str[:-1])
                if t_str[-1] == "A" and (t_int // 100) == 12:
                    t_int = f"{(t_int % 1200):04d}"
                elif t_int != 1230 and t_str[-1] == "P":
                    t_int += 1200

                t_str_display = str(t_int).zfill(4)
                if t_str_display == '0001':
                    t_str_display = '0000'

                date_time_str = f'{outbound_date} {t_str_display[:-2]}:{t_str_display[-2:]}'

                if datetime.now().timestamp() <= datetime.strptime(
                        date_time_str, "%Y/%m/%d %H:%M").timestamp():
                    self.logger.info(f'{idx}. {date_time_str}')
                else:
                    if idx == default_value:
                        default_value += 1

            index = input(f'outbound time (default: {default_value}): ')
            if index == '' or not index.isdigit():
                index = default_value
            else:
                index = int(index)
                if index < 1 or index > len(self.config['available-timetable']):
                    index = default_value
            return self.config['available-timetable'][index-1]
        else:
            t_int = int(self.fields['outbound-time'].replace(':', ''))
            if t_int % 100 >= 30:
                t_int = int(t_int/100)*100 + 30
            else:
                t_int = int(t_int/100)*100

            if t_int == 0:
                t_str = '1201A'
            elif t_int == 30:
                t_str = '1230A'
            elif t_int == 1200:
                t_str = '1200N'
            elif t_int == 1230:
                t_str = '1230P'
            elif t_int < 1200:
                t_str = f'{t_int}A'
            else:
                t_str = f'{t_int-1200}P'

            return t_str

    def select_ticket_num(self, default_value: int = 1) -> list:
        """Select ticket number"""
        total = 0
        tickets = list()
        ticket_types = ['adult', 'child', 'disabled', 'elder', 'college', 'teenager']

        for ticket in ticket_types:
            if ticket in self.fields['ticket']:
                ticket_num = int(self.fields['ticket'][ticket])
                total += ticket_num
                if ticket_num >= 0:
                    tickets.append(
                        f"{ticket_num}{self.config['ticket-type'][ticket]}")
                else:
                    tickets.append('')
            else:
                tickets.append(f"0{self.config['ticket-type'].get(ticket, 'T')}")

        if total > self.config['max-ticket-num']:
            self.logger.error(
                "\nYou can only order a maximum of %s tickets!", self.config['max-ticket-num'])
            sys.exit()
        elif total == 0:
            tickets = [
                f"{default_value}{self.config['ticket-type']['adult']}", '0H', '0W', '0E', '0P', '0T']
        return tickets

    def select_car_type(self, default_value: int = 0) -> str:
        """Select class"""
        car_type = self.config['car-type'].get(self.fields['car-type'])
        if not car_type:
            car_type = default_value
        return car_type

    def select_preferred_seat(self, default_value: int = 0) -> str:
        """Select preferred seat"""
        preferred_seat = self.config['preferred-seat'].get(
            self.fields['preferred-seat'])
        if not preferred_seat:
            preferred_seat = default_value
        return preferred_seat

    def get_security_code(self, captcha_img_element):
        """OCR captcha using dual system (holey.cc + Gemini Vision)"""
        try:
            # Method 1: Try to get image directly from Selenium screenshot (most reliable)
            try:
                image_data = captcha_img_element.screenshot_as_png
                self.logger.info("Got captcha via Selenium screenshot")
            except Exception as screenshot_err:
                self.logger.warning(f"Screenshot failed: {screenshot_err}, trying src attribute...")

                # Method 2: Fallback to src attribute
                captcha_src = captcha_img_element.get_attribute('src')

                if captcha_src.startswith('data:'):
                    # Data URL - extract base64 directly
                    base64_str = captcha_src.split(',')[1]
                    image_data = base64.b64decode(base64_str)
                else:
                    # External URL - use Selenium's execute_script to get image as base64
                    # This uses the browser's session/cookies
                    script = """
                    var img = arguments[0];
                    var canvas = document.createElement('canvas');
                    canvas.width = img.naturalWidth;
                    canvas.height = img.naturalHeight;
                    var ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0);
                    return canvas.toDataURL('image/png').split(',')[1];
                    """
                    base64_str = self.driver.execute_script(script, captcha_img_element)
                    image_data = base64.b64decode(base64_str)

            # Use dual OCR system (Gemini Vision first, holey.cc fallback)
            security_code = self.captcha_ocr.recognize(image_data, use_gemini_first=True)

            if security_code:
                self.logger.info("+ Security code: %s", security_code)
                return security_code
            else:
                self.logger.warning("All OCR methods failed")
                return None

        except Exception as e:
            self.logger.warning(f"Captcha OCR error: {e}")
            return None

    def load_booking_page(self, max_retries=3):
        """Load the booking page and return captcha element"""
        self.logger.info("\nLoading...")

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(f"Connecting to THSRC website... (attempt {attempt}/{max_retries})")
                self.driver.get(self.config['page']['reservation'])

                # Wait for captcha image to load
                wait = WebDriverWait(self.driver, 30)
                captcha_img = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'img.captcha-img'))
                )
                self.logger.info("Page loaded successfully")
                return captcha_img

            except TimeoutException:
                self.logger.warning(f"Timeout on attempt {attempt}, retrying...")
                if attempt < max_retries:
                    time.sleep(2)
            except Exception as e:
                self.logger.warning(f"Connection failed: {e}")
                if attempt < max_retries:
                    wait_time = attempt * 3
                    self.logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)

        self.logger.error("Failed to connect after multiple retries")
        sys.exit(1)

    def update_captcha(self):
        """Click refresh captcha and get new captcha element"""
        self.logger.info("Updating captcha")
        try:
            # Try multiple selectors for the refresh captcha link
            refresh_selectors = [
                'a[id*="reCodeLink"]',
                'a[id*="reCaptcha"]',
                'a.captcha-refresh',
                'a[onclick*="captcha"]',
                '.captcha-box a',
                'a[href*="captcha"]',
            ]

            refresh_link = None
            for selector in refresh_selectors:
                try:
                    refresh_link = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if refresh_link:
                        self.logger.info(f"Found refresh link with selector: {selector}")
                        break
                except:
                    continue

            if refresh_link:
                self.driver.execute_script("arguments[0].click();", refresh_link)
                time.sleep(1.5)  # Wait for new captcha to load
            else:
                # If no refresh link found, try clicking on the captcha image itself
                self.logger.info("No refresh link found, trying to click captcha image...")
                captcha_img = self.driver.find_element(By.CSS_SELECTOR, 'img.captcha-img')
                self.driver.execute_script("arguments[0].click();", captcha_img)
                time.sleep(1.5)

            # Get new captcha image
            captcha_img = self.driver.find_element(By.CSS_SELECTOR, 'img.captcha-img')
            return captcha_img
        except Exception as e:
            self.logger.error(f"Failed to update captcha: {e}")
            return None

    def fill_booking_form(self, security_code):
        """Fill the booking form using Selenium"""
        try:
            self.logger.info("Filling booking form...")

            # First, dismiss any overlay/popup that might block interactions
            # THSRC website has a "mTop" div that can intercept clicks
            self._dismiss_overlays()

            # Scroll to the form area to ensure visibility
            try:
                form_element = self.driver.find_element(By.CSS_SELECTOR, 'form')
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'start'});", form_element)
                time.sleep(0.3)
            except Exception as scroll_err:
                self.logger.warning(f"Could not scroll to form: {scroll_err}")

            # Select booking method (time search or train number search)
            # Local version uses: radio31 (time search), radio33 (train number search)
            self.logger.info("Selecting booking method...")
            if self.fields['train-no']:
                # Train number search - find radio by value 'radio33'
                train_no_radio = self.driver.find_element(By.CSS_SELECTOR, 'input[name="bookingMethod"][value="radio33"]')
                self.driver.execute_script("arguments[0].click();", train_no_radio)
                train_no_input = self.driver.find_element(By.NAME, 'toTrainIDInputField')
                train_no_input.clear()
                train_no_input.send_keys(self.fields['train-no'].strip())
            else:
                # Time search (default) - find radio by value 'radio31'
                time_radio = self.driver.find_element(By.CSS_SELECTOR, 'input[name="bookingMethod"][value="radio31"]')
                self.driver.execute_script("arguments[0].click();", time_radio)

            # Select start station (use JavaScript to set value directly)
            self.logger.info(f"Setting start station: {self.start_station}")
            start_station_select = self.driver.find_element(By.NAME, 'selectStartStation')
            self.driver.execute_script(
                "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
                start_station_select, str(self.start_station)
            )

            # Select destination station
            self.logger.info(f"Setting destination station: {self.dest_station}")
            dest_station_select = self.driver.find_element(By.NAME, 'selectDestinationStation')
            self.driver.execute_script(
                "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
                dest_station_select, str(self.dest_station)
            )

            # Set outbound date
            self.logger.info(f"Setting outbound date: {self.outbound_date}")
            date_input = self.driver.find_element(By.NAME, 'toTimeInputField')
            self.driver.execute_script("arguments[0].value = arguments[1]", date_input, self.outbound_date)

            # Select outbound time (if not using train number)
            if not self.fields['train-no']:
                self.logger.info(f"Setting outbound time: {self.outbound_time}")
                time_select = self.driver.find_element(By.NAME, 'toTimeTable')
                self.driver.execute_script(
                    "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
                    time_select, self.outbound_time
                )

            # Select car type (use JavaScript click)
            car_type_radios = self.driver.find_elements(By.NAME, 'trainCon:trainRadioGroup')
            if len(car_type_radios) > self.car_type:
                self.driver.execute_script("arguments[0].click();", car_type_radios[self.car_type])

            # Select preferred seat (use JavaScript click)
            seat_radios = self.driver.find_elements(By.NAME, 'seatCon:seatRadioGroup')
            if len(seat_radios) > self.preferred_seat:
                self.driver.execute_script("arguments[0].click();", seat_radios[self.preferred_seat])

            # Set ticket quantities
            ticket_selects = [
                ('ticketPanel:rows:0:ticketAmount', self.ticket_num[0]),  # Adult
                ('ticketPanel:rows:1:ticketAmount', self.ticket_num[1]),  # Child
                ('ticketPanel:rows:2:ticketAmount', self.ticket_num[2]),  # Disabled
                ('ticketPanel:rows:3:ticketAmount', self.ticket_num[3]),  # Elder
                ('ticketPanel:rows:4:ticketAmount', self.ticket_num[4]),  # College
                ('ticketPanel:rows:5:ticketAmount', self.ticket_num[5]),  # Teenager
            ]

            for select_name, value in ticket_selects:
                try:
                    ticket_select = self.driver.find_element(By.NAME, select_name)
                    self.driver.execute_script(
                        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
                        ticket_select, value
                    )
                except NoSuchElementException:
                    pass  # Some ticket types may not exist

            # Enter security code
            self.logger.info("Entering security code...")
            security_input = self.driver.find_element(By.NAME, 'homeCaptcha:securityCode')
            security_input.clear()
            security_input.send_keys(security_code)

            # Click submit button using JavaScript
            self.logger.info("Clicking submit button...")
            submit_btn = self.driver.find_element(By.NAME, 'SubmitButton')
            self.driver.execute_script("arguments[0].click();", submit_btn)

            # Wait for page to load
            self.logger.info("Waiting for response...")
            time.sleep(2)

            self.logger.info("Form submitted successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to fill booking form: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _dismiss_overlays(self):
        """Dismiss any overlay/popup elements that might block interactions"""
        try:
            # Hide or remove common overlay elements
            overlay_selectors = [
                '.mTop',           # THSRC top banner
                '.cookie-banner',  # Cookie consent
                '.modal-backdrop', # Bootstrap modal
                '.overlay',        # Generic overlay
                '#mask',           # Common mask element
            ]

            for selector in overlay_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        # Try to hide the overlay using JavaScript
                        self.driver.execute_script(
                            "arguments[0].style.display = 'none'; arguments[0].style.visibility = 'hidden';",
                            el
                        )
                        self.logger.info(f"Dismissed overlay: {selector}")
                except:
                    pass

            # Also try to click any close buttons
            close_selectors = [
                '.close', '.btn-close', '[aria-label="Close"]',
                '.modal-close', '.dismiss', '.cookie-close'
            ]

            for selector in close_selectors:
                try:
                    close_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if close_btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", close_btn)
                        self.logger.info(f"Clicked close button: {selector}")
                        time.sleep(0.3)
                except:
                    pass

        except Exception as e:
            self.logger.debug(f"Error dismissing overlays: {e}")

    def check_booking_result(self):
        """Check if booking form submission was successful"""
        page_source = self.driver.page_source
        page = BeautifulSoup(page_source, 'html.parser')

        # Check for errors
        errors = self.print_error_message(page)
        if errors:
            return False, errors, page

        # Check if we're on the train selection page
        if 'TrainQueryDataViewPanel' in page_source:
            return True, None, page

        return False, ['Unknown error'], page

    def confirm_train(self, default_value: int = 1):
        """2. Confirm train selection"""
        page_source = self.driver.page_source
        page = BeautifulSoup(page_source, 'html.parser')

        trains = []
        has_discount = False

        for train in page.find_all('input', {'name': 'TrainQueryDataViewPanel:TrainGroup'}):
            if not self.fields['inbound-time'] or datetime.strptime(train['queryarrival'], '%H:%M').time() <= datetime.strptime(self.fields['inbound-time'], '%H:%M').time():
                duration = train.parent.findNext('div').find('div', class_='duration').text.replace(
                    '\n', '').replace('schedule', '').replace('directions_railway', '').split('|')
                schedule = duration[0]
                train_no = duration[1] if len(duration) > 1 else ''
                discount = train.parent.findNext('div').find(
                    'div', class_='discount').text.replace('\n', '')
                if discount:
                    has_discount = True

                trains.append({
                    'departure_time': train['querydeparture'],
                    'arrival_time': train['queryarrival'],
                    'duration': schedule,
                    'discount': discount,
                    'no': train_no,
                    'value': train['value']
                })

        if not trains:
            if self.fields['inbound-time']:
                self.logger.info(
                    '\nNo trains left on %s before %s, please select different outbound time!', self.outbound_date, self.fields['inbound-time'])
            else:
                self.logger.info(
                    '\nNo trains left on %s, please select another day!', self.outbound_date)
            sys.exit(0)

        self.logger.info('\nSelect train:')
        for idx, train in enumerate(trains, start=1):
            self.logger.info(
                f"{idx}. {train['departure_time']} -> {train['arrival_time']} ({train['duration']}) | {train['no']}\t{train['discount']}")

        if self.list:
            return None

        if self.auto:
            if has_discount:
                trains = list(filter(lambda train: train['discount'], trains)) or trains
            if self.fields['inbound-time']:
                trains = list(filter(lambda train: datetime.strptime(self.fields['inbound-time'], '%H:%M') < datetime.strptime(
                    train['arrival_time'], '%H:%M') + timedelta(minutes=20), trains)) or trains

            trains = [min(trains, key=lambda train: datetime.strptime(
                train['duration'], '%H:%M').time())]
            self.logger.info(
                f"\nAuto pick train: {trains[0]['departure_time']} -> {trains[0]['arrival_time']} ({trains[0]['duration']}) | {trains[0]['no']}\t{trains[0]['discount']}")
            selected_opt = 0
        else:
            selected_opt = int(
                input(f'train (default: {default_value}): ') or default_value) - 1

        # Select the train using Selenium
        try:
            train_radios = self.driver.find_elements(By.NAME, 'TrainQueryDataViewPanel:TrainGroup')
            if train_radios and len(train_radios) > selected_opt:
                train_radios[selected_opt].click()

            # Click confirm button
            submit_btn = self.driver.find_element(By.NAME, 'SubmitButton')
            submit_btn.click()
            time.sleep(2)

            return True
        except Exception as e:
            self.logger.error(f"Failed to confirm train: {e}")
            return False

    def confirm_ticket(self):
        """3. Confirm ticket and fill passenger info"""
        dummy_id = self.fields['id']
        if not dummy_id:
            dummy_id = input("\nInput id: ")

        try:
            # Fill ID number
            id_input = self.driver.find_element(By.NAME, 'dummyId')
            id_input.clear()
            id_input.send_keys(dummy_id)

            # Fill phone number
            phone_input = self.driver.find_element(By.NAME, 'dummyPhone')
            phone_input.clear()
            phone_input.send_keys(self.fields['phone'])

            # Fill email
            email_input = self.driver.find_element(By.NAME, 'email')
            email_input.clear()
            email_input.send_keys(self.fields['email'])

            # Handle TGO membership
            if self.fields['tgo-id']:
                try:
                    tgo_radio = self.driver.find_element(
                        By.XPATH, "//input[@name='TicketMemberSystemInputPanel:TakerMemberSystemDataView:memberSystemRadioGroup' and @value!='']")
                    tgo_radio.click()
                    tgo_input = self.driver.find_element(
                        By.NAME, 'TicketMemberSystemInputPanel:TakerMemberSystemDataView:memberSystemRadioGroup:memberShipNumber')
                    tgo_input.clear()
                    tgo_input.send_keys(self.fields['tgo-id'])
                except NoSuchElementException:
                    pass

            # Check agree checkbox
            agree_checkbox = self.driver.find_element(By.NAME, 'agree')
            if not agree_checkbox.is_selected():
                agree_checkbox.click()

            # Click submit button
            submit_btn = self.driver.find_element(By.NAME, 'SubmitButton')
            submit_btn.click()
            time.sleep(2)

            return True
        except Exception as e:
            self.logger.error(f"Failed to confirm ticket: {e}")
            return False

    def print_result(self):
        """4. Print result"""
        page_source = self.driver.page_source
        page = BeautifulSoup(page_source, 'html.parser')

        try:
            reservation_no = page.find('p', class_='pnr-code').get_text(strip=True)
            payment_status = page.find('p', class_='payment-status').get_text(strip=True)
            car_type = page.find('div', class_='car-type').find('p', class_='info-data').get_text(strip=True)
            ticket_type = page.find('div', class_='ticket-type').find('div').get_text(strip=True)
            ticket_price = page.find('span', id='setTrainTotalPriceValue').get_text(strip=True)
            card = page.find('div', class_='ticket-card')
            onbound_date = card.find('span', class_='date').get_text(strip=True)
            train_no = card.find('span', id='setTrainCode0').get_text(strip=True)
            departure_time = card.find('p', class_='departure-time').get_text(strip=True)
            departure_station = card.find('p', class_='departure-stn').get_text(strip=True)
            arrival_time = card.find('p', class_='arrival-time').get_text(strip=True)
            arrival_station = card.find('p', class_='arrival-stn').get_text(strip=True)
            duration = card.find('span', id='InfoEstimatedTime0').get_text(strip=True)
            seats = [seat.get_text(strip=True) for seat in page.find(
                'div', class_='detail').find_all('div', class_='seat-label')]

            self.logger.info("\nBooking success!")
            self.logger.info("\n---------------------- Ticket ----------------------")
            self.logger.info("Reservation No: %s", reservation_no)
            self.logger.info("Payment Status: %s", payment_status)
            self.logger.info("Car Type: %s", car_type)
            self.logger.info("Ticket Type: %s", ticket_type)
            self.logger.info("Price: %s", ticket_price)
            self.logger.info("----------------------------------------------------")
            self.logger.info("Date: %s", onbound_date)
            self.logger.info("Train No: %s", train_no)
            self.logger.info("Duration: %s", duration)
            self.logger.info("%s (%s) -> %s (%s)", departure_time,
                             departure_station, arrival_time, arrival_station)
            self.logger.info("----------------------------------------------------")
            self.logger.info("Seats: %s", ', '.join(seats))
            self.logger.info("\n\nGo to the reservation record to confirm the ticket and pay!\n (%s) ", self.config['page']['history'])

            if not os.getenv("COLAB_RELEASE_TAG") and not os.getenv("DOCKER_ENV"):
                try:
                    pyperclip.copy(reservation_no)
                    self.logger.info("\nReservation No. has been copied to clipboard!")
                except Exception:
                    pass

            return reservation_no
        except Exception as e:
            self.logger.error(f"Failed to parse result: {e}")
            return None

    def main(self):
        """Buy ticket process"""
        search_attempt = 0

        while True:  # Keep searching until ticket is booked
            search_attempt += 1
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"Search attempt #{search_attempt}...")
            self.logger.info(f"{'='*50}")

            # Load booking page
            captcha_img = self.load_booking_page()

            retry_count = 0
            max_retries = 20
            found_train = False
            no_ticket_error = False

            while retry_count < max_retries:
                # Get security code from captcha
                security_code = self.get_security_code(captcha_img)

                if security_code is None:
                    self.logger.warning("Failed to get security code, restarting...")
                    time.sleep(5)
                    break

                # Fill and submit booking form
                if not self.fill_booking_form(security_code):
                    retry_count += 1
                    captcha_img = self.update_captcha()
                    continue

                # Check result
                success, errors, page = self.check_booking_result()

                if success:
                    found_train = True
                    self.logger.info("Captcha correct! Found train list")
                    break
                else:
                    retry_count += 1

                    # Check for "no tickets" error
                    page_source = self.driver.page_source
                    if '查無可售車次' in page_source or '已售完' in page_source:
                        self.logger.warning("No available trains or sold out, retrying in 30s...")
                        no_ticket_error = True
                        time.sleep(30)
                        break

                    if retry_count >= max_retries:
                        self.logger.warning(f"Captcha retry limit ({max_retries}) reached, getting new session...")
                        break

                    self.logger.info(f"Captcha error, updating... ({retry_count}/{max_retries})")
                    captcha_img = self.update_captcha()
                    if captcha_img is None:
                        break

            if found_train:
                break

            if no_ticket_error:
                continue

            self.logger.info("Restarting search...")

        # Confirm train selection
        if not self.fields['train-no']:
            result = self.confirm_train()
            if self.list:
                return
            if not result:
                self.logger.error("Failed to confirm train")
                sys.exit(1)
            self.logger.info("Train selection successful!")

        # Confirm ticket and fill info
        if not self.confirm_ticket():
            self.logger.error("Failed to confirm ticket")
            sys.exit(1)
        self.logger.info("Ticket confirmation successful!")

        # Print result
        reservation_no = self.print_result()

        if reservation_no:
            self.logger.info("\nBooking success! Program will now exit.")
            sys.exit(0)
        else:
            self.logger.error("Failed to complete booking")
            sys.exit(1)
