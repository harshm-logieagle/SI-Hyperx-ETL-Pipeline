# Call Analytics Extraction System Documentation

## Overview
The `level_reasons_extractor.py` script is a comprehensive tool for analyzing customer call recordings. It utilizes Large Language Models (LLMs) and speech-to-text technology to transcribe calls, extract key metadata (intent, sentiment, products mentioned), and traverse a hierarchical decision tree to determine the specific conversational journey (reason paths).

The system is designed for high accuracy through fuzzy string matching, hierarchical validation, and a "backfilling" mechanism to ensure consistency between extracted products and the decision tree.

---

## 1. System Architecture 

The core processing follows a multi-step pipeline:
1.  **Data Retrieval**: Fetches call details (URL, Brand, Outlet ID) and the brand-specific decision tree from the database. It also retrieves the associated outlet's **state** for localized logic.
2.  **Language Detection**: Calls a specialized internal API to detect the language of the call recording, using the outlet's state as optional context.
3.  **Transcription**: Uses `WHISPER-LARGE-V3` via Groq to convert the audio file into a text transcript.
3.  **Base Analytics**: Calls an LLM to perform initial high-level analysis, extracting reason types, overall sentiment, customer metadata, emotions, and mentioned products.
4.  **Tree Traversal**: Analyzes the transcript against a hierarchical workflow tree to identify structured traversal paths (Level 0, Level 1, etc.).
5.  **Validation & Rectification**: Uses Levenshtein distance to resolve transcription errors and ensures the extracted path is valid within the decision tree. It also uses "Product Templating" to allow products not explicitly in the tree to follow standard hierarchical structures.
6.  **Accuracy Check (Backfilling)**: Cross-references mentioned products from Base Analytics with the Traversal Paths to ensure no entities are missed.
7.  **Data Storage**: Saves the results into three primary database tables:
    *   `call_recording_analytics`: Summary and metadata.
    *   `call_product_mentions`: Granular product-level analysis.
    *   `level_reasons`: Structured hierarchy of the conversation reason.

---

## 2. Key Components & Logic

### 2.1 Fuzzy String Matching
*   **Functions**: `levenshtein_distance()`, `closest_match()`
*   **Purpose**: Handles spelling errors in transcripts. For example, if a transcript says "Scooty Pet", the system resolves it to "Scooty Pep" by comparing it against the master product list using string distance.

### 2.2 Hierarchical Validation (`rectify_and_validate_node_path`)
*   Ensures that every journey extracted by the LLM exists in the database's `decision_nodes`.
*   **Product Templating**: If the LLM identifies a valid product (verified against the database) but that product doesn't have its own branch in the tree, the system dynamically "borrows" the hierarchy from another product in the same category.

### 2.3 Accuracy Backfilling
*   Located in `process_transcript_with_tree`.
*   If a product is found in the "Base Analytics" phase but is missing from the "Traversal" phase, the system manually backfills a path for that product based on the tree structure. This ensures 100% relational consistency between what products were mentioned and what reasons are logged.

### 2.4 Database Storage Mapping
*   **`call_recording_analytics`**:
    *   Stores `transcript` as a JSON list for easy retrieval.
    *   Stores summary strings like `emotions` and `products` using a special delimiter `--||--`.
    *   Maps LLM output to columns like `customer_gender`, `customer_type`, `overall_sentiment`, etc.
*   **`call_product_mentions`**:
    *   Stores canonical product IDs, sentiment, and verbatim text.
    *   Automatically clears old records for the same call before saving to maintain idempotency.

---

## 3. Database Schema Requirements

The system interacts with the following primary tables:
*   `brands`: Maps brands to `master_outlet_id`.
*   `decision_nodes`: Stores the hierarchical tree.
*   `master_outlet_products`: Master list of products for matching.
*   `master_outlet_categories`: Category metadata for products.
*   `call_recording_analytics`: Primary analytics storage.
*   `call_product_mentions`: Relational product mentions.
*   `level_reasons`: The specific path taken in the decision tree.

---

## 4. Configuration

The script relies on a `.env` file containing:
*   `GROQ_API_KEY`: For LLM and Whisper access.
*   `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: Database credentials.

---

## 5. Execution

To process a specific call, set the `CALL_ID` in the main block and run:
```bash
python call_analytics/level_reasons_extractor.py
```
