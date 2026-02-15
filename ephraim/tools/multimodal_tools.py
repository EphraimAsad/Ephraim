"""
Multimodal Tools

Provides tools for reading and analyzing images and PDF files.
Uses Ollama vision models (llava, llama3.2-vision) when available.
"""

import base64
import io
import os
from typing import Optional, List, Dict, Any

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool

# Check for vision model availability
VISION_AVAILABLE = False
VISION_MODEL = None
PDF_IMAGE_AVAILABLE = False
PDF_TEXT_AVAILABLE = False

try:
    import ollama
    # Check if a vision model is available
    try:
        response = ollama.list()
        model_names = [m.model for m in response.models]
        # Look for vision-capable models
        vision_models = ["llava", "llama3.2-vision", "bakllava", "moondream"]
        for vm in vision_models:
            for m in model_names:
                if vm in m.lower():
                    VISION_MODEL = m
                    VISION_AVAILABLE = True
                    break
            if VISION_AVAILABLE:
                break
    except Exception:
        pass
except ImportError:
    pass

# Check for PDF to image capability
try:
    from pdf2image import convert_from_path
    PDF_IMAGE_AVAILABLE = True
except ImportError:
    pass

# Check for PDF text extraction capability
try:
    import fitz  # PyMuPDF
    PDF_TEXT_AVAILABLE = True
except ImportError:
    pass

# Check for PIL (image handling)
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def encode_image_to_base64(image_path: str) -> str:
    """Encode an image file to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image_with_vision(image_path: str, prompt: str = "Describe this image in detail.") -> str:
    """
    Analyze an image using Ollama vision model.

    Returns description or error message.
    """
    if not VISION_AVAILABLE:
        return "Vision model not available. Install llava: ollama pull llava"

    try:
        # Encode image
        image_data = encode_image_to_base64(image_path)

        # Call Ollama with image
        response = ollama.chat(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_data],
                }
            ],
        )

        return response["message"]["content"]
    except Exception as e:
        return f"Error analyzing image: {str(e)}"


def extract_pdf_text(pdf_path: str, page_range: Optional[str] = None) -> str:
    """
    Extract text from a PDF file using PyMuPDF.

    Args:
        pdf_path: Path to PDF file
        page_range: Optional page range (e.g., "1-5", "3")

    Returns:
        Extracted text
    """
    if not PDF_TEXT_AVAILABLE:
        return "PDF text extraction not available. Install PyMuPDF: pip install PyMuPDF"

    try:
        doc = fitz.open(pdf_path)

        # Parse page range
        start, end = 0, len(doc)
        if page_range:
            try:
                if '-' in page_range:
                    start, end = map(int, page_range.split('-'))
                    start -= 1  # Convert to 0-indexed
                else:
                    start = int(page_range) - 1
                    end = start + 1
            except ValueError:
                pass

        # Extract text from pages
        text = ""
        for page_num in range(start, min(end, len(doc))):
            page = doc[page_num]
            text += f"\n--- Page {page_num + 1} ---\n"
            text += page.get_text()

        doc.close()
        return text.strip()
    except Exception as e:
        return f"Error extracting PDF text: {str(e)}"


def analyze_pdf_with_vision(pdf_path: str, page_range: Optional[str] = None, prompt: str = "Describe what you see.") -> str:
    """
    Analyze PDF pages as images using vision model.

    Converts PDF pages to images and analyzes them.
    """
    if not PDF_IMAGE_AVAILABLE:
        return "PDF to image not available. Install pdf2image: pip install pdf2image"

    if not VISION_AVAILABLE:
        return "Vision model not available. Install llava: ollama pull llava"

    try:
        # Parse page range for pdf2image (1-indexed)
        first_page, last_page = None, None
        if page_range:
            try:
                if '-' in page_range:
                    first_page, last_page = map(int, page_range.split('-'))
                else:
                    first_page = int(page_range)
                    last_page = first_page
            except ValueError:
                pass

        # Convert PDF pages to images
        images = convert_from_path(
            pdf_path,
            first_page=first_page,
            last_page=last_page,
        )

        results = []
        for i, img in enumerate(images):
            # Convert PIL image to base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

            # Analyze with vision model
            page_num = (first_page or 1) + i
            response = ollama.chat(
                model=VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": f"Page {page_num}: {prompt}",
                        "images": [image_data],
                    }
                ],
            )

            results.append(f"--- Page {page_num} ---\n{response['message']['content']}")

        return "\n\n".join(results)
    except Exception as e:
        return f"Error analyzing PDF with vision: {str(e)}"


@register_tool
class ReadImageTool(BaseTool):
    """
    Read and analyze an image using vision model.

    Supports PNG, JPG, GIF, BMP, WebP formats.
    Requires a vision-capable Ollama model (llava, llama3.2-vision).
    """

    name = "read_image"
    description = "Read an image and describe/analyze its contents using AI vision"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the image file",
            required=True,
        ),
        ToolParam(
            name="prompt",
            type="string",
            description="What to analyze (default: describe the image)",
            required=False,
            default="Describe this image in detail.",
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Analyze the image."""
        path = params["path"]
        prompt = params.get("prompt", "Describe this image in detail.")

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Validate file exists
        if not os.path.exists(path):
            return ToolResult.fail(f"File not found: {path}")

        # Check extension
        valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        ext = os.path.splitext(path)[1].lower()
        if ext not in valid_extensions:
            return ToolResult.fail(f"Unsupported image format: {ext}")

        # Check vision availability
        if not VISION_AVAILABLE:
            return ToolResult.fail(
                "Vision model not available. "
                "Install a vision model: ollama pull llava"
            )

        # Analyze image
        description = analyze_image_with_vision(path, prompt)

        return ToolResult.ok(
            data={
                "path": path,
                "model": VISION_MODEL,
                "prompt": prompt,
                "description": description,
            },
            summary=f"Analyzed image with {VISION_MODEL}",
        )


@register_tool
class ReadPDFTool(BaseTool):
    """
    Read a PDF file and return its contents.

    Can extract text or analyze pages as images using vision model.
    """

    name = "read_pdf"
    description = "Read a PDF file and extract text or analyze with vision"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the PDF file",
            required=True,
        ),
        ToolParam(
            name="pages",
            type="string",
            description="Page range to read (e.g., '1-5', '3'). Default: all",
            required=False,
            default=None,
        ),
        ToolParam(
            name="mode",
            type="string",
            description="Mode: 'text' (extract text) or 'vision' (analyze as images). Default: text",
            required=False,
            default="text",
        ),
        ToolParam(
            name="prompt",
            type="string",
            description="Prompt for vision analysis (only used if mode='vision')",
            required=False,
            default="Describe what you see on this page.",
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Read the PDF."""
        path = params["path"]
        pages = params.get("pages")
        mode = params.get("mode", "text")
        prompt = params.get("prompt", "Describe what you see on this page.")

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Validate file exists
        if not os.path.exists(path):
            return ToolResult.fail(f"File not found: {path}")

        # Check extension
        if not path.lower().endswith('.pdf'):
            return ToolResult.fail(f"Not a PDF file: {path}")

        # Handle based on mode
        if mode == "vision":
            if not VISION_AVAILABLE:
                return ToolResult.fail(
                    "Vision model not available. Use mode='text' or install: ollama pull llava"
                )
            if not PDF_IMAGE_AVAILABLE:
                return ToolResult.fail(
                    "PDF to image conversion not available. "
                    "Install pdf2image: pip install pdf2image"
                )

            content = analyze_pdf_with_vision(path, pages, prompt)
            method = f"vision ({VISION_MODEL})"
        else:
            if not PDF_TEXT_AVAILABLE:
                return ToolResult.fail(
                    "PDF text extraction not available. "
                    "Install PyMuPDF: pip install PyMuPDF"
                )

            content = extract_pdf_text(path, pages)
            method = "text extraction"

        # Get page count
        page_count = "unknown"
        if PDF_TEXT_AVAILABLE:
            try:
                doc = fitz.open(path)
                page_count = len(doc)
                doc.close()
            except Exception:
                pass

        return ToolResult.ok(
            data={
                "path": path,
                "mode": mode,
                "pages": pages or "all",
                "total_pages": page_count,
                "content": content,
            },
            summary=f"Read PDF using {method} ({page_count} pages)",
        )


# Convenience functions
def read_image(path: str, prompt: Optional[str] = None) -> ToolResult:
    """Read and analyze an image."""
    tool = ReadImageTool()
    return tool(path=path, prompt=prompt)


def read_pdf(path: str, pages: Optional[str] = None, mode: str = "text") -> ToolResult:
    """Read a PDF file."""
    tool = ReadPDFTool()
    return tool(path=path, pages=pages, mode=mode)


def get_multimodal_status() -> Dict[str, Any]:
    """Get the status of multimodal capabilities."""
    return {
        "vision_available": VISION_AVAILABLE,
        "vision_model": VISION_MODEL,
        "pdf_image_available": PDF_IMAGE_AVAILABLE,
        "pdf_text_available": PDF_TEXT_AVAILABLE,
        "pil_available": PIL_AVAILABLE,
    }
