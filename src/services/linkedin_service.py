from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import List, Optional, Set
import random

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc
from selenium import webdriver
from src.services.event_bus import bus


LOGIN_URL = "https://www.linkedin.com/login"


@dataclass
class InboxMessage:
    sender_name: str
    text: str
    timestamp: float
    profile_url: str | None = None
    participant_name: str | None = None


class LinkedInAutomation:
    def __init__(self, headless: bool = True, profile_dir: str | None = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.headless = headless
        self.profile_dir = profile_dir or os.environ.get("SELENIUM_PROFILE_DIR", "selenium_profile")
        self.driver = None

    def _ensure_driver(self):
        if self.driver:
            return
        
        # Clean profile directory completely
        import shutil
        if os.path.exists(self.profile_dir):
            try:
                shutil.rmtree(self.profile_dir)
            except Exception:
                pass
        os.makedirs(self.profile_dir, exist_ok=True)

        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        if self.headless:
            options.add_argument('--headless')

        bus.emit("info", "Starting Chrome")
        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_page_load_timeout(45)
        except Exception as e:
            bus.emit("error", f"Chrome startup failed: {str(e)[:100]}")
            raise

    def _human_like_wait(self, min_seconds: float = 0.2, max_seconds: float = 0.6) -> None:
        time.sleep(random.uniform(min_seconds, max_seconds))

    def _try_find(self, locator, timeout: int = 6):
        try:
            return WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located(locator))
        except TimeoutException:
            return None

    def _find_first_message_box(self, timeout: int = 12):
        locators = [
            (By.CSS_SELECTOR, "div[contenteditable='true'][role='textbox']"),
            (By.CSS_SELECTOR, "div.msg-form__contenteditable[contenteditable='true']"),
            (By.CSS_SELECTOR, "div.msg-form__msg-content-container--scrollable div[contenteditable='true']"),
            (By.CSS_SELECTOR, "div[data-placeholder*='message']"),
            (By.XPATH, "//div[@role='textbox' and @contenteditable='true']"),
        ]
        deadline = time.time() + timeout
        while time.time() < deadline:
            for loc in locators:
                el = self._try_find(loc, timeout=2)
                if el is not None and el.is_enabled():
                    return el
            time.sleep(0.5)
        raise TimeoutException("Could not locate a message input box")

    def _maybe_accept_message_request(self):
        accept_selectors = [
            "//button[contains(text(), 'Accept')]",
            "//button[.//span[contains(text(), 'Accept')]]",
            "//button[@aria-label*='Accept']",
            "//button[contains(@class, 'artdeco-button--primary') and contains(., 'Accept')]"
        ]
        for selector in accept_selectors:
            btn = self._try_find((By.XPATH, selector), timeout=2)
            if btn is not None:
                try:
                    btn.click()
                    self._human_like_wait(0.5, 1.0)
                    bus.emit("info", "Accepted message request")
                    return
                except Exception as e:
                    self.logger.debug(f"Failed to click accept button: {e}")

    def _type_message_human_like(self, element, message: str) -> None:
        for chunk in message.split(" "):
            element.send_keys(chunk + " ")
            time.sleep(random.uniform(0.03, 0.12))

    def _sanitize_bmp(self, text: str) -> str:
        # Remove characters outside Basic Multilingual Plane to avoid ChromeDriver BMP error
        return "".join(ch for ch in text or "" if ord(ch) <= 0xFFFF)



    def login(self, username: str, password: str) -> bool:
        try:
            self._ensure_driver()
            bus.emit("info", "Navigating to LinkedIn login page")
            self.driver.get(LOGIN_URL)

            # If already logged in (cached session), messaging link or global nav appears quickly
            already = self._try_find((By.CSS_SELECTOR, "a[href*='/messaging']"), timeout=6) or \
                      self._try_find((By.ID, "global-nav"), timeout=2)
            if already:
                self.logger.info("Already logged in to LinkedIn")
                bus.emit("success", "LinkedIn login successful (session)")
                return True

            # Otherwise, enter credentials
            try:
                self._try_find((By.ID, "username"), timeout=15).send_keys(username)
                self.driver.find_element(By.ID, "password").send_keys(password)
                self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
            except Exception:
                # If fields not present but nav is, treat as logged-in
                if self._try_find((By.CSS_SELECTOR, "a[href*='/messaging']"), timeout=5):
                    bus.emit("success", "LinkedIn login successful (session)")
                    return True
                raise

            # Wait for any logged-in indicator
            WebDriverWait(self.driver, 30).until(
                EC.any_of(
                    EC.url_contains("/feed"),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/messaging']")),
                    EC.presence_of_element_located((By.ID, "global-nav")),
                )
            )
            self.logger.info("Logged in to LinkedIn")
            bus.emit("success", "LinkedIn login successful")
            return True
        except TimeoutException:
            self.logger.error("Login timeout. May require MFA.")
            bus.emit("error", "Login timeout. Might require MFA or manual login.")
            return False
        except WebDriverException as e:
            self.logger.exception("Login error: %s", e)
            bus.emit("error", f"Login error: {e}")
            return False

    def send_reply(self, message: str) -> bool:
        """Send a reply in the currently open conversation"""
        try:
            # Find the message input box using exact selector from HTML
            box = self._try_find((By.CSS_SELECTOR, "div.msg-form__contenteditable[contenteditable='true'][role='textbox']"), timeout=10)
            if not box:
                bus.emit("error", "Message input box not found")
                return False
            
            # Click and focus the input
            box.click()
            self._human_like_wait(0.5, 1.0)
            
            # Clear any existing content and type message
            box.clear()
            safe_message = self._sanitize_bmp(message)
            box.send_keys(safe_message)
            
            # Send with Enter
            self._human_like_wait(0.5, 1.0)
            box.send_keys(Keys.RETURN)
            self._human_like_wait(1, 2)
            
            bus.emit("success", "Reply sent successfully")
            return True
            
        except Exception as e:
            self.logger.exception(f"Failed to send reply: {e}")
            bus.emit("error", f"Reply failed: {str(e)[:100]}")
            return False
    
    def send_message(self, profile_url: str, message: str) -> bool:
        try:
            self._ensure_driver()
            bus.emit("info", f"Opening profile: {profile_url}")
            self.driver.get(profile_url)
            self._human_like_wait(2, 3)
            
            # Try to find and click message button
            message_selectors = [
                "//button[contains(@aria-label, 'Message')]",
                "//a[contains(@href, '/messaging/thread/')]",
                "//button[contains(., 'Message')]",
                "//a[contains(., 'Message')]",
                "//button[@data-control-name='message']"
            ]
            
            msg_btn = None
            for selector in message_selectors:
                try:
                    msg_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not msg_btn:
                # Try connect with note as fallback
                try:
                    connect_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Connect')]"))
                    )
                    connect_btn.click()
                    self._human_like_wait(1, 2)
                    
                    add_note_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Add a note')]"))
                    )
                    add_note_btn.click()
                except TimeoutException:
                    bus.emit("error", f"No messaging or connect option for: {profile_url}")
                    return False
            else:
                msg_btn.click()
            
            self._human_like_wait(2, 3)
            self._maybe_accept_message_request()
            
            # Find and use message box
            box = self._find_first_message_box(timeout=15)
            box.click()
            self._human_like_wait(0.5, 1.0)
            
            # Clear any existing text and type message
            box.clear()
            safe_message = self._sanitize_bmp(message)
            self._type_message_human_like(box, safe_message)
            
            # Send message
            self._human_like_wait(0.5, 1.0)
            box.send_keys(Keys.RETURN)
            self._human_like_wait(1, 2)
            
            bus.emit("success", f"Message sent to {profile_url}")
            return True
            
        except Exception as e:
            self.logger.exception(f"Failed to send message to {profile_url}: {e}")
            bus.emit("error", f"Failed to send message: {str(e)[:100]}")
            return False

    def _normalize_profile_url(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        clean = url.split('?')[0].rstrip('/')
        return clean

    def fetch_inbox_latest(self, limit: int = 30, allowed_profile_urls: Optional[Set[str]] = None) -> List[InboxMessage]:
        try:
            self._ensure_driver()
            bus.emit("info", "Checking LinkedIn inbox")
            self.driver.get("https://www.linkedin.com/messaging/")
            
            # Wait for conversations to load
            conversation_selectors = [
                "li.msg-conversation-listitem",
                "div[data-view-name='msg-conversations-container'] li",
                "ul.msg-conversations-container__conversations-list li"
            ]
            
            conv_cards = None
            for selector in conversation_selectors:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    conv_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)[:limit]
                    break
                except TimeoutException:
                    continue
            
            if not conv_cards:
                bus.emit("warning", "No conversations found in inbox")
                return []
            
            messages: List[InboxMessage] = []
            normalized_allow: Optional[Set[str]] = None
            if allowed_profile_urls is not None:
                normalized_allow = {self._normalize_profile_url(u) for u in allowed_profile_urls if u}
            
            for i, card in enumerate(conv_cards):
                try:
                    # Click conversation
                    self.driver.execute_script("arguments[0].click();", card)
                    self._human_like_wait(1, 2)
                    
                    # Get participant info
                    profile_url, participant_name = self._extract_participant_info()
                    
                    # Get latest message
                    message_text, is_incoming = self._extract_latest_message()
                    
                    if is_incoming and message_text:
                        # Check if this conversation is allowed
                        if self._is_conversation_allowed(profile_url, participant_name, normalized_allow):
                            bus.emit("info", f"New reply from {participant_name or 'Unknown'}: {message_text[:50]}...")
                            messages.append(InboxMessage(
                                sender_name="user",
                                text=message_text,
                                timestamp=time.time(),
                                profile_url=profile_url,
                                participant_name=participant_name
                            ))
                    
                except Exception as e:
                    self.logger.debug(f"Error processing conversation {i}: {e}")
                    continue
            
            bus.emit("info", f"Found {len(messages)} new messages")
            return messages
            
        except Exception as e:
            self.logger.exception(f"Failed to fetch inbox: {e}")
            bus.emit("error", f"Inbox check failed: {str(e)[:100]}")
            return []
    
    def _extract_participant_info(self) -> tuple[Optional[str], Optional[str]]:
        """Extract profile URL and name from current conversation"""
        profile_url = None
        participant_name = None
        
        # Try to get profile URL
        profile_selectors = [
            "a.msg-entity-lockup__link",
            "header a[href*='linkedin.com/in/']",
            "a[href*='linkedin.com/in/']",
            ".msg-thread__link-to-profile"
        ]
        
        for selector in profile_selectors:
            try:
                link = self.driver.find_element(By.CSS_SELECTOR, selector)
                href = link.get_attribute("href")
                if href and "/in/" in href:
                    profile_url = href
                    break
            except Exception:
                continue
        
        # Try to get participant name
        name_selectors = [
            ".msg-entity-lockup__entity-title",
            ".msg-thread__link-to-profile",
            "h2.msg-entity-lockup__entity-title",
            ".artdeco-entity-lockup__title"
        ]
        
        for selector in name_selectors:
            try:
                name_el = self.driver.find_element(By.CSS_SELECTOR, selector)
                participant_name = (name_el.text or "").strip()
                if participant_name:
                    break
            except Exception:
                continue
        
        return profile_url, participant_name
    
    def _extract_latest_message(self) -> tuple[str, bool]:
        """Extract latest message text and determine if it's incoming"""
        message_text = ""
        is_incoming = False
        
        try:
            # Use data-event-urn selector (most reliable)
            messages = self.driver.find_elements(By.CSS_SELECTOR, "div[data-event-urn]")
            if not messages:
                # Fallback to other selectors
                messages = self.driver.find_elements(By.CSS_SELECTOR, "div.msg-s-event-listitem")
            
            if messages:
                last_message = messages[-1]
                
                # Method 1: Check for profile picture (incoming messages have profile pics)
                profile_pics = last_message.find_elements(By.CSS_SELECTOR, "img[alt*='profile'], img.msg-s-event-listitem__profile-picture")
                if profile_pics:
                    is_incoming = True
                else:
                    # Method 2: Check data-event-urn for sender info
                    urn = last_message.get_attribute("data-event-urn") or ""
                    # If URN exists and doesn't contain our profile, it's incoming
                    is_incoming = bool(urn and "fsd_profile" in urn)
                
                # Extract message text
                text_selectors = [
                    "p.msg-s-event-listitem__body",
                    "div.msg-s-event__content p",
                    "p",
                    "span"
                ]
                
                for text_sel in text_selectors:
                    text_elements = last_message.find_elements(By.CSS_SELECTOR, text_sel)
                    if text_elements:
                        message_text = text_elements[-1].text.strip()
                        if message_text:
                            break
                
                if not message_text:
                    message_text = last_message.text.strip()
        
        except Exception as e:
            self.logger.debug(f"Error extracting message: {e}")
        
        return message_text, is_incoming
    
    def _is_conversation_allowed(self, profile_url: Optional[str], participant_name: Optional[str], 
                               normalized_allow: Optional[Set[str]]) -> bool:
        """Check if conversation is from an allowed contact"""
        if normalized_allow is None:
            return True
        
        if profile_url:
            norm_url = self._normalize_profile_url(profile_url)
            if norm_url in normalized_allow:
                return True
        
        # Allow if we can't determine - let scheduler handle name matching
        return True

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass


