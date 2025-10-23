"""
Text extraction utilities for various file formats.
This module handles the extraction of text content from different document types.
"""
import os
import json
import logging
import uuid
import base64
import io
from pathlib import Path
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor

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
    
    async def _process_file_async(self, file_path, folder_path_obj, graphname, use_direct_loading):
        """
        Async helper to process a single file.
        Runs in thread pool to avoid blocking on I/O operations.
        """
        try:
            # Run file extraction in thread pool (CPU/IO intensive)
            loop = asyncio.get_event_loop()
            
            if use_direct_loading:
                doc_entries = await loop.run_in_executor(
                    None, 
                    extract_text_from_file_with_images_as_docs, 
                    file_path, 
                    graphname
                )
                
                return {
                    'success': True,
                    'file_path': str(file_path),
                    'documents': doc_entries,
                    'num_documents': len(doc_entries)
                }
            else:
                # OLD APPROACH
                content = await loop.run_in_executor(
                    None,
                    extract_text_from_file,
                    file_path,
                    graphname
                )
                
                if content.strip():
                    relative_path = file_path.relative_to(folder_path_obj)
                    doc_id = str(relative_path).replace('\\', '/')
                    file_ext = file_path.suffix.lower()
                    
                    return {
                        'success': True,
                        'file_path': str(file_path),
                        'documents': [{
                            'file_path': str(file_path),
                            'doc_id': doc_id,
                            'content': content,
                            'doc_type': get_doc_type_from_extension(file_ext),
                            'status': 'success'
                        }]
                    }
                else:
                    return {'success': False, 'file_path': str(file_path), 'error': 'Empty content'}
                    
        except FileNotFoundError:
            return {'success': False, 'file_path': str(file_path), 'error': 'File not found'}
        except PermissionError:
            return {'success': False, 'file_path': str(file_path), 'error': 'Permission denied'}
        except Exception as e:
            logger.warning(f"Failed to process file {file_path}: {e}")
            return {'success': False, 'file_path': str(file_path), 'error': str(e)}
    
    async def _process_folder_async(self, folder_path, graphname=None, use_direct_loading=True, max_concurrent=10):
        """
        Async version of process_folder for parallel file processing.
        This prevents conflicts when multiple users process folders simultaneously.
        """
        logger.info(f"Processing local folder ASYNC: {folder_path} for graph: {graphname} (max_concurrent={max_concurrent})")
        
        folder_path_obj = Path(folder_path)
        
        if not folder_path_obj.exists():
            raise Exception(f"Folder path does not exist: {folder_path}")
        
        if not folder_path_obj.is_dir():
            raise Exception(f"Path is not a directory: {folder_path}")
        
        # Collect all files
        def safe_walk(path):
            try:
                for item in path.iterdir():
                    if item.name.startswith(('.', '~', '$')) or 'BROMIUM' in item.name.upper():
                        continue
                    if item.is_file():
                        yield item
                    elif item.is_dir():
                        yield from safe_walk(item)
            except (PermissionError, OSError) as e:
                logger.warning(f"Cannot access directory {path}: {e}")
        
        files_to_process = []
        for file_path in safe_walk(folder_path_obj):
            if file_path.is_file():
                if file_path.name.startswith(('.', '~', '$')) or 'BROMIUM' in file_path.name.upper():
                    continue
                file_ext = file_path.suffix.lower()
                if file_ext in self.supported_extensions:
                    files_to_process.append(file_path)
        
        logger.info(f"Found {len(files_to_process)} files to process")
        
        # Process files in parallel with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(file_path):
            async with semaphore:
                return await self._process_file_async(file_path, folder_path_obj, graphname, use_direct_loading)
        
        tasks = [process_with_semaphore(fp) for fp in files_to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        all_documents = []
        processed_files_info = []
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"File processing failed with exception: {result}")
                continue
            
            if result.get('success'):
                all_documents.extend(result.get('documents', []))
                processed_files_info.append({
                    'file_path': result['file_path'],
                    'num_documents': result.get('num_documents', len(result.get('documents', []))),
                    'status': 'success'
                })
            else:
                processed_files_info.append({
                    'file_path': result['file_path'],
                    'status': 'failed',
                    'error': result.get('error', 'Unknown error')
                })
        
        logger.info(f"Processed {len(processed_files_info)} files, extracted {len(all_documents)} total documents")
        
        if use_direct_loading:
            return {
                'statusCode': 200,
                'message': f'Processed {len(processed_files_info)} files, {len(all_documents)} documents',
                'documents': all_documents,
                'files': processed_files_info,
                'num_documents': len(all_documents)
            }
        else:
            # OLD APPROACH: Create JSONL
            if all_documents:
                loader_config = {
                    "doc_id_field": "doc_id",
                    "content_field": "content"
                }
                jsonl_filepath = self.create_jsonl_file(all_documents, loader_config)
                return {
                    'statusCode': 200,
                    'message': f'Processed {len(all_documents)} files from local folder',
                    'files': all_documents,
                    'jsonl_file_path': jsonl_filepath,
                    'num_documents': len(all_documents)
                }
            else:
                return {
                    'statusCode': 200,
                    'message': 'No supported files found in folder',
                    'files': [],
                    'jsonl_file_path': None,
                    'num_documents': 0
                }
    
    def process_folder(self, folder_path, graphname=None, use_direct_loading=True):
        """
        Process local folder with multiple file formats and extract text content.
        Uses async processing internally for parallel file handling (prevents conflicts when multiple users run simultaneously).
        
        Args:
            folder_path: Path to folder
            graphname: Graph name
            use_direct_loading: If True, extract images as separate docs (new approach).
                               If False, use old JSONL approach.
        
        Returns:
            dict with documents list (for direct loading) or jsonl_file_path (for old approach)
        """
        logger.info(f"Processing local folder: {folder_path} for graph: {graphname} (direct_loading={use_direct_loading})")
        
        # Run async processing in event loop
        return asyncio.run(self._process_folder_async(folder_path, graphname, use_direct_loading))
    
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

def extract_text_from_file_with_images_as_docs(file_path, graphname=None):
    """
    Extract text and images from a file, treating images as separate document entries.
    This is used for the new async direct loading approach.
    
    Args:
        file_path (str or Path): Path to the file to extract from
        graphname (str): Graph name for organizing data
        
    Returns:
        list[dict]: List of document entries with ordering:
            [
                {
                    "doc_id": "file.pdf",
                    "doc_type": "markdown",
                    "content": "text content",
                    "position": 0
                },
                {
                    "doc_id": "file.pdf_image_1",
                    "doc_type": "image",
                    "content": "![description](image://file.pdf_image_1)",
                    "image_description": "LLM description",
                    "image_data": "base64_encoded_data",
                    "image_format": "jpg",
                    "parent_doc": "file.pdf",
                    "page_number": 1,
                    "width": 800,
                    "height": 600,
                    "position": 1
                },
                ...
            ]
    """
    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    base_doc_id = str(file_path.stem)
    
    logger.debug(f"Extracting with images as docs: {file_path} (type: {extension})")
    
    # For PDF files, extract text and images separately
    if extension == '.pdf':
        return _extract_pdf_with_images_as_docs(file_path, base_doc_id, graphname)
    
    # For standalone image files
    elif extension in ['.jpeg', '.jpg', '.png', '.gif']:
        return _extract_standalone_image_as_doc(file_path, base_doc_id, graphname)
    
    # For all other files, extract text only (no images)
    else:
        content = extract_text_from_file(file_path, graphname)
        doc_type = get_doc_type_from_extension(extension)
        return [{
            "doc_id": base_doc_id,
            "doc_type": doc_type,
            "content": content,
            "position": 0
        }]


def _extract_pdf_with_images_as_docs(file_path, base_doc_id, graphname=None):
    """
    Extract PDF as ONE markdown document with inline image references.
    
    Returns:
    - ONE document entry with markdown content (including inline image refs)
    - Separate Image vertex entries for base64 storage
    
    Example markdown output:
        Text content...
        ![Image description](image://doc_id_image_1)
        More text...
    """
    try:
        import fitz  # PyMuPDF
        from PIL import Image as PILImage
        
        doc = fitz.open(file_path)
        markdown_parts = []  # Will build ONE markdown document
        image_entries = []  # Separate entries for Image vertex
        image_counter = 0
        
        for page_num, page in enumerate(doc, start=1):
            # Add page header
            if page_num > 1:
                markdown_parts.append("\n\n")
            markdown_parts.append(f"--- Page {page_num} ---\n\n")
            
            # Extract text blocks with positions
            blocks = page.get_text("blocks", sort=True)  # sorted by position
            text_blocks_with_pos = []
            
            for block in blocks:
                block_type = block[6] if len(block) > 6 else 0
                if block_type == 0:  # Text block
                    text = block[4].strip()
                    if text:
                        # block format: (x0, y0, x1, y1, "text", block_no, block_type)
                        y_pos = block[1]  # y0 coordinate (top of block)
                        text_blocks_with_pos.append({
                            'type': 'text',
                            'content': text,
                            'y_pos': y_pos
                        })
            
            # Extract images with their positions
            image_list = page.get_images(full=True)
            images_with_pos = []
            
            if image_list:
                for img_index, img_info in enumerate(image_list):
                    try:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Get image position from page
                        img_rects = page.get_image_rects(xref)
                        y_pos = img_rects[0].y0 if img_rects else 999999  # Default to end if no position
                        
                        # Convert to PIL Image
                        pil_image = PILImage.open(io.BytesIO(image_bytes))
                        
                        # Skip very small images (likely logos/icons)
                        if pil_image.width < 100 or pil_image.height < 100:
                            logger.debug(f"Skipping small image ({pil_image.width}x{pil_image.height}) on page {page_num} - likely logo/icon")
                            continue
                        
                        # Get LLM description
                        from common.utils.image_data_extractor import describe_image_with_llm
                        description = describe_image_with_llm(pil_image)
                        
                        # Check if logo/icon (skip if so)
                        description_lower = description.lower()
                        # Check for explicit LOGO:/ICON: prefix or common indicators
                        logo_indicators = ['logo:', 'icon:', 'logo', 'icon', 'branding', 'watermark', 'trademark', 
                                          'stylized letter', 'stylized text', 'word "', "word '"]
                        if any(indicator in description_lower for indicator in logo_indicators):
                            logger.info(f"Skipping logo/icon on page {page_num}: {description[:50]}...")
                            continue
                        
                        # Convert image to base64
                        buffer = io.BytesIO()
                        if pil_image.mode != 'RGB':
                            pil_image = pil_image.convert('RGB')
                        pil_image.save(buffer, format="JPEG", quality=95)
                        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        
                        image_counter += 1
                        image_doc_id = f"{base_doc_id}_image_{image_counter}"
                        
                        images_with_pos.append({
                            'type': 'image',
                            'image_doc_id': image_doc_id,
                            'description': description,
                            'y_pos': y_pos,
                            'image_data': image_base64,
                            'image_format': image_ext,
                            'width': pil_image.width,
                            'height': pil_image.height
                        })
                        
                    except Exception as img_error:
                        logger.warning(f"Failed to extract image on page {page_num}: {img_error}")
            
            # Combine and sort by position (text and images interleaved)
            all_elements = text_blocks_with_pos + images_with_pos
            all_elements.sort(key=lambda x: x['y_pos'])
            
            # Build markdown with properly ordered text and images
            for element in all_elements:
                if element['type'] == 'text':
                    markdown_parts.append(element['content'])
                    markdown_parts.append("\n\n")
                else:  # image
                    # Wrap image description in header to create natural chunk boundary
                    # Chunker will keep this as single chunk
                    markdown_parts.append("### Image Description\n\n")
                    markdown_parts.append(element['description'])
                    markdown_parts.append(f"\n\n[IMAGE_REF:{element['image_doc_id']}]\n\n")
                    
                    # Store image entry for Image vertex
                    image_entries.append({
                        "doc_id": element['image_doc_id'],
                        "doc_type": "image",
                        "image_description": element['description'],
                        "image_data": element['image_data'],
                        "image_format": element['image_format'],
                        "parent_doc": base_doc_id,
                        "page_number": page_num,
                        "width": element['width'],
                        "height": element['height'],
                        "position": int(element['image_doc_id'].split('_')[-1])  # Extract image number
                    })
        
        doc.close()
        
        # Build final result: ONE markdown document + separate image entries
        result = []
        
        # ONE markdown document with inline image references
        markdown_content = "".join(markdown_parts) if markdown_parts else "[No content extracted from PDF]"
        result.append({
            "doc_id": base_doc_id,
            "doc_type": "markdown",
            "content": markdown_content,
            "position": 0
        })
        
        # Add image entries (for Image vertex storage)
        result.extend(image_entries)
        
        logger.info(f"Extracted PDF as 1 markdown document with {image_counter} image references")
        return result
        
    except ImportError:
        logger.error("PyMuPDF not available")
        return [{
            "doc_id": base_doc_id,
            "doc_type": "markdown",
            "content": "[PDF extraction requires PyMuPDF]",
            "position": 0
        }]
    except Exception as e:
        logger.error(f"Error extracting PDF: {e}")
        raise


def _extract_standalone_image_as_doc(file_path, base_doc_id, graphname=None):
    """
    Extract standalone image file as ONE markdown document with inline image reference.
    
    Returns:
    - ONE markdown document with image description
    - Separate Image vertex entry for base64 storage
    """
    try:
        from PIL import Image as PILImage
        from common.utils.image_data_extractor import describe_image_with_llm
        
        pil_image = PILImage.open(file_path)
        
        # Skip very small images (likely logos/icons)
        if pil_image.width < 100 or pil_image.height < 100:
            logger.info(f"Skipping small image ({pil_image.width}x{pil_image.height}): {file_path.name} - likely logo/icon")
            return [{
                "doc_id": base_doc_id,
                "doc_type": "markdown",
                "content": f"[Skipped small image: {file_path.name}]",
                "position": 0
            }]
        
        # Get description
        description = describe_image_with_llm(pil_image)
        
        # Check if logo/icon
        description_lower = description.lower()
        logo_indicators = ['logo:', 'icon:', 'logo', 'icon', 'branding', 'watermark', 'trademark',
                          'stylized letter', 'stylized text', 'word "', "word '"]
        if any(indicator in description_lower for indicator in logo_indicators):
            logger.info(f"Skipping logo/icon image: {file_path.name} - {description[:50]}...")
            return [{
                "doc_id": base_doc_id,
                "doc_type": "markdown",
                "content": f"[Skipped logo/icon: {file_path.name}]",
                "position": 0
            }]
        
        # Convert to base64
        buffer = io.BytesIO()
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        pil_image.save(buffer, format="JPEG", quality=95)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        image_id = f"{base_doc_id}_image_1"
        
        # Return ONE document + separate image storage entry
        # Use doc_type="image" to trigger SingleChunker (NEVER splits)
        # This preserves [IMAGE_REF:] marker for UI display
        content = f"{description}\n\n[IMAGE_REF:{image_id}]"
        
        return [
            {
                "doc_id": base_doc_id,
                "doc_type": "image",  # Triggers SingleChunker - always 1 chunk
                "content": content,
                "position": 0
            },
            {
                "doc_id": image_id,
                "doc_type": "image",
                "image_description": description,
                "image_data": image_base64,
                "image_format": "jpg",
                "parent_doc": base_doc_id,
                "page_number": 0,
                "width": pil_image.width,
                "height": pil_image.height,
                "position": 1
            }
        ]
        
    except Exception as e:
        logger.error(f"Error extracting image: {e}")
        return [{
            "doc_id": base_doc_id,
            "doc_type": "markdown",
            "content": f"[Image extraction failed: {str(e)}]",
            "position": 0
        }]


def extract_text_from_file(file_path, graphname=None):
    """
    Extract text content from a file based on its extension.
    
    LEGACY/OLD APPROACH: Used for backward compatibility with JSONL-based loading.
    For new direct loading approach, use extract_text_from_file_with_images_as_docs() instead.
    
    Args:
        file_path (str or Path): Path to the file to extract text from
        graphname (str): Graph name for organizing images by graph (for OLD img:// protocol)
        
    Returns:
        str: Extracted text content (with img:// references for images)
        
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
    NEW STRATEGY: Most files use 'markdown' for flexible chunking via MarkdownChunker.
    
    Returns chunker types that match the available chunkers in ECC:
    - 'html' for HTML files -> HTMLChunker
    - 'image' for image files -> No chunking (bypass)
    - 'markdown' for most other files -> MarkdownChunker (flexible, handles text well)
    
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
    elif extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']:
        # Images should not be chunked - treat as single content
        return 'image'
    else:
        # Most file types use markdown chunker for flexible semantic splitting
        # This includes: .md, .txt, .pdf, .docx, .csv, .json, .xml, etc.
        return 'markdown'

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

