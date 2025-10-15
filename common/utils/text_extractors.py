"""
Text extraction utilities for various file formats.
This module handles the extraction of text content from different document types.
"""
import os
import json
import logging
import uuid
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)

class TextExtractor:
    """Class for handling text extraction from various file formats and cleanup."""
    
    def __init__(self):
        """Initialize the TextExtractor."""
        self.supported_extensions = {
            '.txt': 'text/plain',
            '.md': 'text/markdown', 
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.html': 'text/html',
            '.htm': 'text/html',
            '.json': 'application/json',
            '.csv': 'text/csv',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.xml': 'application/xml',
            '.jpeg': 'image/jpeg',
            '.jpg': 'image/jpeg'
        }
    
    def cleanup_tmp_folder(self, tmp_path: str = None):
        """Remove everything inside the tmp_extract folder (files + subdirectories)."""
        if tmp_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            tmp_path = os.path.join(project_root, "tmp_extract")
        tmp_dir = Path(tmp_path)

        # If folder exists, clean it first
        if tmp_dir.exists():
            logger.info(f"Cleaning temp folder {tmp_path}")
            items_deleted = 0
            for item in tmp_dir.iterdir():
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                        logger.debug(f"Deleted file: {item}")
                        items_deleted += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        logger.debug(f"Deleted directory: {item}")
                        items_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {item}: {e}")
            logger.info(f"Cleaned {items_deleted} items from temp folder")
        else:
            logger.info(f"Creating temp folder {tmp_path}")
        
        # Ensure the folder exists (create if needed)
        os.makedirs(tmp_path, exist_ok=True)
    
    def process_folder(self, folder_path, graphname=None):
        """Process local folder with multiple file formats and extract text content."""
        logger.info(f"Processing local folder: {folder_path} for graph: {graphname}")
        
        # Check if folder exists
        if not os.path.exists(folder_path):
            raise Exception(f"Folder path does not exist: {folder_path}")
        
        if not os.path.isdir(folder_path):
            raise Exception(f"Path is not a directory: {folder_path}")
        
        processed_files = []
        
        try:
            # Recursively find all supported files
            folder_path_obj = Path(folder_path)
            
            # First, clean up any system directories that shouldn't be there
            for item in folder_path_obj.iterdir():
                if item.is_dir() and (item.name.startswith(('.', '~', '$')) or 'BROMIUM' in item.name.upper()):
                    logger.debug(f"Found system directory to skip: {item.name}")
            
            # Use a safer approach to avoid traversing problematic directories
            def safe_walk(path):
                """Safely walk directory tree, skipping problematic directories."""
                try:
                    for item in path.iterdir():
                        # Skip system/temp directories and files
                        if item.name.startswith(('.', '~', '$')) or 'BROMIUM' in item.name.upper():
                            logger.debug(f"Skipping system item: {item.name}")
                            continue
                            
                        if item.is_file():
                            yield item
                        elif item.is_dir():
                            # Recursively walk subdirectories
                            yield from safe_walk(item)
                except (PermissionError, OSError) as e:
                    logger.warning(f"Cannot access directory {path}: {e}")
                    
            for file_path in safe_walk(folder_path_obj):
                if file_path.is_file():
                    # Skip temporary and hidden files, including Bromium and other security software temp files
                    if file_path.name.startswith(('.', '~', '$')) or 'BROMIUM' in file_path.name.upper():
                        logger.debug(f"Skipping temporary/system file: {file_path.name}")
                        continue
                        
                    file_ext = file_path.suffix.lower()
                    if file_ext in self.supported_extensions:
                        try:
                            # Double check file still exists (temp files can disappear)
                            if not file_path.exists():
                                logger.warning(f"File disappeared during processing: {file_path}")
                                continue
                            
                            # Additional check for system/temp files that might have been created after initial scan
                            if file_path.name.startswith(('.', '~', '$')) or 'BROMIUM' in file_path.name.upper():
                                logger.debug(f"Skipping system file detected during processing: {file_path.name}")
                                continue
                                
                            content = extract_text_from_file(file_path, graphname=graphname)
                            if content.strip():  # Only process files with content
                                # Use relative path from the base folder as doc_id
                                relative_path = file_path.relative_to(folder_path_obj)
                                doc_id = str(relative_path).replace('\\', '/')  # Normalize path separators
                                
                                processed_files.append({
                                    'file_path': str(file_path),
                                    'doc_id': doc_id,
                                    'content': content,
                                    'doc_type': get_doc_type_from_extension(file_ext),
                                    'status': 'success'
                                })
                                logger.info(f"Successfully processed file: {file_path}")
                        except FileNotFoundError as e:
                            logger.debug(f"File disappeared during processing (likely temporary file): {file_path}")
                            continue
                        except PermissionError as e:
                            logger.warning(f"Permission denied accessing file: {file_path}")
                            continue
                        except Exception as e:
                            logger.warning(f"Failed to process file {file_path}: {e}")
                            # Skip adding failed files to processed_files to avoid issues
            
            logger.info(f"Processed {len(processed_files)} files from local folder")
            
            # Create JSONL file from processed documents
            if processed_files:
                loader_config = {
                    "doc_id_field": "doc_id",
                    "content_field": "content"
                }
                jsonl_filepath = self.create_jsonl_file(processed_files, loader_config)
                logger.info(f"Created JSONL file: {jsonl_filepath}")
                
                return {
                    'statusCode': 200,
                    'message': f'Processed {len(processed_files)} files from local folder',
                    'files': processed_files,
                    'jsonl_file_path': jsonl_filepath,
                    'num_documents': len(processed_files)
                }
            else:
                return {
                    'statusCode': 200,
                    'message': 'No supported files found in folder',
                    'files': [],
                    'jsonl_file_path': None,
                    'num_documents': 0
                }
            
        except Exception as e:
            logger.error(f"Error processing local folder: {e}")
            return {
                'statusCode': 500,
                'error': str(e)
            }
    
    def create_jsonl_file(self, documents, loader_config):
        """Create JSONL file from processed documents."""
        
        # Create JSONL file in tmp_extract directory within project root
        jsonl_filename = f"local_folder_ingest_{uuid.uuid4().hex}.jsonl"
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        tmp_dir = os.path.join(project_root, "tmp_extract")
        
        # Create tmp_extract directory if it doesn't exist
        os.makedirs(tmp_dir, exist_ok=True)
        
        jsonl_filepath = os.path.join(tmp_dir, jsonl_filename)
        
        with open(jsonl_filepath, 'w', encoding='utf-8') as jsonl_file:
            for doc in documents:
                jsonl_entry = {
                    loader_config["doc_id_field"]: doc['doc_id'],
                    loader_config["content_field"]: doc['content'],
                    "doc_type": doc['doc_type'],
                    "file_path": doc['file_path']
                }
                jsonl_file.write(json.dumps(jsonl_entry, ensure_ascii=False) + '\n')
        
        logger.info(f"Created JSONL file: {jsonl_filepath} with {len(documents)} documents")
        return jsonl_filepath

def extract_text_from_file(file_path, graphname=None):
    """
    Extract text content from a file based on its extension.
    
    Args:
        file_path (str or Path): Path to the file to extract text from
        graphname (str): Graph name for organizing images by graph
        
    Returns:
        str: Extracted text content
        
    Raises:
        Exception: If file cannot be read or processed
    """
    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    
    logger.debug(f"Extracting text from {file_path} (type: {extension}) for graph: {graphname}")
    
    try:
        # Plain text files
        if extension in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                logger.debug(f"Extracted {len(content)} characters from text file")
                return content
        
        # HTML files
        elif extension in ['.html', '.htm']:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return content
        
        # CSV files
        elif extension == '.csv':
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                logger.debug(f"Extracted {len(content)} characters from CSV file")
                return content
        
        # JSON files
        elif extension == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                content = json.dumps(data, indent=2, ensure_ascii=False)
                logger.debug(f"Extracted {len(content)} characters from JSON file")
                return content
        
        # PDF files
        elif extension == '.pdf':
            try:
                import fitz  # PyMuPDF
                
                # Read PDF file and extract text in natural order
                doc = fitz.open(file_path)
                final_output = []
                
                for page_num, page in enumerate(doc, start=1):
                    page_content = []
                    
                    try:
                        # Extract blocks sorted top-left → bottom-right
                        blocks = page.get_text("blocks", sort=True)
                        
                        for block in blocks:
                            block_type = block[6] if len(block) > 6 else 0  # 0=text, 1=image
                            
                            # Text Block
                            if block_type == 0:
                                text = block[4].strip()
                                if text:
                                    page_content.append(text)
                            # Image Block (rare case where image is a separate block)
                            elif block_type == 1:
                                page_content.append("[Image detected in block]")
                        
                        # Extract and describe all images on the page
                        # (Many PDFs embed images without creating image blocks)
                        image_list = page.get_images(full=True)
                        if image_list:
                            logger.debug(f"Found {len(image_list)} embedded image(s) on page {page_num}")
                            for img_index, img_info in enumerate(image_list):
                                try:
                                    xref = img_info[0]
                                    base_image = doc.extract_image(xref)
                                    image_bytes = base_image["image"]
                                    
                                    # Convert to PIL Image
                                    from PIL import Image
                                    import io
                                    pil_image = Image.open(io.BytesIO(image_bytes))
                                    
                                    # Save image and get markdown reference (for local folder processing)
                                    # The function will return None if it's a logo/icon (detected by LLM)
                                    from common.utils.image_data_extractor import save_image_and_get_markdown
                                    context_info = f"PDF embedded image {img_index + 1} from page {page_num} of {file_path.name}"
                                    result = save_image_and_get_markdown(pil_image, context_info=context_info, graphname=graphname)
                                    
                                    # Skip if logo/icon was detected
                                    if result is None:
                                        logger.debug(f"Skipped logo/icon image {img_index + 1} on page {page_num}")
                                        continue
                                    
                                    # Append markdown reference to page content
                                    page_content.append(result['markdown'])
                                    logger.debug(f"Saved embedded image {img_index + 1} on page {page_num} as {result.get('image_id', 'unknown')}")
                                    
                                except Exception as img_error:
                                    logger.warning(f"Failed to process embedded image {img_index + 1} on page {page_num}: {img_error}")
                                    page_content.append(f"[Embedded Image {img_index + 1}: processing failed]")
                        
                        # Optional Table Extraction
                        try:
                            tables = page.find_tables()
                            for table in tables.tables:
                                df = table.to_pandas()
                                page_content.append("\n[Table]\n" + df.to_string(index=False))
                        except Exception:
                            pass  # ignore if no tables
                            
                    except Exception as e:
                        logger.error(f"Failed to read page {page_num}: {str(e)}")
                        page_content.append(f"[Page {page_num} content could not be read]")
                    
                    final_output.append(f"--- Page {page_num} ---\n" + "\n".join(page_content))
                
                doc.close()
                content = "\n\n".join(final_output)
                logger.debug(f"Extracted {len(content)} characters from PDF file using PyMuPDF")
                return content   
            except ImportError:
                logger.warning("PyMuPDF not available for PDF processing")
                return "[PDF processing requires PyMuPDF library]"
            except Exception as pdf_error:
                logger.error(f"Error processing PDF {file_path}: {pdf_error}")
                raise Exception(f"PDF processing failed: {pdf_error}")
        
        # DOCX files
        elif extension == '.docx':
            try:
                import docx
                doc = docx.Document(file_path)
                text_content = ""
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        text_content += paragraph.text + "\n"
                
                content = text_content.strip()
                logger.debug(f"Extracted {len(content)} characters from DOCX file")
                return content
                
            except ImportError:
                logger.warning("python-docx not available for DOCX processing")
                return "[DOCX processing requires python-docx library]"
            except Exception as docx_error:
                logger.error(f"Error processing DOCX {file_path}: {docx_error}")
                raise Exception(f"DOCX processing failed: {docx_error}")
        # XML files
        elif extension == '.xml':
            try:
                import xml.etree.ElementTree as ET
                
                def extract_text_from_element(element):
                    """Recursively extract text from XML element and its children"""
                    text = element.text or ""
                    for child in element:
                        text += " " + extract_text_from_element(child)
                    if element.tail:
                        text += " " + element.tail
                    return text.strip()
                
                tree = ET.parse(file_path)
                root = tree.getroot()
                content = extract_text_from_element(root)
                # Clean up extra whitespace
                import re
                content = re.sub(r'\s+', ' ', content).strip()
                logger.debug(f"Extracted {len(content)} characters from XML file")
                return content
                
            except ET.ParseError as xml_error:
                logger.error(f"Error parsing XML {file_path}: {xml_error}")
                raise Exception(f"XML parsing failed: {xml_error}")
            except Exception as xml_error:
                logger.error(f"Error processing XML {file_path}: {xml_error}")
                raise Exception(f"XML processing failed: {xml_error}")
        
        # Image files (JPEG, JPG, PNG, GIF)
        elif extension in ['.jpeg', '.jpg','png','.gif']:
            try:
                from common.utils.image_data_extractor import save_image_and_get_markdown
                from PIL import Image
                
                # Open image with PIL
                pil_image = Image.open(file_path)
                
                # Save image and get markdown reference (for local folder processing)
                # The function will return None if it's a logo/icon (detected by LLM)
                result = save_image_and_get_markdown(pil_image, context_info=f"Standalone image: {file_path.name}", graphname=graphname)
                
                # Skip if logo/icon was detected
                if result is None:
                    logger.debug(f"Skipped logo/icon standalone image: {file_path.name}")
                    return f"[Skipped logo/icon image: {file_path.name}]"
                
                content = result['markdown']
                
                logger.debug(f"Created markdown reference for standalone image: {result.get('image_id', 'unknown')}")
                return content
                
            except ImportError:
                logger.warning("PIL not available for image processing")
                return "[Image processing requires PIL library]"
            except Exception as image_error:
                logger.error(f"Error processing image {file_path}: {image_error}")
                # Fallback to basic metadata
                try:
                    from PIL import Image
                    image = Image.open(file_path)
                    content = f"[Image file: {file_path.name}, Format: {image.format}, Size: {image.size}, Mode: {image.mode}]"
                    logger.debug(f"Returned image metadata for {file_path}")
                    return content
                except:
                    return f"[Image file: {file_path.name} - LLM vision failed: {image_error}]"
        
        # Unsupported file types
        else:
            logger.warning(f"Unsupported file type: {extension}")
            return f"[Unsupported file type: {extension}]"
            
    except UnicodeDecodeError as e:
        logger.error(f"Unicode decode error for {file_path}: {e}")
        raise Exception(f"Cannot decode file (possibly binary): {e}")
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {e}")
        raise Exception(f"Text extraction failed: {e}")

def get_doc_type_from_extension(extension):
    """
    Map file extension to a chunker-compatible document type.
    Returns chunker types that match the available chunkers in ECC:
    - 'html' for HTML files -> HTMLChunker
    - 'markdown' for Markdown files -> MarkdownChunker
    - 'image' for image files -> No chunking (bypass)
    - 'semantic' for all other files -> SemanticChunker (default)
    
    Args:
        extension (str): File extension (with or without dot)
        
    Returns:
        str: Chunker-compatible document type
    """
    if not extension.startswith('.'):
        extension = '.' + extension
    
    extension = extension.lower()
    
    # Map extensions to chunker types
    if extension in ['.html', '.htm']:
        return 'html'
    elif extension == '.md':
        return 'markdown'
    elif extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']:
        # Images should not be chunked - treat as single content
        return 'image'
    else:
        # All other types (pdf, text, docx, csv, etc.) use semantic chunker
        return 'semantic'

def get_supported_extensions():
    """
    Get list of supported file extensions.
    
    Returns:
        set: Set of supported file extensions (with dots)
    """
    return {'.txt', '.md', '.html', '.htm', '.csv', '.json', '.pdf', '.docx', '.xml', '.jpeg', '.jpg','png','.gif'}

def is_supported_file(file_path):
    """
    Check if a file is supported for text extraction.
    
    Args:
        file_path (str or Path): Path to the file
        
    Returns:
        bool: True if file type is supported
    """
    extension = Path(file_path).suffix.lower()
    return extension in get_supported_extensions()

