"""Text utility functions for bot."""

import re


def escape_markdown(text: str) -> str:
    """
    Escape Markdown special characters to prevent parse errors.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for Markdown parsing
    """
    # Escape special Markdown characters
    special_chars = ['*', '_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

