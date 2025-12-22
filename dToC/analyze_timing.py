"""
Script to analyze timing data from processing runs.
Reads timing summary JSON files and displays performance metrics.
"""

import json
import os
import sys
from pathlib import Path

UPLOAD_FOLDER = "uploads"

def find_latest_timing_file():
    """Find the most recent timing summary file."""
    if not os.path.exists(UPLOAD_FOLDER):
        print(f"[ERROR] Upload folder '{UPLOAD_FOLDER}' not found.")
        return None
    
    timing_files = list(Path(UPLOAD_FOLDER).glob("*_timing_summary.json"))
    if not timing_files:
        print("[ERROR] No timing summary files found.")
        return None
    
    # Sort by modification time, most recent first
    latest_file = max(timing_files, key=lambda p: p.stat().st_mtime)
    return latest_file

def analyze_timing_file(file_path):
    """Analyze and display timing data from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("\n" + "="*100)
        print("TIMING ANALYSIS - Performance Metrics")
        print("="*100)
        print(f"File: {os.path.basename(file_path)}")
        print(f"Timestamp: {data.get('timestamp', 'N/A')}")
        print(f"File Prefix: {data.get('file_prefix', 'N/A')}")
        print("="*100)
        
        timing_summary = data.get('timing_summary', [])
        if not timing_summary:
            print("[WARNING] No timing data found in file.")
            return
        
        # Display in a formatted table
        print(f"\n{'Function':<35} {'Count':<8} {'Total (min)':<15} {'Avg (min)':<15} {'Max (min)':<15} {'Min (min)':<15}")
        print("-"*100)
        
        for stat in timing_summary:
            print(f"{stat['function']:<35} {stat['count']:<8} {stat['total_minutes']:<15.2f} {stat['average_minutes']:<15.2f} {stat['max_minutes']:<15.2f} {stat['min_minutes']:<15.2f}")
        
        print("-"*100)
        
        # Show top 5 slowest functions
        print("\n[TOP 5 SLOWEST FUNCTIONS BY TOTAL TIME]")
        print("-"*100)
        for i, stat in enumerate(timing_summary[:5], 1):
            print(f"{i}. {stat['function']}")
            print(f"   Total: {stat['total_minutes']:.2f} min ({stat['total_seconds']:.2f} sec)")
            print(f"   Average: {stat['average_minutes']:.2f} min per call")
            print(f"   Called: {stat['count']} times")
            print(f"   Max: {stat['max_minutes']:.2f} min, Min: {stat['min_minutes']:.2f} min")
            print()
        
        # Calculate total processing time
        total_time = sum(stat['total_seconds'] for stat in timing_summary)
        print(f"[TOTAL PROCESSING TIME] {total_time / 60:.2f} minutes ({total_time:.2f} seconds)")
        print("="*100 + "\n")
        
    except FileNotFoundError:
        print(f"[ERROR] File not found: {file_path}")
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in file: {e}")
    except Exception as e:
        print(f"[ERROR] Error reading file: {e}")

def main():
    """Main function."""
    if len(sys.argv) > 1:
        # Use provided file path
        file_path = sys.argv[1]
        if not os.path.exists(file_path):
            print(f"[ERROR] File not found: {file_path}")
            return
        analyze_timing_file(file_path)
    else:
        # Find latest timing file
        latest_file = find_latest_timing_file()
        if latest_file:
            analyze_timing_file(latest_file)

if __name__ == "__main__":
    main()

