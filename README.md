# Disclaimer

This project is created **for educational purposes only**.

You are free to use, modify, and distribute the code **at your own risk**.  
The developer or contributors **are not responsible for any damage, data loss, or misuse** resulting from the use of this code or any part of it.

By using this project, you agree that it comes **as-is, without any warranty** of any kind.

---

**Purpose:** To learn, explore, and demonstrate programming or technical concepts only.  
**Do not use this code in production environments** or for any illegal or unethical activities.


# US-RealEstate-Metadata
Real Estate Metadata Extractor is a Python-based tool that extracts property listing metadata from Zillow XML sitemaps and exports to CSV/JSON files. It features a user-friendly web interface with real-time progress tracking, multi-threaded concurrent processing, and pause/resume controls.


 REAL ESTATE METADATA EXTRACT   ---> Quick Start Guide
-------------------------------------------------------------------------------

📌 WHAT DOES THIS TOOL DO?
--------------------------------------------------------------------------------
Extracts property listing data from Zillow XML sitemaps and saves it as CSV 
or JSON files. Features a beautiful web interface for easy control and live 
monitoring of extraction progress.


✅ REQUIREMENTS
--------------------------------------------------------------------------------
• Windows 10/11, macOS, or Linux operating system
• Python 3.8 or newer installed
• Active internet connection
• At least 2GB free disk space for output files


🚀 INSTALLATION STEPS
--------------------------------------------------------------------------------
1. Save the extractor.py file to a folder on your computer

2. Open Command Prompt (Windows) or Terminal (Mac/Linux) in that folder
   Windows: Shift + Right-click in folder → "Open PowerShell window here"
   Mac: Right-click folder → Services → "New Terminal at Folder"

3. Run the command:
   python extractor.py --webui

4. Dependencies install automatically on first run
   (requests, flask, and pytz packages)

5. Open your web browser and go to:
   http://localhost:5000


🎯 HOW TO EXTRACT DATA
--------------------------------------------------------------------------------

STEP 1: Select Sitemaps
------------------------
• Click on the sitemap dropdown menu
• Hold CTRL (Windows) or CMD (Mac) to select multiple sitemaps
• Choose "✅ SELECT ALL" for everything, or pick specific categories:

  HDP (Home Detail Pages):
  - For Sale By Agent
  - For Sale By Owner
  - New Construction
  - Auction Properties
  - Pending Sales
  - Recently Sold
  - For Rent
  - Off Market
  - Other Listings

  BDP (Building Detail Pages):
  - Buildings
  - Apartments


STEP 2: Configure Settings
---------------------------
• Output Format: Choose between CSV or JSON
  - CSV: Best for Excel, Google Sheets, data analysis
  - JSON: Best for developers, APIs, databases

• Concurrent Workers: Set number of parallel downloads (3-10)
  - 3 Workers: Safe, slower, good for weak internet
  - 5 Workers: Recommended default
  - 8-10 Workers: Fast, requires good internet

• Output Directory (Optional):
  - Leave blank to save in current folder
  - Or enter path like: C:\output or /home/user/data


STEP 3: Start Extraction
-------------------------
• Click the "🚀 Start Extraction" button
• Watch the live progress bar fill up
• Monitor logs in the black console box
• See extraction statistics update in real-time:
  - Sitemaps processed
  - Total listings extracted
  - Time elapsed
  - Current sitemap being processed


STEP 4: Control Extraction
---------------------------
• ⏸️ PAUSE: Temporarily stop extraction (resume anytime)
• ▶️ RESUME: Continue from where you paused
• ⏹️ STOP: Completely stop extraction


STEP 5: Download Files
-----------------------
• Files appear in "Generated Files" section as they complete
• Click 📥 Download icon next to each file
• Files are also automatically saved to your output folder
• On Windows, output folder opens automatically when done


💡 PRO TIPS
--------------------------------------------------------------------------------
⚡ Use 5-8 workers for optimal extraction speed

📊 CSV format works great with Excel and Google Sheets - just open directly

🔄 JSON format is perfect for developers working with databases or APIs

⏸️ You can pause anytime and resume later without losing any data

📁 Windows users: Output folder auto-opens when extraction completes

🕐 Large extractions may take 30-60 minutes depending on categories selected

💾 Each sitemap category creates a separate file with timestamp


🆘 TROUBLESHOOTING
--------------------------------------------------------------------------------

❌ ERROR: "Port 5000 already in use"
   SOLUTION: Run with different port:
   python extractor.py --webui --port 8000
   Then open http://localhost:8000


❌ ERROR: "No sitemaps found"
   SOLUTION: Check your internet connection
   Try selecting fewer categories at once


❌ ERROR: "Script won't start"
   SOLUTION: Manually install dependencies:
   python -m pip install requests flask pytz


❌ ERROR: "ModuleNotFoundError"
   SOLUTION: Install missing package:
   python -m pip install [package_name]


❌ SLOW EXTRACTION
   SOLUTION: Increase workers to 8-10
   Check your internet speed


📝 NEED MORE HELP?
   Check the log file in your output folder:
   extraction_[timestamp].log
   It contains detailed information about any errors


📧 SUPPORT
--------------------------------------------------------------------------------
For technical issues, check the log files generated during extraction.
Each run creates a detailed log: extraction_YYYYMMDD_HHMMSS.log



 REAL ESTATE METADATA EXTRACT   ---> Technical Architecture & Deep Dive
--------------------------------------------------------------------------------

🏗️ SYSTEM ARCHITECTURE
--------------------------------------------------------------------------------

The system follows a multi-layered architecture:

CLIENT LAYER (Web Browser)
    ↓ HTTP Requests (GET/POST)
WEB SERVER (Flask Application)
    ↓ Background Threading
EXTRACTION ENGINE (Python Core)
    ↓ HTTP Downloads (gzipped XML)
ZILLOW SERVERS (XML Sitemaps)
    ↓ Parse, Transform, Deduplicate
OUTPUT FILES (CSV/JSON on Disk)


⚙️ HOW EXTRACTION WORKS
--------------------------------------------------------------------------------

PHASE 1: Parent Sitemap Fetch
------------------------------
1. User selects categories (e.g., "For Rent", "For Sale By Agent")
2. System sends HTTP GET request to parent sitemap URL
3. Downloads and parses parent XML (contains ~50-200 child URLs)
4. Extracts all child sitemap URLs
5. Total child sitemaps determined (shows as "X/Y Sitemaps")


PHASE 2: Child Sitemap Processing
----------------------------------
1. Each child sitemap URL downloaded (typically gzipped XML)
2. Each contains 40,000-50,000 individual property URLs
3. Multi-threaded processing with configurable workers (default 5)
4. Downloads happen in parallel for maximum speed
5. Each worker processes one sitemap at a time


PHASE 3: URL Parsing
---------------------
Property URLs follow this pattern:
https://www.zillow.com/homes/123-Main-St-City-CA-12345/456_zpid/

Parser extracts:
• property_id: "456" (from _zpid suffix)
• address: "123 Main St" (street portion)
• city: "City" (parsed from URL slug)
• state: "CA" (2-letter state code)
• zipcode: "12345" (5-digit ZIP)
• last_modified: UTC timestamp from XML
• last_modified_est: Converted to EST timezone


PHASE 4: Deduplication
-----------------------
• property_id tracked in memory set
• Duplicate listings automatically skipped
• Ensures each property appears only once
• Critical for "ALL" selections with overlapping categories


PHASE 5: Data Export
---------------------
• Listings batched per sitemap category
• One file per sitemap child (e.g., "listings_CA_20251024_173045.csv")
• CSV: Direct Excel compatibility, comma-separated
• JSON: Structured array of objects, indent=2 for readability
• Files written incrementally (no memory overflow)
• Timestamp in filename prevents overwrites


📊 DATA FIELDS EXTRACTED
--------------------------------------------------------------------------------

Field Name          Type       Description
-----------------------------------------------------------------------------
property_id         String     Unique Zillow property identifier
listing_url         String     Full URL to property page
address             String     Street address (parsed from URL)
city                String     City name (parsed from URL)
state               String     2-letter state code (e.g., CA, NY, TX)
zipcode             String     5-digit ZIP code
last_modified       String     UTC timestamp (ISO 8601 format)
last_modified_est   String     EST timestamp (formatted for readability)


🔥 PERFORMANCE FEATURES
--------------------------------------------------------------------------------

MULTI-THREADING
---------------
• Concurrent processing with ThreadPoolExecutor
• Default 5 workers = 5x faster than single-threaded
• Thread-safe duplicate tracking with Python sets
• Automatic retry on network failures (3 attempts)
• Random user-agent rotation to avoid rate limiting


MEMORY OPTIMIZATION
-------------------
• Streaming XML parsing (xml.etree.ElementTree)
• Incremental file writes (no memory buffering)
• Only 200 most recent log entries kept in memory
• Garbage collection after each sitemap completion
• Suitable for extracting millions of listings


NETWORK OPTIMIZATION
--------------------
• Gzip decompression for faster downloads
• Connection pooling via requests.Session()
• 0.3-0.8 second delays between requests (polite scraping)
• Automatic decompression of gzipped XML sitemaps
• 30-second timeout per request (prevents hanging)


🔧 TECHNICAL STACK
--------------------------------------------------------------------------------

BACKEND
-------
• Python 3.8+ (3.14 compatible)
• Flask 2.x (web framework)
• requests (HTTP library)
• pytz (timezone conversion)
• xml.etree.ElementTree (XML parsing)
• gzip (decompression)
• concurrent.futures (threading)


FRONTEND
--------
• Pure HTML5 + CSS3 (no frameworks)
• Vanilla JavaScript (ES6+)
• Real-time status polling (500ms intervals)
• Responsive design (mobile-friendly)
• Progress bar with CSS transitions


DATA FORMATS
------------
• Input: XML Sitemaps (gzipped, namespace-aware)
• Output CSV: UTF-8 encoding, comma-separated
• Output JSON: UTF-8 encoding, pretty-printed
• Logs: Plain text, timestamped entries


📈 PERFORMANCE METRICS
--------------------------------------------------------------------------------

TYPICAL EXTRACTION SPEEDS
-------------------------
• Single worker: ~10,000 listings/minute
• 5 workers (default): ~40,000-50,000 listings/minute
• 10 workers (fast): ~80,000-100,000 listings/minute

DATASET SIZES
-------------
• Single category (e.g., For Rent): 1-5 million listings
• ALL categories: 10-20 million listings
• File size: 200-500 bytes per listing
• Total storage: 2-10 GB for complete extraction


TIME ESTIMATES
--------------
• Single category: 15-30 minutes (5 workers)
• 3-4 categories: 45-90 minutes (5 workers)
• ALL categories: 4-8 hours (5 workers)
• ALL categories: 2-4 hours (10 workers)


🛠️ ADVANCED CUSTOMIZATION
--------------------------------------------------------------------------------

CHANGE PORT
-----------
python extractor.py --webui --port 8000


PROGRAMMATIC USE (No Web UI)
-----------------------------
from extractor import RealEstateExtractor

extractor = RealEstateExtractor(
    output_dir="/path/to/output",
    sitemap_urls=["https://..."],
    output_format="csv",
    max_workers=10,
    webui_mode=False
)
extractor.run()


OUTPUT DIRECTORY STRUCTURE
--------------------------
output_folder/
├── extraction_20251024_170530.log
├── listings_CA_20251024_170545.csv
├── listings_NY_20251024_170612.csv
├── listings_TX_20251024_170638.csv
└── ...


🔍 CODE ARCHITECTURE
--------------------------------------------------------------------------------

CLASS: RealEstateExtractor
---------------------------
Main extraction engine

Methods:
• __init__() - Initialize configuration
• setup_logging() - Configure logging handlers
• download_sitemap() - Fetch and decompress XML
• parse_listing_url() - Extract data from URL
• extract_listings_from_sitemap() - Process one sitemap
• save_to_csv() - Export to CSV format
• save_to_json() - Export to JSON format
• process_sitemap() - Worker thread entry point
• run() - Main execution loop


FUNCTION: get_sitemap_children()
---------------------------------
Fetches child sitemap URLs from parent sitemap
Returns: List of child URLs


FLASK ROUTES
------------
GET  /              - Render main UI
GET  /get-children  - Fetch child sitemaps
POST /start         - Begin extraction
POST /pause         - Pause extraction
POST /resume        - Resume extraction
POST /stop          - Stop extraction
GET  /status        - Get current status (JSON)
GET  /download      - Download generated file


📋 TROUBLESHOOTING GUIDE
--------------------------------------------------------------------------------

COMMON ERRORS AND SOLUTIONS
----------------------------

1. IMPORT ERRORS
   Problem: ModuleNotFoundError: No module named 'X'
   Solution: pip install [module_name]

2. PORT CONFLICTS
   Problem: Address already in use
   Solution: Use different port with --port flag

3. NETWORK TIMEOUTS
   Problem: ReadTimeout or ConnectionError
   Solution: Reduce workers, check internet connection

4. MEMORY ERRORS
   Problem: MemoryError on large extractions
   Solution: Process fewer categories at once

5. PERMISSION ERRORS
   Problem: Can't write to output directory
   Solution: Run with administrator privileges or change directory

6. ENCODING ERRORS
   Problem: UnicodeDecodeError
   Solution: Already handled (UTF-8), shouldn't occur


PERFORMANCE OPTIMIZATION
------------------------
• Increase workers for faster extraction (8-10 for good internet)
• Use SSD for output directory (faster writes)
• Close unnecessary applications (frees memory)
• Use wired connection instead of WiFi (more stable)
• Process categories separately for very large extractions


🔐 ETHICAL CONSIDERATIONS
--------------------------------------------------------------------------------
• Respects robots.txt and sitemap protocols
• Polite delays between requests (0.3-0.8s)
• Uses standard Googlebot user-agent
• Only accesses public XML sitemaps
• No scraping of actual property pages
• No bypassing of rate limits or CAPTCHAs


📝 FILE NAMING CONVENTION
--------------------------------------------------------------------------------
Format: listings_[CATEGORY]_[TIMESTAMP].[EXT]

Examples:
• listings_CA_20251024_173045.csv
• listings_for-rent_20251024_173112.json
• extraction_20251024_173000.log

Timestamp format: YYYYMMDD_HHMMSS (24-hour)


🚀 FUTURE ENHANCEMENTS
--------------------------------------------------------------------------------
• Database export (MySQL, PostgreSQL)
• Excel (.xlsx) format support
• Resume interrupted extractions
• Advanced filtering by state/city
• Email notifications on completion
• Scheduled/automated extractions
• API endpoint for programmatic access


================================================================================
                         END OF DOCUMENTATION
================================================================================
