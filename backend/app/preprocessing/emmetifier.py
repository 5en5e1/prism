"""Emmetify HTML compression for efficient API usage."""
from emmetify import Emmetifier

from ..core.tracing import get_logger

logger = get_logger(__name__)

# Global emmetifier instance
_emmetifier = Emmetifier()


def compress_html(html: str) -> tuple[str, dict]:
    """
    Compress HTML to Emmet notation for efficient token usage.
    
    Emmet notation is a compact representation of HTML that significantly
    reduces token count while preserving structure and content.
    
    Args:
        html: HTML content to compress
        
    Returns:
        Tuple of (compressed_emmet, stats_dict)
        where stats_dict contains compression metrics
    """
    try:
        emmet_result = _emmetifier.emmetify(html)
        # emmetify() returns a HtmlConverterResult dataclass; the emmet
        # string is the .result attribute. str(emmet_result) would emit the
        # dataclass repr (with the maps object) instead of the emmet itself.
        emmet = emmet_result.result
        
        original_size = len(html)
        compressed_size = len(emmet)
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        
        stats = {
            "original_size": original_size,
            "compressed_size": compressed_size,
            "compression_ratio": compression_ratio,
            "compression_method": "emmet"
        }
        
        logger.info(
            f"Emmetified HTML: {original_size} -> {compressed_size} bytes "
            f"({compression_ratio:.1f}% reduction)"
        )
        
        return emmet, stats
        
    except Exception as e:
        logger.warning(f"Emmetify compression failed: {e}, returning original HTML")
        return html, {
            "original_size": len(html),
            "compressed_size": len(html),
            "compression_ratio": 0,
            "compression_method": "none",
            "error": str(e)
        }


def decompress_html(emmet: str) -> str:
    """
    Decompress Emmet notation back to HTML.
    
    Note: Emmetify is primarily for compression to send to AI.
    The AI should return full HTML, not Emmet notation.
    
    Args:
        emmet: Emmet notation to decompress
        
    Returns:
        Decompressed HTML string
    """
    try:
        # Emmetify doesn't have a built-in decompress method
        # The AI should return full HTML, not Emmet
        logger.warning("Emmet decompression not supported - AI should return full HTML")
        return emmet
    except Exception as e:
        logger.error(f"Emmet decompression failed: {e}")
        return emmet

# Made with Bob
