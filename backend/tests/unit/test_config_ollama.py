from src.config import Config


def test_default_ollama_base_url_uses_localhost():
    assert Config._default_ollama_base_url() == "http://localhost:11434/v1"
