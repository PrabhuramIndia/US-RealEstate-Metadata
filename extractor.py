#!/usr/bin/env python3
"""
Real Estate Listing Metadata Extraction System
Extracts property data from Zillow XML sitemaps
Supports CSV and JSON export formats
Author: Real Estate Data Tools
Version: 2.0
"""

import sys
import subprocess

def check_and_install_dependencies():
    """
    Check for required dependencies and install if missing
    """
    required_packages = {
        'requests': 'requests',
        'pytz': 'pytz',
        'flask': 'flask'
    }
    
    missing_packages = []
    
    print("\n" + "="*60)
    print("🔍 Checking for required dependencies...")
    print("="*60)
    
    for package_import, package_install in required_packages.items():
        try:
            __import__(package_import)
            print(f"  ✓ {package_install} is installed")
        except ImportError:
            missing_packages.append(package_install)
            print(f"  ✗ {package_install} is NOT installed")
    
    if missing_packages:
        print(f"\n📦 Installing {len(missing_packages)} missing package(s)...")
        try:
            for package in missing_packages:
                print(f"  📥 Installing {package}...")
                subprocess.check_call(
                    [sys.executable, '-m', 'pip', 'install', package],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            print("\n✅ All dependencies successfully installed!")
        except Exception as e:
            print(f"❌ Error installing dependencies: {e}")
            sys.exit(1)
    else:
        print("\n✅ All dependencies are already installed!")
    
    print("="*60 + "\n")

# Run dependency check
check_and_install_dependencies()

# Import required modules
import requests
import gzip
import xml.etree.ElementTree as ET
import csv
import json
import re
import platform
import argparse
import logging
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse
import os
import time
import pytz
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import threading
from flask import Flask, render_template_string, request, jsonify, send_from_directory


# Global extraction status dictionary
extraction_status = {
    'running': False,
    'progress': 0,
    'current_category': '',
    'total_categories': 0,
    'processed_categories': 0,
    'total_properties': 0,
    'logs': [],
    'files': [],
    'start_time': None,
    'end_time': None,
    'output_dir': None,
    'error': None
}

# Global pause flag
extraction_paused = False


class WebUILogger(logging.Handler):
    """
    Custom logging handler for Web UI
    Captures log messages and stores them for display in the web interface
    """
    def emit(self, record):
        log_entry = self.format(record)
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_log = f"[{timestamp}] {log_entry}"
        extraction_status['logs'].append(formatted_log)
        
        # Keep only the last 200 log entries to prevent memory issues
        if len(extraction_status['logs']) > 200:
            extraction_status['logs'] = extraction_status['logs'][-200:]


class RealEstateExtractor:
    """
    Main extraction class for processing real estate listings from XML sitemaps
    """
    
    def __init__(self, output_dir=None, sitemap_urls=None, max_workers=5, 
                 output_format='csv', webui_mode=False):
        """
        Initialize the extractor
        
        Args:
            output_dir: Directory to save output files
            sitemap_urls: List of sitemap URLs to process
            max_workers: Number of concurrent workers
            output_format: Output format (csv or json)
            webui_mode: Whether running in web UI mode
        """
        # Initialize HTTP session
        self.session = requests.Session()
        
        # User agents to rotate for better success rate
        self.bot_agents = [
            'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Safari/537.36',
        ]
        
        # Timezone configuration
        self.utc_tz = pytz.UTC
        self.est_tz = pytz.timezone('US/Eastern')
        
        # Configuration parameters
        self.max_workers = max_workers
        self.output_format = output_format
        self.webui_mode = webui_mode
        
        # Tracking variables
        self.saved_files = []
        self.total_properties = 0
        self.sitemap_urls = sitemap_urls or []
        
        # Setup output directory
        if output_dir:
            self.output_dir = os.path.abspath(output_dir)
        else:
            self.output_dir = os.getcwd()
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Track seen property IDs to avoid duplicates
        self.seen_ids = set()
        
        # Setup logging
        self.setup_logging()
        
        # Update web UI status
        if webui_mode:
            extraction_status['output_dir'] = self.output_dir
    
    def setup_logging(self):
        """
        Setup logging system with file and console handlers
        """
        log_filename = os.path.join(
            self.output_dir, 
            f'extraction_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
        
        self.logger = logging.getLogger('RealEstateExtractor')
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        # File handler for persistent logs
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler for terminal output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Web UI handler if in web mode
        if self.webui_mode:
            web_handler = WebUILogger()
            web_handler.setFormatter(formatter)
            self.logger.addHandler(web_handler)
        
        self.logger.info(f"Log file created: {log_filename}")
    
    def convert_utc_to_est(self, utc_datetime_str):
        """
        Convert UTC datetime string to EST timezone
        
        Args:
            utc_datetime_str: UTC datetime string in ISO format
            
        Returns:
            datetime object in EST timezone or None if conversion fails
        """
        if not utc_datetime_str:
            return None
        
        try:
            # Parse UTC datetime
            utc_dt = datetime.strptime(
                utc_datetime_str.replace('Z', ''), 
                '%Y-%m-%dT%H:%M:%S'
            )
            
            # Localize to UTC
            utc_dt = self.utc_tz.localize(utc_dt)
            
            # Convert to EST
            return utc_dt.astimezone(self.est_tz)
        except Exception as e:
            self.logger.debug(f"Failed to convert datetime: {e}")
            return None
    
    def download_sitemap(self, url):
        """
        Download and decompress sitemap from URL
        
        Args:
            url: Sitemap URL to download
            
        Returns:
            Decompressed sitemap content as string or None if failed
        """
        try:
            # Set random user agent
            self.session.headers['User-Agent'] = random.choice(self.bot_agents)
            
            # Download sitemap
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Try to decompress if gzipped
            try:
                with gzip.GzipFile(fileobj=BytesIO(response.content)) as gz:
                    content = gz.read().decode('utf-8')
            except (OSError, gzip.BadGzipFile):
                # Not gzipped, use as-is
                content = response.text
            
            return content
        except Exception as e:
            self.logger.error(f"Failed to download sitemap {url}: {e}")
            return None
    
    def parse_listing_url(self, url):
        """
        Parse listing URL to extract property details
        
        Args:
            url: Full listing URL
            
        Returns:
            Dictionary with property details or None if parsing failed
        """
        try:
            # Parse URL path
            path = urlparse(url).path
            parts = path.strip('/').split('/')
            
            if len(parts) >= 3:
                address_part = parts[1]
                id_part = parts[2]
                
                # Extract property ID
                property_id = id_part.replace('_zpid', '')
                
                # Parse address format: street-city-STATE-ZIPCODE
                pattern = r'^(.+?)-([A-Z]{2})-(\d{5})$'
                match = re.search(pattern, address_part)
                
                if match:
                    address_city = match.group(1)
                    state = match.group(2)
                    zipcode = match.group(3)
                    
                    # Split address and city
                    parts_list = address_city.split('-')
                    if len(parts_list) >= 2:
                        city = ' '.join(parts_list[-2:])
                        address = ' '.join(parts_list[:-2])
                    else:
                        address = address_city.replace('-', ' ')
                        city = ''
                    
                    return {
                        'property_id': property_id,
                        'address': address,
                        'city': city,
                        'state': state,
                        'zipcode': zipcode
                    }
        except Exception as e:
            self.logger.debug(f"Failed to parse URL {url}: {e}")
        
        return None
    
    def extract_listings_from_sitemap(self, sitemap_url):
        """
        Extract all listings from a sitemap
        
        Args:
            sitemap_url: URL of the sitemap to process
            
        Returns:
            List of listing dictionaries
        """
        # Download sitemap content
        content = self.download_sitemap(sitemap_url)
        if not content:
            return []
        
        # Parse XML
        root = ET.fromstring(content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        listings = []
        urls = root.findall('ns:url', namespace)
        total_urls = len(urls)
        
        self.logger.info(f"Processing {total_urls} URLs from sitemap...")
        
        # Process each URL in sitemap
        for idx, url_elem in enumerate(urls, 1):
            # Log progress every 10,000 URLs
            if idx % 10000 == 0:
                self.logger.info(f"Processed {idx}/{total_urls} URLs...")
            
            # Extract URL and last modified date
            loc = url_elem.find('ns:loc', namespace)
            lastmod = url_elem.find('ns:lastmod', namespace)
            
            if loc is not None:
                listing_url = loc.text
                last_modified_utc = lastmod.text if lastmod is not None else ''
                last_modified_est = self.convert_utc_to_est(last_modified_utc)
                
                # Parse listing details from URL
                parsed = self.parse_listing_url(listing_url)
                
                if parsed:
                    # Check for duplicates
                    if parsed['property_id'] in self.seen_ids:
                        continue
                    
                    # Create listing record
                    listing = {
                        'property_id': parsed['property_id'],
                        'listing_url': listing_url,
                        'address': parsed['address'],
                        'city': parsed['city'],
                        'state': parsed['state'],
                        'zipcode': parsed['zipcode'],
                        'last_modified': last_modified_utc,
                        'last_modified_est': last_modified_est
                    }
                    
                    # Add to seen IDs
                    self.seen_ids.add(parsed['property_id'])
                    listings.append(listing)
        
        self.logger.info(f"✓ Extracted {len(listings)} unique listings")
        return listings
    
    def save_to_csv(self, listings, category):
        """
        Save listings to CSV file
        
        Args:
            listings: List of listing dictionaries
            category: Category name for filename
            
        Returns:
            Path to saved file or None if failed
        """
        if not listings:
            return None
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"listings_{category}_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        # CSV field names
        fields = [
            'property_id', 
            'listing_url', 
            'address', 
            'city', 
            'state', 
            'zipcode', 
            'last_modified', 
            'last_modified_est'
        ]
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                
                for listing in listings:
                    row = {}
                    for field in fields:
                        value = listing.get(field, '')
                        
                        # Format EST datetime if present
                        if field == 'last_modified_est' and value:
                            value = value.strftime('%Y-%m-%d %H:%M:%S %Z')
                        
                        row[field] = value
                    
                    writer.writerow(row)
            
            # Track saved file
            self.saved_files.append(filename)
            
            if self.webui_mode:
                extraction_status['files'].append(filename)
            
            self.logger.info(f"✓ Saved {len(listings)} records to CSV: {filename}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Failed to save CSV file: {e}")
            return None
    
    def save_to_json(self, listings, category):
        """
        Save listings to JSON file
        
        Args:
            listings: List of listing dictionaries
            category: Category name for filename
            
        Returns:
            Path to saved file or None if failed
        """
        if not listings:
            return None
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"listings_{category}_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Prepare data for JSON export
            data = []
            for listing in listings:
                item = dict(listing)
                
                # Convert datetime to string for JSON serialization
                if item.get('last_modified_est'):
                    item['last_modified_est'] = item['last_modified_est'].strftime('%Y-%m-%d %H:%M:%S %Z')
                
                data.append(item)
            
            # Write JSON file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Track saved file
            self.saved_files.append(filename)
            
            if self.webui_mode:
                extraction_status['files'].append(filename)
            
            self.logger.info(f"✓ Saved {len(listings)} records to JSON: {filename}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Failed to save JSON file: {e}")
            return None
    
    def process_sitemap(self, sitemap_url, current, total):
        """
        Process a single sitemap
        
        Args:
            sitemap_url: URL of sitemap to process
            current: Current sitemap number
            total: Total number of sitemaps
        """
        global extraction_paused
        
        # Handle pause state
        while extraction_paused:
            time.sleep(1)
            if not extraction_status['running']:
                return
        
        # Handle stop state
        if not extraction_status['running']:
            return
        
        # Extract category name from URL
        category = sitemap_url.split('/')[-1].replace('.xml.gz', '')
        
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"[{current}/{total}] Processing: {category}")
        self.logger.info(f"{'='*50}")
        
        # Update web UI status
        if self.webui_mode:
            extraction_status['current_category'] = category
            extraction_status['processed_categories'] = current
            extraction_status['progress'] = int((current / total) * 100)
        
        # Extract listings
        listings = self.extract_listings_from_sitemap(sitemap_url)
        
        # Save listings
        if self.output_format == 'csv':
            self.save_to_csv(listings, category)
        elif self.output_format == 'json':
            self.save_to_json(listings, category)
        
        # Update totals
        self.total_properties += len(listings)
        
        if self.webui_mode:
            extraction_status['total_properties'] = self.total_properties
    
    def run(self):
        """
        Main execution method
        """
        start_time = time.time()
        
        if self.webui_mode:
            extraction_status['start_time'] = datetime.now().isoformat()
        
        self.logger.info("="*60)
        self.logger.info("Real Estate Listing Metadata Extraction")
        self.logger.info("="*60)
        self.logger.info(f"Output format: {self.output_format.upper()}")
        self.logger.info(f"Output directory: {self.output_dir}")
        self.logger.info(f"Concurrent workers: {self.max_workers}")
        
        if not self.sitemap_urls:
            self.logger.error("No sitemaps provided for extraction!")
            return
        
        total_sitemaps = len(self.sitemap_urls)
        
        if self.webui_mode:
            extraction_status['total_categories'] = total_sitemaps
        
        self.logger.info(f"Processing {total_sitemaps} sitemaps...\n")
        
        # Process sitemaps concurrently
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_sitemap, url, i+1, total_sitemaps): url 
                for i, url in enumerate(self.sitemap_urls)
            }
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Error processing sitemap: {e}")
        
        # Calculate execution time
        execution_time = time.time() - start_time
        minutes = int(execution_time // 60)
        seconds = int(execution_time % 60)
        
        self.logger.info("\n" + "="*60)
        self.logger.info("EXTRACTION COMPLETE!")
        self.logger.info(f"Execution time: {minutes}m {seconds}s")
        self.logger.info(f"Total listings extracted: {self.total_properties:,}")
        self.logger.info(f"Total files created: {len(self.saved_files)}")
        self.logger.info("="*60)
        
        if self.webui_mode:
            extraction_status['end_time'] = datetime.now().isoformat()
            extraction_status['running'] = False
        
        # Auto-open output folder on Windows
        if platform.system() == 'Windows' and self.saved_files:
            try:
                subprocess.run(['explorer', self.output_dir], check=False)
            except:
                pass


def get_sitemap_children(parent_url):
    """
    Fetch child sitemap URLs from parent sitemap
    
    Args:
        parent_url: URL of parent sitemap
        
    Returns:
        List of child sitemap URLs
    """
    try:
        response = requests.get(parent_url, timeout=30)
        response.raise_for_status()
        
        # Try to decompress if gzipped
        try:
            with gzip.GzipFile(fileobj=BytesIO(response.content)) as gz:
                content = gz.read().decode('utf-8')
        except:
            content = response.text
        
        # Parse XML
        root = ET.fromstring(content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        children = []
        for sitemap in root.findall('ns:sitemap', namespace):
            loc = sitemap.find('ns:loc', namespace)
            if loc is not None:
                children.append(loc.text)
        
        return children
    except Exception as e:
        print(f"Error fetching children from {parent_url}: {e}")
        return []
# Flask Web Application
app = Flask(__name__)

# HTML Template for Web UI
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real Estate Metadata Extractor</title>
    <style>
        /* Reset and Base Styles */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        /* Container Styles */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        
        /* Header Styles */
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        /* Content Area */
        .content {
            padding: 30px;
        }
        
        /* Form Styles */
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
            font-size: 14px;
        }
        
        .form-group select,
        .form-group textarea,
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            font-family: inherit;
            transition: border-color 0.3s;
        }
        
        .form-group select:focus,
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .form-group select[multiple] {
            height: 250px;
        }
        
        /* Grid Layout for Form Rows */
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        /* Button Styles */
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 40px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin: 5px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn-pause {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        .btn-stop {
            background: linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%);
        }
        
        /* Status Panel */
        .status-panel {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 25px;
            margin-top: 30px;
            display: none;
        }
        
        .status-panel.active {
            display: block;
        }
        
        /* Progress Bar */
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin: 15px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 14px;
        }
        
        /* Statistics Grid */
        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin: 20px 0;
        }
        
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
        }
        
        .stat-label {
            color: #666;
            margin-top: 5px;
            font-size: 14px;
        }
        
        /* Log Console */
        .logs {
            background: #1e1e1e;
            color: #00ff00;
            padding: 20px;
            border-radius: 10px;
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            margin-top: 20px;
        }
        
        .log-entry {
            margin-bottom: 5px;
            line-height: 1.6;
        }
        
        /* Files List */
        .files-list {
            margin-top: 20px;
        }
        
        .file-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        
        .file-download {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.3s;
        }
        
        .file-download:hover {
            color: #764ba2;
        }
        
        /* Info Box */
        .info-box {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        
        /* Dropdown Styles */
        optgroup {
            font-weight: bold;
            font-size: 14px;
            padding: 5px;
        }
        
        option {
            padding: 8px;
        }
        
        /* Responsive Design */
        @media (max-width: 768px) {
            .form-row {
                grid-template-columns: 1fr;
            }
            
            .stats {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header Section -->
        <div class="header">
            <h1>🏠 Real Estate Metadata Extractor</h1>
            <p>Extract listing data from XML sitemaps to CSV/JSON</p>
        </div>
        
        <!-- Main Content -->
        <div class="content">
            <!-- Information Box -->
            <div class="info-box">
                <strong>📌 Quick Start Guide:</strong><br>
                1. Select one or more sitemaps (Hold CTRL/CMD for multiple)<br>
                2. Choose your output format (CSV or JSON)<br>
                3. Set number of concurrent workers<br>
                4. Click "Start Extraction"
            </div>
            
            <!-- Extraction Form -->
            <form id="extractForm">
                <!-- Sitemap Selection -->
                <div class="form-group">
                    <label>📂 Select Sitemaps (Hold CTRL/CMD to select multiple)</label>
                    <select name="sitemaps" id="sitemapSelect" multiple required>
                        <option value="ALL">✅ SELECT ALL SITEMAPS</option>
                        <optgroup label="🏘️ Home Detail Pages (HDP)">
                            <option value="https://www.zillow.com/xml/indexes/us/hdp/for-sale-by-agent.xml.gz">For Sale By Agent</option>
                            <option value="https://www.zillow.com/xml/indexes/us/hdp/for-sale-by-owner.xml.gz">For Sale By Owner</option>
                            <option value="https://www.zillow.com/xml/indexes/us/hdp/new-construction.xml.gz">New Construction</option>
                            <option value="https://www.zillow.com/xml/indexes/us/hdp/auction.xml.gz">Auction Properties</option>
                            <option value="https://www.zillow.com/xml/indexes/us/hdp/pending.xml.gz">Pending Sales</option>
                            <option value="https://www.zillow.com/xml/indexes/us/hdp/recently-sold.xml.gz">Recently Sold</option>
                            <option value="https://www.zillow.com/xml/indexes/us/hdp/for-rent.xml.gz">For Rent</option>
                            <option value="https://www.zillow.com/xml/indexes/us/hdp/off-market.xml.gz">Off Market</option>
                            <option value="https://www.zillow.com/xml/indexes/us/hdp/other.xml.gz">Other Listings</option>
                        </optgroup>
                        <optgroup label="🏢 Building Detail Pages (BDP)">
                            <option value="https://www.zillow.com/xml/indexes/us/bdp/buildings.xml.gz">Buildings</option>
                            <option value="https://www.zillow.com/xml/indexes/us/bdp/apartments.xml.gz">Apartments</option>
                        </optgroup>
                    </select>
                </div>
                
                <!-- Format and Workers Settings -->
                <div class="form-row">
                    <div class="form-group">
                        <label>📄 Output Format</label>
                        <select name="output_format">
                            <option value="csv">CSV (Comma-Separated Values)</option>
                            <option value="json">JSON (JavaScript Object Notation)</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>👷 Concurrent Workers</label>
                        <select name="workers">
                            <option value="3">3 Workers (Safe)</option>
                            <option value="5" selected>5 Workers (Recommended)</option>
                            <option value="8">8 Workers (Fast)</option>
                            <option value="10">10 Workers (Very Fast)</option>
                        </select>
                    </div>
                </div>
                
                <!-- Output Directory -->
                <div class="form-group">
                    <label>📁 Output Directory (optional - leave empty for current directory)</label>
                    <input type="text" name="output_dir" placeholder="e.g., C:\output or /home/user/output">
                </div>
                
                <!-- Submit Button -->
                <div style="text-align: center; margin-top: 30px;">
                    <button type="submit" class="btn" id="startBtn">🚀 Start Extraction</button>
                </div>
            </form>
            
            <!-- Status Panel (hidden by default) -->
            <div class="status-panel" id="statusPanel">
                <h2>📊 Extraction Status</h2>
                
                <!-- Control Buttons -->
                <div style="text-align: center; margin: 20px 0;">
                    <button type="button" class="btn btn-pause" id="pauseBtn" style="display:none;">⏸️ Pause</button>
                    <button type="button" class="btn" id="resumeBtn" style="display:none;">▶️ Resume</button>
                    <button type="button" class="btn btn-stop" id="stopBtn" style="display:none;">⏹️ Stop</button>
                </div>
                
                <!-- Progress Bar -->
                <div class="progress-bar">
                    <div class="progress-fill" id="progressBar" style="width: 0%;">0%</div>
                </div>
                
                <!-- Statistics Cards -->
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value" id="statCategories">0/0</div>
                        <div class="stat-label">Sitemaps</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="statProperties">0</div>
                        <div class="stat-label">Listings</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="statTime">0s</div>
                        <div class="stat-label">Time Elapsed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="statCurrent" style="font-size: 1em;">-</div>
                        <div class="stat-label">Current Sitemap</div>
                    </div>
                </div>
                
                <!-- Log Console -->
                <h3>📝 Live Extraction Logs</h3>
                <div class="logs" id="logs"></div>
                
                <!-- Files List -->
                <div class="files-list" id="filesList" style="display:none;">
                    <h3>📁 Generated Files</h3>
                    <div id="filesContainer"></div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- JavaScript -->
    <script>
        let statusInterval;
        let isPaused = false;
        
        // All available sitemaps
        const allSitemaps = [
            'https://www.zillow.com/xml/indexes/us/hdp/for-sale-by-agent.xml.gz',
            'https://www.zillow.com/xml/indexes/us/hdp/for-sale-by-owner.xml.gz',
            'https://www.zillow.com/xml/indexes/us/hdp/new-construction.xml.gz',
            'https://www.zillow.com/xml/indexes/us/hdp/auction.xml.gz',
            'https://www.zillow.com/xml/indexes/us/hdp/pending.xml.gz',
            'https://www.zillow.com/xml/indexes/us/hdp/recently-sold.xml.gz',
            'https://www.zillow.com/xml/indexes/us/hdp/for-rent.xml.gz',
            'https://www.zillow.com/xml/indexes/us/hdp/off-market.xml.gz',
            'https://www.zillow.com/xml/indexes/us/hdp/other.xml.gz',
            'https://www.zillow.com/xml/indexes/us/bdp/buildings.xml.gz',
            'https://www.zillow.com/xml/indexes/us/bdp/apartments.xml.gz',
        ];
        
        // Form submission handler
        document.getElementById('extractForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const selected = Array.from(document.getElementById('sitemapSelect').selectedOptions);
            
            // Determine which sitemaps to process
            let parents = selected.some(o => o.value === 'ALL') 
                ? allSitemaps 
                : selected.map(o => o.value).filter(v => v !== 'ALL');
            
            if (parents.length === 0) {
                alert('⚠️ Please select at least one sitemap');
                return;
            }
            
            // Disable start button and show loading
            document.getElementById('startBtn').disabled = true;
            document.getElementById('startBtn').textContent = '⏳ Loading sitemaps...';
            
            // Fetch child sitemaps from parent sitemaps
            let children = [];
            for (const parent of parents) {
                const res = await fetch(`/get-children?url=${encodeURIComponent(parent)}`);
                const data = await res.json();
                if (data.children) {
                    children = children.concat(data.children);
                }
            }
            
            if (children.length === 0) {
                alert('❌ No child sitemaps found!');
                document.getElementById('startBtn').disabled = false;
                document.getElementById('startBtn').textContent = '🚀 Start Extraction';
                return;
            }
            
            // Prepare payload
            const payload = {
                sitemaps: children,
                output_format: formData.get('output_format'),
                output_dir: formData.get('output_dir') || null,
                workers: parseInt(formData.get('workers'))
            };
            
            // Show status panel
            document.getElementById('statusPanel').classList.add('active');
            
            // Start extraction
            const res = await fetch('/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            
            const result = await res.json();
            if (result.error) {
                alert('❌ ERROR: ' + result.error);
                document.getElementById('startBtn').disabled = false;
                document.getElementById('startBtn').textContent = '🚀 Start Extraction';
            } else {
                // Start status polling
                statusInterval = setInterval(updateStatus, 500);
            }
        });
        
        // Pause button handler
        document.getElementById('pauseBtn').addEventListener('click', async () => {
            await fetch('/pause', {method: 'POST'});
            document.getElementById('pauseBtn').style.display = 'none';
            document.getElementById('resumeBtn').style.display = 'inline-block';
            isPaused = true;
        });
        
        // Resume button handler
        document.getElementById('resumeBtn').addEventListener('click', async () => {
            await fetch('/resume', {method: 'POST'});
            document.getElementById('pauseBtn').style.display = 'inline-block';
            document.getElementById('resumeBtn').style.display = 'none';
            isPaused = false;
        });
        
        // Stop button handler
        document.getElementById('stopBtn').addEventListener('click', async () => {
            if (confirm('Are you sure you want to stop the extraction?')) {
                await fetch('/stop', {method: 'POST'});
            }
        });
        
        // Update status from server
        async function updateStatus() {
            const res = await fetch('/status');
            const s = await res.json();
            
            // Update progress bar
            document.getElementById('progressBar').style.width = s.progress + '%';
            document.getElementById('progressBar').textContent = s.progress + '%';
            
            // Update statistics
            document.getElementById('statCategories').textContent = s.processed_categories + '/' + s.total_categories;
            document.getElementById('statProperties').textContent = s.total_properties.toLocaleString();
            document.getElementById('statCurrent').textContent = s.current_category || '-';
            
            // Update elapsed time
            if (s.start_time) {
                const elapsed = s.end_time 
                    ? (new Date(s.end_time) - new Date(s.start_time)) / 1000 
                    : (Date.now() - new Date(s.start_time)) / 1000;
                const m = Math.floor(elapsed / 60);
                const sec = Math.floor(elapsed % 60);
                document.getElementById('statTime').textContent = `${m}m ${sec}s`;
            }
            
            // Update logs
            const logsDiv = document.getElementById('logs');
            logsDiv.innerHTML = s.logs.slice(-50).map(l => `<div class="log-entry">${l}</div>`).join('');
            logsDiv.scrollTop = logsDiv.scrollHeight;
            
            // Update files list
            if (s.files.length > 0) {
                document.getElementById('filesList').style.display = 'block';
                document.getElementById('filesContainer').innerHTML = s.files.map(f =>
                    `<div class="file-item">
                        <span>📄 ${f}</span>
                        <a href="/download?file=${encodeURIComponent(f)}" class="file-download">📥 Download</a>
                    </div>`
                ).join('');
            }
            
            // Update control buttons visibility
            if (s.running) {
                document.getElementById('pauseBtn').style.display = isPaused ? 'none' : 'inline-block';
                document.getElementById('resumeBtn').style.display = isPaused ? 'inline-block' : 'none';
                document.getElementById('stopBtn').style.display = 'inline-block';
            } else {
                document.getElementById('pauseBtn').style.display = 'none';
                document.getElementById('resumeBtn').style.display = 'none';
                document.getElementById('stopBtn').style.display = 'none';
            }
            
            // Stop polling when extraction is complete
            if (!s.running && s.end_time) {
                clearInterval(statusInterval);
                document.getElementById('startBtn').disabled = false;
                document.getElementById('startBtn').textContent = '🚀 Start Extraction';
            }
        }
    </script>
</body>
</html>
'''


# Flask Routes

@app.route('/')
def index():
    """Render main page"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/get-children')
def get_children_route():
    """Get child sitemaps from parent sitemap"""
    parent_url = request.args.get('url')
    if not parent_url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        children = get_sitemap_children(parent_url)
        return jsonify({'parent': parent_url, 'children': children})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/start', methods=['POST'])
def start_extraction():
    """Start extraction process"""
    global extraction_status
    
    if extraction_status['running']:
        return jsonify({'error': 'Extraction already running'}), 400
    
    config = request.json
    extraction_status['running'] = True
    extraction_status['error'] = None
    extraction_status['logs'] = []
    extraction_status['files'] = []
    extraction_status['progress'] = 0
    extraction_status['total_properties'] = 0
    
    def run():
        try:
            extractor = RealEstateExtractor(
                output_dir=config.get('output_dir'),
                sitemap_urls=config.get('sitemaps', []),
                output_format=config.get('output_format', 'csv'),
                max_workers=int(config.get('workers', 5)),
                webui_mode=True
            )
            extractor.run()
        except Exception as e:
            extraction_status['logs'].append(f'[FATAL ERROR] {str(e)}')
            extraction_status['error'] = str(e)
            extraction_status['running'] = False
    
    # Start extraction in background thread
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    
    time.sleep(0.5)
    
    if extraction_status['error']:
        return jsonify({'error': extraction_status['error']}), 400
    
    return jsonify({'status': 'started'})


@app.route('/pause', methods=['POST'])
def pause_extraction():
    """Pause extraction"""
    global extraction_paused
    extraction_paused = True
    extraction_status['logs'].append('[PAUSED BY USER]')
    return jsonify({'status': 'paused'})


@app.route('/resume', methods=['POST'])
def resume_extraction():
    """Resume extraction"""
    global extraction_paused
    extraction_paused = False
    extraction_status['logs'].append('[RESUMED BY USER]')
    return jsonify({'status': 'resumed'})


@app.route('/stop', methods=['POST'])
def stop_extraction():
    """Stop extraction"""
    extraction_status['running'] = False
    extraction_status['logs'].append('[STOPPED BY USER]')
    return jsonify({'status': 'stopped'})


@app.route('/status')
def get_status():
    """Get current extraction status"""
    return jsonify(extraction_status)


@app.route('/download')
def download_file():
    """Download generated file"""
    filename = request.args.get('file')
    directory = extraction_status.get('output_dir', os.getcwd())
    return send_from_directory(directory, filename, as_attachment=True)


# Main Entry Point

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(
        description='Real Estate Metadata Extractor - Extract property data from XML sitemaps'
    )
    parser.add_argument(
        '--webui', 
        action='store_true', 
        help='Run Web UI (default: disabled)'
    )
    parser.add_argument(
        '--port', 
        type=int, 
        default=5000, 
        help='Web UI port (default: 5000)'
    )
    
    args = parser.parse_args()
    
    if args.webui:
        print("\n" + "="*60)
        print("🌐 Real Estate Metadata Extractor - Web UI")
        print("="*60)
        print(f"\n📍 Access the application at: http://localhost:{args.port}")
        print("\n✨ Features:")
        print("  • CSV & JSON export formats")
        print("  • Multi-threaded concurrent extraction")
        print("  • Pause/Resume/Stop controls")
        print("  • Live progress tracking")
        print("  • Real-time log monitoring")
        print("  • Automatic file downloads")
        print("\n⚠️  Press CTRL+C to stop the server")
        print("\n" + "="*60 + "\n")
        
        # Start Flask server
        app.run(
            host='0.0.0.0', 
            port=args.port, 
            debug=False, 
            threaded=True
        )
    else:
        print("\n" + "="*60)
        print("Real Estate Metadata Extractor")
        print("="*60)
        print("\nUsage:")
        print("  python extractor.py --webui              # Start on port 5000")
        print("  python extractor.py --webui --port 8000  # Start on custom port")
        print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    main()
