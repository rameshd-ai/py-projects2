"""
Script to parse timing information from terminal/log output.
Usage: Save your terminal output to a text file, then run:
    python parse_timing_from_log.py <log_file.txt>
"""

import re
import sys
from collections import defaultdict

def parse_timing_from_log(log_content):
    """Parse timing information from log text."""
    timing_data = defaultdict(list)
    
    # Pattern to match: [TIMING] FunctionName completed in X.XX seconds
    pattern1 = r'\[TIMING\]\s+(\w+)\s+completed\s+in\s+([\d.]+)\s+seconds'
    
    # Pattern to match: [TIMING] Starting FunctionName...
    # Then find the corresponding completion
    lines = log_content.split('\n')
    
    for line in lines:
        # Match completion messages
        match = re.search(pattern1, line, re.IGNORECASE)
        if match:
            func_name = match.group(1)
            time_seconds = float(match.group(2))
            timing_data[func_name].append(time_seconds)
    
    return timing_data

def analyze_timing_data(timing_data):
    """Analyze and display timing data."""
    if not timing_data:
        print("[ERROR] No timing data found in log file.")
        return
    
    # Calculate statistics
    summary = []
    for func_name, times in timing_data.items():
        if times:
            total_time = sum(times)
            avg_time = total_time / len(times)
            max_time = max(times)
            min_time = min(times)
            summary.append({
                "function": func_name,
                "count": len(times),
                "total_seconds": total_time,
                "total_minutes": total_time / 60.0,
                "average_seconds": avg_time,
                "average_minutes": avg_time / 60.0,
                "max_seconds": max_time,
                "max_minutes": max_time / 60.0,
                "min_seconds": min_time,
                "min_minutes": min_time / 60.0
            })
    
    # Sort by total time
    summary.sort(key=lambda x: x["total_seconds"], reverse=True)
    
    # Display results
    print("\n" + "="*100)
    print("TIMING ANALYSIS - Performance Metrics (Parsed from Log)")
    print("="*100)
    
    print(f"\n{'Function':<35} {'Count':<8} {'Total (min)':<15} {'Avg (min)':<15} {'Max (min)':<15} {'Min (min)':<15}")
    print("-"*100)
    
    for stat in summary:
        print(f"{stat['function']:<35} {stat['count']:<8} {stat['total_minutes']:<15.2f} {stat['average_minutes']:<15.2f} {stat['max_minutes']:<15.2f} {stat['min_minutes']:<15.2f}")
    
    print("-"*100)
    
    # Show top 5 slowest functions
    print("\n[TOP 5 SLOWEST FUNCTIONS BY TOTAL TIME]")
    print("-"*100)
    for i, stat in enumerate(summary[:5], 1):
        print(f"{i}. {stat['function']}")
        print(f"   Total: {stat['total_minutes']:.2f} min ({stat['total_seconds']:.2f} sec)")
        print(f"   Average: {stat['average_minutes']:.2f} min per call")
        print(f"   Called: {stat['count']} times")
        print(f"   Max: {stat['max_minutes']:.2f} min, Min: {stat['min_minutes']:.2f} min")
        print()
    
    # Calculate total processing time
    total_time = sum(stat['total_seconds'] for stat in summary)
    print(f"[TOTAL PROCESSING TIME] {total_time / 60:.2f} minutes ({total_time:.2f} seconds)")
    print("="*100 + "\n")

def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python parse_timing_from_log.py <log_file.txt>")
        print("\nOr paste your terminal output here (press Ctrl+D or Ctrl+Z when done):")
        try:
            log_content = sys.stdin.read()
            if log_content:
                timing_data = parse_timing_from_log(log_content)
                analyze_timing_data(timing_data)
        except KeyboardInterrupt:
            print("\n[ERROR] Input cancelled.")
    else:
        log_file = sys.argv[1]
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
            timing_data = parse_timing_from_log(log_content)
            analyze_timing_data(timing_data)
        except FileNotFoundError:
            print(f"[ERROR] File not found: {log_file}")
        except Exception as e:
            print(f"[ERROR] Error reading file: {e}")

if __name__ == "__main__":
    main()



