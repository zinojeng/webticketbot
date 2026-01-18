"""
Dual Captcha OCR System: holey.cc + Gemini Vision
Combines multiple OCR methods to achieve higher accuracy
"""
import os
import base64
import logging
import httpx

logger = logging.getLogger('CaptchaOCR')


class CaptchaOCR:
    """
    Dual captcha recognition system using:
    1. holey.cc API (primary, fast)
    2. Gemini Vision API (fallback, more accurate)
    """

    def __init__(self, holey_api_url: str = None):
        self.holey_api_url = holey_api_url or "https://holey.cc/api/ocr"
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY')
        self.gemini_model = None

        # Initialize Gemini if API key is available
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                # Use gemini-2.0-flash-exp for vision capabilities
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
                logger.info("Gemini Vision API initialized (gemini-2.0-flash-exp)")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
                self.gemini_model = None

    def recognize(self, image_data: bytes, use_gemini_first: bool = False) -> str:
        """
        Recognize captcha using dual OCR system

        Args:
            image_data: Raw image bytes
            use_gemini_first: If True, try Gemini first then holey.cc

        Returns:
            Recognized captcha text or None
        """
        if use_gemini_first and self.gemini_model:
            # Try Gemini first
            result = self._ocr_gemini(image_data)
            if result and self._validate_captcha(result):
                logger.info(f"[Gemini] Captcha: {result}")
                return result

            # Fallback to holey.cc
            result = self._ocr_holey(image_data)
            if result and self._validate_captcha(result):
                logger.info(f"[Holey.cc] Captcha: {result}")
                return result
        else:
            # Try holey.cc first (default, faster)
            result = self._ocr_holey(image_data)
            if result and self._validate_captcha(result):
                logger.info(f"[Holey.cc] Captcha: {result}")
                return result

            # Fallback to Gemini
            if self.gemini_model:
                result = self._ocr_gemini(image_data)
                if result and self._validate_captcha(result):
                    logger.info(f"[Gemini] Captcha: {result}")
                    return result

        logger.warning("Both OCR methods failed")
        return None

    def _ocr_holey(self, image_data: bytes) -> str:
        """Use holey.cc API for OCR"""
        try:
            base64_str = base64.b64encode(image_data).decode("utf-8")
            base64_url_safe = base64_str.replace('+', '-').replace('/', '_').replace('=', '')

            with httpx.Client(timeout=30) as client:
                res = client.post(
                    self.holey_api_url,
                    json={'base64_str': base64_url_safe}
                )

            if res.status_code == 200:
                data = res.json()
                return data.get('data', '').strip()
            else:
                logger.warning(f"Holey.cc API error: HTTP {res.status_code}")
                return None

        except Exception as e:
            logger.warning(f"Holey.cc OCR failed: {e}")
            return None

    def _ocr_gemini(self, image_data: bytes) -> str:
        """Use Gemini Vision API for OCR"""
        if not self.gemini_model:
            return None

        try:
            import google.generativeai as genai

            # Create image part for Gemini
            image_part = {
                "mime_type": "image/png",
                "data": image_data
            }

            prompt = """Look at this CAPTCHA image and extract the text/characters shown.
Rules:
- The CAPTCHA contains alphanumeric characters (letters and numbers)
- Return ONLY the characters you see, nothing else
- No spaces, no explanation, just the raw characters
- Case sensitive - preserve uppercase/lowercase as shown
- Common confusions: 0 vs O, 1 vs l vs I, 5 vs S
- If unsure between similar characters, make your best guess

Output the captcha text only:"""

            response = self.gemini_model.generate_content([prompt, image_part])

            if response and response.text:
                # Clean up the response
                result = response.text.strip()
                # Remove any quotes or extra characters
                result = result.replace('"', '').replace("'", '').strip()
                return result

            return None

        except Exception as e:
            logger.warning(f"Gemini OCR failed: {e}")
            return None

    def _validate_captcha(self, text: str) -> bool:
        """Validate captcha format (THSRC uses 4 alphanumeric characters)"""
        if not text:
            return False
        # THSRC captcha is typically 4 characters
        if len(text) < 4 or len(text) > 6:
            return False
        # Should be alphanumeric
        if not text.isalnum():
            return False
        return True

    def recognize_with_retry(self, image_data: bytes, max_retries: int = 3) -> str:
        """
        Try to recognize captcha with multiple attempts
        Alternates between OCR methods for better accuracy
        """
        for attempt in range(max_retries):
            # Alternate between methods
            use_gemini_first = (attempt % 2 == 1)
            result = self.recognize(image_data, use_gemini_first=use_gemini_first)
            if result:
                return result
            logger.info(f"OCR attempt {attempt + 1}/{max_retries} failed, retrying...")

        return None


# Convenience function for direct use
def recognize_captcha(image_data: bytes, holey_api_url: str = None) -> str:
    """
    Convenience function to recognize captcha

    Args:
        image_data: Raw image bytes
        holey_api_url: Optional holey.cc API URL

    Returns:
        Recognized captcha text or None
    """
    ocr = CaptchaOCR(holey_api_url)
    return ocr.recognize(image_data)
