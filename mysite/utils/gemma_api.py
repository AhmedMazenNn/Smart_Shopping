# يمكنك وضع هذا الكود في ملف جديد مثل `mysite/utils/gemma_api.py`
# ثم استيراده واستخدامه في Views أو Tasks الخاصة بك.

import requests
import json
import logging

logger = logging.getLogger(__name__)

def call_gemma_model(prompt_text, model_name="gemma2"):
    """
    يتصل بـ Ollama API لتوليد نص باستخدام نموذج Gemma.
    """
    ollama_api_url = "http://localhost:11434/api/generate"
    
    payload = {
        "model": model_name,
        "prompt": prompt_text,
        "stream": False # لانتظار الإجابة كاملة
    }

    try:
        logger.info(f"Sending prompt to Ollama model {model_name}: {prompt_text[:50]}...")
        response = requests.post(ollama_api_url, json=payload, timeout=120) # زيادة المهلة
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

        result = response.json()
        if "response" in result:
            logger.info(f"Received response from Gemma: {result['response'][:100]}...")
            return result['response']
        else:
            logger.warning(f"No 'response' field in Ollama API result: {result}")
            return "Error: No response from model."

    except requests.exceptions.Timeout:
        logger.error(f"Ollama API request timed out after 120 seconds for prompt: {prompt_text[:50]}...")
        return "Error: Model response timed out."
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Could not connect to Ollama API. Is Ollama server running? Error: {e}")
        return "Error: Could not connect to model server. Please ensure Ollama is running."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API: {e}", exc_info=True)
        return f"Error: Failed to get response from model. Details: {e}"
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response from Ollama: {e}")
        logger.error(f"Raw response: {response.text}")
        return "Error: Invalid response from model."